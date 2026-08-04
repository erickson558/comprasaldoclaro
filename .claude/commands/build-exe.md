# Build EXE -- Compra Saldo Claro GT

Compila la aplicacion a ejecutable Windows (`ComprasClaroGT.exe`), dejandolo en la MISMA carpeta que `main.py`, usando el icono `Banking_00012_A_icon-icons.com_59833.ico` de esa misma carpeta.

## ⚠️ Nota para ejecucion no interactiva (agente/CI)

`build.bat` termina con `pause`, que bloquea esperando entrada de teclado si se invoca desde un agente o script no interactivo. Un agente debe invocar `pyinstaller` DIRECTAMENTE con los mismos flags, no ejecutar `build.bat` tal cual. Un usuario humano en su propia terminal SI puede simplemente hacer doble clic en `build.bat` o ejecutarlo normalmente.

## Pasos (invocacion directa, para agente)

1. Verificar que `pyinstaller` esta disponible:
   ```
   pyinstaller --version
   ```
   Si falla con "No module named pyinstaller" al usar `python -m pyinstaller`, NO reintentar con `python -m` -- usar el ejecutable `pyinstaller`/`pyinstaller.exe` directo (puede estar en `Scripts/` de una instalacion `pip install --user`, fuera del PATH de `python -m`).

2. Limpiar build previo:
   ```
   rm -f ComprasClaroGT.exe
   rm -rf build_tmp
   ```

3. Compilar con **ruta ABSOLUTA del icono** (con `--specpath="build_tmp"`, una ruta relativa de `--icon` falla con `FileNotFoundError` porque PyInstaller la resuelve contra `specpath`, no contra el cwd):
   ```
   pyinstaller \
     --onefile \
     --noconsole \
     --icon="<ruta-absoluta>/Banking_00012_A_icon-icons.com_59833.ico" \
     --name="ComprasClaroGT" \
     --distpath="." \
     --workpath="build_tmp" \
     --specpath="build_tmp" \
     main.py
   ```

4. Limpiar temporales:
   ```
   rm -rf build_tmp
   ```

5. Verificar resultado:
   - Confirmar que `ComprasClaroGT.exe` existe en la raiz del proyecto (misma carpeta que `main.py`)
   - Reportar tamaño en MB

## ⚠️ Smoke test seguro (NUNCA lanzar con config.json real)

Si se necesita verificar que el `.exe` abre sin crashear:
1. Mover `config.json` a un nombre temporal (`mv config.json config.json.bak_test`) -- esto evita que `auto_start` (si esta activo) dispare una compra real con credenciales reales al arrancar
2. Lanzar el `.exe` en background, esperar unos segundos, confirmar que el proceso sigue vivo (ventana abierta sin crash)
3. Matar el proceso de prueba
4. Restaurar `config.json` a su nombre original de inmediato

NUNCA dejar `config.json.bak_test` sin restaurar al terminar.

## Requisitos
- Python 3.12 instalado
- PyInstaller (no fijado en `requirements.txt` -- comentario explicito: "se usa solo para compilar")
- customtkinter y playwright instalados (se empaquetan en el `.exe`)
- Icono `Banking_00012_A_icon-icons.com_59833.ico` en la raiz del proyecto

## Configuracion
- Output: `ComprasClaroGT.exe` en la raiz del proyecto (misma carpeta que `main.py`)
- Modo: `--noconsole` (sin ventana de consola adicional)
- Nunca commitear el `.exe` -- esta en `.gitignore` (`*.exe`); la distribucion oficial es via GitHub Releases, generada automaticamente por `release.yml` en cada push a `main`
