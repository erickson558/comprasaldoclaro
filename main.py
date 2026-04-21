# ─────────────────────────────────────────────────────────────────────────────
# main.py  –  Punto de entrada de la aplicación Compra Saldo Claro
# Inicializa el logger, verifica dependencias y lanza la ventana GUI.
# ─────────────────────────────────────────────────────────────────────────────

import sys
import logging

# Inicializar logger antes de importar cualquier otro módulo de la app
from log_setup import setup_logger
logger = setup_logger()

# ── Verificar dependencias antes de arrancar ───────────────────────────────
def _check_dependencies() -> bool:
    """
    Verifica que las librerías requeridas estén instaladas.
    Muestra un mensaje claro si falta alguna, en vez de un traceback críptico.
    """
    missing = []

    try:
        import customtkinter  # noqa: F401
    except ImportError:
        missing.append("customtkinter  →  pip install customtkinter")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        missing.append("playwright  →  pip install playwright && playwright install chromium")

    if missing:
        msg = (
            "Faltan las siguientes dependencias:\n\n"
            + "\n".join(f"  • {m}" for m in missing)
            + "\n\nInstálalas y vuelve a ejecutar la aplicación."
        )
        logger.error(msg)
        # Si tkinter está disponible, mostrar cuadro de error gráfico
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Dependencias faltantes", msg)
            root.destroy()
        except Exception:
            print(msg, file=sys.stderr)
        return False

    return True


def main() -> None:
    """Función principal: verifica entorno y lanza la GUI."""
    logger.info("Iniciando Compra Saldo Claro…")

    # Abortar si faltan dependencias
    if not _check_dependencies():
        sys.exit(1)

    # Importar la GUI aquí (después de verificar dependencias)
    from gui import ClaroApp

    try:
        app = ClaroApp()
        app.mainloop()          # Bloquea hasta que el usuario cierra la ventana
    except Exception as exc:
        logger.critical("Error fatal en la aplicación: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
