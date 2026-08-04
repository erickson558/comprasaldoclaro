# Architecture Decision Records — Compra Saldo Claro GT

Proyecto: Compra Saldo Claro GT
Version de referencia: V0.7.4
Responsable: erickson558
Fecha: 2026-08-03

---

## ADR-001 — Modulo Unico por Responsabilidad (sin paquetes frontend/backend)

**Estado:** Aceptado

### Contexto

A diferencia de proyectos hermanos del mismo autor (ej. `whatsappmessagesender`, que separa `frontend/`/`backend/` en paquetes), este proyecto es deliberadamente mas pequeño en alcance: un flujo de compra de un solo intento por corrida, sin scheduler, sin cola de comandos, sin reconexion a sesiones externas.

### Decision

Se mantiene un modulo por responsabilidad en la raiz del proyecto (sin subpaquetes): `gui.py` (interfaz), `automation.py` (automatizacion Playwright), `config_manager.py` (persistencia), `log_setup.py` (logging), `i18n.py` (traducciones), `version.py` (version). `main.py` es el punto de entrada delgado que verifica dependencias y lanza `gui.py`.

### Consecuencias

**Positivas:**
- Estructura simple, facil de navegar para un proyecto de este tamaño (~6 modulos).
- No hay sobre-ingenieria de capas para un flujo lineal de un solo paso.

**Negativas:**
- Si el proyecto crece (multi-cuenta, scheduler, mas flujos de compra), esta estructura plana se volveria dificil de mantener y ameritaria refactor a paquetes (frontend/backend como en whatsappmessagesender).
- `gui.py` y `automation.py` son archivos grandes (~1700 y ~1500 lineas respectivamente); cualquier nueva feature grande deberia evaluar extraer submodulos en vez de seguir creciendo estos dos archivos.

---

## ADR-002 — CustomTkinter Puro (no hibrido) como Framework de GUI

**Estado:** Aceptado

### Contexto

Se requeria una GUI moderna para Windows con soporte nativo de tema oscuro/claro, sin la curva de aprendizaje ni el peso de frameworks como PyQt/PySide. El proyecto hermano `whatsappmessagesender` adopto un enfoque **hibrido** (Tkinter clasico + algunos `CTkButton`) por compatibilidad con una GUI Tkinter preexistente grande. Este proyecto se construyo desde cero, sin esa restriccion.

### Decision

Se usa **CustomTkinter puro**: la ventana raiz es `ctk.CTk()` (no `tk.Tk()`), y todos los widgets relevantes son `CTk*` (`CTkButton`, `CTkFrame`, `CTkLabel`, `CTkOptionMenu`, etc.). `ctk.set_appearance_mode(...)` y `ctk.set_default_color_theme("blue")` se configuran antes de construir cualquier widget.

### Consecuencias

**Positivas:**
- Tema oscuro/claro coherente en toda la app sin necesidad de un `_theme_children()` recursivo como en el proyecto hibrido.
- Look moderno sin mezclar dos sistemas de widgets.

**Negativas:**
- Persisten algunos widgets Tkinter clasicos puntuales (`tk.Menu` para la barra de menu nativa, ya que CustomTkinter no incluye menu bar) — requieren estilizado manual coherente con el tema activo (colores hardcodeados en `menu_cfg`).
- Guardas anti-bucle (`_suppress_ui_callbacks`, `_is_rebuilding_ui`) fueron necesarias para evitar parpadeo al reconstruir OptionMenus en cambios de idioma/tema (fix V0.7.3) — un costo de complejidad especifico de reconstruir UI en caliente.

---

## ADR-003 — Playwright con Chromium Propio (launch, NO connect_over_cdp)

**Estado:** Aceptado

### Contexto

A diferencia de `whatsappmessagesender` (que se conecta via CDP a un navegador YA autenticado por el usuario, sin manejar credenciales), este proyecto necesita loguearse con credenciales propias del usuario en Mi Claro GT y ejecutar una transaccion completa. No hay sesion previa que reutilizar de forma util para este caso de uso — el login es parte necesaria del flujo.

### Decision

Se usa `playwright.chromium.launch(headless=?, slow_mo=?, executable_path=?)` para lanzar una instancia de Chromium **propia y aislada**, descargada e instalada localmente en `playwright-browsers/` junto al `.exe`/`.py` (no en `%LOCALAPPDATA%\ms-playwright`, para evitar depender de rutas temporales `_MEI` de PyInstaller que se borran entre ejecuciones). Si el ejecutable local no existe, se instala automaticamente (`playwright install chromium`) antes de continuar.

### Consecuencias

**Positivas:**
- No depende de que el usuario tenga un navegador especifico abierto ni de un puerto CDP configurado — mas simple para un usuario no tecnico (un solo `.exe`, cero configuracion de navegador).
- El Chromium local persiste entre ejecuciones del `.exe` compilado (a diferencia del temp dir por defecto de PyInstaller).

**Negativas:**
- El primer arranque debe descargar Chromium (~150-200 MB) si no existe localmente — requiere conexion a internet la primera vez.
- Gestionar el ciclo de vida completo de `browser`/`context`/`page` (incluyendo cierre en `finally`) es responsabilidad total de la app — ver ADR-006 sobre el riesgo de cierre sin timeout descubierto en V0.7.4.
- No hay reutilizacion de sesion: cada corrida hace login completo desde cero.

---

## ADR-004 — Persistencia JSON con config.json (sin config.example.json)

**Estado:** Aceptado

### Contexto

Se necesita persistir credenciales, telefono, parametros de carrusel/facturacion, geometria de ventana e idioma entre sesiones, en un proyecto de un unico usuario/maquina.

### Decision

Se usa un archivo JSON (`config.json`) gestionado por `config_manager.py`, con `DEFAULT_CONFIG` como fuente de defaults y deep-merge simple (`DEFAULT_CONFIG.copy(); merged.update(stored)`) para tolerar claves faltantes de versiones anteriores. A diferencia de `whatsappmessagesender`, este proyecto **no** mantiene un `config.example.json` versionado — el propio `DEFAULT_CONFIG` en codigo cumple ese rol de plantilla seedeada.

### Consecuencias

**Positivas:**
- Simple, legible, sin dependencias de base de datos.
- `config.json` esta excluido de git (`.gitignore`) — las credenciales (password, CVV) nunca se suben al repositorio.
- `auto_start` por defecto es `False`: un `config.json` ausente o corrupto nunca dispara una compra automatica sin que el usuario lo haya configurado explicitamente.

**Negativas:**
- Sin `config.example.json`, un colaborador nuevo debe leer `DEFAULT_CONFIG` en codigo para saber que claves existen (documentado igualmente en la tabla de la GUI del README).
- No hay control de concurrencia: dos instancias simultaneas del `.exe` podrian pisarse la configuracion mutuamente (riesgo aceptado dado el uso mono-instancia esperado).

---

## ADR-005 — PyInstaller Onefile sin Consola

**Estado:** Aceptado

### Contexto

Distribucion a un usuario final de Windows sin Python instalado, como aplicacion de escritorio (no herramienta de linea de comandos).

### Decision

`build.bat` invoca `pyinstaller --onefile --noconsole --icon=... --name="ComprasClaroGT" --distpath="." main.py`, dejando el `.exe` en la misma carpeta del `.bat`/`.py`. El icono se referencia con **ruta absoluta** (`%SCRIPT_DIR%`) porque `--specpath` apunta a una carpeta temporal distinta (`build_tmp`) y PyInstaller resuelve rutas relativas de `--icon` contra `specpath`, no contra el cwd — una ruta relativa falla con `FileNotFoundError` (aprendido empiricamente durante la creacion de este SDD).

### Consecuencias

**Positivas:**
- Un unico `.exe` (~65 MB) sin instalador, sin consola visible.
- `build_tmp/` se limpia despues de compilar; solo el `.exe` final queda en la raiz.

**Negativas:**
- El modulo `pyinstaller` no siempre se resuelve via `python -m pyinstaller` en Windows si se instalo con `pip install --user` (el modulo no queda en el `PATH` de `python -m`, pero el ejecutable si en `Scripts/`) — usar el ejecutable `pyinstaller`/`pyinstaller.exe` directamente, nunca `python -m pyinstaller`, tanto local (fix V0.1.6) como en CI (mismo patron documentado en `release.yml`).
- `build.bat` termina con `pause` — al invocarlo desde un agente/CI de forma no interactiva, este `pause` bloquea esperando stdin indefinidamente. Un agente debe invocar `pyinstaller` directamente con los mismos flags en vez de ejecutar `build.bat` tal cual.

---

## ADR-006 — Cierre de Playwright Acotado con Timeout (V0.7.4)

**Estado:** Aceptado (implementado en V0.7.4)

### Contexto

`page.close()`, `context.close()` y `browser.close()` de Playwright no aceptan un parametro `timeout` propio (a diferencia de casi todas las demas esperas del codigo, que si lo declaran explicitamente). Estas tres llamadas viven en el bloque `finally` de `run_automation()`. Si Chromium queda no-responsivo — el log de produccion registro un `TargetClosedError` en `_dismiss_modal` sugiriendo que el navegador se cerro externamente en medio de una operacion — la espera de estas llamadas puede no retornar nunca. Como estan en el `finally`, el hilo de automatizacion (`_automation_thread_worker` en `gui.py`) nunca ejecuta su propio `finally` que notifica `"done"` a la cola de mensajes, y la GUI queda con `is_running=True` para siempre: sintoma reportado por el usuario como "la automatizacion no termina".

### Decision

Cada cierre (`_safe_close_page`, `_safe_close_context`, `_safe_close_browser`) se envuelve en `asyncio.wait_for(..., timeout=_CLOSE_TIMEOUT_SECONDS)` (8s). Ante `TimeoutError` se registra un warning y se continua con el siguiente recurso, garantizando que el `finally` completo del `run_automation` SIEMPRE termina en tiempo acotado. La espera del `watchdog_task` tras `cancel()` recibe el mismo tratamiento (timeout `_CLOSE_TIMEOUT_SECONDS * 3`). Adicionalmente, si `browser.new_context()` falla tras un `launch()` exitoso, el browser ya lanzado se cierra explicitamente antes de re-lanzar la excepcion, evitando un proceso huerfano que nunca llegaria al `finally` principal.

### Consecuencias

**Positivas:**
- La app SIEMPRE termina (con exito o con un error/timeout claro), nunca se cuelga indefinidamente por un Chromium no-responsivo.
- El patron es generico y replicable: cualquier futura llamada de Playwright sin `timeout` nativo debe seguir el mismo envoltorio.

**Negativas:**
- En el caso raro de timeout real en el cierre, el proceso Chromium subyacente podria quedar como huerfano en el sistema (no hay kill forzoso del proceso OS, solo se deja de esperar la confirmacion). Se acepto este trade-off: preferible un chrome.exe huerfano ocasional (visible y matable manualmente en Task Manager) a una app que nunca termina.
- Requiere disciplina: cualquier nueva llamada a un metodo de Playwright que no tenga `timeout` propio debe revisarse contra este mismo riesgo antes de mergear (ver checklist en `commands/diagnose-automation.md`).

---

## ADR-007 — GitHub Actions para CI/CD, Release Automatico en Cada Push a Main

**Estado:** Aceptado

### Contexto

Se necesitaba un proceso reproducible para compilar y publicar el `.exe` sin depender de builds manuales locales que pudieran desincronizarse con `version.py`.

### Decision

`.github/workflows/release.yml` se dispara en **cada push a `main`** (no solo en tags): instala dependencias + PyInstaller + Chromium, lee `VERSION` desde `version.py`, compila el `.exe` con PyInstaller (mismos flags que `build.bat`, mas `--add-data` del icono porque el runner de CI si lo necesita explicito), crea el tag `v{VERSION}` (idempotente: `|| echo "Tag ya existe"` si ya fue creado) y publica un GitHub Release adjuntando el `.exe`.

A diferencia de `whatsappmessagesender` (que **falla** el workflow si el tag ya existe, forzando bump de version antes de mergear), este proyecto es mas permisivo: si el tag ya existe, simplemente omite ese paso sin fallar el build completo.

### Consecuencias

**Positivas:**
- Cada push a `main` con un `VERSION` nuevo produce automaticamente un Release publico con el `.exe` adjunto — cero pasos manuales de publicacion.
- El runner usa Windows nativo (`windows-latest`), garantizando compatibilidad binaria real con el `.exe` de Windows.

**Negativas:**
- Cualquier push a `main` (incluso uno que no ameritaba nueva version) dispara un build completo de varios minutos; si se olvida incrementar `VERSION`, el release se salta silenciosamente en vez de fallar visiblemente (a diferencia de whatsappmessagesender) — se debe recordar bumpear version.py en cada push relevante a main.
- Requiere que la cuenta de GitHub autenticada (via `gh`/credential helper) tenga permiso de escritura sobre `erickson558/comprasaldoclaro` — ver nota operativa en `agents/github-devops.md` sobre el conflicto de multiples cuentas `gh` logueadas.

---

## ADR-008 — Multi-idioma en Vivo (ES/EN/PT) sin Reinicio

**Estado:** Aceptado (V0.7.0/V0.7.1)

### Contexto

Se queria soporte multi-idioma sin la limitacion de `whatsappmessagesender` (que a la fecha de este documento aun exige reiniciar la app tras cambiar idioma).

### Decision

`i18n.py` expone `LANGUAGES: dict[str, str]` (codigo → nombre visible) y `get_text(key, lang)` con fallback en cascada (idioma solicitado → ingles → español → clave literal, nunca crashea). `gui.py` reconstruye los widgets afectados al cambiar idioma, protegido por guardas anti-bucle (`_suppress_ui_callbacks`, `_is_rebuilding_ui`) para evitar reconstrucciones redundantes y parpadeo (fix V0.7.3).

### Consecuencias

**Positivas:**
- Cambio de idioma inmediato, mejor UX que el proyecto hermano.
- Agregar un idioma nuevo solo requiere extender el catalogo en `i18n.py` y `LANGUAGES` — la GUI itera el dict dinamicamente.

**Negativas:**
- La reconstruccion de widgets en caliente es una fuente conocida de bugs sutiles (parpadeo, transparencia intermitente) si se agregan nuevos `OptionMenu`/widgets sin pasar por las guardas existentes — cualquier nuevo widget dependiente del idioma debe registrarse en el mismo patron de reconstruccion protegida.
