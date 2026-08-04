# Bump Version -- Compra Saldo Claro GT

Incrementa la version del proyecto (Semantic Versioning).

Argumento: $ARGUMENTS -- "major", "minor", o "patch" (default: patch)

A diferencia de otros proyectos del mismo autor, este NO tiene `scripts/bump_version.py` ni `CHANGELOG.md` separado -- la version vive unicamente en `version.py` y el historial de cambios vive dentro del README.

## Pasos

1. Leer version actual:
   - Abrir `version.py`, leer `VERSION = "x.y.z"`

2. Determinar tipo desde $ARGUMENTS:
   - **major**: cambio incompatible en el flujo de automatizacion (ej. reescritura del flujo de compra) -> `X.0.0`
   - **minor**: nueva funcionalidad compatible en la GUI o automatizacion -> `x.Y.0`
   - **patch**: correccion de bug, mejora menor, endurecimiento de un selector -> `x.y.Z`
   - Sin argumento -> usar patch

3. Editar `version.py`:
   ```python
   VERSION = "x.y.z"  # nueva version
   ```

4. Editar `README.md`:
   - Badge de version (linea ~5): `https://img.shields.io/badge/version-x.y.z-blue`
   - Nueva entrada al INICIO de la seccion `## Changelog` (mas reciente arriba):
     ```markdown
     ### Vx.y.z — YYYY-MM-DD
     - **fix/feat:** Descripcion del cambio
     ```

5. Reportar: version anterior -> nueva version, tipo de incremento y justificacion

## Flujo Post-Bump

1. `/build-exe` -- compilar `.exe` local para verificacion (opcional si solo se pusheará y se deja que CI compile)
2. `/github-push` -- subir cambios a `main`
3. El push a `main` dispara automaticamente `release.yml`: build en CI + tag `v{VERSION}` + GitHub Release con `.exe` + `.exe.sha256` adjuntos -- **no hace falta `/github-release` manual** salvo que el workflow haya fallado y se necesite reintentarlo a mano

## Convencion de Versionado (segun README del proyecto)

| Tipo de cambio | Incrementa | Ejemplo |
|---|---|---|
| Cambio en el flujo de automatizacion | MAJOR | V1.0.0 |
| Nueva funcionalidad en GUI | MINOR | V0.1.0 |
| Correccion de bug / ajuste menor | PATCH | V0.0.3 |

La version debe coincidir SIEMPRE en: `version.py` -> GUI (la lee de `version.py`) -> badge de README -> Changelog de README -> tag git -> GitHub Release.
