# ─────────────────────────────────────────────────────────────────────────────
# automation.py  –  Automatización de compra de paquetes en Mi Claro (GT)
# Convierte el script Playwright/JS original a Python asíncrono.
# Se ejecuta en un hilo de fondo; la GUI lo controla mediante un threading.Event
# y recibe actualizaciones de estado mediante un callback.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import logging
import threading
from typing import Callable, Optional

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger("ComprasClaroApp")

# URL base de Mi Claro Guatemala
CLARO_LOGIN_URL = "https://www.claro.com.gt/miclaro/login"


# ── Helpers internos ───────────────────────────────────────────────────────

async def _safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    """
    Intenta hacer clic en un selector.
    Devuelve True si lo logra, False si no lo encuentra en el tiempo dado.
    Útil para clics opcionales (popup condicional, botones que pueden no existir).
    """
    try:
        await page.click(selector, timeout=timeout)
        return True
    except Exception:
        return False


async def _try_selectors(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """
    Itera una lista de selectores y hace clic en el primero que encuentre.
    Devuelve True si alguno funcionó.
    """
    for sel in selectors:
        if await _safe_click(page, sel, timeout=timeout):
            logger.debug("Selector encontrado y clicado: %s", sel)
            return True
    return False


async def _dismiss_modal(page: Page) -> None:
    """
    Cierra cualquier modal u overlay que pueda bloquear clics en la página.
    El sitio muestra modales de renovación/notificaciones dentro de div#Modal
    con clases .renovationFavoriteModal y .blur que interceptan eventos de puntero.
    Se prueban varios métodos en orden: botón X interno, Escape, clic en blur,
    y como último recurso ocultar via JavaScript (legítimo en contexto de automatización).
    """
    # Si no hay modal visible, no hacer nada
    modal = page.locator("#Modal")
    try:
        visible = await modal.is_visible()
    except Exception:
        return

    if not visible:
        return

    logger.debug("Modal detectado; intentando cerrarlo...")

    # Intentar botón de cierre interno del modal (distintas convenciones de clase)
    close_selectors = [
        "#Modal .close",
        "#Modal .btn-close",
        "#Modal [aria-label='Close']",
        "#Modal .ico-close",
        "#Modal .modal-close",
        ".renovationFavoriteModal .close",
        ".renovationFavoriteModal button",
    ]
    for sel in close_selectors:
        if await _safe_click(page, sel, timeout=1000):
            logger.debug("Modal cerrado con selector: %s", sel)
            await asyncio.sleep(0.3)
            return

    # Intentar tecla Escape
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.4)

    # Intentar clic directo en el overlay blur (a veces cierra el modal)
    await _safe_click(page, "#Modal .blur", timeout=1000)
    await _safe_click(page, ".Blurxx", timeout=1000)

    # Último recurso: forzar ocultado por JavaScript.
    # Aceptable en automatización porque controlamos el contexto del navegador.
    await page.evaluate("""() => {
        const modal = document.getElementById('Modal');
        if (modal) modal.style.display = 'none';
        document.querySelectorAll('.blur, .renovationFavoriteModal').forEach(el => {
            el.style.display = 'none';
        });
    }""")
    logger.debug("Modal ocultado via JavaScript como último recurso.")


async def _safe_wait_networkidle(page: Page, timeout: int = 15000) -> None:
    """
    Espera a que la red esté inactiva ("networkidle").
    Si el sitio mantiene conexiones persistentes (WebSockets, polling) y no
    alcanza networkidle en el timeout dado, registra un warning y continúa.
    Esto evita que el proceso quede bloqueado por requests de fondo.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # Algunos sitios nunca alcanzan networkidle; el flujo puede continuar igual
        logger.debug("networkidle no alcanzado en %dms; continuando de todos modos.", timeout)


def _check_stop(stop_event: Optional[threading.Event]) -> None:
    """
    Lanza una excepción controlada si el usuario pidió detener la automatización.
    Se llama periódicamente dentro del flujo para que el stop sea responsivo.
    """
    if stop_event and stop_event.is_set():
        raise RuntimeError("stopped by user")


# ── Función principal exportada ────────────────────────────────────────────

async def run_automation(
    config: dict,
    status_callback: Optional[Callable[[str], None]] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """
    Ejecuta el flujo completo de compra de paquetes en Mi Claro Guatemala.

    Parámetros
    ----------
    config          : Diccionario con toda la configuración (email, teléfono, etc.)
    status_callback : Función que recibe un str con el mensaje de estado actual.
                      Se llama desde el hilo de la coroutine (NOT desde el hilo GUI).
    stop_event      : threading.Event que, cuando se pone en set(), interrumpe
                      la automatización de forma segura en el siguiente checkpoint.
    """

    def notify(msg: str) -> None:
        """Registra en log y notifica a la GUI al mismo tiempo."""
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    # ── Extraer parámetros de config ───────────────────────────────────────
    email           = config.get("email", "")
    password        = config.get("password", "")
    phone_number    = config.get("phone_number", "34884422")
    headless        = config.get("headless", True)
    slow_mo         = int(config.get("slow_mo", 0))

    # Clics en botón "Next" de cada carrusel de paquetes
    c1_clicks       = int(config.get("carousel1_next_clicks", 3))
    c1_slide        = int(config.get("carousel1_slide", 13))
    c2_clicks       = int(config.get("carousel2_next_clicks", 9))
    c3_clicks       = int(config.get("carousel3_next_clicks", 4))
    c3_slide        = int(config.get("carousel3_slide", 13))

    payment_method  = config.get("payment_method", "tarjeta")  # "saldo" | "tarjeta"

    async with async_playwright() as playwright:
        # ── Lanzar Chromium ────────────────────────────────────────────────
        notify("Iniciando navegador Chromium...")
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
        )

        # Contexto con viewport fijo (igual que el script JS original)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1696, "height": 784},
        )

        try:
            page: Page = await context.new_page()

            # ── 1. Página de login ─────────────────────────────────────────
            _check_stop(stop_event)
            notify("Navegando a Mi Claro Guatemala...")
            await page.goto(CLARO_LOGIN_URL, wait_until="domcontentloaded")

            # Pausa breve para que el JavaScript del sitio (SweetAlert2) termine
            # de inicializarse después del evento DOMContentLoaded.
            await asyncio.sleep(1)

            # ── FIX V0.0.2: El popup SweetAlert2 es CONDICIONAL ───────────
            # El sitio no siempre lo muestra (depende de sesión, caché del servidor,
            # o cambios en el sitio). Usamos _safe_click con timeout de 8 s:
            #  · Si el popup aparece → se acepta y se continúa.
            #  · Si NO aparece       → se omite y se va directo al formulario de login.
            # Antes usaba page.click() directo que lanzaba timeout de 30 s si no había popup.
            notify("Verificando popup inicial 'Ir a Login'...")
            _check_stop(stop_event)
            popup_clicked = await _safe_click(page, ".swal2-confirm", timeout=8000)
            if popup_clicked:
                notify("Popup 'Ir a Login' aceptado.")
            else:
                notify("Popup no presente; continuando directamente al login...")
            await _safe_wait_networkidle(page)

            # ── 2. Ingresar credenciales ───────────────────────────────────
            _check_stop(stop_event)
            notify("Ingresando credenciales...")
            await page.fill('[name="email"]', email)

            # Si hay contraseña configurada y el campo existe, llenarla también
            if password:
                pass_field = page.locator('[name="password"], [type="password"]')
                if await pass_field.count() > 0:
                    await pass_field.first.fill(password)

            # Enviar formulario de login
            await page.click(".btnPrimario")
            await _safe_wait_networkidle(page)

            # ── 3. Seleccionar número de teléfono ─────────────────────────
            _check_stop(stop_event)
            notify(f"Seleccionando número {phone_number}...")

            # Abrir menú desplegable de números
            await page.click(".menu_header_movil > .ico-chevron-down")

            # Buscar el número por texto (más robusto que el selector posicional original)
            phone_link = page.locator(f".hideOnDesk a", has_text=phone_number)
            if await phone_link.count() > 0:
                await phone_link.first.click()
            else:
                # Fallback al selector original si no se encuentra por texto
                logger.warning("Número %s no encontrado por texto; usando selector posicional.", phone_number)
                await page.click(".hideOnDesk:nth-child(5) a:nth-child(2)")

            await _safe_wait_networkidle(page)

            # ── 4. Revisar consumos (igual que el flujo original) ──────────
            _check_stop(stop_event)
            notify("Revisando detalle de consumos...")
            await page.mouse.wheel(0, 108)
            await page.click("#misConsumos")
            await page.click("#misConsumos")
            await page.click("#misConsumos p")
            await page.mouse.wheel(0, 864)
            await _safe_click(page, "#sectHistRecargas p")
            await page.mouse.wheel(0, 216)
            await _safe_click(page, "#historialPaquete p")
            await page.mouse.wheel(0, 432)
            await page.mouse.wheel(0, -1404)

            # ── 5. Volver al menú de números y navegar a "Ver todo" ────────
            _check_stop(stop_event)
            notify("Navegando hacia la sección de paquetes...")
            await page.click(".menu_header_movil > .ico-chevron-down")

            # Seleccionar número nuevamente
            phone_link2 = page.locator(f".hideOnDesk a", has_text=phone_number)
            if await phone_link2.count() > 0:
                await phone_link2.first.click()
            else:
                await page.click(".hideOnDesk:nth-child(5) a:nth-child(2)")
            await _safe_wait_networkidle(page)

            # Cerrar menús extra que puedan estar abiertos
            await _safe_click(page, ".menu_header_gestiones > label")
            await _safe_click(page, ".menu_header_claro_hogar > label")
            await _safe_click(page, ".headerProfile")

            # Abrir menú nuevamente y hacer clic en "Ver todo"
            await page.click(".menu_header_movil > .ico-chevron-down")
            await page.click(".viewAll > a")
            await _safe_wait_networkidle(page)

            # ── 6. Navegar hasta el botón "Comprar Paquete" ────────────────
            _check_stop(stop_event)
            notify("Buscando sección de compra de paquetes...")
            await page.mouse.wheel(0, 648)
            await page.mouse.wheel(0, -540)

            # Ir al resumen de consumo del primer número
            await _safe_click(page, ".boxConsume:nth-child(1) .arrow1 > img")
            await _safe_click(page, ".headerProfile")

            # Ir a la página de paquetes disponibles
            await page.click(".container > [href='#']")
            await _safe_wait_networkidle(page)

            # Hacer scroll para encontrar el paquete deseado
            await page.mouse.wheel(0, 3348)
            await page.mouse.wheel(0, -3672)
            await page.mouse.wheel(0, 2160)

            # ── 7. Abrir la vista de compra de paquetes ────────────────────
            _check_stop(stop_event)

            # FIX V0.0.3: El sitio muestra un modal (#Modal / .renovationFavoriteModal /
            # .blur) que bloquea el clic en "Comprar Paquete". Debe descartarse ANTES
            # del clic, no después. El selector .Blurxx original era incorrecto;
            # el overlay real es .blur dentro de #Modal.
            notify("Cerrando modal o overlay antes de abrir compra...")
            await _dismiss_modal(page)

            notify("Abriendo compra de paquetes...")
            await page.click(".boxConsume:nth-child(7) #compraPaquete > .textLink1:nth-child(2)")
            await _safe_wait_networkidle(page)

            # Cerrar cualquier modal que haya aparecido después de navegar a la sección
            await _dismiss_modal(page)

            await page.mouse.wheel(0, 648)
            await page.mouse.wheel(0, -432)
            await page.mouse.wheel(0, 1728)
            await page.mouse.wheel(0, -1296)

            # ── 8. Seleccionar método de pago con Saldo ────────────────────
            _check_stop(stop_event)
            notify("Seleccionando opción de pago por saldo...")
            await page.click("#saldo")
            await page.mouse.wheel(0, 216)

            # ── 9. Navegar carrusel 1 (paquetes de saldo) ──────────────────
            _check_stop(stop_event)
            notify(f"Navegando carrusel 1 ({c1_clicks} clic(s) en Siguiente)...")
            for _ in range(c1_clicks):
                _check_stop(stop_event)
                await page.click("div:nth-child(2) > .contBoxPaquetes .slick-next")

            await page.mouse.wheel(0, 972)

            # ── 10. Navegar carrusel 2 (paquetes adicionales) ──────────────
            _check_stop(stop_event)
            notify(f"Navegando carrusel 2 ({c2_clicks} clic(s) en Siguiente)...")
            for _ in range(c2_clicks):
                _check_stop(stop_event)
                await page.click("div:nth-child(4) .slick-next")

            await page.mouse.wheel(0, -972)
            await page.mouse.wheel(0, 1080)
            await page.mouse.wheel(0, -972)

            # ── 11. Comprar paquete en carrusel 1 ──────────────────────────
            _check_stop(stop_event)
            notify(f"Comprando paquete del carrusel 1 (posición {c1_slide})...")
            await page.click(f".slick-slide:nth-child({c1_slide}) .btn")

            # Confirmar en popup SweetAlert2 (también puede no aparecer en algunos casos)
            await _safe_click(page, ".swal2-confirm")

            # Ver/cerrar tooltip informativo si aparece
            await _safe_click(page, f".slick-slide:nth-child({c1_slide}) .viewTooltip", timeout=2000)
            await _safe_click(page, '[aria-label="Close this dialog"]', timeout=2000)

            await page.mouse.wheel(0, -216)

            # ── 12. Seleccionar método de pago por Tarjeta ─────────────────
            if payment_method == "tarjeta":
                _check_stop(stop_event)
                notify("Seleccionando pago con Tarjeta...")
                await page.click(".boxmt:nth-child(1) > label")

            await page.mouse.wheel(0, 864)

            # ── 13. Navegar carrusel 3 (paquetes con tarjeta) ──────────────
            _check_stop(stop_event)
            notify(f"Navegando carrusel 3 ({c3_clicks} clic(s) en Siguiente)...")
            for _ in range(c3_clicks):
                _check_stop(stop_event)
                await page.click("div:nth-child(3) > .contBoxPaquetes .slick-next")

            # ── 14. Comprar paquete en carrusel 3 ──────────────────────────
            _check_stop(stop_event)
            notify(f"Comprando paquete del carrusel 3 (posición {c3_slide})...")
            await page.click(
                f"div:nth-child(3) > .contBoxPaquetes:nth-child(5) "
                f".slick-slide:nth-child({c3_slide}) .btn:nth-child(1)"
            )
            await _safe_wait_networkidle(page)

            # Scrolls finales del flujo original
            await page.mouse.wheel(0, 216)
            await page.mouse.wheel(0, -216)
            await page.mouse.wheel(0, 216)
            await page.mouse.wheel(0, -216)

            # ── 15. Hacer clic en "Continuar" para finalizar ───────────────
            _check_stop(stop_event)
            notify("Buscando botón 'Continuar' para finalizar el proceso...")

            # Lista de selectores posibles para el botón "Continuar".
            # Se prueban en orden; se detiene en el primero que funcione.
            continuar_selectors = [
                'button:has-text("Continuar")',
                'a:has-text("Continuar")',
                'input[value="Continuar"]',
                '.swal2-confirm',       # Si aparece otro popup de confirmación
                '#btnContinuar',
                '.btn-continuar',
                'button.continuar',
                '[data-action="continuar"]',
            ]

            clicked = await _try_selectors(page, continuar_selectors, timeout=5000)

            if clicked:
                notify("✅ Botón 'Continuar' presionado. Proceso finalizado.")
                await _safe_wait_networkidle(page, timeout=10000)
            else:
                notify("⚠ Botón 'Continuar' no encontrado. El proceso puede igualmente haberse completado.")

            # Pausa breve para que el estado final sea visible si headless=False
            await asyncio.sleep(2)

        except RuntimeError as exc:
            # Error controlado: el usuario detuvo el proceso
            if "stopped by user" in str(exc):
                notify("⏹ Proceso detenido por el usuario.")
                raise
            logger.error("Error inesperado en la automatización: %s", exc, exc_info=True)
            notify(f"❌ Error: {exc}")
            raise

        except Exception as exc:
            logger.error("Error inesperado en la automatización: %s", exc, exc_info=True)
            notify(f"❌ Error inesperado: {exc}")
            raise

        finally:
            # Siempre cerrar el navegador, incluso si hubo error
            await context.close()
            await browser.close()
            notify("Navegador cerrado.")
