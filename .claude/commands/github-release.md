# GitHub Release -- Compra Saldo Claro GT

Verifica/crea el release en GitHub para la version actual.

Argumento opcional: $ARGUMENTS (notas adicionales)

## Importante: este proyecto ya automatiza el release en CI

A diferencia de otros proyectos del mismo autor, `release.yml` se dispara en **cada push a `main`** y crea el tag + Release automaticamente (paso "Crear tag" usa `|| echo "Tag ya existe"`, no falla si ya existe). Este comando es principalmente para **verificar** que el release automatico se genero correctamente, o para recrearlo manualmente si el workflow fallo.

## Pasos

1. Confirmar cuenta `gh` activa (ver `/github-push` Paso 0):
   ```bash
   gh auth status
   ```

2. Leer version actual desde `version.py` (`VERSION = "x.y.z"`)

3. Verificar que el workflow corrio tras el ultimo push:
   ```bash
   gh run list -R erickson558/comprasaldoclaro --limit 3
   ```

4. Si el run fue exitoso, verificar el release publicado:
   ```bash
   gh release view v{version} -R erickson558/comprasaldoclaro
   ```
   Confirmar que adjunta `ComprasClaroGT.exe` Y `ComprasClaroGT.exe.sha256`.

5. **Solo si el workflow fallo o no corrio** (ej. push hecho antes de que existiera el workflow, o fallo de CI): crear el release manualmente:
   ```bash
   git -c safe.directory='*' tag -a "v{version}" -m "Release v{version}" || echo "Tag ya existe"
   git -c safe.directory='*' push origin "v{version}"
   gh release create "v{version}" --title "Compra Saldo Claro GT v{version}" --notes "{notas}" -R erickson558/comprasaldoclaro ComprasClaroGT.exe ComprasClaroGT.exe.sha256
   ```

6. Reportar URL del release y artefactos incluidos (debe incluir SIEMPRE el `.exe` y su hash SHA-256 -- ver `SECURITY.md`).

## Cuenta
- erickson558 autenticado via `gh` CLI
- Repo: https://github.com/erickson558/comprasaldoclaro/releases
- CI/CD crea el `.exe` + hash automaticamente en cada push a `main` (ver `.github/workflows/release.yml`)
