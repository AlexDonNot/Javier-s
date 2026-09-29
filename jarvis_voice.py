"""
jarvis_voice.py
----------------
Módulo de voz para tu Jarvis usando Edge-TTS (voz natural, gratis).
Reemplaza tu función actual de "hablar" (probablemente basada en pyttsx3)
por las funciones de este archivo.

Instalación (si no lo hiciste ya):
    pip install edge-tts pygame

Uso básico:
    from jarvis_voice import hablar
    hablar("Buenas noches, señor. Todo listo.")
"""

import asyncio
import edge_tts
import pygame
import os
import tempfile

# ---------------------------------------------------------
# Configuración de la voz
# ---------------------------------------------------------
# Voces en español recomendadas (puedes probar varias y quedarte con la que más te guste):
#   "es-MX-JorgeNeural"     -> masculina, neutra latam
#   "es-AR-TomasNeural"     -> masculina, acento argentino
#   "es-PE-AlexNeural"      -> masculina, acento peruano
#   "es-ES-AlvaroNeural"    -> masculina, acento españa
#   "es-US-AlonsoNeural"    -> masculina, neutra US-latino
VOZ = "es-PE-AlexNeural"

# Velocidad y tono (puedes ajustar para darle más "personalidad")
# rate: "-10%" más lento, "+10%" más rápido
# pitch: "-5Hz" más grave, "+5Hz" más agudo
VELOCIDAD = "+0%"
TONO = "+0Hz"

pygame.mixer.init()


async def _generar_audio(texto: str, ruta_salida: str):
    """Genera el archivo de audio a partir del texto usando Edge-TTS."""
    comunicador = edge_tts.Communicate(
        texto,
        voice=VOZ,
        rate=VELOCIDAD,
        pitch=TONO,
    )
    await comunicador.save(ruta_salida)


def hablar(texto: str):
    """
    Función principal: convierte texto a voz y lo reproduce.
    Esta es la función que debes llamar en vez de tu antiguo
    engine.say(texto) / engine.runAndWait() de pyttsx3.
    """
    # Archivo temporal para el audio generado
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        ruta_temp = f.name

    try:
        # Generar el audio (Edge-TTS es async, así que lo corremos con asyncio)
        asyncio.run(_generar_audio(texto, ruta_temp))

        # Reproducir el audio generado
        pygame.mixer.music.load(ruta_temp)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    finally:
        # Limpiar el archivo temporal
        pygame.mixer.music.unload()
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)


def listar_voces_disponibles():
    """
    Utilidad: imprime todas las voces en español disponibles,
    por si quieres probar otras antes de decidirte.
    """
    async def _listar():
        voces = await edge_tts.list_voices()
        voces_es = [v for v in voces if v["Locale"].startswith("es")]
        for v in voces_es:
            print(f"{v['ShortName']:25} - {v['Gender']:8} - {v['Locale']}")

    asyncio.run(_listar())


if __name__ == "__main__":
    # Prueba rápida: ejecuta este archivo directamente para escuchar la voz
    print(f"Probando voz: {VOZ}")
    hablar("Buenas, señor. Sistemas en línea y listos para operar.")

    # Descomenta la siguiente línea si quieres ver todas las voces en español disponibles:
    # listar_voces_disponibles()
