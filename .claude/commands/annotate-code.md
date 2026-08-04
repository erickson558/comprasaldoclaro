# Annotate Code -- Compra Saldo Claro GT

Agrega docstrings y comentarios inline a los modulos Python del proyecto. El objetivo es que el usuario (no necesariamente programador de profesion) pueda entender **que hace cada parte del codigo**, sin depender de leer el historial de git ni preguntar de nuevo.

A diferencia de la convencion general de "solo comentar el POR QUE, nunca el QUE" -- este skill existe especificamente porque el usuario pidio explicitamente entender que hace cada parte, asi que aqui SI se documenta el QUE ademas del POR QUE, con moderacion (sin caer en un comentario por cada linea trivial).

## Argumento opcional
Nombre del modulo a anotar (default: todos los modulos principales). Ej: `automation.py` o `all` (default)

## Alcance por modulo

| Modulo | Que anotar |
|--------|-----------|
| `automation.py` | Cada funcion (que hace + por que existe si no es obvio); bloques JS de `page.evaluate` (que busca en el DOM y por que esa estrategia); la cadena de fallback de `_dismiss_modal`; el flujo completo de `run_automation` con comentarios de seccion (ya tiene "── N. Paso ──" -- mantener ese estilo) |
| `gui.py` | Ciclo de vida GUI <-> hilo de automatizacion (`queue.Queue` + polling), construccion de widgets por pestaña, manejo de cierre/countdown |
| `config_manager.py` | Estrategia de merge con defaults, manejo de corrupcion |
| `i18n.py` | Estructura del catalogo, logica de fallback de `get_text` |
| `log_setup.py` | Configuracion de `RotatingFileHandler` |
| `main.py` | Verificacion de dependencias al arrancar |

## Reglas de anotacion

1. **Docstrings**: formato triple-quote. Primera linea: que hace la funcion (<=80 chars). Parrafo adicional si tiene restricciones/invariantes no obvios (ej. "debe llamarse antes de X", "asume que Y ya ocurrio").
2. **Comentarios inline**: uno por bloque logico no trivial (no linea por linea). Explicar que hace el bloque Y por que se hizo asi cuando la razon no sea evidente (ej. por que un selector tiene fallback, por que hay un `await asyncio.sleep(0.3)` especifico).
3. **Bloques JS** (`page.evaluate(...)`): comentar que elemento(s) del DOM busca y por que esa estrategia (ej. "bypasea el overlay .blur que intercepta page.click()").
4. **NO comentar**: imports, getters/setters triviales, asignaciones auto-descriptivas de una variable con nombre claro.
5. **Idioma**: español (coherente con el resto del proyecto).
6. **Preservar** los comentarios `FIX V0.x.x` / referencias a version existentes -- documentan decisiones historicas, no se deben borrar ni reemplazar, solo complementar si falta contexto.

## Pasos

1. Leer el modulo objetivo completo
2. Identificar funciones sin docstring o con logica no obvia sin comentar
3. Agregar docstrings y comentarios respetando las reglas anteriores
4. Verificar sintaxis: `python -m py_compile <ruta>`
5. Reportar: cuantas funciones documentadas, cuantos comentarios agregados

## Flujo Post-Anotacion
1. `/bump-version patch` -- comentarios/docs no ameritan minor, pero si se quiere dejar rastro de version usar patch
2. `/build-exe` -- compilar con los cambios (la documentacion no cambia el comportamiento, pero confirma que sigue compilando)
3. `/github-push` -- subir a GitHub

## Notas
- NO refactorizar codigo al anotar -- solo agregar texto explicativo
- NO agregar type hints si no existen ya en esa funcion (fuera de alcance de este skill)
- NO tocar la logica de `run_automation` -- es el flujo que realiza compras reales; cualquier cambio de comportamiento (no solo comentarios) debe pasar por `/python-maestro`, no por este skill
