# ─────────────────────────────────────────────────────────────────────────────
# i18n.py  –  Internacionalización (ES / EN / PT)
# Agrega nuevos idiomas sumando una clave al dict TRANSLATIONS con el código
# ISO 639-1 correspondiente (ej. "fr" para francés).
# ─────────────────────────────────────────────────────────────────────────────

# Mapa código → nombre visible del idioma
LANGUAGES: dict[str, str] = {
    "es": "Español",
    "en": "English",
    "pt": "Português",
}

# ── Diccionario de traducciones ────────────────────────────────────────────
# Clave → { "es": texto_es, "en": texto_en, "pt": texto_pt }
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Título de la aplicación
    "app_title": {
        "es": "Compra Saldo Claro",
        "en": "Claro Balance Purchase",
        "pt": "Compra de Saldo Claro",
    },
    # Pestañas de configuración
    "tab_credentials": {"es": "Credenciales",    "en": "Credentials"},
    "tab_automation":  {"es": "Automatización",  "en": "Automation"},
    "tab_billing":     {"es": "Facturación",     "en": "Billing"},
    "tab_options":     {"es": "Opciones",         "en": "Options"},

    # Textos de dirección de carrusel
    "label_carousel_direction": {"es": "Dirección carrusel:", "en": "Carousel direction:", "pt": "Direção do carrossel:"},
    "direction_next":           {"es": "Siguiente →",          "en": "Next →",              "pt": "Próximo →"},
    "direction_prev":           {"es": "← Anterior",           "en": "← Previous",          "pt": "← Anterior"},

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
    "label_target_package_slide": {"es": "Paquete a comprar (slide)",   "en": "Package to buy (slide)"},
    "label_target_package_keyword": {"es": "Texto del paquete",         "en": "Package text keyword"},
    "help_target_package_keyword": {"es": "Ejemplo: 10GB, Ilimitado, Q50. Si coincide, se prioriza sobre el slide.", "en": "Example: 10GB, Unlimited, Q50. If matched, it takes priority over slide."},

    # Método de pago
    "label_payment":   {"es": "Método de pago",  "en": "Payment method"},
    "payment_saldo":   {"es": "Saldo",           "en": "Balance"},
    "payment_tarjeta": {"es": "Tarjeta",         "en": "Card"},

    # Facturación
    "chk_billing_autofill": {"es": "Autocompletar formulario de factura", "en": "Autofill invoice form"},
    "billing_help":         {"es": "Se usa cuando Mi Claro solicita datos para emitir la factura final.", "en": "Used when Mi Claro requests data to issue the final invoice."},
    "label_billing_name":   {"es": "Nombre en factura", "en": "Invoice name"},
    "label_billing_nit":    {"es": "NIT",               "en": "Tax ID"},
    "label_billing_address": {"es": "Dirección de facturación", "en": "Billing address"},
    "label_billing_email":  {"es": "Correo para factura", "en": "Invoice email"},
    "label_billing_cvv":    {"es": "CVV de tarjeta", "en": "Card CVV"},

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
    "btn_pause":  {"es": "Pausar",   "en": "Pause",  "pt": "Pausar"},
    "btn_resume": {"es": "Reanudar", "en": "Resume", "pt": "Retomar"},
    "btn_ok":     {"es": "OK",       "en": "OK",     "pt": "OK"},

    # Panel de log
    "log_title":     {"es": "Registro de actividad",   "en": "Activity log"},
    "btn_clear_log": {"es": "Limpiar",                 "en": "Clear"},

    # Barra de estado
    "status_ready":         {"es": "Listo",                                   "en": "Ready"},
    "autoclose_countdown":  {"es": "Cerrando en",                             "en": "Closing in"},
    "status_starting":      {"es": "Iniciando automatización...",             "en": "Starting automation...", "pt": "Iniciando automação..."},
    "status_pause_hint":    {"es": "Pausado; presiona Reanudar (F7) para continuar", "en": "Paused; press Resume (F7) to continue", "pt": "Pausado; pressione Retomar (F7) para continuar"},
    "status_log_missing":   {"es": "log.txt no encontrado.",                  "en": "log.txt not found.", "pt": "log.txt não encontrado."},
    "status_close_cancelled": {"es": "Cierre cancelado; automatización continúa en ejecución.", "en": "Close canceled; automation is still running.", "pt": "Fechamento cancelado; a automação continua em execução."},
    "status_stopping_before_close": {"es": "Deteniendo automatización antes de cerrar...", "en": "Stopping automation before closing...", "pt": "Parando automação antes de fechar..."},

    # Mensajes de log de GUI
    "log_starting_process":    {"es": "Iniciando proceso de automatización...", "en": "Starting automation process...", "pt": "Iniciando processo de automação..."},
    "log_resuming":            {"es": "Reanudando automatización...", "en": "Resuming automation...", "pt": "Retomando automação..."},
    "log_paused":              {"es": "Automatización pausada.", "en": "Automation paused.", "pt": "Automação pausada."},
    "log_close_cancelled":     {"es": "Cierre cancelado por el usuario; automatización continúa.", "en": "Close canceled by user; automation continues.", "pt": "Fechamento cancelado pelo usuário; automação continua."},
    "log_closing_wait":        {"es": "Cierre solicitado; esperando detención limpia de la automatización...", "en": "Close requested; waiting for clean automation stop...", "pt": "Fechamento solicitado; aguardando parada limpa da automação..."},
    "log_closing_after_stop":  {"es": "Automatización detenida; cerrando aplicación...", "en": "Automation stopped; closing application...", "pt": "Automação parada; fechando aplicação..."},

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
    "menu_help_donate":     {"es": "☕  Invítame una cerveza (PayPal)", "en": "☕  Buy me a beer (PayPal)"},

    # Donaciones
    "btn_donate":       {"es": "☕  Invítame una cerveza",  "en": "☕  Buy me a beer"},
    "donate_tooltip":   {"es": "Apoya el proyecto vía PayPal", "en": "Support the project via PayPal"},

    # Idioma
    "label_language":   {"es": "Idioma de la interfaz", "en": "Interface language"},

    # Diálogo About
    "about_title": {"es": "Acerca de la aplicación", "en": "About this application"},
    "about_version": {"es": "Versión", "en": "Version", "pt": "Versão"},
    "about_created_by": {"es": "Creado por", "en": "Created by", "pt": "Criado por"},
    "about_rights": {"es": "Derechos Reservados", "en": "All rights reserved", "pt": "Todos os direitos reservados"},

    # Diálogos
    "dialog_running_title": {"es": "Automatización en curso", "en": "Automation in progress", "pt": "Automação em andamento"},
    "dialog_running_message": {"es": "La automatización sigue en ejecución. ¿Deseas detenerla y cerrar la aplicación?", "en": "Automation is still running. Do you want to stop it and close the app?", "pt": "A automação ainda está em execução. Deseja pará-la e fechar o aplicativo?"},

    # Mensajes de estado
    "status_stopping":   {"es": "Deteniendo...",                      "en": "Stopping...", "pt": "Parando..."},
    "status_completed":  {"es": "✅ Proceso completado.",              "en": "✅ Process completed.", "pt": "✅ Processo concluído."},
    "status_stopped":    {"es": "⏹ Detenido por el usuario.",         "en": "⏹ Stopped by user.", "pt": "⏹ Interrompido pelo usuário."},
    "error_email_req":   {"es": "⚠ Se requiere un correo electrónico.","en": "⚠ Email address is required.", "pt": "⚠ E-mail é obrigatório."},
}


def get_text(key: str, lang: str = "es") -> str:
    """
    Devuelve el texto traducido para una clave y un código de idioma.
    Si la clave o el idioma no existe, intenta devolver inglés o español
    y como último recurso devuelve la clave literal (never crashes).
    """
    entry = TRANSLATIONS.get(key, {})
    return entry.get(lang) or entry.get("en") or entry.get("es") or key
