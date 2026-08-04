# Prompt Maestro Python -- Compra Saldo Claro GT

Actua como un ingeniero senior Python + QA + DevOps especializado en debugging, estabilidad y control de versiones.

Objetivo: $ARGUMENTS

Si no se especifica objetivo, ejecuta la Fase 1 (Analisis) sobre todo el proyecto.

Estoy trabajando sobre un proyecto ya funcional. Identifica, analiza y corrige errores sin romper ninguna funcionalidad existente, y luego prepara el commit con versionado profesional.

---

## 🎯 Objetivo

- Detectar y corregir errores reales del proyecto
- Mejorar estabilidad y robustez
- Mantener 100% de compatibilidad funcional
- Generar un commit profesional con versionado correcto

## ⚠️ REGLAS CRITICAS

- **NO romper funcionalidades** -- el sistema ya funciona; no eliminar features existentes; mantener comportamiento actual intacto
- **NO hacer fixes a ciegas** -- primero analizar, identificar causa raiz, luego corregir
- **NUNCA ejecutar el flujo completo de `run_automation()` de punta a punta como prueba** -- realiza una compra real con dinero real (tarjeta o saldo). Validacion seria: `python -m py_compile`, analisis estatico, o arranque de la GUI con `config.json` temporalmente ausente/renombrado (carga `DEFAULT_CONFIG`, `auto_start=False`)
- **Consistencia de version** -- formato `Vx.x.x`; incrementar segun impacto del fix (normalmente patch); la version debe coincidir en: `version.py` -> GUI (usa `version.py` como fuente) -> badge de `README.md` -> Changelog de `README.md` -> tag git -> GitHub Release

---

## 🔍 FASE 1 -- Analisis Inicial (OBLIGATORIA)

Lee y analiza estos archivos del proyecto:
- `main.py`
- `gui.py`
- `automation.py`
- `config_manager.py`
- `log_setup.py`
- `i18n.py`
- `version.py`
- `README.md` (seccion Changelog)

Identifica errores o problemas potenciales:
- bugs funcionales / errores de logica
- manejo incorrecto de excepciones
- problemas de rendimiento
- problemas de concurrencia (GUI congelada, hilo de automatizacion que no notifica "done", esperas de Playwright sin `timeout`)

Reporta:
1. Que hace el proyecto actualmente
2. Que se puede mejorar
3. Que riesgos hay (causa raiz + impacto + riesgo de la correccion)
4. Que NO debe tocarse para no romper funcionalidades

---

## 🛠️ FASE 2 -- Correccion

- Corregir errores detectados
- Aplicar mejoras sin romper compatibilidad
- Mejorar manejo de errores, validaciones, estabilidad
- Mantener codigo limpio y legible
- Respetar los Patrones de Confiabilidad documentados en `.claude/agents/python-desktop-engineer.md` (cierre de Playwright acotado con timeout, notificacion de "done" garantizada, watchdog de parada, `_dismiss_modal`/`_handle_random_survey`, no relanzar el `.exe` en bucle al instalar Chromium)

---

## 🧪 FASE 3 -- Validacion

Antes del commit, verifica que:
- `python -m py_compile main.py gui.py automation.py config_manager.py i18n.py log_setup.py version.py` pasa sin errores
- No se introdujeron regresiones (revisa que ninguna funcionalidad documentada en `.claude/specs/feature-specs.md` se haya roto)
- Si el cambio toca la GUI, arranca la app con `config.json` temporalmente renombrado (para no disparar `auto_start` con credenciales reales) y confirma que la ventana abre sin traceback

---

## 🔢 FASE 4 -- Versionado

- Determinar nueva version `Vx.x.x` (patch = fix, minor = feature compatible, major = cambio incompatible en el flujo de automatizacion)
- Explicar el tipo de incremento
- Actualizar version en:
  - `version.py` (`VERSION = "x.y.z"`)
  - Badge de version en `README.md` (linea del shield `version-x.y.z-blue`)
  - Nueva entrada en el Changelog de `README.md` (no existe `CHANGELOG.md` separado en este proyecto)

---

## 📝 FASE 5 -- Commit

Generar mensaje profesional tipo Conventional Commit, con la version entre parentesis:

```
fix: resolve <problema> and improve <mejora> (V0.7.5)
```

---

## 🚀 FASE 6 -- Push

Ver `.claude/agents/github-devops.md` antes de pushear -- **confirmar `gh auth status` muestra la cuenta `erickson558` como activa** (esta maquina tiene multiples cuentas `gh` logueadas; un push con la cuenta equivocada falla con 403).

```bash
git -c safe.directory='*' add <archivos especificos, nunca -A>
git -c safe.directory='*' commit -m "fix: descripcion (Vx.y.z)"
gh auth status   # confirmar cuenta activa = erickson558
git -c safe.directory='*' push origin main
```

El push a `main` dispara `.github/workflows/release.yml`, que compila el `.exe` en CI, crea el tag `v{VERSION}` y publica el GitHub Release automaticamente -- **no es necesario crear el tag manualmente** (a diferencia de otros proyectos del mismo autor).

Si ademas quieres el `.exe` recompilado localmente (junto a `main.py`, usando el `.ico` de la carpeta), usa `/build-exe` antes o despues del push.

---

## 📦 ENTREGABLES

Responde en este orden:

1. **Analisis de errores** -- lista de problemas encontrados, causa raiz, impacto
2. **Cambios realizados** -- que se corrigio y como
3. **Nueva version** -- numero y justificacion del incremento
4. **Codigo actualizado** -- completo si es critico, no fragmentos
5. **Commit message**
6. **Comandos paso a paso** con breve explicacion de cada uno

---

## ⚙️ Forma de Trabajo

- No omitir el analisis (Fase 1)
- No hacer cambios innecesarios ni sobre-ingenieria
- Priorizar estabilidad sobre refactorizacion agresiva
- Si hay duda -> explicar antes de cambiar
- Comentar el codigo nuevo/modificado explicando el PORQUE cuando no sea obvio (constraint oculto, workaround de un bug especifico del sitio, invariante no evidente) -- no reafirmar en comentarios lo que el nombre de la funcion/variable ya deja claro

---

## Contexto del Proyecto
- Raiz: d:\\OneDrive\\Regional\\1 pendientes para analisis\\proyectospython\\comprasaldoclaro
- GitHub: https://github.com/erickson558/comprasaldoclaro (cuenta: erickson558)
- Build: `build.bat` -> `ComprasClaroGT.exe` (mismo folder que `main.py`, icono `Banking_00012_A_icon-icons.com_59833.ico`)
- Specs SDD: `.claude/specs/`
- Otros skills relacionados: `/build-exe`, `/bump-version`, `/github-push`, `/github-release`, `/diagnose-automation`, `/annotate-code`, `/security-audit`
