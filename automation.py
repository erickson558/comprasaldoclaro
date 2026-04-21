# ─────────────────────────────────────────────────────────────────────────────
# automation.py  –  Automatización de compra de paquetes en Mi Claro (GT)
# Flujo actualizado a partir de la grabación más reciente de Deploy Sentinel.
# Usa el menú de escritorio "Gestiones > Paquetes y recargas".
# Selecciona la línea objetivo en .selectLine y compra desde el carrusel 3.
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
        logger.debug("Click exitoso en selector opcional: %s", selector)
        return True
    except Exception as exc:
        logger.debug("No se pudo hacer click en selector opcional '%s': %s", selector, exc)
        return False


async def _try_selectors(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """
    Itera una lista de selectores y hace clic en el primero que encuentre.
    Devuelve True si alguno funcionó. Útil para el botón "Continuar" con
    múltiples posibles selectores.
    """
    logger.debug("Probando %d selector(es): %s", len(selectors), selectors)
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


async def _is_selector_visible(page: Page, selector: str, timeout: int = 2500) -> bool:
    """
    Verifica visibilidad de un selector sin romper el flujo si no aparece.
    """
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def _is_execution_context_destroyed(exc: Exception) -> bool:
    """
    Detecta errores transitorios de Playwright cuando la página navega y el
    contexto JavaScript se reinicia.
    """
    msg = str(exc)
    return (
        "Execution context was destroyed" in msg
        or "Cannot find context with specified id" in msg
    )


async def _safe_page_evaluate(page: Page, script: str, retries: int = 1):
    """
    Ejecuta page.evaluate con reintento cuando hay navegación en curso.
    Si el contexto sigue inestable tras los reintentos, devuelve None para que
    el llamador continúe sin romper el flujo.
    """
    for attempt in range(retries + 1):
        try:
            return await page.evaluate(script)
        except Exception as exc:
            if not _is_execution_context_destroyed(exc):
                raise

            if attempt < retries:
                logger.debug(
                    "Execution context destruido durante evaluate; reintentando (%d/%d).",
                    attempt + 1,
                    retries,
                )
                await asyncio.sleep(0.25)
                await _safe_wait_networkidle(page, timeout=5000)
                continue

            logger.debug("Se omite evaluate por navegación en curso: %s", exc)
            return None


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


async def _select_phone_line(page: Page, phone_number: str, timeout: int = 15000) -> None:
    """
    Selecciona en .selectLine la opción cuyo value contiene el número deseado.
    El sitio serializa la línea como JSON en el atributo value del <option>.
    """
    await page.wait_for_selector(".selectLine", state="visible", timeout=timeout)
    logger.debug("Selector .selectLine visible; buscando número %s", phone_number)

    option_values = await page.locator(".selectLine option").evaluate_all(
        """options => options
            .map(option => option.value)
            .filter(value => typeof value === 'string' && value.trim().length > 0)"""
    )
    logger.debug(".selectLine contiene %d option(es) con value utilizable.", len(option_values))

    selected_value = next(
        (value for value in option_values if phone_number in value),
        None,
    )

    if not selected_value:
        raise RuntimeError(
            f"No se encontró la línea {phone_number} dentro del selector .selectLine."
        )

    logger.debug("Línea seleccionada para %s: %s", phone_number, selected_value)
    await page.select_option(".selectLine", value=selected_value)
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
    modal_present = await _safe_page_evaluate(
        page,
        "() => !!document.querySelector('.btnBlancoRojo, #Modal, .renovationFavoriteModal')"
    )
    # Si no se pudo evaluar por navegación transitoria, no romper el flujo.
    if modal_present is None:
        return

    if not modal_present:
        return

    logger.debug("Modal detectado en DOM; intentando cerrarlo...")

    # ── Prioridad 1: JS click directo en .btnBlancoRojo ───────────────────────
    # El overlay .blur tiene z-index superior → page.click() falla porque
    # Playwright verifica interceptación de puntero. element.click() en JS
    # bypasea esa verificación y dispara el evento directo en el nodo DOM.
    clicked = await _safe_page_evaluate(page, """() => {
        const btn = document.querySelector('.btnBlancoRojo');
        if (btn) { btn.click(); return true; }
        return false;
    }""")
    if clicked is None:
        return

    if clicked:
        logger.debug("Modal cerrado con JS click en .btnBlancoRojo")
        await asyncio.sleep(0.5)
        return

    # ── Prioridad 2: JS click en cualquier botón del modal por texto ──────────
    clicked = await _safe_page_evaluate(page, """() => {
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
    if clicked is None:
        return

    if clicked:
        logger.debug("Modal cerrado con JS click por texto")
        await asyncio.sleep(0.5)
        return

    # ── Prioridad 3: Escape + JS hide (solo si el modal existe pero no respondió) ──
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.4)
    hidden = await _safe_page_evaluate(page, """() => {
        const hide = (el) => {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.pointerEvents = 'none';
        };
        const modal = document.getElementById('Modal');
        if (modal) hide(modal);
        document.querySelectorAll('.blur, .renovationFavoriteModal').forEach(hide);
        return true;
    }""")
    if hidden is None:
        return

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
            already_logged = await _is_selector_visible(page, ".menu_header_gestiones", timeout=2500)

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

                # Click en el botón de login.
                # Primero intenta el selector exacto de Sentinel (.btnPrimario).
                # Si el sitio cambia ligeramente el DOM, usa fallbacks compatibles.
                notify("Enviando formulario de login...")
                login_submit_selectors = [
                    ".btnPrimario",              # Selector principal Sentinel
                    "button.btnPrimario",        # Variante común en botón
                    "button[type='submit']",     # Fallback HTML estándar
                    "input[type='submit']",      # Fallback HTML estándar
                ]

                submitted = False
                for sel in login_submit_selectors:
                    try:
                        if await page.locator(sel).count() == 0:
                            continue
                        await _click_and_navigate(page, sel, timeout=15000)
                        submitted = True
                        break
                    except Exception as exc:
                        logger.debug("Falló envío de login con '%s': %s", sel, exc)
                        await _dismiss_modal(page)

                if not submitted:
                    # Verificación final: algunos escenarios redirigen automáticamente
                    # y ocultan el botón de login aunque la sesión ya esté activa.
                    await _safe_wait_networkidle(page, timeout=5000)
                    if await _is_selector_visible(page, ".menu_header_gestiones", timeout=2500):
                        notify("Sesión activa detectada tras validar envío de login; continuando...")
                    else:
                        raise RuntimeError(
                            "No se encontró botón de login (.btnPrimario) ni alternativas. "
                            "Valida si Mi Claro cambió el formulario de acceso."
                        )

            await _safe_wait_networkidle(page)

            # Cierre preventivo del modal inmediatamente después de login/sesión activa.
            # Este modal aparece de forma intermitente y puede bloquear todo el menú.
            _check_stop(stop_event)
            await _dismiss_modal(page)

            # ── 3. Navegar a Gestiones → Paquetes y recargas ──────────────
            # Flujo Sentinel actualizado: abrir Gestiones, expandir la opción
            # Compras y entrar en "Paquetes y recargas".
            _check_stop(stop_event)
            notify("Abriendo menú Gestiones...")
            await page.click(".menu_header_gestiones > label")
            logger.debug("Menú Gestiones abierto.")

            notify("Expandiendo menú Compras...")
            await page.click(".hideOnDesk:nth-child(3) .ico-chevron-down")
            logger.debug("Submenú Compras expandido.")

            notify("Abriendo Paquetes y recargas...")
            await _click_and_navigate(page, ".subRoutes a", timeout=20000)

            # Descartar modal de renovación si aparece al entrar en la vista.
            await _dismiss_modal(page)
            await asyncio.sleep(0.3)

            # ── 4. Selección de línea en el combo .selectLine ──────────────
            _check_stop(stop_event)
            notify(f"Seleccionando línea {phone_number}...")
            await _select_phone_line(page, phone_number, timeout=15000)
            logger.debug("Selección de línea completada para %s.", phone_number)

            # Scroll del Sentinel para posicionarse sobre el carrusel.
            await page.mouse.wheel(0, 648)
            logger.debug("Scroll hacia carrusel completado (Y=648).")

            # ── 5. Navegar Carrusel 3 (Tarjeta) ───────────────────────────
            # El flujo actualizado entra directo al carrusel luego de elegir línea.
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

            # ── 6. Comprar paquete en el carrusel ─────────────────────────
            # Hace clic en el botón "Comprar" del paquete en la posición c3_slide.
            # El índice nth-child es configurable desde la GUI.
            _check_stop(stop_event)
            notify(f"Comprando paquete (posición {c3_slide})...")
            logger.debug("Intentando compra con posición de slide %d.", c3_slide)
            buy_selectors = [
                f"div:nth-child(3) > .contBoxPaquetes:nth-child(5) .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".contBoxPaquetes:nth-child(5) .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".contBoxPaquetes .slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
                f".slick-slide:nth-child({c3_slide}) .btn:nth-child(1)",
            ]
            bought = await _try_selectors(page, buy_selectors, timeout=15000)
            if not bought:
                # Fallback: _click_and_navigate con el selector original
                logger.debug("Compra no encontrada por _try_selectors; usando fallback con navegación.")
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

            # ── 7. Scrolls finales (igual que Sentinel actualizado) ────────
            await page.mouse.wheel(0, 432)
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
