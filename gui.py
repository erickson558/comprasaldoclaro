# ─────────────────────────────────────────────────────────────────────────────
# gui.py  –  Interfaz gráfica principal (CustomTkinter)
# Diseño moderno con pestañas, log en vivo, barra de estado y countdown.
# Toda la lógica de automatización corre en hilos separados para que la GUI
# nunca se congele mientras el bot está trabajando.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import datetime
import logging
import os
import queue
import sys
import threading
from typing import Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from automation import run_automation
from config_manager import load_config, save_config
from i18n import get_text, LANGUAGES
from version import APP_NAME, VERSION, AUTHOR, YEAR

logger = logging.getLogger("ComprasClaroApp")


class ClaroApp(ctk.CTk):
    """
    Ventana principal de la aplicación.
    Hereda de ctk.CTk (CustomTkinter) para obtener la apariencia moderna.
    """

    # ── Construcción ──────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()

        # Cargar configuración guardada desde config.json
        self.cfg = load_config()

        # Estado interno de la automatización
        self.is_running: bool = False
        self.stop_event = threading.Event()   # Para solicitar parada desde la GUI
        self.msg_queue: queue.Queue = queue.Queue()  # Canal GUI ↔ hilo de automatización

        # Estado del countdown de autocierre
        self._countdown_active: bool = False
        self._countdown_value: int = 0
        self._pending_close: bool = False   # Cierre diferido mientras el bot se detiene

        # Aplicar tema antes de construir cualquier widget
        ctk.set_appearance_mode(self.cfg.get("appearance_mode", "dark"))
        ctk.set_default_color_theme("blue")

        # Construir la ventana paso a paso
        self._setup_window()
        self._create_menubar()
        self._create_widgets()
        self._load_config_into_ui()

        # Iniciar el bucle de procesamiento de mensajes del hilo de automatización
        self._poll_message_queue()

        # Auto-iniciar si el usuario lo configuró así
        if self.cfg.get("auto_start", False):
            self.after(800, self._start_automation)

    # ── Configuración de ventana ──────────────────────────────────────────

    def _setup_window(self) -> None:
        """Título, tamaño, posición, icono y atajos de teclado globales."""
        lang = self.cfg.get("language", "es")
        self.title(f"{get_text('app_title', lang)}  ·  v{VERSION}")

        # Restaurar geometría guardada
        w = self.cfg.get("window_width", 860)
        h = self.cfg.get("window_height", 680)
        x = self.cfg.get("window_x", 100)
        y = self.cfg.get("window_y", 100)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(760, 580)

        # Cargar ícono .ico:
        # · .exe frozen → sys._MEIPASS (dentro del exe) o junto al exe
        # · .py         → misma carpeta que el script
        if getattr(sys, "frozen", False):
            # Primero buscar junto al .exe (recomendado: copiar el .ico al lado del exe)
            ico = os.path.join(os.path.dirname(sys.executable),
                               "Banking_00012_A_icon-icons.com_59833.ico")
            # Fallback: dentro del paquete (si se usó --add-data)
            if not os.path.exists(ico):
                ico = os.path.join(sys._MEIPASS,
                                   "Banking_00012_A_icon-icons.com_59833.ico")
        else:
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "Banking_00012_A_icon-icons.com_59833.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass  # Ignorar si el ícono no es compatible con el SO

        # Interceptar el cierre normal de la ventana (botón X)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Atajos de teclado estilo Windows
        self.bind("<F5>",        lambda _e: self._start_automation())
        self.bind("<F6>",        lambda _e: self._stop_automation())
        self.bind("<Escape>",    lambda _e: self._on_close())
        self.bind("<Alt-Return>",lambda _e: self._show_about())

    # ── Barra de menú ─────────────────────────────────────────────────────

    def _create_menubar(self) -> None:
        """Crea la barra de menús nativa de tkinter (customtkinter no la incluye)."""
        lang = self.cfg.get("language", "es")

        # Estilo oscuro coherente con el tema de la app
        menu_cfg = dict(bg="#1e1e2e", fg="white",
                        activebackground="#1f538d", activeforeground="white",
                        tearoff=0)

        bar = tk.Menu(self, **{k: v for k, v in menu_cfg.items() if k != "tearoff"})
        self.configure(menu=bar)

        # Menú Archivo
        m_file = tk.Menu(bar, **menu_cfg)
        bar.add_cascade(label=get_text("menu_file", lang), menu=m_file)
        m_file.add_command(label=f"{get_text('menu_file_run', lang)} (F5)",  command=self._start_automation)
        m_file.add_command(label=f"{get_text('menu_file_stop', lang)} (F6)", command=self._stop_automation)
        m_file.add_separator()
        m_file.add_command(label=f"{get_text('menu_file_exit', lang)} (Esc)", command=self._on_close)

        # Menú Herramientas
        m_tools = tk.Menu(bar, **menu_cfg)
        bar.add_cascade(label=get_text("menu_tools", lang), menu=m_tools)
        m_tools.add_command(label=get_text("menu_tools_clear_log", lang), command=self._clear_log)
        m_tools.add_command(label=get_text("menu_tools_open_log", lang),  command=self._open_log_file)

        # Menú Idioma
        m_lang = tk.Menu(bar, **menu_cfg)
        bar.add_cascade(label=get_text("menu_language", lang), menu=m_lang)
        m_lang.add_command(label="Español", command=lambda: self._change_language("es"))
        m_lang.add_command(label="English",  command=lambda: self._change_language("en"))

        # Menú Apariencia
        m_appear = tk.Menu(bar, **menu_cfg)
        bar.add_cascade(label=get_text("menu_appearance", lang), menu=m_appear)
        m_appear.add_command(label=get_text("appearance_dark",   lang), command=lambda: self._change_appearance("dark"))
        m_appear.add_command(label=get_text("appearance_light",  lang), command=lambda: self._change_appearance("light"))
        m_appear.add_command(label=get_text("appearance_system", lang), command=lambda: self._change_appearance("system"))

        # Menú Ayuda
        m_help = tk.Menu(bar, **menu_cfg)
        bar.add_cascade(label=get_text("menu_help", lang), menu=m_help)
        m_help.add_command(label=f"{get_text('menu_help_about', lang)} (Alt+Enter)", command=self._show_about)

    # ── Widgets ───────────────────────────────────────────────────────────

    def _create_widgets(self) -> None:
        """Construye todos los widgets de la interfaz en el orden correcto."""
        lang = self.cfg.get("language", "es")

        # ── Cabecera ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#12122a"))
        hdr.pack(fill="x")

        ctk.CTkLabel(
            hdr, text=f"⚡  {get_text('app_title', lang)}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#1153a0", "#4fc3f7"),
        ).pack(side="left", padx=18, pady=10)

        ctk.CTkLabel(
            hdr, text=f"v{VERSION}",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray55"),
        ).pack(side="right", padx=18)

        # ── Área central (config izquierda + log derecha) ─────────────────
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        # Panel izquierdo fijo: configuración en pestañas
        self._left = ctk.CTkFrame(center, width=370)
        self._left.pack(side="left", fill="y", padx=(0, 6))
        self._left.pack_propagate(False)

        # Panel derecho expandible: log de actividad
        self._right = ctk.CTkFrame(center)
        self._right.pack(side="right", fill="both", expand=True)

        # Pestañas de configuración
        self._tabs = ctk.CTkTabview(self._left)
        self._tabs.pack(fill="both", expand=True, padx=4, pady=4)

        t_creds = self._tabs.add(get_text("tab_credentials", lang))
        t_auto  = self._tabs.add(get_text("tab_automation",  lang))
        t_bill  = self._tabs.add(get_text("tab_billing",     lang))
        t_opts  = self._tabs.add(get_text("tab_options",     lang))

        self._build_credentials_tab(t_creds, lang)
        self._build_automation_tab(t_auto,   lang)
        self._build_billing_tab(t_bill,      lang)
        self._build_options_tab(t_opts,      lang)

        # Panel de log
        self._build_log_panel(lang)

        # ── Barra de botones ──────────────────────────────────────────────
        btn_bar = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#12122a"))
        btn_bar.pack(fill="x")

        self.btn_start = ctk.CTkButton(
            btn_bar,
            text=f"▶  {get_text('btn_start', lang)}  (F5)",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=170, height=38,
            fg_color="#1f6aa5", hover_color="#1a5a8a",
            command=self._start_automation,
        )
        self.btn_start.pack(side="left", padx=10, pady=8)

        self.btn_stop = ctk.CTkButton(
            btn_bar,
            text=f"⏹  {get_text('btn_stop', lang)}  (F6)",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=150, height=38,
            fg_color="#b03030", hover_color="#8b2020",
            state="disabled",
            command=self._stop_automation,
        )
        self.btn_stop.pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            btn_bar,
            text=f"✕  {get_text('btn_exit', lang)}  (Esc)",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=130, height=38,
            fg_color=("gray55", "gray35"), hover_color=("gray45", "gray25"),
            command=self._on_close,
        ).pack(side="right", padx=10, pady=8)

        # ── Barra de estado ───────────────────────────────────────────────
        status_bar = ctk.CTkFrame(self, height=26, corner_radius=0,
                                   fg_color=("gray75", "#0b0b1a"))
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            status_bar,
            text=f"●  {get_text('status_ready', lang)}",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray65"),
            anchor="w",
        )
        self._status_lbl.pack(side="left", padx=10)

        # Countdown de autocierre (visible solo cuando está activo)
        self._countdown_lbl = ctk.CTkLabel(
            status_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("#c0392b", "#e74c3c"),
        )
        self._countdown_lbl.pack(side="right", padx=8)

        ctk.CTkLabel(
            status_bar, text=f"v{VERSION}",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray55"),
        ).pack(side="right", padx=6)

    # ── Pestaña 1: Credenciales ───────────────────────────────────────────

    def _build_credentials_tab(self, parent: ctk.CTkFrame, lang: str) -> None:
        """Campos de acceso: email, contraseña, número de teléfono, modo del navegador."""

        def row(text: str, pady_top: int = 10) -> None:
            ctk.CTkLabel(parent, text=text, anchor="w").pack(fill="x", padx=12, pady=(pady_top, 2))

        # Email
        row(get_text("label_email", lang), pady_top=14)
        self._email = ctk.CTkEntry(parent, placeholder_text="usuario@email.com", height=34)
        self._email.pack(fill="x", padx=12, pady=(0, 4))
        self._email.bind("<FocusOut>", lambda _e: self._autosave())

        # Contraseña + botón mostrar/ocultar
        row(get_text("label_password", lang))
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.pack(fill="x", padx=12, pady=(0, 4))

        self._password = ctk.CTkEntry(pf, placeholder_text="••••••••", show="•", height=34)
        self._password.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._password.bind("<FocusOut>", lambda _e: self._autosave())

        self._show_btn = ctk.CTkButton(pf, text="👁", width=34, height=34,
                                        command=self._toggle_password)
        self._show_btn.pack(side="right")

        # Número de teléfono
        row(get_text("label_phone", lang))
        self._phone = ctk.CTkEntry(parent, placeholder_text="34884422", height=34)
        self._phone.pack(fill="x", padx=12, pady=(0, 4))
        self._phone.bind("<FocusOut>", lambda _e: self._autosave())

        # Separador visual
        ctk.CTkFrame(parent, height=1, fg_color=("gray65", "gray30")).pack(fill="x", padx=12, pady=10)

        # Modo del navegador (sin ventana / con ventana)
        row(get_text("label_browser_mode", lang), pady_top=4)
        self._headless_var = ctk.StringVar(value="headless")
        mf = ctk.CTkFrame(parent, fg_color="transparent")
        mf.pack(fill="x", padx=12)
        ctk.CTkRadioButton(mf, text=get_text("mode_headless", lang),
                            variable=self._headless_var, value="headless",
                            command=self._autosave).pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(mf, text=get_text("mode_visible", lang),
                            variable=self._headless_var, value="visible",
                            command=self._autosave).pack(side="left")

        # Retardo entre acciones (slowmo)
        row(get_text("label_slowmo", lang))
        sf = ctk.CTkFrame(parent, fg_color="transparent")
        sf.pack(fill="x", padx=12, pady=(0, 8))
        self._slowmo_var = ctk.StringVar(value="0")
        sme = ctk.CTkEntry(sf, textvariable=self._slowmo_var, width=80, height=32)
        sme.pack(side="left", padx=(0, 8))
        sme.bind("<FocusOut>", lambda _e: self._autosave())
        ctk.CTkLabel(sf, text="ms", text_color=("gray50", "gray60")).pack(side="left")

    # ── Pestaña 2: Automatización ─────────────────────────────────────────

    def _build_automation_tab(self, parent: ctk.CTkFrame, lang: str) -> None:
        """Configuración de carruseles y método de pago."""

        def _carousel_block(container, title_key: str, clicks_var, slide_var=None) -> None:
            """Crea un bloque de configuración para un carrusel."""
            frm = ctk.CTkFrame(container)
            frm.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(frm, text=get_text(title_key, lang),
                         font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

            # Fila: clics en Siguiente
            r1 = ctk.CTkFrame(frm, fg_color="transparent")
            r1.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(r1, text=get_text("carousel_next_clicks", lang),
                         width=160, anchor="w").pack(side="left")
            e1 = ctk.CTkEntry(r1, textvariable=clicks_var, width=65, height=28)
            e1.pack(side="left", padx=6)
            e1.bind("<FocusOut>", lambda _e: self._autosave())

            # Fila: posición del paquete (slide) — solo si aplica
            if slide_var is not None:
                r2 = ctk.CTkFrame(frm, fg_color="transparent")
                r2.pack(fill="x", padx=10, pady=(0, 8))
                ctk.CTkLabel(r2, text=get_text("carousel_slide", lang),
                             width=160, anchor="w").pack(side="left")
                e2 = ctk.CTkEntry(r2, textvariable=slide_var, width=65, height=28)
                e2.pack(side="left", padx=6)
                e2.bind("<FocusOut>", lambda _e: self._autosave())

        # Variables de los carruseles
        self._c1_clicks = ctk.StringVar(value="3")
        self._c1_slide  = ctk.StringVar(value="13")
        self._c2_clicks = ctk.StringVar(value="9")
        self._c3_clicks = ctk.StringVar(value="4")
        self._c3_slide  = ctk.StringVar(value="13")

        _carousel_block(parent, "carousel1_title", self._c1_clicks, self._c1_slide)
        _carousel_block(parent, "carousel2_title", self._c2_clicks)          # sin slide
        _carousel_block(parent, "carousel3_title", self._c3_clicks, self._c3_slide)

        # Separador + método de pago
        ctk.CTkFrame(parent, height=1, fg_color=("gray65", "gray30")).pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(parent, text=get_text("label_payment", lang),
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12)
        self._payment_var = ctk.StringVar(value="tarjeta")
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.pack(fill="x", padx=12, pady=(4, 6))
        ctk.CTkRadioButton(pf, text=get_text("payment_saldo",   lang),
                            variable=self._payment_var, value="saldo",
                            command=self._autosave).pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(pf, text=get_text("payment_tarjeta", lang),
                            variable=self._payment_var, value="tarjeta",
                            command=self._autosave).pack(side="left")

    # ── Pestaña 3: Opciones ───────────────────────────────────────────────

    def _build_options_tab(self, parent: ctk.CTkFrame, lang: str) -> None:
        """Auto-inicio, auto-cierre, tiempo de cierre y apariencia."""

        self._auto_start_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            parent, text=get_text("chk_auto_start", lang),
            variable=self._auto_start_var, command=self._autosave,
        ).pack(anchor="w", padx=14, pady=(18, 6))

        self._auto_close_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            parent, text=get_text("chk_auto_close", lang),
            variable=self._auto_close_var, command=self._autosave,
        ).pack(anchor="w", padx=14, pady=(0, 6))

        # Tiempo de autocierre
        df = ctk.CTkFrame(parent, fg_color="transparent")
        df.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(df, text=get_text("label_close_delay", lang)).pack(side="left")
        self._delay_var = ctk.StringVar(value="60")
        de = ctk.CTkEntry(df, textvariable=self._delay_var, width=72, height=30)
        de.pack(side="left", padx=8)
        de.bind("<FocusOut>", lambda _e: self._autosave())
        ctk.CTkLabel(df, text=get_text("label_seconds", lang),
                     text_color=("gray50", "gray55")).pack(side="left")

        # Separador
        ctk.CTkFrame(parent, height=1, fg_color=("gray65", "gray30")).pack(fill="x", padx=10, pady=12)

        # Apariencia
        ctk.CTkLabel(parent, text=get_text("label_appearance", lang),
                     anchor="w").pack(fill="x", padx=14)
        appear_values = [
            get_text("appearance_dark",   lang),
            get_text("appearance_light",  lang),
            get_text("appearance_system", lang),
        ]
        self._appear_menu = ctk.CTkOptionMenu(
            parent, values=appear_values,
            command=self._on_appearance_change,
        )
        self._appear_menu.pack(fill="x", padx=14, pady=(4, 8))

    # ── Pestaña 3: Facturación ───────────────────────────────────────────

    def _build_billing_tab(self, parent: ctk.CTkFrame, lang: str) -> None:
        """Campos para completar automáticamente el formulario de facturación."""

        def row(text: str, pady_top: int = 10) -> None:
            ctk.CTkLabel(parent, text=text, anchor="w").pack(fill="x", padx=12, pady=(pady_top, 2))

        self._billing_autofill_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent,
            text=get_text("chk_billing_autofill", lang),
            variable=self._billing_autofill_var,
            command=self._autosave,
        ).pack(anchor="w", padx=14, pady=(16, 6))

        ctk.CTkLabel(
            parent,
            text=get_text("billing_help", lang),
            wraplength=310,
            justify="left",
            text_color=("gray40", "gray65"),
        ).pack(fill="x", padx=14, pady=(0, 8))

        row(get_text("label_billing_name", lang), pady_top=8)
        self._billing_name = ctk.CTkEntry(parent, placeholder_text="Consumidor Final", height=34)
        self._billing_name.pack(fill="x", padx=12, pady=(0, 4))
        self._billing_name.bind("<FocusOut>", lambda _e: self._autosave())

        row(get_text("label_billing_nit", lang))
        self._billing_nit = ctk.CTkEntry(parent, placeholder_text="CF o tu NIT", height=34)
        self._billing_nit.pack(fill="x", padx=12, pady=(0, 4))
        self._billing_nit.bind("<FocusOut>", lambda _e: self._autosave())

        row(get_text("label_billing_address", lang))
        self._billing_address = ctk.CTkEntry(parent, placeholder_text="Ciudad, zona, dirección", height=34)
        self._billing_address.pack(fill="x", padx=12, pady=(0, 4))
        self._billing_address.bind("<FocusOut>", lambda _e: self._autosave())

        row(get_text("label_billing_email", lang))
        self._billing_email = ctk.CTkEntry(parent, placeholder_text="factura@email.com", height=34)
        self._billing_email.pack(fill="x", padx=12, pady=(0, 4))
        self._billing_email.bind("<FocusOut>", lambda _e: self._autosave())

    # ── Panel de log ──────────────────────────────────────────────────────

    def _build_log_panel(self, lang: str) -> None:
        """Área de texto que muestra el registro de actividad en tiempo real."""
        hdr = ctk.CTkFrame(self._right, fg_color="transparent")
        hdr.pack(fill="x", padx=6, pady=(6, 0))

        ctk.CTkLabel(hdr, text=get_text("log_title", lang),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        ctk.CTkButton(hdr, text=get_text("btn_clear_log", lang),
                      width=78, height=24, font=ctk.CTkFont(size=11),
                      command=self._clear_log).pack(side="right", padx=4)

        # Área de texto no editable con scroll automático
        self._log_box = ctk.CTkTextbox(
            self._right,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True, padx=6, pady=6)

    # ── Carga de config en la UI ──────────────────────────────────────────

    def _load_config_into_ui(self) -> None:
        """Rellena todos los widgets con los valores leídos del config.json."""
        c = self.cfg
        lang = c.get("language", "es")

        # Credenciales
        self._email.insert(0,    c.get("email", ""))
        self._password.insert(0, c.get("password", ""))
        self._phone.insert(0,    c.get("phone_number", "34884422"))

        # Modo de navegador
        self._headless_var.set("headless" if c.get("headless", True) else "visible")
        self._slowmo_var.set(str(c.get("slow_mo", 0)))

        # Carruseles
        self._c1_clicks.set(str(c.get("carousel1_next_clicks", 3)))
        self._c1_slide.set(str( c.get("carousel1_slide",        13)))
        self._c2_clicks.set(str(c.get("carousel2_next_clicks",  9)))
        self._c3_clicks.set(str(c.get("carousel3_next_clicks",  4)))
        self._c3_slide.set(str( c.get("carousel3_slide",        13)))

        # Método de pago
        self._payment_var.set(c.get("payment_method", "tarjeta"))

        # Facturación
        self._billing_autofill_var.set(c.get("billing_autofill", True))
        self._billing_name.insert(0, c.get("billing_name", ""))
        self._billing_nit.insert(0, c.get("billing_nit", ""))
        self._billing_address.insert(0, c.get("billing_address", ""))
        self._billing_email.insert(0, c.get("billing_email", ""))

        # Opciones
        self._auto_start_var.set(c.get("auto_start",    False))
        self._auto_close_var.set(c.get("auto_close",    False))
        self._delay_var.set(str( c.get("auto_close_delay", 60)))

        # Apariencia
        mode_idx = {"dark": 0, "light": 1, "system": 2}
        appear_values = [
            get_text("appearance_dark",   lang),
            get_text("appearance_light",  lang),
            get_text("appearance_system", lang),
        ]
        idx = mode_idx.get(c.get("appearance_mode", "dark"), 0)
        self._appear_menu.set(appear_values[idx])

    # ── Autoguardado ──────────────────────────────────────────────────────

    def _autosave(self) -> None:
        """
        Recoge los valores actuales de la GUI y los escribe en config.json.
        Se llama en cada cambio relevante del usuario (FocusOut, radio, checkbox…).
        """
        self.update_idletasks()  # Asegurar que la geometría esté actualizada

        def _int(var, default: int) -> int:
            try:
                return int(var.get())
            except (ValueError, tk.TclError):
                return default

        self.cfg.update({
            # Credenciales
            "email":          self._email.get(),
            "password":       self._password.get(),
            "phone_number":   self._phone.get(),
            # Navegador
            "headless":       self._headless_var.get() == "headless",
            "slow_mo":        _int(self._slowmo_var, 0),
            # Carruseles
            "carousel1_next_clicks": _int(self._c1_clicks, 3),
            "carousel1_slide":       _int(self._c1_slide,  13),
            "carousel2_next_clicks": _int(self._c2_clicks, 9),
            "carousel3_next_clicks": _int(self._c3_clicks, 4),
            "carousel3_slide":       _int(self._c3_slide,  13),
            # Pago
            "payment_method": self._payment_var.get(),
            # Facturación
            "billing_autofill": self._billing_autofill_var.get(),
            "billing_name":     self._billing_name.get(),
            "billing_nit":      self._billing_nit.get(),
            "billing_address":  self._billing_address.get(),
            "billing_email":    self._billing_email.get(),
            # Opciones
            "auto_start":       self._auto_start_var.get(),
            "auto_close":       self._auto_close_var.get(),
            "auto_close_delay": _int(self._delay_var, 60),
            # Geometría
            "window_x":      self.winfo_x(),
            "window_y":      self.winfo_y(),
            "window_width":  self.winfo_width(),
            "window_height": self.winfo_height(),
        })
        save_config(self.cfg)

    # ── Control de automatización ─────────────────────────────────────────

    def _start_automation(self) -> None:
        """Valida entradas, guarda config y lanza el hilo de automatización."""
        if self.is_running:
            return

        # Validación básica de entrada
        if not self._email.get().strip():
            self._log_msg("⚠  Se requiere un correo electrónico.", "warn")
            self._set_status(f"⚠  {get_text('error_email_req', self.cfg.get('language','es'))}")
            return

        self._autosave()
        self.stop_event.clear()
        self.is_running = True

        # Actualizar UI: deshabilitar Start, habilitar Stop
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._set_status("⚙  Iniciando automatización…")
        self._log_msg("▶  Iniciando proceso de automatización…", "info")

        # Lanzar en un hilo demonio para no bloquear la GUI
        t = threading.Thread(target=self._automation_thread_worker, daemon=True)
        t.start()

    def _automation_thread_worker(self) -> None:
        """
        Corre en un hilo separado.
        Crea su propio asyncio event loop para ejecutar la coroutine.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Solo los parámetros que usa automation.py (V0.1.x).
            # Carruseles 1/2 y payment_method fueron eliminados del flujo Sentinel.
            auto_cfg = {k: self.cfg[k] for k in (
                "email", "password", "phone_number",
                "headless", "slow_mo",
                "billing_autofill", "billing_name", "billing_nit",
                "billing_address", "billing_email",
                "carousel3_next_clicks", "carousel3_slide",
            ) if k in self.cfg}

            loop.run_until_complete(
                run_automation(auto_cfg,
                               status_callback=self._enqueue_status,
                               stop_event=self.stop_event)
            )
            self.msg_queue.put(("success", "✅  ¡Proceso completado exitosamente!"))

        except RuntimeError as exc:
            if "stopped by user" in str(exc):
                self.msg_queue.put(("warn", "⏹  Proceso detenido por el usuario."))
            else:
                self.msg_queue.put(("error", f"❌  Error: {exc}"))
        except Exception as exc:
            self.msg_queue.put(("error", f"❌  Error inesperado: {exc}"))
        finally:
            loop.close()
            self.msg_queue.put(("done", ""))  # Señal de terminación para la GUI

    def _enqueue_status(self, msg: str) -> None:
        """Encola un mensaje de estado desde el hilo de automatización hacia la GUI."""
        self.msg_queue.put(("status", msg))

    def _poll_message_queue(self) -> None:
        """
        Procesa la cola de mensajes cada 100 ms.
        Es el único punto donde el hilo de automatización actualiza la GUI
        (tkinter no es thread-safe; siempre actualizar desde el hilo principal).
        """
        try:
            while not self.msg_queue.empty():
                kind, text = self.msg_queue.get_nowait()

                if kind == "status":
                    self._log_msg(f"  → {text}", "info")
                    self._set_status(f"⚙  {text}")

                elif kind == "success":
                    self._log_msg(text, "ok")
                    self._set_status(text)

                elif kind in ("error", "warn"):
                    self._log_msg(text, kind)
                    self._set_status(text)

                elif kind == "done":
                    # Limpiar estado de ejecución
                    self.is_running = False
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")

                    # Si el usuario pidió cerrar mientras el bot corría,
                    # cerrar solo cuando el hilo ya terminó limpiamente.
                    if self._pending_close:
                        self._log_msg("ℹ  Automatización detenida; cerrando aplicación...", "info")
                        self.after(50, self._finalize_close)
                        continue

                    # Iniciar countdown si el usuario eligió autocierre
                    if self._auto_close_var.get():
                        # Proteger contra valores no numéricos ingresados por el usuario
                        try:
                            delay = int(self._delay_var.get() or 60)
                        except ValueError:
                            delay = 60
                        self._start_countdown(delay)

        except queue.Empty:
            pass
        finally:
            # Reprogramar para la próxima iteración
            self.after(100, self._poll_message_queue)

    def _stop_automation(self) -> None:
        """Solicita al hilo de automatización que se detenga de forma segura."""
        if self.is_running:
            self.stop_event.set()
            self._set_status(f"⏹  {get_text('status_stopping', self.cfg.get('language','es'))}")
            self._log_msg("⏹  Solicitando detención…", "warn")

    # ── Countdown de autocierre ───────────────────────────────────────────

    def _start_countdown(self, seconds: int) -> None:
        """Arranca el temporizador visible de autocierre."""
        self._countdown_active = True
        self._countdown_value  = seconds
        self._tick_countdown()

    def _tick_countdown(self) -> None:
        """Decrementa el contador cada segundo y cierra la app al llegar a 0."""
        if not self._countdown_active:
            self._countdown_lbl.configure(text="")
            return

        lang = self.cfg.get("language", "es")
        if self._countdown_value <= 0:
            self._countdown_lbl.configure(text="")
            self._countdown_active = False
            self._on_close()
            return

        self._countdown_lbl.configure(
            text=f"⏱  {get_text('autoclose_countdown', lang)}: {self._countdown_value}s"
        )
        self._countdown_value -= 1
        self.after(1000, self._tick_countdown)

    def _stop_countdown(self) -> None:
        """Cancela el countdown (p.ej. si el usuario cierra la app manualmente)."""
        self._countdown_active = False
        self._countdown_lbl.configure(text="")

    # ── Helpers de UI ─────────────────────────────────────────────────────

    def _log_msg(self, message: str, level: str = "info") -> None:
        """Escribe una línea con timestamp en el panel de log."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {message}\n"
        self._log_box.configure(state="normal")
        self._log_box.insert("end", line)
        self._log_box.see("end")   # Auto-scroll al último mensaje
        self._log_box.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        """Actualiza la barra de estado inferior."""
        self._status_lbl.configure(text=text)

    def _clear_log(self) -> None:
        """Vacía el panel de log visible."""
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _toggle_password(self) -> None:
        """Alterna la visibilidad del campo de contraseña."""
        if self._password.cget("show") == "•":
            self._password.configure(show="")
            self._show_btn.configure(text="🔒")
        else:
            self._password.configure(show="•")
            self._show_btn.configure(text="👁")

    def _change_language(self, lang_code: str) -> None:
        """Guarda el idioma y notifica que se requiere reiniciar para aplicarlo."""
        self.cfg["language"] = lang_code
        save_config(self.cfg)
        name = LANGUAGES.get(lang_code, lang_code)
        self._set_status(f"Idioma cambiado a {name}. Reinicia la app para aplicarlo.")
        self._log_msg(f"Idioma cambiado a {name}. Reinicia para aplicar.", "info")

    def _change_appearance(self, mode: str) -> None:
        """Aplica el modo de apariencia y lo guarda."""
        ctk.set_appearance_mode(mode)
        self.cfg["appearance_mode"] = mode
        save_config(self.cfg)

    def _on_appearance_change(self, value: str) -> None:
        """Callback del menú desplegable de apariencia."""
        lang = self.cfg.get("language", "es")
        reverse = {
            get_text("appearance_dark",   lang): "dark",
            get_text("appearance_light",  lang): "light",
            get_text("appearance_system", lang): "system",
        }
        self._change_appearance(reverse.get(value, "dark"))
        self._autosave()

    def _open_log_file(self) -> None:
        """Abre log.txt con el editor predeterminado del sistema."""
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(base, "log.txt")
        if os.path.exists(log_path):
            os.startfile(log_path)  # Windows; en Linux/Mac usar subprocess.run(["xdg-open", log_path])
        else:
            self._set_status("⚠  log.txt no encontrado.")

    def _show_about(self) -> None:
        """Abre el diálogo 'Acerca de' con información de la app."""
        lang = self.cfg.get("language", "es")
        win = ctk.CTkToplevel(self)
        win.title(get_text("about_title", lang))
        win.geometry("380x230")
        win.resizable(False, False)
        win.transient(self)   # Modal sobre la ventana principal
        win.grab_set()

        # Centrar sobre la ventana principal
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        win.geometry(f"380x230+{px + (pw - 380)//2}+{py + (ph - 230)//2}")

        ctk.CTkLabel(win, text=f"⚡  {APP_NAME}",
                     font=ctk.CTkFont(size=19, weight="bold")).pack(pady=(22, 4))
        ctk.CTkLabel(win, text=f"Versión  {VERSION}",
                     font=ctk.CTkFont(size=13)).pack()
        ctk.CTkLabel(win, text=f"Creado por  {AUTHOR}",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(pady=(12, 2))
        ctk.CTkLabel(win, text=f"© {YEAR}  Derechos Reservados",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).pack()
        ctk.CTkButton(win, text="OK", width=100, command=win.destroy).pack(pady=18)

    def _on_close(self) -> None:
        """Guarda posición y cierra la app; si el bot corre, pide confirmación."""
        if self.is_running:
            answer = messagebox.askyesno(
                "Automatización en curso",
                "La automatización sigue en ejecución. ¿Deseas detenerla y cerrar la aplicación?"
            )
            if not answer:
                self._set_status("⚙  Cierre cancelado; automatización continúa en ejecución.")
                self._log_msg("ℹ  Cierre cancelado por el usuario; automatización continúa.", "info")
                return

            self._pending_close = True
            self.stop_event.set()
            self._set_status("⏹  Deteniendo automatización antes de cerrar...")
            self._log_msg("⏹  Cierre solicitado; esperando detención limpia de la automatización...", "warn")
            return

        self._finalize_close()

    def _finalize_close(self) -> None:
        """Persiste estado final y destruye la ventana principal de forma segura."""
        self._stop_countdown()
        self._pending_close = False

        # Persistir geometría final antes de cerrar
        self.cfg.update({
            "window_x":      self.winfo_x(),
            "window_y":      self.winfo_y(),
            "window_width":  self.winfo_width(),
            "window_height": self.winfo_height(),
        })
        save_config(self.cfg)

        logger.info("Aplicación cerrada por el usuario.")
        self.destroy()
