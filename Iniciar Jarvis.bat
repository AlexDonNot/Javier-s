@echo off
REM Iniciar Jarvis.bat
REM -------------------
REM Doble clic aquí para abrir Jarvis, sin necesidad de abrir cmd manualmente.
REM Debe estar guardado en la MISMA carpeta que jarvis_gui.py.

REM Si ya configuraste GEMINI_API_KEY y YOUTUBE_API_KEY con "setx" (permanentes),
REM no necesitas tocar nada más abajo. Si NO las configuraste como permanentes,
REM descomenta (quita el "REM" de) las 2 líneas de abajo y pon tus keys reales:

REM set GEMINI_API_KEY=tu_key_de_gemini_aqui
REM set YOUTUBE_API_KEY=tu_key_de_youtube_aqui

cd /d "%~dp0"
py -3.12 jarvis_gui.py

REM Si algo falla, esto mantiene la ventana abierta para que veas el error
pause
