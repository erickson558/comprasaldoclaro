@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM build.bat  –  Compila la aplicación a un .exe usando PyInstaller
REM El ejecutable queda en la misma carpeta que este .bat
REM Uso: Doble clic o ejecutar desde una terminal en esta carpeta
REM ─────────────────────────────────────────────────────────────────────────────

echo ============================================================
echo  Compilando Compra Saldo Claro a .exe...
echo ============================================================

REM Verificar que PyInstaller esté instalado
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller no está instalado.
    echo Instálalo con:  pip install pyinstaller
    pause
    exit /b 1
)

REM Compilar con PyInstaller:
REM  --onefile       : un solo .exe (más portátil)
REM  --noconsole     : sin ventana de consola (app GUI)
REM  --icon          : icono del .exe (el .ico de la carpeta)
REM  --name          : nombre del ejecutable
REM  --distpath .    : dejar el .exe en esta misma carpeta
REM  --add-data      : incluir config.json y el ícono en el ejecutable
REM Usar ruta absoluta del ícono para que PyInstaller lo encuentre
REM aunque --specpath apunte a otra carpeta
pyinstaller ^
    --onefile ^
    --noconsole ^
    --icon="%~dp0Banking_00012_A_icon-icons.com_59833.ico" ^
    --name="ComprasClaroGT" ^
    --distpath="%~dp0" ^
    --workpath="%~dp0build_tmp" ^
    --specpath="%~dp0build_tmp" ^
    main.py

REM Limpiar archivos temporales de compilación
if exist "build_tmp" rmdir /s /q "build_tmp"

echo.
if exist "ComprasClaroGT.exe" (
    echo  OK: ComprasClaroGT.exe generado en esta carpeta.
) else (
    echo  ERROR: La compilación falló. Revisa los mensajes anteriores.
)

echo ============================================================
pause
