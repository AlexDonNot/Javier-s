# J.A.V.I.E.R. personal v1.0

Asistente por voz que ve tu pantalla en tiempo real, te responde hablando,
y puede controlar tu compu: abrir/cerrar apps, buscar en el navegador,
reproducir música/videos, manejar un calendario y recordatorios locales,
consultar el clima, controlar volumen/brillo, y más.

Corre con la **Gemini Live API** (audio + video en streaming) y tiene una
interfaz gráfica estilo "arco reactor" hecha con Tkinter.

## Estructura del proyecto

| Archivo | Qué hace |
|---|---|
| `jarvis_live.py` | El núcleo: conexión con Gemini, micrófono, pantalla, detección de aplausos |
| `jarvis_acciones.py` | Todas las acciones que Jarvis puede ejecutar en tu PC |
| `jarvis_gui.py` | La interfaz gráfica (HUD) |
| `Iniciar Jarvis.bat` | Doble clic para abrir todo sin usar la terminal manualmente |
| `test_mic_volumen.py` | Script de diagnóstico: mide el volumen que capta tu micrófono |
| `diagnostico_pantalla.py` | Script de diagnóstico de la captura de pantalla |

## Requisitos

- **Windows 10/11**
- **Python 3.12** (recomendado — versiones más nuevas, como 3.13/3.14, suelen
  dar problemas al instalar `pyaudio`/librerías de audio en Windows por
  falta de wheels precompilados)
- Una API key de **Gemini** (gratis en [aistudio.google.com](https://aistudio.google.com))
- Opcional: API key de **YouTube Data API** (para reproducir directo, no solo
  buscar) y de **OpenWeather** (para clima real)

## Instalación

**Opción rápida:** doble clic en `instalar.bat`. Revisa que tengas Python
3.12, instala todas las librerías, y te dice exactamente qué API keys te
faltan configurar (con el comando `setx` listo para copiar).

**Opción manual:**
1. Clona o descarga este repo.
2. Abre una terminal en la carpeta del proyecto.
3. Instala las librerías:
   ```
   py -3.12 -m pip install -r requirements.txt
   ```

## Configurar tus API keys

**Nunca las escribas directo en el código** si vas a subir esto a GitHub.
Dos formas de configurarlas:

**Opción A — variable de entorno permanente (recomendada):**
```
setx GEMINI_API_KEY "tu_clave_aqui"
setx YOUTUBE_API_KEY "tu_clave_aqui"
setx OPENWEATHER_API_KEY "tu_clave_aqui"
```
Cierra y abre una terminal nueva para que tome efecto.

**Opción B — solo para esta sesión (PowerShell):**
```
$env:GEMINI_API_KEY="tu_clave_aqui"
```

`YOUTUBE_API_KEY` y `OPENWEATHER_API_KEY` son opcionales: si faltan, esas
funciones puntuales avisan que no están configuradas, pero el resto de
Jarvis funciona igual.

## Uso

**Con interfaz gráfica (recomendado):**
```
py -3.12 jarvis_gui.py
```
o doble clic en `Iniciar Jarvis.bat`.

**Solo en terminal, sin interfaz:**
```
py -3.12 jarvis_live.py
```

Usa **audífonos**: si usas parlantes, el micrófono capta la propia voz de
Jarvis y se interrumpe solo.

## Algunas cosas que sabe hacer

- Ver tu pantalla y describir/explicar lo que hay en ella
- Abrir y cerrar apps (Spotify, Chrome, Word, Excel, calculadora, notas...)
- Buscar y reproducir en YouTube, buscar en Google
- Controlar volumen, brillo y modo "no molestar"
- Agendar recordatorios y eventos (con calendario local, persiste entre sesiones)
- Consultar el clima real de cualquier ciudad
- Leer el portapapeles
- **Modo estudio**: silencia notificaciones, pone música, abre Word y (opcional) campus universitario, y programa un descanso — se activa por voz o con 2 aplausos
- Comandos básicos de control en juegos (moverse, saltar, mirar, etc.)

## Notas técnicas

- El nombre del modelo de Gemini Live (`MODELO` en `jarvis_live.py`) puede
  cambiar con el tiempo, ya que son versiones "preview". Si deja de conectar,
  revisa la [documentación oficial](https://ai.google.dev/gemini-api/docs/live)
  por el nombre vigente.
- El detector de "2 aplausos" tiene un cooldown de 20s tras activarse, para
  evitar que la propia música que prende el modo estudio (si el micrófono la
  capta) dispare falsos positivos en cadena.
- Los datos personales (`jarvis_historial.json`, `perfil_usuario.json`,
  recordatorios y calendario) se guardan localmente en tu equipo y **no**
  se suben al repo (ver `.gitignore`).

  ES EDITABLE AWA
  
