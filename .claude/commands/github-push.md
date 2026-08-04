# GitHub Push -- Compra Saldo Claro GT

Sube cambios actuales a GitHub con la cuenta `erickson558`.

Argumento opcional: $ARGUMENTS (pista para el mensaje de commit)

## ⚠️ Paso 0 -- OBLIGATORIO antes de cualquier push

Esta maquina puede tener mas de una cuenta de GitHub logueada en `gh` CLI simultaneamente. El credential helper de git para `github.com` usa `gh auth git-credential`, asi que `git push` autentica con la cuenta que `gh` marque como **activa**, sin importar cual sea la "correcta" para este repo.

```bash
gh auth status
```

Si la cuenta activa NO es `erickson558`, cambiarla PRIMERO:
```bash
gh auth switch --hostname github.com --user erickson558
```

Un push con la cuenta equivocada activa falla con `403 Permission denied to erickson558/comprasaldoclaro.git`.

## Pasos

1. Revisar cambios:
   ```bash
   git -c safe.directory='*' status
   git -c safe.directory='*' diff --stat
   ```
   (El flag `safe.directory='*'` es solo para esta invocacion -- el repo vive en una unidad OneDrive y puede reportar "dubious ownership"; no persistir este flag en config global salvo que el usuario lo pida.)

2. Determinar tipo de commit:
   - `feat:` nueva funcionalidad
   - `fix:` correccion de bug
   - `docs:` documentacion
   - `chore:` mantenimiento
   - `refactor:` refactorizacion

3. Stagear archivos especificos (NUNCA `git add -A`/`git add .` a ciegas). EXCLUIR siempre (ya en `.gitignore`, pero verificar con `git status` que ninguno aparece tracked por error):
   - `config.json` (contiene password/CVV en texto plano)
   - `log.txt`, `log.txt.1`, `debug.log`, `comprasclaro.txt`
   - `*.exe`, `*.spec`, `build_tmp/`, `playwright-browsers/`

4. Crear commit con Conventional Commits (incluir version si aplica):
   ```bash
   git -c safe.directory='*' commit -m "tipo: descripcion en español (Vx.y.z)"
   ```

5. Push:
   ```bash
   git -c safe.directory='*' push origin main
   ```
   Si el trabajo esta en una rama que no es `main` y ya tiene PR abierto (`gh pr list --head <rama>`), pushear a esa rama en vez de `main`.

   **Recordar:** cada push a `main` dispara `release.yml` (build + GitHub Release publico automatico). Confirmar con el usuario antes si el push no fue pedido explicitamente con esa intencion.

6. Reportar archivos commiteados y URL del commit/PR.

## Cuenta GitHub
- Usuario: erickson558
- Repo: https://github.com/erickson558/comprasaldoclaro
- Autenticado via: `gh` CLI (verificar cuenta activa en Paso 0)
- Rama principal: `main`

## Reglas
- NUNCA `--no-verify` ni `--force`
- NUNCA force-push a `main`
- No amend de commits ya publicados -- crear siempre un commit nuevo
