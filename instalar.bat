@echo off
color 0B
cls
echo.
echo   ==========================================
echo.
echo          JARVIS - TU CHERO
echo.
echo   ==========================================
echo.
echo   Este instalador va a:
echo     1. Verificar que tengas Python 3.12
echo     2. Instalar las librerias necesarias
echo     3. Revisar que tus API keys esten configuradas
echo.
echo   ------------------------------------------
set /p RESPUESTA="   Deseas continuar? (s/n): "
echo   ------------------------------------------
echo.

if /i not "%RESPUESTA%"=="s" (
    echo   Instalacion cancelada. Nos vemos, chero.
    echo.
    pause
    exit /b
)

REM ============================================
REM 1. Verificar Python 3.12
REM ============================================
echo   [1/3] Verificando Python 3.12...
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [X] No encontre Python 3.12 instalado.
    echo.
    echo       Jarvis necesita especificamente la version 3.12
    echo       ^(versiones mas nuevas, como 3.13 o 3.14, suelen
    echo       fallar al instalar las librerias de audio en Windows^).
    echo.
    echo       Descargala aqui:
    echo       https://www.python.org/downloads/windows/
    echo.
    echo       Busca "Python 3.12.8" ^(o el 3.12 mas reciente^) y al
    echo       instalarla, MARCA la casilla "Add python.exe to PATH".
    echo.
    echo       Luego vuelve a correr este instalador.
    echo.
    pause
    exit /b
)
echo   [OK] Python 3.12 encontrado.
echo.

REM ============================================
REM 2. Instalar librerias
REM ============================================
echo   [2/3] Instalando librerias, dale un momento...
echo.
py -3.12 -m pip install -r requirements.txt
echo.
echo   [OK] Librerias instaladas.
echo.

REM ============================================
REM 3. Revisar API keys configuradas
REM ============================================
echo   [3/3] Revisando tus API keys...
echo.

set FALTAN_KEYS=0

if not defined GEMINI_API_KEY (
    echo   [X] Falta GEMINI_API_KEY ^(OBLIGATORIA, Jarvis no arranca sin ella^)
    set FALTAN_KEYS=1
) else (
    echo   [OK] GEMINI_API_KEY configurada.
)

if not defined YOUTUBE_API_KEY (
    echo   [ ] Falta YOUTUBE_API_KEY ^(opcional, solo para reproducir directo en YouTube^)
) else (
    echo   [OK] YOUTUBE_API_KEY configurada.
)

if not defined OPENWEATHER_API_KEY (
    echo   [ ] Falta OPENWEATHER_API_KEY ^(opcional, solo para el clima real^)
) else (
    echo   [OK] OPENWEATHER_API_KEY configurada.
)

echo.

if "%FALTAN_KEYS%"=="1" (
    echo   ==========================================
    echo   Te falta configurar al menos una key OBLIGATORIA.
    echo   ==========================================
    echo.
    echo   Para ponerla de forma PERMANENTE, cierra este instalador
    echo   y en una terminal normal escribe esto ^(cambia el texto
    echo   entre comillas por tu key real^):
    echo.
    echo        setx GEMINI_API_KEY "tu_clave_de_gemini_aqui"
    echo.
    echo   Si tambien quieres las opcionales:
    echo        setx YOUTUBE_API_KEY "tu_clave_de_youtube_aqui"
    echo        setx OPENWEATHER_API_KEY "tu_clave_de_openweather_aqui"
    echo.
    echo   IMPORTANTE: despues de usar "setx", CIERRA esta terminal
    echo   y abre una NUEVA antes de correr Jarvis ^(setx no se nota
    echo   en la ventana donde lo escribiste, solo en las nuevas^).
    echo.
    echo   Consigue tu GEMINI_API_KEY gratis en:
    echo        https://aistudio.google.com
    echo.
) else (
    echo   ==========================================
    echo   [OK] Todo listo. Jarvis esta configurado por completo.
    echo.
    echo   Para ejecutarlo, escribe:
    echo        py -3.12 jarvis_gui.py
    echo   o haz doble clic en "Iniciar Jarvis.bat"
    echo   ==========================================
)

echo.
pause
