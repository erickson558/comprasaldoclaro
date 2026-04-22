# ─────────────────────────────────────────────────────────────────────────────
# log_setup.py  –  Configuración centralizada del sistema de logging
# Crea un logger con salida a archivo (log.txt) y a consola.
# El archivo se guarda junto al .py / .exe para facilitar depuración.
# ─────────────────────────────────────────────────────────────────────────────

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Nombre del logger compartido en toda la app
LOGGER_NAME = "ComprasClaroApp"


def setup_logger() -> logging.Logger:
    """
    Inicializa y devuelve el logger principal.

    - FileHandler: escribe en log.txt con rotación manual (sobreescribe al reiniciar)
    - StreamHandler: escribe en consola (útil durante desarrollo)
    - Formato: timestamp ISO + nivel + mensaje
    """
    # Cuando corre como .exe (frozen), guardar log.txt junto al ejecutable.
    # Cuando corre como .py, guardarlo junto al script.
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "log.txt")

    # Crear logger con el nombre global de la app
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)  # Captura todos los niveles

    # Evitar agregar handlers duplicados si setup_logger() se llama varias veces
    if logger.handlers:
        return logger

    # Formato estándar: fecha-hora nivel nombre_logger mensaje
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler → archivo log.txt con rotación automática.
    # maxBytes=500 KB, backupCount=1 → mantiene log.txt + log.txt.1 (máx ~1 MB total).
    # Evita que el archivo crezca indefinidamente sesión tras sesión.
    file_handler = RotatingFileHandler(
        log_path, encoding="utf-8", mode="a",
        maxBytes=500_000, backupCount=1,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler → consola (solo INFO y superior para no saturar)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Primer mensaje en el log para marcar el inicio de sesión
    logger.info("=" * 60)
    logger.info("Logger inicializado. Archivo: %s", log_path)

    return logger
