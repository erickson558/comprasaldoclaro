# Especificacion del Proyecto: Compra Saldo Claro GT

> Documento vivo de Spec-Driven Development. Actualizar con cada cambio de version mayor o menor.
> Version del documento alineada con: `version.py` — **v0.7.10**

---

## 1. Vision General

**Compra Saldo Claro GT** es una aplicacion de escritorio para Windows que automatiza la compra de paquetes de datos/saldo en el portal **Mi Claro Guatemala** (`claro.com.gt/miclaro`) usando un Chromium propio controlado por Playwright. No reutiliza sesion de navegador del usuario ni requiere API oficial de Claro: hace login con credenciales configuradas y ejecuta el flujo completo de compra de principio a fin.

### Propuesta de valor

- Automatiza un flujo de compra repetitivo (recarga mensual/periodica) sin intervencion manual.
- Login propio con credenciales del usuario — no depende de una sesion de navegador preexistente.
- Distribucion como `.exe` unico sin necesidad de instalar Python.
- Chromium se descarga e instala localmente junto al `.exe`, sin depender de un navegador del sistema.
- Gratuita, de codigo abierto, uso personal.

### Usuarios objetivo

Usuario individual que recarga saldo/paquetes periodicamente en una o mas lineas prepago/tarjetero de Claro Guatemala y quiere automatizar la compra recurrente (via tarjeta guardada o saldo).

### Diferencia clave frente a otros proyectos del mismo autor

A diferencia de `whatsappmessagesender` (que se **conecta** via CDP a un navegador ya abierto y autenticado por el usuario), esta app **lanza su propio Chromium** (`playwright.chromium.launch()`) con credenciales propias y ejecuta un flujo transaccional de un solo intento por corrida — no hay scheduler recurrente ni cola de tareas: se ejecuta, compra, y termina.

**Precaucion operativa:** una corrida exitosa de este bot realiza una **compra real con dinero real** (tarjeta o saldo). Nunca ejecutar el flujo completo (`run_automation` de punta a punta) como parte de pruebas, diagnostico o CI — cualquier verificacion debe limitarse a analisis estatico de codigo, `py_compile`, o arranque de la GUI con `config.json` temporalmente sin `auto_start` para no disparar una compra involuntaria.

---

## 2. Estado Actual

| Campo | Valor |
|---|---|
| Version | **v0.7.10** |
| Rama principal | `main` |
| Plataforma soportada | Windows 10 / 11 (x64) |
| Python requerido (dev) | 3.12 |
| Distribucion | `ComprasClaroGT.exe` (PyInstaller, single-file, ~65 MB) |
| Release CI | GitHub Actions — `release.yml` (build + release automatico en CADA push a `main`) |
| Licencia | Apache License 2.0 |
| GitHub | https://github.com/erickson558/comprasaldoclaro (cuenta: **erickson558**) |

### Modulos principales

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Punto de entrada: verifica dependencias y lanza la GUI |
| `gui.py` | Interfaz grafica completa en CustomTkinter (`ctk.CTk()` como root, no hibrida con Tkinter clasico), pestañas de configuracion, log en vivo, countdown de autocierre |
| `automation.py` | Automatizacion async con Playwright, corre en un hilo de fondo con su propio event loop asyncio |
| `config_manager.py` | Persistencia de `config.json` (deep-merge con defaults, autoguardado en cada cambio de la GUI) |
| `log_setup.py` | Logger con `RotatingFileHandler` → `log.txt` (500 KB + 1 backup) + consola |
| `i18n.py` | Traducciones ES/EN/PT, cambio de idioma en vivo sin reiniciar |
| `version.py` | Fuente unica de version (`VERSION = "x.x.x"`) |
| `build.bat` | Compilacion local a `.exe` con PyInstaller |

### Capacidades actuales (v0.7.10)

- Login con email/password configurables (password opcional segun flujo del sitio).
- Seleccion de linea objetivo por numero de telefono (`.selectLine`).
- Navegacion configurable del carrusel de paquetes (numero de clics, direccion, slide objetivo o busqueda por texto/keyword del paquete).
- Metodo de pago: `tarjeta` (tarjeta guardada + CVV) o `saldo`.
- Formulario de facturacion con autollenado configurable (nombre, NIT, direccion, correo).
- Manejo robusto de modales/overlays intermitentes del sitio (`_dismiss_modal` con fallback JS → Escape → hide forzado).
- Manejo de encuestas Qualtrics aleatorias que pueden interrumpir el flujo (`_handle_random_survey`).
- Descarga/instalacion automatica de Chromium local (`playwright-browsers/`) junto al `.exe` si no existe.
- Auto-inicio configurable al abrir la app, auto-cierre configurable con countdown visible.
- Pausa/reanudacion y detencion inmediata (watchdog dedicado que fuerza cierre de Chromium sin esperar timeouts largos).
- **[V0.7.4]** Cierre de `page`/`context`/`browser` acotado con timeout (8s) — evita que la app quede colgada para siempre si Chromium no responde.
- **[V0.7.6/V0.7.7/V0.7.8]** Verificacion de avance real tras el envio obligatorio del formulario de facturacion, evitando notificar una compra exitosa que nunca ocurrio; desde V0.7.8 se hace con un sondeo de salida temprana (`_wait_screen_transition`) en vez de esperas fijas, para no fallar en equipos/conexiones mas lentas.
- **[V0.7.9]** Cierre robusto de la encuesta Qualtrics con bypass JS dentro de su propio frame (`frame.evaluate`) cuando su backdrop intercepta el click normal, con oculamiento forzado del iframe como ultimo recurso — evita que la encuesta bloquee el resto del flujo (ver ADR-010).
- Idiomas: español, ingles, portugues — cambio en vivo sin reiniciar.
- Tema oscuro/claro persistente.
- Boton de donacion (PayPal) en barra de acciones y About.
- Logs con rutas absolutas junto al `.exe`, tolerantes al directorio de lanzamiento.

---

## 3. Stack Tecnologico

### Runtime y GUI

| Componente | Version / Restriccion | Rol |
|---|---|---|
| Python | 3.12 (dev) / >=3.10 (runtime declarado) | Runtime de desarrollo |
| CustomTkinter | `>=5.2.2` | Interfaz grafica completa (root `ctk.CTk()`, no hibrida) |

### Automatizacion de navegador

| Componente | Version / Restriccion | Rol |
|---|---|---|
| Playwright (Python, async API) | `>=1.44.0` | Lanza y controla Chromium propio (`playwright.chromium.launch()`, NO conecta via CDP a un navegador existente) |
| Chromium (bundled) | Descargado por Playwright en `playwright-browsers/` local | Navegador headed/headless controlado end-to-end por la app |

### Distribucion y CI

| Componente | Version / Restriccion | Rol |
|---|---|---|
| PyInstaller | instalado ad-hoc (no fijado en requirements.txt: comentario "solo se usa para compilar") | Empaquetado `.exe` single-file |
| GitHub Actions (`windows-latest`) | — | Build + release automatico en cada push a `main` |

### Persistencia

- `config.json` (local, excluido de git via `.gitignore`): credenciales, telefono, parametros de carrusel, facturacion, ventana, idioma. Nunca se sube al repo.
- `version.py`: fuente unica de verdad para el numero de version.
- No existe `config.example.json` en este proyecto (a diferencia de whatsappmessagesender) — el fallback es `config_manager.DEFAULT_CONFIG`.

---

## 4. Requisitos No Funcionales

### Confiabilidad

- El cierre de `page`/`context`/`browser` en el `finally` de `run_automation` SIEMPRE debe estar acotado con timeout — Playwright no ofrece timeout nativo en `close()` y un Chromium no-responsivo puede colgar el hilo de automatizacion indefinidamente, dejando la GUI con `is_running=True` para siempre. **[V0.7.4]**
- Toda espera de red/DOM (`wait_for_selector`, `wait_for_function`, `page.click`, etc.) debe declarar un `timeout` explicito — nunca depender solo del default de Playwright quedando implicito.
- Un `config.json` corrupto o con claves faltantes no debe crashear la app — `config_manager.load_config()` hace deep-merge con `DEFAULT_CONFIG`.
- La deteccion de parada (`stop_event`) debe ser inmediata: el watchdog dedicado (`_stop_watchdog`) cierra Chromium sin esperar a que el paso actual complete su timeout normal.
- El hilo de automatizacion SIEMPRE debe notificar `"done"` a la cola de mensajes de la GUI, sin importar si termino con exito, error controlado o excepcion inesperada — de lo contrario la GUI queda con los botones Start/Stop en el estado incorrecto para siempre.

### Seguridad

- `config.json` (contiene email, password, CVV, datos de facturacion) nunca debe subirse al repositorio.
- No hardcodear credenciales en el codigo fuente.
- El `.exe` no expone consola (`--noconsole`).

### Experiencia de Usuario (UX)

- La GUI no debe bloquearse durante la automatizacion — Playwright corre en un hilo daemon separado con su propio event loop asyncio; la GUI Tkinter se actualiza solo via `queue.Queue` + polling `after(100, ...)`.
- El `slow_mo` configurado en la GUI debe respetarse tanto en las acciones de Playwright como en las pausas internas del codigo (`_runtime_pause`).
- Los errores deben notificarse en el log/estado de la GUI en lenguaje natural, no como stack traces crudos.
- La ventana recuerda geometria/posicion entre sesiones.

---

## 5. Limites del Sistema

| Limite | Valor actual | Razon |
|---|---|---|
| Lineas/cuentas por corrida | 1 (numero de telefono configurado) | Diseno actual de la GUI y del flujo; no hay soporte multi-cuenta |
| Metodos de pago | `tarjeta` (guardada) o `saldo` | Unicos flujos mapeados desde grabaciones Deploy Sentinel |
| Plataforma | Solo Windows | PyInstaller + rutas hardcodeadas para Windows |
| Ejecucion concurrente | 1 instancia de Chromium por corrida | Arquitectura single-worker, sin cola ni paralelismo |
| Reintentos automaticos de compra completa | Ninguno | Si el flujo falla, el usuario debe re-lanzar manualmente — no hay reintento automatico de la transaccion completa (evita compras duplicadas) |

---

## 6. Features Pendientes

### 6.1 Timeout global de watchdog para todo el flujo

**Descripcion:** ademas del timeout acotado en el cierre de Playwright (V0.7.4), evaluar envolver el flujo completo de compra en un `asyncio.wait_for` con un limite generoso (ej. 5-8 min) para que cualquier espera no prevista en el sitio tambien termine el proceso con un error claro en vez de una espera silenciosa larga.

**Estado actual:** no implementado — cada paso individual ya tiene timeout propio, pero no hay un limite agregado de principio a fin.

### 6.2 Otras mejoras identificadas (backlog)

| Feature | Descripcion breve |
|---|---|
| Soporte multi-linea/multi-cuenta | Ejecutar la compra para varias lineas configuradas en una sola corrida |
| Notificacion nativa de Windows al completar/fallar la compra | Feedback fuera de la ventana de la app |
| Exportar/importar `config.json` | Migrar configuracion entre equipos sin exponer password en texto plano |

---

## 7. Fuera de Alcance

| Fuera de alcance | Justificacion |
|---|---|
| Programacion/scheduler de compras recurrentes | El proyecto es deliberadamente "un click, una compra"; un scheduler introduciria riesgo de compras duplicadas no supervisadas |
| Conexion via CDP a un navegador ya abierto del usuario | A diferencia de whatsappmessagesender, este flujo requiere login propio y no depende de sesiones externas |
| Multiples cuentas/lineas simultaneas | Requeriria arquitectura multi-worker y localizacion de credenciales por linea |
| Soporte macOS/Linux | PyInstaller + rutas de Windows; sin necesidad actual de portar |
| Reintento automatico de transacciones fallidas | Riesgo de doble cobro; el usuario debe decidir manualmente si reintenta |
