# Compra Saldo Claro GT

> Automatización de compra de paquetes en **Mi Claro Guatemala** con interfaz gráfica moderna.

[![Version](https://img.shields.io/badge/version-0.0.2-blue)](https://github.com/SynysterRick/comprasaldoclaro/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://python.org)

---

## Características

- 🤖 **Automatización completa** del proceso de compra en Mi Claro GT usando Playwright/Chromium
- 🎨 **Interfaz moderna** con modo oscuro/claro (CustomTkinter)
- ⚙️ **Totalmente configurable**: email, teléfono, carruseles de paquetes, método de pago
- 💾 **Auto-guardado** de toda la configuración en `config.json`
- ⏱️ **Auto-cierre** con countdown visible
- 📋 **Log en tiempo real** con registro en `log.txt`
- 🌐 **Multi-idioma** (Español / English)
- ⌨️ **Atajos de teclado** (F5, F6, Esc, Alt+Enter)
- 📦 Compilable a `.exe` sin consola

---

## Requisitos

- Python 3.10 o superior
- Windows 10/11 (para la versión `.exe`)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/SynysterRick/comprasaldoclaro.git
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
| **Método de pago** | Saldo o Tarjeta |

---

## Compilar a .exe

```bat
build.bat
```

El ejecutable `ComprasClaroGT.exe` quedará en la misma carpeta.

---

## Estructura del proyecto

```
comprasaldoclaro/
├── main.py               # Punto de entrada
├── gui.py                # Interfaz gráfica (CustomTkinter)
├── automation.py         # Automatización Playwright
├── config_manager.py     # Gestión de config.json
├── log_setup.py          # Configuración de logging
├── i18n.py               # Traducciones ES/EN
├── version.py            # Versión de la app
├── requirements.txt      # Dependencias
├── build.bat             # Script de compilación
└── .github/workflows/
    └── release.yml       # GitHub Actions (release automático)
```

---

## Versionado

Se usa [Versionado Semántico](https://semver.org/):

| Tipo de cambio | Incrementa |
|---|---|
| Nuevo flujo de automatización | MAYOR |
| Nueva funcionalidad en GUI | MENOR |
| Corrección de bug / ajuste menor | PARCHE |

---

## Licencia

Copyright 2025 Synyster Rick  
Licencia Apache 2.0 — ver [LICENSE](LICENSE)

---

*Creado por Synyster Rick · © 2025 Derechos Reservados*
