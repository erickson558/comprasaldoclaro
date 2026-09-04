# Skill: /diagnose-automation — Diagnostico de la Automatizacion de Compra

> **Alcance:** este skill audita `automation.py` (el flujo de compra Playwright) y la integracion con `gui.py` (hilo de fondo, notificacion de estado). NO ejecuta el flujo real de compra (eso gastaria dinero real) — es analisis estatico de codigo + revision de `log.txt`.

## Cuando usar esta skill

- El usuario reporta "la automatizacion no termina", "se queda colgada", "no hace la compra"
- El usuario reporta que el bot dice "compra completada" pero el navegador se quedo visualmente en el formulario de facturacion (falso exito — ver FIX V0.7.6)
- Se va a compilar un release y se quiere confirmar que los patrones de confiabilidad conocidos siguen aplicados
- Se agrego un paso nuevo al flujo de compra y se quiere verificar que sigue los mismos patrones que el resto del codigo
- Antes de cerrar un reporte de bug sobre el navegador quedandose abierto o la GUI quedandose "pegada"

---

## Lo que hace esta skill

1. **Diagnostico de codigo** — revisa `automation.py` y `gui.py` en busca de los patrones de confiabilidad documentados en `.claude/specs/feature-specs.md` y `.claude/agents/python-desktop-engineer.md`.
2. **Revision de logs** — si existe `log.txt` en el directorio raiz, escanea las ultimas ~200 lineas buscando: `TargetClosedError`, `Error inesperado`, `Timeout`, `no respondió` (los warnings del cierre acotado V0.7.4), `Execution context was destroyed`.
3. **Reporte de salud** con checklist ✅/❌ y recomendacion.

## Instrucciones para el agente

### Archivos a revisar

1. `version.py` — ¿es >= 0.7.4? (version donde se introdujo el cierre acotado de Playwright)
2. `automation.py`:
   - ¿`_safe_close_page`, `_safe_close_context`, `_safe_close_browser` envuelven su `.close()` en `asyncio.wait_for(..., timeout=_CLOSE_TIMEOUT_SECONDS)`? (FIX V0.7.4 — sin esto, un Chromium no-responsivo cuelga la app para siempre)
   - ¿el `await watchdog_task` en el `finally` de `run_automation` tambien esta acotado con timeout?
   - ¿`browser.new_context()` esta envuelto en try/except que cierra el `browser` si falla? (evita huerfanos)
   - ¿`_dismiss_modal` detecta el modal via `document.querySelector` (no `is_visible()`)? (FIX V0.1.4)
   - ¿`_safe_page_evaluate` reintenta ante `Execution context was destroyed`? (FIX V0.1.8)
   - ¿`_stop_watchdog` cierra Chromium de inmediato al detectar `stop_event`, sin esperar el timeout del paso en curso? (FIX V0.3.1)
   - ¿`_install_local_chromium` evita `sys.executable -m playwright` cuando `sys.frozen`? (FIX V0.7.2 — evita bucle de reapertura del `.exe`)
   - ¿toda espera de Playwright nueva (`wait_for_selector`, `page.click`, `wait_for_function`) declara `timeout` explicito?
   - ¿`_complete_billing_form` verifica con `_wait_screen_transition` que el formulario desaparecio O que la pantalla de tarjeta ya aparecio tras el clic en "Continuar", lanzando `RuntimeError` si ninguna se cumple dentro del timeout? (FIX V0.7.6/V0.7.7/V0.7.8 — sin esto, una validacion rechazada por el sitio deja la pagina en el formulario de facturacion mientras el bot notifica exito falso)
   - ¿esa verificacion sondea ambas condiciones en un mismo ciclo (sin encadenar dos esperas fijas independientes) y usa un timeout generoso (>=20s) como techo de seguridad, no como espera fija? (FIX V0.7.8 — un timeout corto o una espera fija encadenada produce falso negativo en PCs/conexiones mas lentas, abortando una compra que si habia avanzado)
3. `gui.py`:
   - ¿`_automation_thread_worker` pone `("done", "")` en `msg_queue` SIEMPRE en su `finally`, sin importar el tipo de excepcion?
   - ¿`asyncio.CancelledError` se captura explicitamente (hereda de `BaseException`, no de `Exception`)? (FIX V0.6.1)
4. `log.txt` (si existe) — buscar en las ultimas ~200 lineas: `TargetClosedError`, `Error inesperado`, `no respondió` (nuevos warnings V0.7.4), timestamps sin un "Navegador cerrado"/"Aplicación cerrada" posterior cercano (indicio de corrida que no termino limpiamente). Ademas, sospechar de falso exito (V0.7.6) si una corrida llega a `"✅ Proceso de compra completado exitosamente."` sin que aparezcan antes lineas de "Tarjeta seleccionada" NI "Paso CVV detectado" junto con "no detectada"/"no detectado" en los pasos de tarjeta/CVV — indica que el flujo salto esas pantallas condicionales porque nunca salio del formulario de facturacion.

### Formato del reporte

```
## Reporte de Salud — Compra Saldo Claro GT

**Version:** X.Y.Z  [✅ >=0.7.4 | ⚠️ <0.7.4 — aplicar fix de cierre acotado]

### Checks de código
| # | Check | Estado |
|---|-------|--------|
| 1 | Cierre de page/context/browser acotado con timeout (V0.7.4) | ✅ / ❌ |
| 2 | new_context() cierra browser huérfano si falla | ✅ / ❌ |
| 3 | _dismiss_modal usa querySelector, no is_visible() | ✅ / ❌ |
| 4 | _safe_page_evaluate reintenta ante contexto destruido | ✅ / ❌ |
| 5 | _stop_watchdog cierra de inmediato al detectar stop_event | ✅ / ❌ |
| 6 | Instalación de Chromium evita relanzar el .exe en modo frozen | ✅ / ❌ |
| 7 | gui.py siempre notifica "done" (incluye CancelledError) | ✅ / ❌ |
| 8 | _complete_billing_form verifica avance real tras "Continuar" (V0.7.6/V0.7.7) | ✅ / ❌ |
| 9 | Esa verificacion sondea todas sus condiciones en un mismo ciclo con techo generoso, sin esperas fijas encadenadas (V0.7.8) | ✅ / ❌ |

### Errores recientes en logs
[Extracto de log.txt o "Sin log disponible"]

### Recomendación
[Nada que corregir / acción sugerida con skill a ejecutar]
```

### Accion correctiva si se detectan problemas

Si algun check falla, describe exactamente que cambiar (archivo + funcion) y sugiere ejecutar en orden:

```
/python-maestro <descripcion del problema>   # análisis + fix siguiendo Fases 1-6
/build-exe                                    # recompilar .exe local
/github-push                                  # subir cambios (dispara release.yml)
```
