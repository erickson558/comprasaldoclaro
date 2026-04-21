# Compra Saldo Claro GT

> Automatización de compra de paquetes en **Mi Claro Guatemala** con interfaz gráfica moderna.

[![Version](https://img.shields.io/badge/version-0.3.1-blue)](https://github.com/erickson558/comprasaldoclaro/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://python.org)
[![Build](https://github.com/erickson558/comprasaldoclaro/actions/workflows/release.yml/badge.svg)](https://github.com/erickson558/comprasaldoclaro/actions/workflows/release.yml)

---

## ¿Qué hace?

Automatiza el proceso completo de compra de paquetes de datos en el portal **Mi Claro Guatemala** (`claro.com.gt/miclaro`) usando Playwright/Chromium. Solo configura tu correo, número y parámetros de carrusel — el bot hace todo por ti.

---

## Características

- 🤖 **Automatización completa** del proceso de compra usando Playwright/Chromium
- 🎨 **Interfaz moderna** con modo oscuro/claro (CustomTkinter)
- ⚙️ **Totalmente configurable**: email, teléfono, carruseles de paquetes, método de pago
- 🧾 **Formulario de facturación configurable** desde una pestaña adicional de la GUI
- 💾 **Auto-guardado** de toda la configuración en `config.json`
- ⏱️ **Auto-cierre** con countdown visible
- 📋 **Log en tiempo real** con registro en `log.txt`
- 🌐 **Multi-idioma** (Español / English)
- ⌨️ **Atajos de teclado** (F5 = Iniciar, F6 = Detener, Esc = Salir, Alt+Enter = Acerca de)
- 📦 Compilable a `.exe` sin consola

---

## Requisitos

- Python 3.10 o superior
- Windows 10/11 (para la versión `.exe`)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/erickson558/comprasaldoclaro.git
cd comprasaldoclaro

# 2. Instalar dependencias de Python
pip install -r requirements.txt

# 3. Instalar el navegador Chromium (solo la primera vez)
playwright install chromium
```

---

## Uso

```bash
# Ejecutar la aplicación
python main.py
```

O hacer doble clic en `ComprasClaroGT.exe` si ya compilaste.

### Configuración en la GUI

| Campo | Descripción |
|---|---|
| **Correo electrónico** | Cuenta de Mi Claro GT |
| **Contraseña** | Si el flujo la requiere |
| **Número de teléfono** | Número al que se comprará el paquete |
| **Modo navegador** | Sin ventana (rápido) o visible (para depurar) |
| **SlowMo** | Retardo en ms entre acciones (0 = máxima velocidad) |
| **Carrusel N / Clics Next** | Cuántas veces avanzar en ese carrusel |
| **Carrusel N / Posición** | Índice del paquete a comprar (nth-child) |
| **Paquete a comprar (slide)** | Selector explícito del paquete objetivo (prioridad en el flujo de compra) |
| **Texto del paquete** | Búsqueda por palabra clave visible en el sitio (ej. 10GB, Ilimitado, Q50) |
| **Método de pago** | Saldo o Tarjeta |
| **Facturación / Nombre** | Nombre que se enviará en la factura |
| **Facturación / NIT** | NIT o CF requerido por el formulario |
| **Facturación / Dirección** | Dirección de facturación |
| **Facturación / Correo** | Correo al que se enviará la factura |
| **Facturación / CVV** | CVV de la tarjeta guardada cuando el sitio lo solicite |

---

## Compilar a .exe

```bat
build.bat
```

O manualmente:

```bash
pyinstaller --onefile --noconsole \
  --icon="Banking_00012_A_icon-icons.com_59833.ico" \
  --name="ComprasClaroGT" \
  --distpath="." \
  main.py
```

El ejecutable `ComprasClaroGT.exe` quedará en la misma carpeta.

---

## Estructura del proyecto

```
comprasaldoclaro/
├── main.py                  # Punto de entrada: verifica deps y lanza GUI
├── gui.py                   # Interfaz gráfica (CustomTkinter, tabbed, log en vivo)
├── automation.py            # Automatización Playwright (async, hilo de fondo)
├── config_manager.py        # Carga/guarda config.json
├── log_setup.py             # Logger → log.txt + consola
├── i18n.py                  # Traducciones ES/EN
├── version.py               # Fuente única de versión (VERSION = "x.x.x")
├── requirements.txt         # Dependencias Python
├── build.bat                # Script de compilación a .exe
├── Banking_00012_A_icon-icons.com_59833.ico  # Ícono de la app
└── .github/workflows/
    └── release.yml          # GitHub Actions: build + release automático
```

---

## Versionado

Se usa [Versionado Semántico](https://semver.org/) con formato `Vx.x.x`:

| Tipo de cambio | Incrementa | Ejemplo |
|---|---|---|
| Cambio en el flujo de automatización | **MAJOR** | V1.0.0 |
| Nueva funcionalidad en GUI | **MINOR** | V0.1.0 |
| Corrección de bug / ajuste menor | **PATCH** | V0.0.3 |

La versión debe coincidir en: `version.py` → GUI → README → git tag → GitHub Release.

---

## Changelog

### V0.3.1 — 2026-04-21
- **fix:** La detención desde GUI ahora cierra Chromium de forma inmediata mediante un watchdog de parada, evitando esperas largas en timeouts de Playwright
- **fix:** Los cierres provocados por detener el proceso se manejan como parada controlada (sin falso error inesperado)
- **fix:** Se robusteció el cierre final de `page/context/browser` para evitar fallos por recursos ya cerrados
- **feat:** Se documenta la selección de paquete por **texto** desde la GUI para elegir más fácilmente según lo que muestra el sitio

### V0.3.0 — 2026-04-21
- **fix:** Detección de formulario de facturación fortalecida con búsqueda en página principal e iframes, incluyendo esperas escalonadas para carga tardía
- **feat:** Nuevo soporte de **CVV** en GUI + automatización; si el sitio solicita CVV, el bot lo completa y confirma el paso de pago
- **feat:** Nuevo campo explícito **Paquete a comprar (slide)** en GUI con efecto directo en la selección del paquete objetivo
- **fix:** Workflow de GitHub Actions ajustado para compilar con ruta absoluta de ícono/datos y evitar fallo por búsqueda en `build_tmp`

### V0.2.0 — 2026-04-21
- **feat:** Nueva pestaña de **Facturación** en la GUI para parametrizar nombre, NIT, dirección y correo de factura
- **feat:** La automatización detecta el formulario de facturación final, completa los campos configurados y continúa el flujo automáticamente
- **fix:** Si la compra redirige a facturación y faltan datos obligatorios, ahora se reporta un error claro en lugar de dejar el proceso pendiente

### V0.1.11 — 2026-04-21
- **fix:** Se agregan trazas `DEBUG` más finas en login, selección de línea, navegación del carrusel y compra para facilitar diagnóstico desde `log.txt`
- **fix:** Cierre accidental protegido: si la automatización está corriendo, la GUI ahora pide confirmación y espera una detención limpia antes de cerrar
- **fix:** `comprasclaro.txt` se ignora en Git como archivo local de referencia de Sentinel para evitar ruido en el repositorio

### V0.1.10 — 2026-04-21
- **fix:** Flujo de compra actualizado a la grabación más reciente de Deploy Sentinel: `Gestiones → Compras → Paquetes y recargas`
- **fix:** La línea ahora se selecciona desde `.selectLine` buscando el `value` que contiene el número configurado, en lugar de navegar por `.boxConsume`
- **fix:** Se eliminó la navegación intermedia a `Comprar Paquete`; tras elegir la línea el bot entra directo al carrusel y conserva la compra configurable por clics/posición

### V0.1.9 — 2026-04-21
- **fix:** Login más robusto: mantiene `.btnPrimario` como selector principal de Sentinel y agrega fallbacks (`button.btnPrimario`, `button[type='submit']`, `input[type='submit']`) para evitar timeout cuando el DOM cambia
- **fix:** Si no existe botón de login, ahora valida sesión activa por visibilidad de `Gestiones` antes de lanzar error, evitando falsos fallos en sesiones/redirecciones automáticas

### V0.1.8 — 2026-04-21
- **fix:** `_dismiss_modal` ahora usa `page.evaluate` seguro con reintento ante `Execution context was destroyed` durante navegación, evitando crash del flujo por contexto JS transitorio
- **fix:** Si el contexto sigue inestable tras reintento, el descarte de modal se omite de forma controlada (`return`) para no romper la automatización

### V0.1.7 — 2026-04-21
- **fix:** Restaurado descarte preventivo de modal inmediatamente después de login/sesión activa para evitar bloqueo del menú `Gestiones` por overlay intermitente
- **fix:** `_click_and_navigate` y `_click_locator_and_navigate` ahora reintentan tras cerrar modal antes del fallback; evita falsos positivos donde el flujo seguía aunque el click real no se ejecutó

### V0.1.6 — 2026-04-20
- **fix:** `_click_locator_and_navigate` usa firma explícita con `page: Page` + `locator: Locator` para evitar dependencia implícita de propiedades internas del Locator y mantener compatibilidad estable entre versiones de Playwright
- **fix:** `build.bat` invoca `pyinstaller` directamente (en validación y compilación), evitando el fallo `No module named pyinstaller` que puede ocurrir con `python -m pyinstaller`

### V0.1.5 — 2026-04-20
- **fix:** Selector `.slick-next` del carrusel usa lista de fallbacks (Sentinel exacto → sin wrapper `div:nth-child(3)` → `.slick-next` global) — el selector original fallaba con timeout 30s porque el DOM no tenía exactamente la estructura grabada; se agrega `wait_for_selector(".contBoxPaquetes")` antes del loop
- **fix:** Botón "Comprar" del carrusel usa la misma estrategia de fallbacks encadenados

### V0.1.4 — 2026-04-20
- **fix:** `_dismiss_modal` elimina pre-chequeo `#Modal.is_visible()` — Playwright podía considerar el modal no visible durante animaciones CSS aunque el botón `.btnBlancoRojo` estuviese presente en el DOM; ahora el JS evaluate se ejecuta siempre, sin guardia de visibilidad

### V0.1.3 — 2026-04-20
- **fix:** `_dismiss_modal` usa `element.click()` desde JavaScript para el botón `.btnBlancoRojo` — bypasea el overlay `.blur` (z-index superior) que bloqueaba `page.click()` normal de Playwright

### V0.1.2 — 2026-04-20
- **fix:** `_dismiss_modal` llamado inmediatamente post-login (antes del menú Gestiones) — el modal bloqueaba `.hideOnDesk:nth-child(3) a` en el paso 3
- **fix:** Segundo `_dismiss_modal` después de abrir menú Gestiones por si reaparece
- **fix:** JS de último recurso agrega `pointerEvents:none` + `visibility:hidden` para garantizar que el overlay no bloquee eventos aunque el CSS lo fuerce visible

### V0.1.1 — 2026-04-20
- **fix:** Login tolerante a sesión activa — detecta `.menu_header_gestiones` antes de intentar llenar credenciales; evita crash cuando el usuario ya está logueado
- **fix:** `page.fill` y `.btnPrimario` click envueltos en try/except — evitan crash si los campos no existen
- **fix:** Nuevo helper `_click_and_navigate` reemplaza `expect_navigation` directo — tolerante a SPA/AJAX sin navegación completa
- **fix:** `gui.py` solo pasa a `automation.py` los parámetros que éste usa (elimina carousel1/2 y payment_method del dict)

### V0.1.0 — 2026-04-20
- **feat:** Flujo reescrito desde grabación Deploy Sentinel — usa menú "Gestiones > Compras" en escritorio; elimina carruseles 1 y 2; navegación más simple y confiable
- **fix:** Botón modal `.btnBlancoRojo` ("Aceptar" en modal de renovación) como primer selector en `_dismiss_modal`
- **fix:** GitHub Actions — cambiar `python -m pyinstaller` a `pyinstaller` directo (resuelve `No module named pyinstaller`)

### V0.0.4 — 2026-04-20
- **fix:** Modal de renovación "¡Hola XXX, ya puedes renovar!" ahora se acepta con clic en botón "Aceptar"/"Entendido" antes de intentar cerrar por X o JavaScript

### V0.0.3 — 2026-04-20
- **fix:** Descarta modal `#Modal` (`.renovationFavoriteModal` / `.blur`) que bloqueaba el clic en "Comprar Paquete" — nuevo helper `_dismiss_modal()` con 4 niveles de fallback

### V0.0.2 — 2026-04-20
- **fix:** Popup SweetAlert2 inicial ahora es opcional (`_safe_click` con 8 s timeout) — eliminado el crash de 30 s cuando no aparece el popup
- **fix:** Todas las llamadas `wait_for_load_state("networkidle")` ahora toleran sitios con conexiones persistentes (`_safe_wait_networkidle`)
- **fix:** Protección `ValueError` en countdown de auto-cierre

### V0.0.1 — 2026-04-20
- Lanzamiento inicial

---

## GitHub Actions — Release automático

Cada push a `main` dispara el workflow `.github/workflows/release.yml` que:
1. Instala dependencias y Chromium
2. Lee la versión desde `version.py`
3. Compila `ComprasClaroGT.exe` con PyInstaller
4. Crea un tag `vX.X.X` en GitHub
5. Publica un GitHub Release con el `.exe` adjunto

---

## Licencia

Copyright 2025 Synyster Rick  
Licencia Apache 2.0 — ver [LICENSE](LICENSE)

---

*Creado por Synyster Rick · © 2025 Derechos Reservados*
