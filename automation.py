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
import time
from typing import Callable, Optional

from playwright.async_api import async_playwright, Page, BrowserContext, Locator, Frame

logger = logging.getLogger("ComprasClaroApp")

# URL de login de Mi Claro Guatemala
CLARO_LOGIN_URL = "https://www.claro.com.gt/miclaro/login"

# Slow motion activo en tiempo de ejecución (en ms), tomado desde config.
# Se usa para que las pausas internas también respeten el valor de la GUI,
# incluso en rutas con evaluate()/click JS que Playwright no ralentiza igual.
_RUNTIME_SLOW_MO_MS = 0


# ── Helpers internos ───────────────────────────────────────────────────────

async def _runtime_pause(min_seconds: float = 0.0) -> None:
    """
    Pausa cooperativa que combina una base mínima con el slow_mo configurado.
    Si slow_mo=0 mantiene el comportamiento previo (solo min_seconds).
    """
    delay = max(float(min_seconds), _RUNTIME_SLOW_MO_MS / 1000.0)
    if delay > 0:
        await asyncio.sleep(delay)

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
                await _runtime_pause(0.25)
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
            .map(option => ({
                value: option.value,
                text: (option.textContent || '').trim()
            }))
            .filter(option => typeof option.value === 'string' && option.value.trim().length > 0)"""
    )
    logger.debug(".selectLine contiene %d option(es) con value utilizable.", len(option_values))

    phone_candidates = [
        option for option in option_values
        if phone_number in option["value"] or phone_number in option["text"]
    ]

    if not phone_candidates:
        raise RuntimeError(
            f"No se encontró la línea {phone_number} dentro del selector .selectLine."
        )

    # Prioriza explícitamente la línea tipo Prepago/Tarjetero (flujo Sentinel).
    preferred_tokens = [
        '"AssociationRoleType":"Prepago/Tarjetero"',
        "prepago/tarjetero",
        '"IsHybrid":"FALSE"',
        '"AssociatedAccountStatus":"Activo"',
    ]
    best_candidate = None
    best_score = -1
    for candidate in phone_candidates:
        haystack = f"{candidate['value']} {candidate['text']}".lower()
        score = sum(1 for token in preferred_tokens if token.lower() in haystack)
        if score > best_score:
            best_candidate = candidate
            best_score = score

    selected_value = best_candidate["value"] if best_candidate else phone_candidates[0]["value"]

    logger.debug("Línea seleccionada para %s: %s", phone_number, selected_value)
    await page.select_option(".selectLine", value=selected_value)

    # Verifica que el value quedó aplicado realmente antes de avanzar.
    selected_value_after = await page.locator(".selectLine").input_value()
    if selected_value_after != selected_value:
        raise RuntimeError(
            "No se pudo confirmar la selección de la línea/tarjeta en .selectLine. "
            f"Esperado: {selected_value}; obtenido: {selected_value_after}"
        )

    await _safe_wait_networkidle(page)


async def _fill_first_visible(page: Page, selectors: list[str], value: str, timeout: int = 5000) -> bool:
    """
    Rellena el primer campo visible encontrado entre varios selectores.
    Devuelve True si logró completar alguno.
    """
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.locator(selector).first.fill(value)
            logger.debug("Campo completado con selector %s", selector)
            return True
        except Exception as exc:
            logger.debug("No se pudo completar selector '%s': %s", selector, exc)
    return False


async def _find_visible_in_frames(page: Page, selectors: list[str], timeout_ms: int = 6000) -> Optional[tuple[Frame, str]]:
    """
    Busca un selector visible en cualquier frame (incluyendo main frame).
    Devuelve (frame, selector) cuando encuentra coincidencia.
    """
    # Usar reloj real evita que el timeout se dispare por número de frames/selectores.
    deadline = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < deadline:
        for frame in page.frames:
            for selector in selectors:
                try:
                    if await frame.locator(selector).first.is_visible(timeout=200):
                        return frame, selector
                except Exception:
                    continue
        await _runtime_pause(0.15)
    return None


async def _fill_first_visible_in_frames(page: Page, selectors: list[str], value: str, timeout_ms: int = 8000) -> bool:
    """
    Rellena un input visible localizado en cualquier frame.
    """
    found = await _find_visible_in_frames(page, selectors, timeout_ms=timeout_ms)
    if not found:
        return False

    frame, selector = found
    await frame.locator(selector).first.fill(value)
    logger.debug("Campo completado en frame con selector %s", selector)
    return True


async def _click_first_visible_in_frames(page: Page, selectors: list[str], timeout_ms: int = 8000) -> bool:
    """
    Hace click en el primer botón/elemento visible encontrado en cualquier frame.
    """
    found = await _find_visible_in_frames(page, selectors, timeout_ms=timeout_ms)
    if not found:
        return False

    frame, selector = found
    try:
        await frame.locator(selector).first.click()
        logger.debug("Click ejecutado en frame con selector %s", selector)
        return True
    except Exception as exc:
        logger.debug("Click normal falló en selector %s: %s", selector, exc)

    # Fallback: click vía JavaScript para casos con overlays/interceptación.
    try:
        clicked = await frame.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                el.click();
                return true;
            }""",
            selector,
        )
        if clicked:
            logger.debug("Click JS ejecutado en frame con selector %s", selector)
            return True
    except Exception as exc:
        logger.debug("Click JS falló en selector %s: %s", selector, exc)

    return False


async def _click_continue_fallback_in_frames(page: Page) -> bool:
    """
    Busca y ejecuta el botón de continuación/confirmación en cualquier frame.
    Útil cuando el DOM no usa botones estándar detectables por selector CSS.
    """
    for frame in page.frames:
        try:
            clicked = await frame.evaluate(
                """() => {
                    const candidates = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a, .btn'));
                    const target = candidates.find(el => {
                        const text = ((el.textContent || '') + ' ' + (el.value || '')).toLowerCase();
                        return text.includes('continuar') || text.includes('siguiente') || text.includes('pagar') || text.includes('finalizar');
                    });
                    if (!target) return false;
                    target.click();
                    return true;
                }"""
            )
            if clicked:
                logger.debug("Click fallback de continuación ejecutado en frame %s", frame.url)
                return True
        except Exception:
            continue
    return False


async def _safe_close_page(page: Optional[Page]) -> None:
    """Cierra la página ignorando errores de recursos ya cerrados."""
    if not page:
        return
    try:
        await page.close()
    except Exception:
        pass


async def _safe_close_context(context: Optional[BrowserContext]) -> None:
    """Cierra el contexto ignorando errores de recursos ya cerrados."""
    if not context:
        return
    try:
        await context.close()
    except Exception:
        pass


async def _safe_close_browser(browser) -> None:
    """Cierra el navegador ignorando errores de recursos ya cerrados."""
    if not browser:
        return
    try:
        await browser.close()
    except Exception:
        pass


async def _stop_watchdog(
    stop_event: Optional[threading.Event],
    page: Optional[Page],
    context: Optional[BrowserContext],
    browser,
    notify: Callable[[str], None],
) -> None:
    """
    Vigila la señal de parada y fuerza cierre de Playwright al detectarla.
    Esto evita que la automatización quede esperando timeouts largos.
    """
    if not stop_event:
        return

    while not stop_event.is_set():
        await asyncio.sleep(0.2)

    notify("Detención solicitada: cerrando Chromium de inmediato...")
    await _safe_close_page(page)
    await _safe_close_context(context)
    await _safe_close_browser(browser)


async def _handle_random_survey(page: Page, notify: Callable[[str], None]) -> None:
    """
    Maneja encuesta aleatoria de Mi Claro (Qualtrics): marcar 10, Siguiente y cerrar.
    No debe romper el flujo si la encuesta no aparece.
    """
    survey_markers = [
        "text=¿Recomendarías el portal Mi Claro",
        "text=Basándote en la gestión",
        "text=Con tecnología de Qualtrics",
    ]

    found = await _find_visible_in_frames(page, survey_markers, timeout_ms=2000)
    if not found:
        return

    frame, _ = found
    notify("Encuesta aleatoria detectada; resolviendo automáticamente...")

    # Resolver encuesta dentro del contenedor del modal para evitar clicks fuera.
    modal_roots = [
        ".QSIWebResponsiveDialog",
        ".QSIWebResponsive",
        "div[role='dialog']",
        "body",
    ]

    score_clicked = False
    for root in modal_roots:
        score_selectors = [
            f"{root} button[aria-label='10']",
            f"{root} [role='button'][aria-label='10']",
            f"{root} button:has-text('10')",
            f"{root} [role='button']:has-text('10')",
            f"{root} label:has-text('10')",
            f"{root} .QSIAnswerChoice:has-text('10')",
        ]
        for selector in score_selectors:
            try:
                await frame.wait_for_selector(selector, state="visible", timeout=350)
                await frame.locator(selector).first.click()
                score_clicked = True
                logger.debug("Encuesta: score 10 marcado con selector %s", selector)
                break
            except Exception:
                continue
        if score_clicked:
            break

    if not score_clicked:
        try:
            # Fallback JS: ubica el texto "10" dentro del modal y clickea su ancestro interactivo.
            score_clicked = bool(await frame.evaluate(
                """() => {
                    const root = document.querySelector('.QSIWebResponsiveDialog, .QSIWebResponsive, [role="dialog"]') || document.body;
                    const nodes = Array.from(root.querySelectorAll('*'));
                    const target = nodes.find(el => (el.textContent || '').trim() === '10');
                    if (!target) return false;

                    const clickable = target.closest('button, label, [role="button"], a, div') || target;
                    ['pointerdown', 'mousedown', 'mouseup', 'click'].forEach(type => {
                        clickable.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                    });
                    return true;
                }"""
            ))
            logger.debug("Encuesta: score 10 por fallback JS = %s", score_clicked)
        except Exception as exc:
            logger.debug("No se pudo marcar score 10 en encuesta: %s", exc)

    if score_clicked:
        await asyncio.sleep(0.2)

    next_clicked = False
    for root in modal_roots:
        next_selectors = [
            f"{root} button:has-text('Siguiente')",
            f"{root} input[value='Siguiente']",
            f"{root} button:has-text('Next')",
            f"{root} input[value='Next']",
        ]
        for selector in next_selectors:
            try:
                await frame.wait_for_selector(selector, state="visible", timeout=350)
                await frame.locator(selector).first.click()
                next_clicked = True
                logger.debug("Encuesta: botón Siguiente con selector %s", selector)
                break
            except Exception:
                continue
        if next_clicked:
            break

    if not next_clicked:
        await _click_first_visible_in_frames(
            page,
            [
                "button:has-text('Siguiente')",
                "input[value='Siguiente']",
                "button:has-text('Next')",
                "input[value='Next']",
            ],
            timeout_ms=2500,
        )

    closed = False
    close_selectors = [
        ".QSIWebResponsiveDialog button[aria-label='Close']",
        ".QSIWebResponsiveDialog button[title='Close']",
        ".QSIWebResponsiveDialog .close",
        ".QSIWebResponsiveDialog button[class*='close']",
        ".QSIWebResponsiveDialog .close-btn",
        "button[aria-label='Close']",
        "button[title='Close']",
        "text=×",
    ]
    for selector in close_selectors:
        try:
            await frame.wait_for_selector(selector, state="visible", timeout=300)
            await frame.locator(selector).first.click()
            closed = True
            logger.debug("Encuesta: modal cerrado con selector %s", selector)
            break
        except Exception:
            continue
    if not closed:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass


async def _buy_package_by_keyword(page: Page, keyword: str) -> bool:
    """
    Intenta comprar paquete buscando una palabra clave visible en la tarjeta.
    Si encuentra la tarjeta, hace click en su botón de compra.
    """
    normalized = keyword.strip().lower()
    if not normalized:
        return False

    cards = page.locator(".contBoxPaquetes .slick-slide")
    count = await cards.count()
    logger.debug("Búsqueda por keyword '%s' en %d tarjeta(s) del carrusel.", normalized, count)

    for idx in range(count):
        card = cards.nth(idx)
        try:
            text = (await card.inner_text(timeout=500) or "").lower()
            if normalized not in text:
                continue

            buy_locator = card.locator(
                "button:has-text('Comprar'), a:has-text('Comprar'), .btn:has-text('Comprar'), .btn:nth-child(1)"
            ).first
            if await buy_locator.count() == 0:
                continue

            logger.debug("Tarjeta coincidente por keyword en índice %d: %s", idx, keyword)
            await _click_locator_and_navigate(page, buy_locator, timeout=20000)
            return True
        except Exception as exc:
            logger.debug("Error evaluando tarjeta %d para keyword '%s': %s", idx, keyword, exc)
            continue

    return False


async def _complete_billing_form(page: Page, config: dict, notify: Callable[[str], None]) -> None:
    """
    Completa el formulario de facturación final si la compra redirige a esa vista.
    El flujo debe seguir aunque la pantalla no aparezca.
    """
    autofill_enabled = bool(config.get("billing_autofill", True))
    billing_name = str(config.get("billing_name", "")).strip()
    billing_nit = str(config.get("billing_nit", "")).strip()
    billing_address = str(config.get("billing_address", "")).strip()
    billing_email = str(config.get("billing_email", "")).strip() or str(config.get("email", "")).strip()

    billing_markers = [
        "input[placeholder*='nombre' i]",
        "input[placeholder*='nit' i]",
        "input[placeholder*='correo' i]",
        "text=Nombre en factura",
        "text=Dirección de facturación",
    ]

    # Esperar de forma robusta porque el formulario puede cargar tarde o en un frame.
    form_found = await _find_visible_in_frames(page, billing_markers, timeout_ms=18000)
    if not form_found:
        logger.debug("Formulario de facturación no detectado; continuando flujo normal.")
        return

    notify("Formulario de facturación detectado; completando datos...")

    if not autofill_enabled:
        raise RuntimeError(
            "Se detectó el formulario de facturación, pero el autocompletado está desactivado en la GUI."
        )

    if not billing_name or not billing_nit:
        raise RuntimeError(
            "Faltan datos obligatorios de facturación (Nombre y NIT) para continuar la compra."
        )

    # Seleccionar la opción de factura por correo si aparece visible.
    invoice_option_selectors = [
        "label:has-text('Deseo recibir mi factura por correo electrónico')",
        "input[type='radio'][value='correo']",
        "input[type='radio']",
    ]
    await _click_first_visible_in_frames(page, invoice_option_selectors, timeout_ms=2000)

    filled_name = await _fill_first_visible_in_frames(
        page,
        ["input[placeholder*='nombre' i]", "input[name*='nombre' i]", "input[id*='nombre' i]"],
        billing_name,
        timeout_ms=8000,
    )
    filled_nit = await _fill_first_visible_in_frames(
        page,
        ["input[placeholder*='NIT' i]", "input[name*='nit' i]", "input[id*='nit' i]"],
        billing_nit,
        timeout_ms=8000,
    )
    filled_address = await _fill_first_visible_in_frames(
        page,
        ["input[placeholder*='dirección' i]", "input[placeholder*='direccion' i]", "input[name*='direccion' i]", "input[id*='direccion' i]"],
        billing_address or "Ciudad de Guatemala",
        timeout_ms=8000,
    )
    filled_email = await _fill_first_visible_in_frames(
        page,
        ["input[placeholder*='correo' i]", "input[name*='correo' i]", "input[id*='correo' i]"],
        billing_email,
        timeout_ms=8000,
    )

    if not (filled_name and filled_nit):
        raise RuntimeError(
            "No se pudieron ubicar los campos obligatorios del formulario de facturación."
        )

    logger.debug(
        "Formulario de facturación completado. name=%s nit=%s address=%s email=%s",
        filled_name,
        filled_nit,
        filled_address,
        filled_email,
    )

    await asyncio.sleep(0.5)

    continue_selectors = [
        "button:has-text('Continuar')",
        "input[value='Continuar']",
        ".btn:has-text('Continuar')",
        ".btnPrimario",
        "button.btnPrimario",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Siguiente')",
        "input[value='Siguiente']",
        "button:has-text('Pagar')",
        "input[value='Pagar']",
        "button:has-text('Finalizar')",
        ".btn:has-text('Pagar')",
    ]
    notify("Enviando formulario de facturación...")
    clicked_continue = await _click_first_visible_in_frames(page, continue_selectors, timeout_ms=12000)
    if not clicked_continue:
        clicked_continue = await _click_continue_fallback_in_frames(page)
    if not clicked_continue:
        raise RuntimeError("No se encontró el botón 'Continuar' del formulario de facturación.")

    await _safe_wait_networkidle(page)


async def _select_payment_method(page: Page, config: dict, notify: Callable[[str], None]) -> None:
    """
    Selecciona explícitamente el método de pago (tarjeta/saldo) si esa vista aparece.
    Mantiene compatibilidad: si el selector no existe, continúa sin romper flujo.
    """
    payment_method = str(config.get("payment_method", "tarjeta")).strip().lower()
    if payment_method not in {"tarjeta", "saldo"}:
        payment_method = "tarjeta"

    target_words = ["tarjeta", "card", "credito", "débito", "debito"] if payment_method == "tarjeta" else ["saldo", "balance"]
    notify(f"Validando método de pago: {payment_method}...")

    selectors = [
        "input[type='radio'][value*='tarjeta' i]" if payment_method == "tarjeta" else "input[type='radio'][value*='saldo' i]",
        "label:has-text('Tarjeta')" if payment_method == "tarjeta" else "label:has-text('Saldo')",
        "button:has-text('Tarjeta')" if payment_method == "tarjeta" else "button:has-text('Saldo')",
        "[class*='tarjeta']" if payment_method == "tarjeta" else "[class*='saldo']",
    ]

    clicked = await _click_first_visible_in_frames(page, selectors, timeout_ms=4000)
    if clicked:
        await _safe_wait_networkidle(page, timeout=6000)
        return

    # Fallback por texto visible dentro de cualquier frame.
    for frame in page.frames:
        try:
            found = await frame.evaluate(
                """(words) => {
                    const candidates = Array.from(document.querySelectorAll('label, button, a, div, span, input[type="radio"]'));
                    const norm = (txt) => (txt || '').toLowerCase();
                    const target = candidates.find(el => {
                        const text = norm(el.textContent) + ' ' + norm(el.getAttribute('value')) + ' ' + norm(el.getAttribute('aria-label'));
                        return words.some(w => text.includes(w));
                    });
                    if (!target) return false;

                    const clickable = target.closest('label, button, a, [role="button"], div') || target;
                    clickable.click();
                    return true;
                }""",
                target_words,
            )
            if found:
                logger.debug("Método de pago '%s' seleccionado por fallback en frame %s", payment_method, frame.url)
                await _safe_wait_networkidle(page, timeout=6000)
                return
        except Exception:
            continue

    logger.debug("No se encontró selector de método de pago '%s'; se continúa con el flujo actual.", payment_method)


async def _select_saved_card_and_continue(page: Page, notify: Callable[[str], None]) -> None:
    """
    Atiende la pantalla intermedia de checkout: "Selecciona tu tarjeta".
    Selecciona la primera tarjeta disponible y luego pulsa "Continuar".
    """
    card_screen_markers = [
        "text=Selecciona tu tarjeta",
        "text=Selecciona la tarjeta",
        "text=Seleccionar tarjeta",
        "text=Elige tu tarjeta",
        "text=Choose your card",
    ]

    found = await _find_visible_in_frames(page, card_screen_markers, timeout_ms=9000)
    if not found:
        # Fallback: algunos flujos muestran solo el dropdown sin el texto exacto.
        probable_card_dropdown = False
        for frame in page.frames:
            try:
                probable_card_dropdown = bool(await frame.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const st = window.getComputedStyle(el);
                            return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
                        };
                        const nodes = Array.from(document.querySelectorAll('select, [role="combobox"], .ng-select, .select2, .dropdown, .mat-select'));
                        return nodes.some(el => {
                            if (!visible(el)) return false;
                            const txt = ((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('placeholder') || '')).toLowerCase();
                            return txt.includes('tarjeta') || txt.includes('card');
                        });
                    }"""
                ))
                if probable_card_dropdown:
                    break
            except Exception:
                continue

        if not probable_card_dropdown:
            logger.debug("Pantalla de selección de tarjeta no detectada; continuando.")
            return

    notify("Pantalla de tarjeta detectada; seleccionando tarjeta guardada...")

    # Intento 1: select nativo con options, pero solo en contexto de tarjeta.
    selected = False
    for frame in page.frames:
        try:
            selected = bool(await frame.evaluate(
                """() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const st = window.getComputedStyle(el);
                        return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
                    };

                    const hasCardContext = (el) => {
                        const selfText = ((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('placeholder') || '')).toLowerCase();
                        const attrs = ((el.id || '') + ' ' + (el.className || '') + ' ' + (el.getAttribute('name') || '')).toLowerCase();
                        if (selfText.includes('tarjeta') || selfText.includes('card')) return true;
                        if (attrs.includes('tarjeta') || attrs.includes('card')) return true;

                        const container = el.closest('section, form, div, article, fieldset, [role="dialog"]');
                        const containerText = (container?.textContent || '').toLowerCase();
                        return containerText.includes('tarjeta') || containerText.includes('card');
                    };

                    const selects = Array.from(document.querySelectorAll('select')).filter(el => visible(el) && hasCardContext(el));
                    for (const sel of selects) {
                        const options = Array.from(sel.options || []);
                        const valid = options.find(opt => {
                            const txt = (opt.textContent || '').trim().toLowerCase();
                            const placeholder = !txt || txt.includes('selecciona') || txt.includes('elige') || txt.includes('escoge') || txt.includes('select');
                            return !opt.disabled && !!opt.value && !placeholder;
                        });
                        if (!valid) continue;

                        sel.value = valid.value;
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }
                    return false;
                }"""
            ))
            if selected:
                logger.debug("Tarjeta seleccionada en select nativo en frame %s", frame.url)
                break
        except Exception:
            continue

    # Intento 2: dropdown custom (placeholder + opciones en overlay/lista).
    if not selected:
        for frame in page.frames:
            try:
                selected = bool(await frame.evaluate(
                    """() => {
                        const visible = (el) => {
                            if (!el) return false;
                            const st = window.getComputedStyle(el);
                            return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
                        };
                        const norm = (v) => (v || '').toLowerCase().trim();
                        const isPlaceholder = (txt) => {
                            const t = norm(txt);
                            return !t || t.includes('selecciona') || t.includes('elige') || t.includes('escoge') || t === '--' || t.includes('select');
                        };

                        const triggers = Array.from(document.querySelectorAll(
                            "[role='combobox'], .ng-select-container, .select2-selection, .mat-select-trigger, button, div, span"
                        )).filter(el => {
                            if (!visible(el)) return false;
                            const txt = norm(el.textContent) + ' ' + norm(el.getAttribute('aria-label')) + ' ' + norm(el.getAttribute('placeholder'));
                            return txt.includes('tarjeta') || txt.includes('card') || txt.includes('selecciona');
                        });

                        if (triggers.length > 0) {
                            triggers[0].click();
                        }

                        const optionSelectors = [
                            "[role='option']",
                            ".ng-option",
                            ".select2-results__option",
                            ".mat-option",
                            "div[role='listbox'] div",
                            "li",
                            ".dropdown-item",
                        ];

                        for (const sel of optionSelectors) {
                            const options = Array.from(document.querySelectorAll(sel)).filter(visible);
                            for (const opt of options) {
                                const txt = norm(opt.textContent) + ' ' + norm(opt.getAttribute('aria-label'));
                                const disabled = opt.hasAttribute('disabled') || opt.getAttribute('aria-disabled') === 'true' || opt.classList.contains('disabled');
                                if (disabled || isPlaceholder(txt)) continue;
                                opt.click();
                                return true;
                            }
                        }

                        return false;
                    }"""
                ))
                if selected:
                    logger.debug("Tarjeta seleccionada en dropdown custom en frame %s", frame.url)
                    break
            except Exception:
                continue

    if not selected:
        logger.debug("No se logró seleccionar tarjeta automáticamente en esta vista.")

    # Con tarjeta elegida (o si ya venía elegida), intentar continuar.
    continue_selectors = [
        "button:has-text('Continuar')",
        "input[value='Continuar']",
        ".btn:has-text('Continuar')",
        ".btnPrimario",
        "button.btnPrimario",
    ]
    clicked_continue = await _click_first_visible_in_frames(page, continue_selectors, timeout_ms=7000)
    if clicked_continue:
        notify("Tarjeta seleccionada; continuando checkout...")
        await _safe_wait_networkidle(page, timeout=8000)
    else:
        logger.debug("Botón Continuar de selección de tarjeta no encontrado en esta vista.")


async def _complete_cvv_step(page: Page, config: dict, notify: Callable[[str], None]) -> None:
    """
    Completa el CVV cuando el sitio lo solicita para confirmar pago con tarjeta guardada.
    Puede aparecer después de facturación y en algunos casos dentro de un iframe.
    """
    cvv = str(config.get("billing_cvv", "")).strip()

    cvv_selectors = [
        "input[placeholder*='CVV' i]",
        "input[name*='cvv' i]",
        "input[id*='cvv' i]",
        "input[autocomplete='cc-csc']",
        "input[maxlength='3'][type='password']",
        "input[maxlength='4'][type='password']",
        "input[maxlength='3'][type='tel']",
        "input[maxlength='4'][type='tel']",
    ]

    cvv_found = await _find_visible_in_frames(page, cvv_selectors, timeout_ms=20000)
    if not cvv_found:
        logger.debug("Paso CVV no detectado; continuando flujo normal.")
        return

    if not cvv:
        raise RuntimeError("Se detectó solicitud de CVV, pero el campo CVV está vacío en la GUI.")

    notify("Paso CVV detectado; completando seguridad de tarjeta...")
    filled_cvv = await _fill_first_visible_in_frames(page, cvv_selectors, cvv, timeout_ms=10000)
    if not filled_cvv:
        raise RuntimeError("No se pudo completar el campo CVV en el sitio.")

    confirm_selectors = [
        "button:has-text('Pagar')",
        "button:has-text('Confirmar')",
        "button:has-text('Continuar')",
        "input[value='Pagar']",
        "input[value='Confirmar']",
        ".btn:has-text('Pagar')",
        ".btn:has-text('Confirmar')",
    ]
    clicked_confirm = await _click_first_visible_in_frames(page, confirm_selectors, timeout_ms=12000)
    if not clicked_confirm:
        logger.debug("No se encontró botón de confirmación tras CVV; esperando estabilización.")

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
        await _runtime_pause(0.5)
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
        await _runtime_pause(0.5)
        return

    # ── Prioridad 3: Escape + JS hide (solo si el modal existe pero no respondió) ──
    await page.keyboard.press("Escape")
    await _runtime_pause(0.4)
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
    try:
        slow_mo = int(config.get("slow_mo", 0))
    except (TypeError, ValueError):
        slow_mo = 0
    # Normalizar a un rango seguro para evitar valores negativos o extremos.
    slow_mo = max(0, min(slow_mo, 5000))
    payment_method = str(config.get("payment_method", "tarjeta")).strip().lower()

    # Exponer slow_mo a helpers internos para pausas consistentes.
    global _RUNTIME_SLOW_MO_MS
    _RUNTIME_SLOW_MO_MS = slow_mo

    # Solo carrusel 3 es relevante en este flujo
    c3_clicks     = int(config.get("carousel3_next_clicks", 4))
    c3_slide      = int(config.get("target_package_slide", config.get("carousel3_slide", 13)))
    package_keyword = str(config.get("target_package_keyword", "")).strip()

    async with async_playwright() as playwright:

        # ── Lanzar Chromium ────────────────────────────────────────────────
        notify(f"Iniciando navegador Chromium (slow_mo={slow_mo}ms)...")
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
        )

        # Viewport fijo igual al grabado con Sentinel
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1696, "height": 784},
        )

        page: Optional[Page] = None
        watchdog_task: Optional[asyncio.Task] = None

        try:
            page = await context.new_page()

            # Watchdog dedicado para cierre inmediato al presionar "Detener".
            watchdog_task = asyncio.create_task(
                _stop_watchdog(stop_event, page, context, browser, notify)
            )

            # ── 1. Página de login ─────────────────────────────────────────
            _check_stop(stop_event)
            notify("Navegando a Mi Claro Guatemala...")
            await page.goto(CLARO_LOGIN_URL, wait_until="domcontentloaded")

            # Pausa breve para que el JS del sitio (SweetAlert, etc.) se inicialice
            await _runtime_pause(1)

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
            await _handle_random_survey(page, notify)

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
            await _handle_random_survey(page, notify)

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
            await _handle_random_survey(page, notify)
            await asyncio.sleep(0.3)

            # ── 4. Selección de línea en el combo .selectLine ──────────────
            _check_stop(stop_event)
            notify(f"Seleccionando línea {phone_number}...")
            await _select_phone_line(page, phone_number, timeout=15000)
            logger.debug("Selección de línea completada para %s.", phone_number)
            await _handle_random_survey(page, notify)

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
                await _handle_random_survey(page, notify)
                clicked = await _try_selectors(page, slick_next_selectors, timeout=10000)
                if not clicked:
                    logger.warning("No se encontró .slick-next para avanzar carrusel")
                await _runtime_pause(0.3)

            # ── 6. Comprar paquete en el carrusel ─────────────────────────
            # Hace clic en el botón "Comprar" del paquete en la posición c3_slide.
            # El índice nth-child es configurable desde la GUI.
            _check_stop(stop_event)
            bought = False
            if package_keyword:
                notify(f"Buscando paquete por texto '{package_keyword}'...")
                bought = await _buy_package_by_keyword(page, package_keyword)

            if not bought:
                notify(f"Comprando paquete por posición {c3_slide}...")
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
            await _handle_random_survey(page, notify)
            await _safe_wait_networkidle(page)
            await _safe_wait_networkidle(page)

            # ── 6.1 Seleccionar método de pago explícito si la vista lo requiere ─
            _check_stop(stop_event)
            config_with_payment = dict(config)
            config_with_payment["payment_method"] = payment_method
            await _select_payment_method(page, config_with_payment, notify)
            await _handle_random_survey(page, notify)

            # ── 6.2 Seleccionar tarjeta guardada y continuar checkout ────────
            _check_stop(stop_event)
            await _select_saved_card_and_continue(page, notify)
            await _handle_random_survey(page, notify)

            # ── 7. Completar formulario de facturación si aparece ──────────
            _check_stop(stop_event)
            await _complete_billing_form(page, config, notify)
            await _handle_random_survey(page, notify)

            # ── 8. Completar CVV si el sitio lo solicita ───────────────────
            _check_stop(stop_event)
            await _complete_cvv_step(page, config, notify)
            await _handle_random_survey(page, notify)

            # ── 9. Scrolls finales (igual que Sentinel actualizado) ────────
            await page.mouse.wheel(0, 432)
            await page.mouse.wheel(0, -324)

            notify("✅ Proceso de compra completado exitosamente.")

            # Pausa para que el estado final sea visible si headless=False
            await _runtime_pause(2)

        except RuntimeError as exc:
            # Error controlado: el usuario detuvo la automatización
            if "stopped by user" in str(exc):
                notify("⏹ Proceso detenido por el usuario.")
                raise
            logger.error("Error en la automatización: %s", exc, exc_info=True)
            notify(f"❌ Error: {exc}")
            raise

        except Exception as exc:
            # Si hubo señal de parada, tratar cierres abruptos de Playwright como detención normal.
            if stop_event and stop_event.is_set():
                notify("⏹ Proceso detenido por el usuario.")
                raise RuntimeError("stopped by user") from exc
            logger.error("Error inesperado en la automatización: %s", exc, exc_info=True)
            notify(f"❌ Error inesperado: {exc}")
            raise

        finally:
            if watchdog_task:
                watchdog_task.cancel()
                try:
                    await watchdog_task
                except Exception:
                    pass

            # Siempre cerrar el navegador, incluso si hubo error
            await _safe_close_page(page)
            await _safe_close_context(context)
            await _safe_close_browser(browser)
            notify("Navegador cerrado.")
