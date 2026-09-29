"""
test_mic.py
-----------
Graba 3 segundos desde un dispositivo específico y te dice si detectó
algo de sonido (para encontrar cuál índice de micrófono sí funciona).

Uso:
    py -3.12 test_mic.py 9
    (cambia el 9 por el índice del dispositivo que quieras probar)
"""
import sys
import numpy as np
import sounddevice as sd

indice = int(sys.argv[1]) if len(sys.argv) > 1 else None
duracion = 3

info = sd.query_devices(indice, "input") if indice is not None else sd.query_devices(kind="input")
rate = int(info["default_samplerate"])  # usa la frecuencia nativa del dispositivo
print(f"Grabando 3 segundos desde: {info['name']} a {rate} Hz  (habla ahora!)")

grabacion = sd.rec(
    int(duracion * rate),
    samplerate=rate,
    channels=1,
    dtype="int16",
    device=indice,
)
sd.wait()

volumen_max = np.abs(grabacion).max()
volumen_promedio = np.abs(grabacion).mean()

print(f"Volumen máximo detectado: {volumen_max} (de 32767 posible)")
print(f"Volumen promedio: {volumen_promedio:.1f}")

if volumen_max < 100:
    print("❌ Prácticamente silencio total. Este dispositivo no está captando tu voz.")
elif volumen_max < 1000:
    print("⚠️  Detectó algo, pero muy bajito. Puede que sí sea el mic correcto pero con volumen bajo.")
else:
    print("✅ ¡Detectó audio con buen volumen! Este dispositivo sirve.")
