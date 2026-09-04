# Especificacion de Diseno de Software (SDD)
# Compra Saldo Claro GT — v0.7.8

**Proyecto:** Automatizacion de compra de paquetes Mi Claro Guatemala
**Autor:** Synyster Rick (GitHub: erickson558)
**Fecha:** 2026-09-04
**Version del documento:** 1.1
**Version de la aplicacion:** 0.7.8

---

## Indice

1. [Flujo de compra end-to-end](#1-flujo-de-compra-end-to-end)
2. [Manejo de modales/overlays intermitentes](#2-manejo-de-modalesoverlays-intermitentes)
3. [Manejo de encuestas aleatorias (Qualtrics)](#3-manejo-de-encuestas-aleatorias-qualtrics)
4. [Instalacion automatica de Chromium local](#4-instalacion-automatica-de-chromium-local)
5. [Control de ejecucion: pausa, detencion y watchdog](#5-control-de-ejecucion-pausa-detencion-y-watchdog)
6. [Cierre acotado de Playwright (V0.7.4)](#6-cierre-acotado-de-playwright-v074)
7. [Persistencia de configuracion](#7-persistencia-de-configuracion)
8. [Soporte multi-idiomas (ES/EN/PT)](#8-soporte-multi-idiomas-esenpt)
9. [Sistema de logging](#9-sistema-de-logging)
10. [GUI CustomTkinter + auto-inicio/auto-cierre](#10-gui-customtkinter--auto-inicioauto-cierre)

---

## 1. Flujo de compra end-to-end

**Estado:** Activo

### Descripcion

`run_automation()` en `automation.py` ejecuta de principio a fin: login (o deteccion de sesion activa) → cierre de modal post-login → navegacion Gestiones → Compras → Paquetes y recargas → seleccion de linea (`.selectLine`) → navegacion del carrusel de paquetes → compra (por keyword o por posicion de slide) → seleccion de metodo de pago → formulario de facturacion → seleccion de tarjeta guardada → CVV → confirmacion. El flujo esta basado en grabaciones de Deploy Sentinel y se ha ido endureciendo version a version (ver README Changelog).

### Criterios de Aceptacion

- Si el usuario ya tiene sesion activa (`.menu_header_gestiones` visible), se omite el llenado de credenciales.
- El envio del formulario de login prueba una cadena de selectores (`.btnPrimario` → `button.btnPrimario` → `button[type='submit']` → `input[type='submit']`) antes de fallar.
- La seleccion de linea busca en `.selectLine` la opcion cuyo `value` contiene el numero de telefono configurado; se registra el JSON completo de la linea seleccionada en el log DEBUG.
- La navegacion del carrusel usa `carousel3_next_clicks`/`carousel3_direction` configurables desde la GUI, con `_wait_for_loader` dentro del bucle (el overlay de carga reaparece entre cada click).
- La compra del paquete prioriza busqueda por `target_package_keyword` (texto visible, ej. "Q 10.00"); si no hay match, cae a compra por posicion (`target_package_slide`, selector `nth-child`).
- El metodo de pago (`tarjeta`/`saldo`) se valida explicitamente antes del formulario de facturacion; si no se encuentra el selector, el flujo continua sin bloquear (algunos sitios no lo requieren).
- El formulario de facturacion se completa via busqueda en pagina principal + iframes (nombre, NIT, direccion, correo), con `billing_autofill` como flag de activacion.
- **(V0.7.6)** Tras enviar el "Continuar" del formulario de facturacion, se verifica que el formulario realmente desaparecio antes de dar el paso por completado. Si el sitio rechaza el envio (NIT/direccion invalidos u otra validacion) la pagina se queda en la misma vista sin que Playwright lance ningun error — sin esta verificacion, los pasos condicionales siguientes (tarjeta, CVV) "continuan sin romper flujo" al no detectar su pantalla, y el bot terminaba notificando un exito falso. Ahora se lanza `RuntimeError` explicito (incluyendo el texto de error del sitio si esta visible) en vez de continuar.
- **(V0.7.7)** Los marcadores usados en la verificacion anterior (`billing_markers`) se acotaron a texto exclusivo de la vista de facturacion (`Nombre en factura`, `Dirección de facturación`) — los selectores genericos originales (`input[placeholder*='correo' i]`, etc.) podian seguir coincidiendo con un campo persistente en la pantalla siguiente y producian el falso negativo opuesto (abortar una compra que si habia avanzado).
- **(V0.7.8)** La comprobacion de avance se reescribio con `_wait_screen_transition(page, disappear_selectors, appear_selectors, timeout_ms)`: en vez de esperar primero un tiempo fijo (10s) a que desaparezca el formulario y luego, solo si eso falla, otro tiempo fijo (2s) buscando la pantalla de tarjeta, sondea ambas condiciones en un unico ciclo y retorna apenas cualquiera de las dos se cumple. Esto corrige un falso negativo observado en una PC mas lenta, donde el sitio tardaba mas de 10s en procesar el envio y renderizar la siguiente pantalla: el techo de seguridad subio a 30s, pero al ser un sondeo con salida temprana (no un `sleep` bloqueante) una corrida normal en un equipo rapido no se hace mas lenta — solo se le da mas margen a un equipo lento antes de declarar fallo.
- La seleccion de tarjeta guardada y el paso de CVV solo se ejecutan si el sitio los solicita (deteccion condicional por presencia de `div.select-container` / campo CVV) — esta logica de "continuar sin bloquear" sigue siendo correcta para SUS pantallas condicionales; el fix de V0.7.6 solo endurece el paso anterior (submit de facturacion), que es obligatorio y no condicional.
- Al completar, se notifica `"✅ Proceso de compra completado exitosamente."` y se cierra el navegador SIEMPRE en el `finally` (ver seccion 6).

### Notas de Implementacion

- Modulo: `automation.py`, funcion principal `run_automation(config, status_callback, stop_event, pause_event)`.
- Los pasos usan helpers reutilizables: `_safe_click`, `_try_selectors`, `_safe_wait_networkidle`, `_wait_for_loader`, `_click_and_navigate`.
- **Advertencia operativa:** este flujo, si se ejecuta de punta a punta con `payment_method` valido y credenciales reales, realiza una compra real con dinero real. Nunca invocarlo como parte de un diagnostico/prueba automatizada.

---

## 2. Manejo de Modales/Overlays Intermitentes

**Estado:** Activo

### Descripcion

El sitio muestra modales condicionales de renovacion/notificaciones (`#Modal`, `.renovationFavoriteModal`, boton `.btnBlancoRojo`) que bloquean clicks mediante un overlay `.blur` de z-index superior. `_dismiss_modal()` implementa una cadena de fallback que se detiene en el primer nivel que funcione.

### Criterios de Aceptacion

- Nivel 1: JS `element.click()` directo en `.btnBlancoRojo` — bypasea la verificacion de interceptacion de puntero de Playwright.
- Nivel 2: JS `element.click()` en cualquier boton/link del modal cuyo texto incluya "Aceptar", "Entendido", "OK", "Cerrar" o "Continuar".
- Nivel 3: tecla `Escape` + ocultamiento forzado via JS (`display:none` + `pointerEvents:none`) como ultimo recurso.
- La deteccion de presencia del modal usa `document.querySelector` (detecta el elemento aunque este cubierto por el overlay), no `is_visible()` (que puede fallar durante animaciones CSS — bug corregido en V0.1.4).
- Se llama a `_dismiss_modal()` en al menos 3 puntos criticos: inmediatamente post-login, al entrar a "Paquetes y recargas", y como recuperacion ante fallos de envio de login.
- Toda evaluacion JS pasa por `_safe_page_evaluate()`, que reintenta una vez ante `Execution context was destroyed` (navegacion SPA en curso) y retorna `None` sin romper el flujo si persiste.

### Notas de Implementacion

- Funciones: `_dismiss_modal(page)`, `_safe_page_evaluate(page, script, retries=1)`, `_is_execution_context_destroyed(exc)`.
- Historial de fixes acumulados: V0.1.2 (llamada post-login), V0.1.3 (JS click bypass overlay), V0.1.4 (elimina guardia `is_visible()`), V0.1.7 (reintento tras fallo de login), V0.1.8 (manejo de contexto destruido).

---

## 3. Manejo de Encuestas Aleatorias (Qualtrics)

**Estado:** Activo

### Descripcion

Mi Claro muestra ocasionalmente una encuesta Qualtrics ("¿Recomendarias el portal Mi Claro...") que puede interceptar clicks si no se descarta. `_handle_random_survey()` la detecta y cierra sin responderla, buscando en pagina principal y en todos los `Frame` de la pagina.

### Criterios de Aceptacion

- Se llama despues de cada paso significativo del flujo (login, seleccion de linea, navegacion de carrusel, formulario de facturacion, seleccion de tarjeta, CVV) — la encuesta puede aparecer en cualquier punto.
- Cierra la encuesta con `img[alt='Cerrar']`; el timeout de deteccion es corto (`timeout_ms=2000` por defecto) para no penalizar el flujo cuando la encuesta no aparece.
- Busca en todos los frames de la pagina, no solo en el frame principal (`_find_visible_in_frames`).

### Notas de Implementacion

- Funciones: `_handle_random_survey(page, notify, timeout_ms)`, `_find_visible_in_frames(page, selectors, timeout_ms)`.

---

## 4. Instalacion Automatica de Chromium Local

**Estado:** Activo

### Descripcion

En vez de depender del Chromium global de Playwright (`%LOCALAPPDATA%\ms-playwright`, que se pierde en `.exe` compilado por rutas temporales `_MEI`), la app mantiene su propia copia de Chromium en `playwright-browsers/` junto al `.exe`/`.py`. Si no la encuentra al arrancar, la descarga automaticamente.

### Criterios de Aceptacion

- `_find_local_chromium_executable()` busca `chromium-*/chrome-win/chrome.exe` dentro de `playwright-browsers/`, ordenado por fecha de modificacion (mas reciente primero).
- Si no existe, `_install_local_chromium()` intenta, en orden: `sys.executable -m playwright install chromium` (SOLO si NO esta compilado — evita el bucle de reapertura del `.exe` corregido en V0.7.2), luego `playwright install chromium`, luego `py -m playwright install chromium`.
- La instalacion corre en modo silencioso en Windows (`CREATE_NO_WINDOW` + `STARTF_USESHOWWINDOW`) — no debe aparecer ventana CMD (fix V0.7.3).
- Si el launch con el ejecutable local falla, hay un fallback al launch por defecto de Playwright (restaurando `PLAYWRIGHT_BROWSERS_PATH` original).
- Si la instalacion automatica falla del todo, se notifica un mensaje claro pidiendo instalacion manual (`playwright install chromium`).

### Notas de Implementacion

- Funciones: `_get_local_playwright_browsers_dir()`, `_find_local_chromium_executable()`, `_install_local_chromium(notify)`.
- **Regla critica (V0.7.2):** NUNCA ejecutar `sys.executable -m playwright ...` cuando `getattr(sys, "frozen", False)` es `True` — `sys.executable` apunta al propio `.exe` compilado y relanzaria la app en bucle.

---

## 5. Control de Ejecucion: Pausa, Detencion y Watchdog

**Estado:** Activo

### Descripcion

La GUI corre la automatizacion en un hilo daemon con su propio event loop asyncio. Dos `threading.Event` (`stop_event`, `pause_event`) coordinan la comunicacion GUI → hilo de automatizacion. Un watchdog dedicado (`_stop_watchdog`) garantiza que "Detener" cierre Chromium de inmediato, sin esperar a que el paso actual complete su timeout normal (que puede ser de hasta 20-30s).

### Criterios de Aceptacion

- `_check_stop(stop_event)` se llama en cada punto de control del flujo; lanza `RuntimeError("stopped by user")` si `stop_event.is_set()`.
- `_check_pause(pause_event, stop_event, notify)` bloquea en un bucle de `asyncio.sleep(0.3)` mientras `pause_event.is_set()`, verificando `stop_event` en cada iteracion para que un Stop durante Pausa tambien sea inmediato.
- `_stop_watchdog` corre en paralelo (`asyncio.create_task`) desde el inicio del flujo; al detectar `stop_event.is_set()` cierra `page`/`context`/`browser` de inmediato sin esperar a que el paso actual del flujo principal complete.
- Un `RuntimeError("stopped by user")` se trata como parada controlada (mensaje `⏹ Proceso detenido por el usuario.`), no como error inesperado.
- `asyncio.CancelledError` (hereda de `BaseException` en Python 3.8+, no de `Exception`) se captura explicitamente en `gui.py` para que la GUI no quede congelada con `is_running=True`.

### Notas de Implementacion

- Funciones: `_check_stop`, `_check_pause`, `_stop_watchdog` en `automation.py`; `_automation_thread_worker` en `gui.py`.
- Historial: V0.3.1 (watchdog de parada inmediata), V0.6.1 (CancelledError capturado en worker thread).

---

## 6. Cierre Acotado de Playwright (V0.7.4)

**Estado:** Activo (implementado en V0.7.4)

### Descripcion

`page.close()`, `context.close()` y `browser.close()` de Playwright **no aceptan un parametro `timeout`** (a diferencia de `click()`, `goto()`, `wait_for_selector()`, etc., que si lo tienen). Si Chromium queda en un estado no-responsivo — crash parcial del renderer, dialogo nativo bloqueante, o el escenario de `TargetClosedError` observado en logs donde el navegador se cierra externamente durante `_dismiss_modal` — estas llamadas pueden esperar indefinidamente la confirmacion que nunca llega. Como estan en el bloque `finally` de `run_automation`, el hilo de automatizacion nunca llega a notificar `"done"` a la cola de mensajes de la GUI, dejando `is_running=True` para siempre: la app "no termina".

### Criterios de Aceptacion

- `_safe_close_page`, `_safe_close_context` y `_safe_close_browser` envuelven su respectiva llamada de cierre en `asyncio.wait_for(..., timeout=_CLOSE_TIMEOUT_SECONDS)` (8s por defecto).
- Ante `asyncio.TimeoutError`, se registra un `logger.warning` y la funcion retorna normalmente — el flujo de cierre continua con el siguiente recurso en vez de bloquear el `finally` completo.
- El `await watchdog_task` tras `cancel()` en el `finally` tambien esta acotado (`_CLOSE_TIMEOUT_SECONDS * 3`) para cubrir el caso en que el watchdog este a mitad de su propia secuencia de cierre cuando se cancela.
- Si `browser.new_context()` falla despues de un `launch()` exitoso, el navegador ya lanzado se cierra explicitamente (`_safe_close_browser`) antes de re-lanzar la excepcion — evita un proceso Chromium huerfano que nunca llega al `finally` principal.

### Notas de Implementacion

- Constante: `_CLOSE_TIMEOUT_SECONDS = 8.0` en `automation.py`.
- Commit: `3e2a390` — "fix: bound Playwright close operations to stop the app hanging forever (V0.7.4)".
- **Patron a replicar:** cualquier nueva llamada a un metodo de Playwright que NO acepte `timeout` nativo (`close()` en sus tres variantes son las conocidas; verificar la documentacion de Playwright ante nuevas APIs) debe envolverse igual con `asyncio.wait_for`.

---

## 7. Persistencia de Configuracion

**Estado:** Activo

### Descripcion

Toda la configuracion (credenciales, telefono, parametros de carrusel, facturacion, geometria de ventana, idioma, tema) se guarda en `config.json` junto al `.exe`/`.py`. Se autoguarda en cada cambio relevante desde la GUI.

### Criterios de Aceptacion

- Si `config.json` no existe o esta corrupto (`JSONDecodeError`/`OSError`), se usa `DEFAULT_CONFIG` sin crashear.
- Las claves presentes en el archivo se preservan; las faltantes (version anterior) se completan con `DEFAULT_CONFIG` via `merged = DEFAULT_CONFIG.copy(); merged.update(stored)`.
- `DEFAULT_CONFIG["auto_start"]` es `False` — arrancar sin `config.json` (o con uno recien creado) nunca dispara una compra automatica sin que el usuario haya configurado explicitamente `auto_start: true`.
- `save_config()` falla silenciosamente (solo log de error) para no interrumpir la GUI ante un error de escritura (ej. archivo bloqueado por OneDrive/antivirus).

### Notas de Implementacion

- Modulo: `config_manager.py`. Ruta: junto al ejecutable (`sys.executable` si `frozen`, si no `__file__`).
- **Nota de seguridad para diagnostico:** `config.json` contiene password y CVV en texto plano. Si se necesita lanzar el `.exe` para verificar que la GUI abre (smoke test), mover `config.json` a un nombre temporal primero para que cargue `DEFAULT_CONFIG` (con `auto_start=False`) y restaurarlo despues — nunca dejar que un smoke test dispare `auto_start=true` con credenciales reales.

---

## 8. Soporte Multi-idiomas (ES/EN/PT)

**Estado:** Activo

### Descripcion

La GUI soporta español, ingles y portugues con cambio en vivo sin reiniciar (a diferencia de whatsappmessagesender, que a la fecha de este documento aun requiere reinicio segun su spec). El catalogo vive en `i18n.py`.

### Criterios de Aceptacion

- `LANGUAGES: dict[str, str]` en `i18n.py` define codigo → nombre visible (`es`, `en`, `pt`).
- `get_text(key, lang)` nunca crashea: si falta la clave o el idioma, intenta ingles, luego español, y como ultimo recurso devuelve la clave literal.
- El menu de idioma en la GUI se genera dinamicamente iterando `LANGUAGES.items()` (no hardcodeado).
- Cambiar de idioma actualiza los textos visibles inmediatamente, sin pedir reinicio (feature V0.7.0/V0.7.1).
- El idioma seleccionado persiste en `config.json`.

### Notas de Implementacion

- Modulo: `i18n.py`. Reconstruccion de widgets al cambiar idioma manejada con guardas anti-bucle (`_suppress_ui_callbacks`, `_is_rebuilding_ui`) en `gui.py` para evitar parpadeo/reconstrucciones redundantes (fix V0.7.3).

---

## 9. Sistema de Logging

**Estado:** Activo

### Descripcion

Logger centralizado (`logger = logging.getLogger("ComprasClaroApp")`) con salida simultanea a archivo rotativo y consola, mas notificacion a la GUI via `status_callback`.

### Criterios de Aceptacion

- `log.txt` usa `RotatingFileHandler` (500 KB por archivo, 1 backup → `log.txt.1`, maximo ~1 MB total).
- Cada linea incluye timestamp, nivel (INFO/DEBUG/WARNING/ERROR) y logger name.
- Los mensajes de nivel INFO relevantes tambien se envian a la GUI (log en vivo + barra de estado) via la funcion `notify()` interna de `run_automation`.
- Los archivos de log (`log.txt`, `log.txt.1`, `debug.log`, `comprasclaro.txt`) estan excluidos de git.

### Notas de Implementacion

- Modulo: `log_setup.py`.

---

## 10. GUI CustomTkinter + Auto-inicio/Auto-cierre

**Estado:** Activo

### Descripcion

A diferencia de whatsappmessagesender (hibrido Tkinter+CTk), esta app usa **CustomTkinter puro** como root (`ctk.CTk()`), con tema oscuro/claro nativo. Incluye auto-inicio configurable al abrir (con delay de 800ms) y auto-cierre con countdown visible tras completar.

### Criterios de Aceptacion

- `ctk.set_appearance_mode(...)` y `ctk.set_default_color_theme("blue")` se configuran ANTES de construir cualquier widget.
- Si `auto_start` esta activo en `config.json`, `self.after(800, self._start_automation)` dispara la automatizacion al abrir la ventana.
- Si `auto_close` esta activo, al completar (mensaje `"done"` en la cola) se inicia un countdown visible (`_start_countdown(delay)`) que cierra la app al llegar a 0.
- Cerrar la ventana mientras el bot corre pide confirmacion (`messagebox.askyesno`); si se confirma, se marca `_pending_close=True` y se dispara `stop_event.set()` — el cierre real (`_finalize_close`) solo ocurre cuando el hilo de automatizacion efectivamente notifica `"done"`.
- La comunicacion hilo-automatizacion → GUI es EXCLUSIVAMENTE via `queue.Queue` + polling `self.after(100, self._poll_message_queue)` — Tkinter no es thread-safe y nunca debe tocarse desde el hilo de automatizacion directamente.

### Notas de Implementacion

- Modulo: `gui.py`. Metodos clave: `_start_automation`, `_automation_thread_worker`, `_poll_message_queue`, `_on_close`, `_finalize_close`, `_start_countdown`/`_tick_countdown`.
- **Riesgo conocido (ver seccion 6):** antes de V0.7.4, si el cierre de Playwright colgaba, `_poll_message_queue` nunca recibia `"done"` y la GUI quedaba con `is_running=True` indefinidamente — este era el sintoma reportado como "la automatizacion no termina".
