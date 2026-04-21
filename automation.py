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

from playwright.async_api import async_playwright, Page, BrowserContext, Locator

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
    click_timeout = min(timeout, 10000)

    # Intento 1: click+navegación estándar
    try:
        async with page.expect_navigation(timeout=timeout):
            await page.click(selector, timeout=click_timeout)
        return
    except Exception as first_exc:
        logger.debug("Primer intento click+navegación falló en '%s': %s", selector, first_exc)

    # Intento 2: cerrar modal/overlay y reintentar click+navegación
    await _dismiss_modal(page)
    try:
        async with page.expect_navigation(timeout=timeout):
            await page.click(selector, timeout=click_timeout)
        return
    except Exception as second_exc:
        logger.debug("Reintento click+navegación falló en '%s': %s", selector, second_exc)

    # Fallback final: click sin navegación dura + espera de estabilidad
    await page.click(selector, timeout=click_timeout)
    await _safe_wait_networkidle(page)


async def _click_locator_and_navigate(page: Page, locator: Locator, timeout: int = 20000) -> None:
    """
    Hace clic en un Locator y espera navegación si ocurre.
    Si el sitio no navega de forma clásica (SPA/AJAX), cae a networkidle.
    """
    click_timeout = min(timeout, 10000)

    # Intento 1: click+navegación estándar con locator
    try:
        async with page.expect_navigation(timeout=timeout):
            await locator.click(timeout=click_timeout)
        return
    except Exception as first_exc:
        logger.debug("Primer intento click+navegación (locator) falló: %s", first_exc)

    # Intento 2: cerrar modal/overlay y reintentar
    await _dismiss_modal(page)
    try:
        async with page.expect_navigation(timeout=timeout):
            await locator.click(timeout=click_timeout)
        return
    except Exception as second_exc:
        logger.debug("Reintento click+navegación (locator) falló: %s", second_exc)

    # Fallback final: click sin navegación dura + espera de estabilidad
    await locator.click(timeout=click_timeout)
    await _safe_wait_networkidle(page)


async def _dismiss_modal(page: Page) -> None:
    """
    Cierra cualquier modal u overlay que bloquee clics en la página.

    El sitio muestra modales condicionales de renovación/notificaciones:
      - El botón de aceptar tiene clase .btnBlancoRojo  ← selector principal
      - El contenedor es div#Modal con .renovationFavoriteModal y .blur

    El botón "Aceptar" es: <button class="btn btnBlancoRojo">Aceptar</button>
    El overlay .blur tiene z-index superior al botón, por lo que page.click() normal
    falla porque Playwright detecta que el puntero sería interceptado por .blur.
    Solución: usar element.click() desde JavaScript, que bypasea z-index y
    pointer-events y dispara el evento directamente sobre el elemento DOM.

    Niveles de fallback (se detiene en el primero que funcione):
      1. JS element.click() en .btnBlancoRojo  ← bypasea overlay
      2. JS element.click() en botón por texto (Aceptar, Entendido, OK…)
      3. Tecla Escape
      4. Ocultar via JavaScript (display:none + pointerEvents:none)
    """
    # Chequeo DOM — querySelector detecta el elemento aunque esté cubierto por
    # el overlay (a diferencia de is_visible() que lee CSS). Si no hay modal en
    # el DOM, retorna inmediatamente sin ningún efecto secundario en la página.
    modal_present = await page.evaluate(
        "() => !!document.querySelector('.btnBlancoRojo, #Modal, .renovationFavoriteModal')"
    )
    if not modal_present:
        return

    logger.debug("Modal detectado en DOM; intentando cerrarlo...")

    # ── Prioridad 1: JS click directo en .btnBlancoRojo ───────────────────────
    # El overlay .blur tiene z-index superior → page.click() falla porque
    # Playwright verifica interceptación de puntero. element.click() en JS
    # bypasea esa verificación y dispara el evento directo en el nodo DOM.
    clicked = await page.evaluate("""() => {
        const btn = document.querySelector('.btnBlancoRojo');
        if (btn) { btn.click(); return true; }
        return false;
    }""")
    if clicked:
        logger.debug("Modal cerrado con JS click en .btnBlancoRojo")
        await asyncio.sleep(0.5)
        return

    # ── Prioridad 2: JS click en cualquier botón del modal por texto ──────────
    clicked = await page.evaluate("""() => {
        const texts = ['Aceptar', 'Entendido', 'OK', 'Cerrar', 'Continuar'];
        const modal = document.getElementById('Modal');
        if (!modal) return false;
        for (const btn of modal.querySelectorAll('button, a')) {
            if (texts.some(t => btn.textContent.trim().includes(t))) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")
    if clicked:
        logger.debug("Modal cerrado con JS click por texto")
        await asyncio.sleep(0.5)
        return

    # ── Prioridad 3: Escape + JS hide (solo si el modal existe pero no respondió) ──
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.4)
    await page.evaluate("""() => {
        const hide = (el) => {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.pointerEvents = 'none';
        };
        const modal = document.getElementById('Modal');
        if (modal) hide(modal);
        document.querySelectorAll('.blur, .renovationFavoriteModal').forEach(hide);
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

            # Cierre preventivo del modal inmediatamente después de login/sesión activa.
            # Este modal aparece de forma intermitente y puede bloquear todo el menú.
            _check_stop(stop_event)
            await _dismiss_modal(page)

            # ── 3. Navegar a Gestiones → Compras ──────────────────────────
            # Flujo Sentinel: menú de escritorio "Gestiones" en lugar del menú móvil
            _check_stop(stop_event)
            notify("Abriendo menú Gestiones...")
            await page.click(".menu_header_gestiones > label")

            notify("Seleccionando Compras en el menú...")
            await page.click(".hideOnDesk:nth-child(3) a")   # Enlace "Compras"
            await page.click(".selectedTitleOp")               # Confirmar selección

            # Paso Sentinel: intentar "Aceptar" justo después de confirmar Compras.
            # Si no está presente, no interrumpe el flujo.
            await _safe_click(page, ".btnBlancoRojo", timeout=1500)

            # Descartar modal de renovación — según Sentinel aparece exactamente
            # tras la primera confirmación de Compras (.selectedTitleOp).
            await _dismiss_modal(page)
            await asyncio.sleep(0.3)

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
                await _click_locator_and_navigate(page, phone_link.first, timeout=15000)
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
            _check_stop(stop_event)
            notify("Abriendo vista de compra de paquetes...")
            await _click_and_navigate(
                page,
                ".boxConsume:nth-child(7) #compraPaquete > .textLink1:nth-child(2)",
                timeout=20000,
            )
            await _safe_wait_networkidle(page)

            # ── 9. Scroll para mostrar el carrusel ────────────────────────
            _check_stop(stop_event)
            notify("Desplazando hacia el carrusel de paquetes...")
            await page.mouse.wheel(0, 756)

            # ── 10. Navegar Carrusel 3 (Tarjeta) ──────────────────────────
            # Solo carrusel 3 según el flujo capturado por Sentinel.
            # El número de clics es configurable desde la GUI.
            # Selectores en orden de especificidad: Sentinel exacto → sin wrapper → global
            _check_stop(stop_event)
            notify("Esperando que cargue el carrusel de paquetes...")
            try:
                await page.wait_for_selector(".contBoxPaquetes", timeout=15000)
            except Exception:
                logger.warning(".contBoxPaquetes no encontrado en 15s; continuando...")

            slick_next_selectors = [
                "div:nth-child(3) > .contBoxPaquetes .slick-next",
                ".contBoxPaquetes .slick-next",
                ".slick-next",
            ]
            notify(f"Navegando carrusel ({c3_clicks} clic(s) en Siguiente)...")
            for _ in range(c3_clicks):
                _check_stop(stop_event)
                clicked = await _try_selectors(page, slick_next_selectors, timeout=10000)
                if not clicked:
                    logger.warning("No se encontró .slick-next para avanzar carrusel")
                await asyncio.sleep(0.3)

            # ── 11. Comprar paquete en el carrusel ────────────────────────
            # Hace clic en el botón "Comprar" del paquete en la posición c3_slide.
            # El índice nth-child es configurable desde la GUI.
            _check_stop(stop_event)
            notify(f"Comprando paquete (posición {c3_slide})...")
            buy_selectors = [
                f"div:nth-child(3) > .contBoxPaquetes:nth-child(5) .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".contBoxPaquetes:nth-child(5) .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".contBoxPaquetes .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
            ]
            bought = await _try_selectors(page, buy_selectors, timeout=15000)
            if not bought:
                # Fallback: _click_and_navigate con el selector original
                await _click_and_navigate(
                    page,
                    f"div:nth-child(3) > .contBoxPaquetes:nth-child(5) "
                    f".slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                    timeout=20000,
                )
            else:
                # Cuando sí se encuentra el selector por fallback, aún podría existir
                # navegación parcial o recarga AJAX; igual esperamos estabilidad.
                await _safe_wait_networkidle(page)
            await _safe_wait_networkidle(page)
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
