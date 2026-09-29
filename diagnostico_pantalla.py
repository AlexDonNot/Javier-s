"""
diagnostico_pantalla.py
------------------------
Script chiquito para averiguar EXACTAMENTE qué resolución ve cada
pieza del sistema (Windows, mss, pyautogui) y detectar si hay un
desfase entre ellas — eso es lo que causaría que los clics de Jarvis
caigan en otro lugar.

Uso:
    py -3.12 diagnostico_pantalla.py

Lee la salida completa y pásamela tal cual.
"""
import ctypes
import os

if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        print("SetProcessDpiAwareness(2) -> OK")
    except Exception as e:
        print(f"SetProcessDpiAwareness(2) -> falló: {e}")
        try:
            ok = ctypes.windll.user32.SetProcessDPIAware()
            print(f"Fallback SetProcessDPIAware() -> devolvió {ok}")
        except Exception as e2:
            print(f"Fallback también falló: {e2}")

print()
print("=== Lo que reporta Windows (GetSystemMetrics) ===")
user32 = ctypes.windll.user32
ancho_gsm = user32.GetSystemMetrics(0)
alto_gsm = user32.GetSystemMetrics(1)
print(f"Ancho: {ancho_gsm}   Alto: {alto_gsm}")

print()
print("=== Lo que captura mss (la librería de screenshots) ===")
try:
    import mss
    with mss.mss() as sct:
        monitores = sct.monitors
        print(f"Cantidad de entradas en sct.monitors: {len(monitores)}")
        for i, m in enumerate(monitores):
            print(f"  monitors[{i}] = {m}")
        img = sct.grab(sct.monitors[1])
        print(f"Captura real de monitors[1]: {img.size[0]} x {img.size[1]} píxeles")
except ImportError:
    print("mss no está instalado (pip install mss)")

print()
print("=== Dónde dice pyautogui que está la pantalla / el cursor ===")
try:
    import pyautogui
    print(f"pyautogui.size() -> {pyautogui.size()}")
    print(f"Posición actual del cursor -> {pyautogui.position()}")
except ImportError:
    print("pyautogui no está instalado (pip install pyautogui)")

print()
print("=== Prueba de movimiento ===")
print("En 3 segundos voy a mover el cursor a la posición (100, 100).")
print("Fíjate en la PANTALLA si de verdad quedó cerca de la esquina")
print("superior izquierda, o se fue a otro lado.")
try:
    import time
    time.sleep(3)
    pyautogui.moveTo(100, 100, duration=0.5)
    print("Listo. ¿Dónde quedó el cursor en la pantalla real?")
except Exception as e:
    print(f"No se pudo mover: {e}")
