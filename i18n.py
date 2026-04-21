# ─────────────────────────────────────────────────────────────────────────────
# i18n.py  –  Internacionalización (ES / EN)
# Agrega nuevos idiomas sumando una clave al dict TRANSLATIONS con el código
# ISO 639-1 correspondiente (ej. "fr" para francés).
# ─────────────────────────────────────────────────────────────────────────────

# Mapa código → nombre visible del idioma
LANGUAGES: dict[str, str] = {
    "es": "Español",
    "en": "English",
}

# ── Diccionario de traducciones ────────────────────────────────────────────
# Clave → { "es": texto_es, "en": texto_en }
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Título de la aplicación
    "app_title": {
        "es": "Compra Saldo Claro",
        "en": "Claro Balance Purchase",
    },
    # Pestañas de configuración
    "tab_credentials": {"es": "Credenciales",    "en": "Credentials"},
    "tab_automation":  {"es": "Automatización",  "en": "Automation"},
    "tab_options":     {"es": "Opciones",         "en": "Options"},

    # Etiquetas de credenciales
    "label_email":        {"es": "Correo electrónico",        "en": "Email address"},
    "label_password":     {"es": "Contraseña (si aplica)",    "en": "Password (if required)"},
    "label_phone":        {"es": "Número de teléfono",        "en": "Phone number"},
    "label_browser_mode": {"es": "Modo del navegador",        "en": "Browser mode"},
    "label_slowmo":       {"es": "Velocidad (slowmo)",        "en": "Speed delay (slowmo)"},

    # Modos de navegador
    "mode_headless": {"es": "Sin ventana (rápido)",  "en": "Headless (fast)"},
    "mode_visible":  {"es": "Con ventana (visible)", "en": "Visible window"},

    # Carruseles
    "carousel1_title":      {"es": "Carrusel 1 – Paquetes Saldo",      "en": "Carousel 1 – Balance Packages"},
    "carousel2_title":      {"es": "Carrusel 2 – Paquetes adicionales", "en": "Carousel 2 – Extra Packages"},
    "carousel3_title":      {"es": "Carrusel 3 – Paquetes Tarjeta",     "en": "Carousel 3 – Card Packages"},
    "carousel_next_clicks": {"es": "Clics en Siguiente",                "en": "Next button clicks"},
    "carousel_slide":       {"es": "Posición del paquete",              "en": "Package position (slide)"},

    # Método de pago
    "label_payment":   {"es": "Método de pago",  "en": "Payment method"},
    "payment_saldo":   {"es": "Saldo",           "en": "Balance"},
    "payment_tarjeta": {"es": "Tarjeta",         "en": "Card"},

    # Opciones generales
    "chk_auto_start":    {"es": "Auto iniciar al abrir la app", "en": "Auto-start when app opens"},
    "chk_auto_close":    {"es": "Auto cerrar al finalizar",     "en": "Auto-close when finished"},
    "label_close_delay": {"es": "Tiempo para cierre:",          "en": "Close delay:"},
    "label_seconds":     {"es": "segundos",                     "en": "seconds"},
    "label_appearance":  {"es": "Apariencia de la interfaz",    "en": "Interface appearance"},

    # Apariencia
    "appearance_dark":   {"es": "Oscuro",  "en": "Dark"},
    "appearance_light":  {"es": "Claro",   "en": "Light"},
    "appearance_system": {"es": "Sistema", "en": "System"},

    # Botones principales
    "btn_start": {"es": "Iniciar",  "en": "Start"},
    "btn_stop":  {"es": "Detener", "en": "Stop"},
    "btn_exit":  {"es": "Salir",   "en": "Exit"},

    # Panel de log
    "log_title":     {"es": "Registro de actividad",   "en": "Activity log"},
    "btn_clear_log": {"es": "Limpiar",                 "en": "Clear"},

    # Barra de estado
    "status_ready":         {"es": "Listo",                                   "en": "Ready"},
    "autoclose_countdown":  {"es": "Cerrando en",                             "en": "Closing in"},

    # Menú principal
    "menu_file":            {"es": "Archivo",     "en": "File"},
    "menu_file_run":        {"es": "Iniciar",     "en": "Run"},
    "menu_file_stop":       {"es": "Detener",     "en": "Stop"},
    "menu_file_exit":       {"es": "Salir",       "en": "Exit"},
    "menu_tools":           {"es": "Herramientas","en": "Tools"},
    "menu_tools_clear_log": {"es": "Limpiar log", "en": "Clear log"},
    "menu_tools_open_log":  {"es": "Abrir log.txt","en": "Open log.txt"},
    "menu_language":        {"es": "Idioma",      "en": "Language"},
    "menu_appearance":      {"es": "Apariencia",  "en": "Appearance"},
    "menu_help":            {"es": "Ayuda",       "en": "Help"},
    "menu_help_about":      {"es": "Acerca de",   "en": "About"},

    # Diálogo About
    "about_title": {"es": "Acerca de la aplicación", "en": "About this application"},

    # Mensajes de estado
    "status_starting":   {"es": "Iniciando...",                       "en": "Starting..."},
    "status_stopping":   {"es": "Deteniendo...",                      "en": "Stopping..."},
    "status_completed":  {"es": "✅ Proceso completado.",              "en": "✅ Process completed."},
    "status_stopped":    {"es": "⏹ Detenido por el usuario.",         "en": "⏹ Stopped by user."},
    "error_email_req":   {"es": "⚠ Se requiere un correo electrónico.","en": "⚠ Email address is required."},
}


def get_text(key: str, lang: str = "es") -> str:
    """
    Devuelve el texto traducido para una clave y un código de idioma.
    Si la clave o el idioma no existe, intenta devolver la versión en español
    y como último recurso devuelve la clave literal (never crashes).
    """
    entry = TRANSLATIONS.get(key, {})
    return entry.get(lang) or entry.get("es") or key
