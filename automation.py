# ─────────────────────────────────────────────────────────────────────────────
# automation.py  –  Automatización de compra de paquetes en Mi Claro (GT)
# Flujo V0.1.0: reescrito a partir de la grabación de Deploy Sentinel.
# Usa el menú de escritorio "Gestiones > Compras" en lugar del menú móvil.
# Solo requiere el Carrusel 3 (Tarjeta); los carruseles 1 y 2 fueron eliminados.
# Se ejecuta en un hilo de fondo con su propio asyncio event loop.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import logging
import threading
from typing import Callable, Optional

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger("ComprasClaroApp")

# URL de login de Mi Claro Guatemala
CLARO_LOGIN_URL = "https://www.claro.com.gt/miclaro/login"


# ── Helpers internos ───────────────────────────────────────────────────────

async def _safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    """
    Intenta hacer clic en un selector.
    Devuelve True si lo logra, False si no lo encuentra en el tiempo dado.
    Útil para elementos opcionales (popups, modales condicionales).
    """
    try:
        await page.click(selector, timeout=timeout)
        return True
    except Exception:
        return False


async def _try_selectors(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """
    Itera una lista de selectores y hace clic en el primero que encuentre.
    Devuelve True si alguno funcionó. Útil para el botón "Continuar" con
    múltiples posibles selectores.
    """
    for sel in selectors:
        if await _safe_click(page, sel, timeout=timeout):
            logger.debug("Selector encontrado y clicado: %s", sel)
            return True
    return False


async def _safe_wait_networkidle(page: Page, timeout: int = 15000) -> None:
    """
    Espera a que la red esté inactiva ("networkidle").
    Si el sitio mantiene conexiones persistentes (WebSockets, polling) y no
    alcanza networkidle en el timeout dado, registra un warning y continúa.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        logger.debug("networkidle no alcanzado en %dms; continuando.", timeout)


async def _click_and_navigate(page: Page, selector: str, timeout: int = 20000) -> None:
    """
    Hace clic en un selector y espera que el navegador complete la navegación.
    Si no ocurre navegación completa (ej. SPA con history.pushState o AJAX),
    captura el timeout silenciosamente y espera networkidle como fallback.
    Equivalente al Promise.all([click, waitForNavigation]) del Sentinel JS.
    """
    try:
        async with page.expect_navigation(timeout=timeout):
            await page.click(selector)
    except Exception:
        # No hubo navegación completa (SPA / AJAX / popup intermedio)
        logger.debug("Sin navegación completa tras click en '%s'; esperando networkidle.", selector)
        await _safe_wait_networkidle(page)


async def _dismiss_modal(page: Page) -> None:
    """
    Cierra cualquier modal u overlay que bloquee clics en la página.

    El sitio muestra modales condicionales de renovación/notificaciones:
      - El botón de aceptar tiene clase .btnBlancoRojo  ← selector principal
      - El contenedor es div#Modal con .renovationFavoriteModal y .blur

    Niveles de fallback (se detiene en el primero que funcione):
      1. Botón .btnBlancoRojo (botón "Aceptar" del modal de renovación)
      2. Botones por texto: Aceptar, Entendido, OK, Cerrar, Continuar
      3. Botón X de cierre interno
      4. Tecla Escape
      5. Clic en el overlay .blur para cerrar
      6. Ocultar via JavaScript (último recurso legítimo en automatización)
    """
    # Verificar si el modal es visible antes de intentar cerrarlo
    modal = page.locator("#Modal")
    try:
        visible = await modal.is_visible()
    except Exception:
        return

    if not visible:
        return

    logger.debug("Modal detectado; intentando cerrarlo...")

    # ── Prioridad 1: .btnBlancoRojo — botón "Aceptar" del modal de renovación
    # Selector capturado con Deploy Sentinel; es el más confiable para este modal.
    if await _safe_click(page, ".btnBlancoRojo", timeout=2000):
        logger.debug("Modal cerrado con .btnBlancoRojo")
        await asyncio.sleep(0.3)
        return

    # ── Prioridad 2: botones por texto dentro del modal ──────────────────────
    text_selectors = [
        '#Modal button:has-text("Aceptar")',
        '#Modal button:has-text("Entendido")',
        '#Modal button:has-text("OK")',
        '#Modal button:has-text("Cerrar")',
        '#Modal button:has-text("Continuar")',
        '#Modal a:has-text("Aceptar")',
        '#Modal a:has-text("Entendido")',
        ".renovationFavoriteModal .btnPrimario",
        ".renovationFavoriteModal .btn",
        ".renovationFavoriteModal a",
    ]
    for sel in text_selectors:
        if await _safe_click(page, sel, timeout=1000):
            logger.debug("Modal cerrado con selector de texto: %s", sel)
            await asyncio.sleep(0.3)
            return

    # ── Prioridad 3: botón X de cierre ───────────────────────────────────────
    close_selectors = [
        "#Modal .close",
        "#Modal .btn-close",
        "#Modal [aria-label='Close']",
        "#Modal [aria-label='Cerrar']",
        "#Modal .ico-close",
        ".renovationFavoriteModal .close",
    ]
    for sel in close_selectors:
        if await _safe_click(page, sel, timeout=1000):
            logger.debug("Modal cerrado con botón X: %s", sel)
            await asyncio.sleep(0.3)
            return

    # ── Prioridad 4: tecla Escape ─────────────────────────────────────────────
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.4)

    # ── Prioridad 5: clic en el backdrop blur ─────────────────────────────────
    await _safe_click(page, "#Modal .blur", timeout=1000)
    await _safe_click(page, ".Blurxx", timeout=1000)

    # ── Prioridad 6 (último recurso): ocultar via JavaScript ─────────────────
    # Aceptable en automatización porque controlamos el contexto del navegador.
    await page.evaluate("""() => {
        const modal = document.getElementById('Modal');
        if (modal) modal.style.display = 'none';
        document.querySelectorAll('.blur, .renovationFavoriteModal').forEach(el => {
            el.style.display = 'none';
        });
    }""")
    logger.debug("Modal ocultado via JavaScript como último recurso.")


def _check_stop(stop_event: Optional[threading.Event]) -> None:
    """
    Lanza RuntimeError si el usuario solicitó detener la automatización.
    Se llama en puntos de control para que la parada sea inmediata.
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
    Flujo basado en la grabación de Deploy Sentinel (V0.1.0).

    Parámetros
    ----------
    config          : Diccionario con la configuración (email, teléfono, etc.)
    status_callback : Función que recibe mensajes de estado para la GUI.
    stop_event      : threading.Event — cuando se pone en set() detiene el bot.
    """

    def notify(msg: str) -> None:
        """Registra en log y notifica a la GUI simultáneamente."""
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    # ── Extraer parámetros de config ───────────────────────────────────────
    email         = config.get("email", "")
    password      = config.get("password", "")
    phone_number  = config.get("phone_number", "34884422")
    headless      = config.get("headless", True)
    slow_mo       = int(config.get("slow_mo", 0))

    # Solo carrusel 3 es relevante en este flujo
    c3_clicks     = int(config.get("carousel3_next_clicks", 4))
    c3_slide      = int(config.get("carousel3_slide", 13))

    async with async_playwright() as playwright:

        # ── Lanzar Chromium ────────────────────────────────────────────────
        notify("Iniciando navegador Chromium...")
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
        )

        # Viewport fijo igual al grabado con Sentinel
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1696, "height": 784},
        )

        try:
            page: Page = await context.new_page()

            # ── 1. Página de login ─────────────────────────────────────────
            _check_stop(stop_event)
            notify("Navegando a Mi Claro Guatemala...")
            await page.goto(CLARO_LOGIN_URL, wait_until="domcontentloaded")

            # Pausa breve para que el JS del sitio (SweetAlert, etc.) se inicialice
            await asyncio.sleep(1)

            # Popup SweetAlert2 inicial — condicional; puede no aparecer.
            # Usamos _safe_click para no lanzar timeout si no está presente.
            notify("Verificando popup inicial 'Ir a Login'...")
            _check_stop(stop_event)
            popup_clicked = await _safe_click(page, ".swal2-confirm", timeout=8000)
            if popup_clicked:
                notify("Popup 'Ir a Login' aceptado.")
            else:
                notify("Popup no presente; continuando al login...")
            await _safe_wait_networkidle(page)

            # ── 2. Login ───────────────────────────────────────────────────
            _check_stop(stop_event)

            # Detectar si el usuario ya está logueado (sesión activa en el navegador).
            # Si el menú de Gestiones ya es visible, no es necesario ingresar credenciales.
            already_logged = await page.locator(".menu_header_gestiones").is_visible()

            if already_logged:
                notify("Sesión activa detectada; omitiendo login...")
            else:
                notify("Ingresando credenciales...")

                # Rellenar email — envuelto en try/except por si el campo no existe
                if email:
                    try:
                        email_field = page.locator('[name="email"]')
                        if await email_field.count() > 0:
                            await email_field.first.fill(email)
                    except Exception as e:
                        logger.warning("No se pudo llenar el email: %s", e)

                # Rellenar contraseña si está configurada y el campo existe
                if password:
                    try:
                        pass_field = page.locator('[name="password"], [type="password"]')
                        if await pass_field.count() > 0:
                            await pass_field.first.fill(password)
                    except Exception as e:
                        logger.warning("No se pudo llenar la contraseña: %s", e)

                # Click en el botón de login — usa _click_and_navigate para manejar
                # tanto navegación completa como redirección SPA
                notify("Enviando formulario de login...")
                await _click_and_navigate(page, ".btnPrimario", timeout=15000)

            await _safe_wait_networkidle(page)

            # ── 3. Navegar a Gestiones → Compras ──────────────────────────
            # Flujo Sentinel: menú de escritorio "Gestiones" en lugar del menú móvil
            _check_stop(stop_event)
            notify("Abriendo menú Gestiones...")
            await page.click(".menu_header_gestiones > label")

            notify("Seleccionando Compras en el menú...")
            await page.click(".hideOnDesk:nth-child(3) a")   # Enlace "Compras"
            await page.click(".selectedTitleOp")               # Confirmar selección

            # ── 4. Aceptar modal de renovación ────────────────────────────
            # El sitio muestra aleatoriamente un modal "¡Hola XXX, ya puedes renovar!"
            # con botón .btnBlancoRojo (Aceptar). _dismiss_modal lo maneja con
            # 6 niveles de fallback.
            _check_stop(stop_event)
            notify("Verificando modal de renovación...")
            await _dismiss_modal(page)

            # ── 5. Scroll y selección de número de teléfono ───────────────
            _check_stop(stop_event)
            notify(f"Buscando número {phone_number}...")

            # Scrolls para exponer la lista de números (del flujo Sentinel)
            await page.mouse.wheel(0, 2376)
            await page.mouse.wheel(0, -216)

            # Clic directo en el número dentro del boxConsume correspondiente.
            # Sentinel usa nth-child(7) para el número configurado;
            # si hay múltiples números intenta primero por texto y luego por posición.
            phone_link = page.locator(".boxConsume p", has_text=phone_number)
            if await phone_link.count() > 0:
                # Clic en el número por texto y esperar navegación con fallback SPA
                await phone_link.first.click()
                await _safe_wait_networkidle(page)
            else:
                logger.warning("Número %s no encontrado por texto; usando posición.", phone_number)
                await _click_and_navigate(page, ".boxConsume:nth-child(7) p:nth-child(1)", timeout=15000)

            await _safe_wait_networkidle(page)

            # ── 6. Scrolls post-selección de número ───────────────────────
            _check_stop(stop_event)
            await page.mouse.wheel(0, 216)
            await page.mouse.wheel(0, 756)
            await page.mouse.wheel(0, -108)

            # ── 7. Navegar nuevamente a Gestiones → Comprar Paquete ────────
            # El sentinel realiza una segunda navegación por el menú Gestiones
            # para llegar directamente a la vista de "Comprar Paquete".
            _check_stop(stop_event)
            notify("Navegando a Comprar Paquete via menú Gestiones...")
            await page.click(".menu_header_gestiones")
            await page.click(".hideOnDesk:nth-child(3) a")
            await page.click(".selectedTitleOp")
            await page.click(".hideOnDesk:nth-child(3) > .displayOp")
            await page.click(".selectedTitleOp")

            # Scrolls para posicionar la vista en la sección de paquetes
            await page.mouse.wheel(0, 1296)
            await page.mouse.wheel(0, -432)
            await page.mouse.wheel(0, 216)

            # ── 8. Click en "Comprar Paquete" ─────────────────────────────
            # Antes de hacer clic, descartar cualquier modal que esté activo.
            _check_stop(stop_event)
            notify("Cerrando modal si está activo antes de abrir compra...")
            await _dismiss_modal(page)

            notify("Abriendo vista de compra de paquetes...")
            await _click_and_navigate(
                page,
                ".boxConsume:nth-child(7) #compraPaquete > .textLink1:nth-child(2)",
                timeout=20000,
            )
            await _safe_wait_networkidle(page)

            # Descartar modal que pueda aparecer en la vista de compra
            await _dismiss_modal(page)

            # ── 9. Scroll para mostrar el carrusel ────────────────────────
            _check_stop(stop_event)
            notify("Desplazando hacia el carrusel de paquetes...")
            await page.mouse.wheel(0, 756)

            # ── 10. Navegar Carrusel 3 (Tarjeta) ──────────────────────────
            # Solo carrusel 3 según el flujo capturado por Sentinel.
            # El número de clics es configurable desde la GUI.
            _check_stop(stop_event)
            notify(f"Navegando carrusel ({c3_clicks} clic(s) en Siguiente)...")
            for _ in range(c3_clicks):
                _check_stop(stop_event)
                await page.click("div:nth-child(3) > .contBoxPaquetes .slick-next")

            # ── 11. Comprar paquete en el carrusel ────────────────────────
            # Hace clic en el botón "Comprar" del paquete en la posición c3_slide.
            # El índice nth-child es configurable desde la GUI.
            _check_stop(stop_event)
            notify(f"Comprando paquete (posición {c3_slide})...")
            await _click_and_navigate(
                page,
                f"div:nth-child(3) > .contBoxPaquetes:nth-child(5) "
                f".slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                timeout=20000,
            )
            await _safe_wait_networkidle(page)

            # ── 12. Scrolls finales (igual que Sentinel) ───────────────────
            await page.mouse.wheel(0, 324)
            await page.mouse.wheel(0, -324)

            notify("✅ Proceso de compra completado exitosamente.")

            # Pausa para que el estado final sea visible si headless=False
            await asyncio.sleep(2)

        except RuntimeError as exc:
            # Error controlado: el usuario detuvo la automatización
            if "stopped by user" in str(exc):
                notify("⏹ Proceso detenido por el usuario.")
                raise
            logger.error("Error en la automatización: %s", exc, exc_info=True)
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
