# ─────────────────────────────────────────────────────────────────────────────
# config_manager.py  –  Persistencia de configuración en config.json
# Lee/escribe un archivo JSON que la app carga al iniciar y actualiza en tiempo
# real cada vez que el usuario cambia cualquier parámetro en la GUI.
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import sys
import logging

logger = logging.getLogger("ComprasClaroApp")

# Cuando corre como .exe compilado (PyInstaller), sys.executable apunta al .exe.
# Cuando corre como .py, __file__ apunta al script.
# En ambos casos queremos que config.json viva junto al ejecutable.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ruta del config.json junto al .py / .exe
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
# ── Valores por defecto ────────────────────────────────────────────────────
# Todos los parámetros que el usuario puede modificar deben estar aquí.
# Sirven como fallback cuando el config.json no existe o le faltan claves.
DEFAULT_CONFIG: dict = {
    # Credenciales de acceso a Mi Claro
    "email": "",
    "password": "",               # Opcional; algunos flujos no lo requieren
    "phone_number": "34884422",   # Número al que se comprará el paquete

    # Comportamiento del navegador
    "headless": True,             # True = sin ventana, False = ventana visible
    "slow_mo": 0,                 # Milisegundos de retardo entre acciones (debug)

    # Configuración de carruseles de paquetes
    "carousel1_next_clicks": 3,   # Clics en "Next" del carrusel 1
    "carousel1_slide": 13,        # Índice (nth-child) del paquete en carrusel 1
    "carousel2_next_clicks": 9,   # Clics en "Next" del carrusel 2 (paquetes extra)
    "carousel3_next_clicks": 4,   # Clics en "Next"/"Prev" del carrusel 3 (tarjeta)
    "carousel3_direction": "next", # Dirección: "next" o "prev"
    "carousel3_slide": 13,        # Índice del paquete en carrusel 3
    "target_package_slide": 13,   # Selector explícito del paquete objetivo (GUI)
    "target_package_keyword": "", # Texto opcional del paquete (prioridad sobre slide)

    # Método de pago seleccionado
    "payment_method": "tarjeta",  # "saldo" o "tarjeta"

    # Datos de facturación final (si el flujo los solicita)
    "billing_autofill": True,      # Completar automáticamente el formulario
    "billing_name": "",           # Nombre en factura
    "billing_nit": "",            # NIT
    "billing_address": "",        # Dirección de facturación
    "billing_email": "",          # Correo para recibir factura
    "billing_cvv": "",            # CVV para confirmar compra con tarjeta guardada

    # Comportamiento automático
    "auto_start": False,          # Iniciar automatización al abrir la app
    "auto_close": False,          # Cerrar la app al finalizar
    "auto_close_delay": 60,       # Segundos antes del cierre automático

    # Posición y tamaño de la ventana (para restaurarla al reabrirla)
    "window_x": 100,
    "window_y": 100,
    "window_width": 860,
    "window_height": 680,

    # Preferencias de interfaz
    "language": "es",             # "es" o "en"
    "appearance_mode": "dark",    # "dark", "light" o "system"
}


def load_config() -> dict:
    """
    Carga el config.json desde disco.
    Si el archivo no existe o está corrupto, devuelve DEFAULT_CONFIG.
    Si le faltan claves (versión anterior del config), las rellena con los defaults.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                stored = json.load(fh)

            # Rellenar claves que puedan faltar en configs antiguos
            merged = DEFAULT_CONFIG.copy()
            merged.update(stored)
            return merged

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer config.json (%s). Usando valores por defecto.", exc)

    # Primera ejecución o archivo dañado → devolver defaults
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """
    Guarda el diccionario de configuración en config.json.
    Falla silenciosamente para no interrumpir la GUI, pero registra el error.
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error("Error al guardar config.json: %s", exc)
