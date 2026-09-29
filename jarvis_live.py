"""
Jarvis: conversación por voz en tiempo real + ve tu pantalla.
Usa la Gemini Live API.

Versión adaptada para usar `sounddevice` en vez de `pyaudio`
(evita el problema de compilación de pyaudio en Windows).

Instalación:
    pip install google-genai mss pillow sounddevice

Uso:
    1) Pon tu API key (aistudio.google.com) en la variable de entorno GEMINI_API_KEY
       o reemplaza el texto TU_API_KEY abajo.
    2) python jarvis_live.py
    3) Habla normalmente. Ctrl+C para salir.

IMPORTANTE: usa AUDÍFONOS. Si usas parlantes, el micrófono captará la voz
de la IA y se interrumpirá a sí misma.
"""
import asyncio
import audioop
import io
import os
import queue
import shutil
import threading
import time

import mss
import sounddevice as sd
from PIL import Image
from google import genai
from google.genai import types

try:
    import psutil
except ImportError:
    psutil = None

from jarvis_acciones import (
    abrir_app,
    buscar_en_navegador,
    reproducir_en_youtube,
    controlar_volumen,
    cerrar_app,
    abrir_carpeta,
    configurar_recordatorio,
    abrir_notas_con_texto,
    buscar_archivos,
    abrir_ruta,
    obtener_saludo,
    obtener_clima_real,
    obtener_clima_temperatura_corta,
    obtener_estado_sistema,
    controlar_brillo,
    tomar_captura_pantalla,
    modo_no_molestar,
    controlar_energia,
    leer_portapapeles,
    obtener_recordatorios_activos,
    cargar_recordatorios_guardados,
    agendar_evento,
    listar_eventos_calendario,
    eliminar_evento_calendario,
    obtener_eventos_calendario_lista,
    revisar_eventos_pendientes,
    escribir_texto_en_foco,
    presionar_tecla,
    buscar_en_barra_navegador,
    jugar_mover,
    jugar_saltar,
    jugar_agacharse,
    jugar_correr,
    jugar_clic,
    jugar_pelear,
    jugar_farmear,
    jugar_mirar,
    jugar_hotbar,
    activar_rutina_aplausos,
    activar_modo_estudio,
    cargar_perfil,
    cargar_ultimo_resumen,
    agregar_al_historial,
    set_notificador,
)

PERFIL = cargar_perfil()

API_KEY = os.environ.get("GEMINI_API_KEY", "TU_API_KEY")

# Los nombres de modelo cambian seguido: revisa la doc de Live API
# (ai.google.dev/gemini-api/docs/live) y usa uno con audio nativo.
# gemini-3.8-live: modelo rápido, sin razonamiento extendido, para
# respuestas ágiles sin demoras extra.
MODELO = "gemini-3.8-live"

INTERVALO_PANTALLA = 4.0   # segundos entre capturas enviadas (antes 3.0; se
                           # subió un poco para aliviar la carga de la
                           # Desktop Duplication API mientras juegas)
ANCHO_MAX = 768            # reduce resolución para gastar menos

# Audio: entrada 16 kHz, salida 24 kHz, PCM 16 bits mono
CANALES = 1
RATE_ENTRADA = 16000
RATE_SALIDA = 24000
CHUNK = 1024

# Índice del micrófono a usar (encontrado con test_mic.py).
# Cambia este número si luego pruebas otro dispositivo y funciona mejor.
DISPOSITIVO_ENTRADA = 9

# Estado del resampler (se usa para convertir del sample rate nativo del
# micrófono, ej. 48000 Hz, al 16000 Hz que pide Gemini)
_resample_state = None

# Última transcripción de lo que dijo Jarvis, para que una interfaz
# gráfica (jarvis_gui.py) la pueda mostrar en pantalla
ultima_transcripcion = {"texto": ""}

# Cola thread-safe para recibir mensajes de texto escritos en la interfaz
# gráfica (jarvis_gui.py corre en otro hilo, así que no puede usar una
# asyncio.Queue directo, necesita queue.Queue normal)
cola_texto_gui: queue.Queue = queue.Queue()

# Los recordatorios (jarvis_acciones.configurar_recordatorio) usan esto
# para "avisarle" algo a Jarvis cuando se cumple el tiempo: lo empujamos
# a la misma cola de texto, y se lo mandamos a Gemini como si lo hubieras
# escrito tú.
set_notificador(lambda texto: cola_texto_gui.put(texto))

# Bandera compartida: True mientras Jarvis está reproduciendo audio
# (evita que se escuche a sí mismo por el parlante y se auto-interrumpa)
esta_hablando = asyncio.Event()

# Bandera para mutear el micrófono manualmente desde la interfaz gráfica
# (botón "Mutear" en jarvis_gui.py). threading.Event porque se lee/escribe
# desde otro hilo (la ventana), no desde el loop de asyncio.
microfono_muteado = threading.Event()

# Bandera para pausar el envío continuo de pantalla (botón "Pausar visión"
# en jarvis_gui.py). La captura de pantalla cada pocos segundos compite
# por la Desktop Duplication API de Windows con juegos en pantalla
# completa y puede causar bajones de FPS; con esto lo puedes apagar sin
# cerrar Jarvis.
vision_pausada = threading.Event()

# --- Datos compartidos con la interfaz gráfica (jarvis_gui.py) --------
# Log tipo "terminal" que se muestra en el panel CHAT/CMD CTR de la
# ventana: líneas "JARVIS: ..." (lo que dijo) y "> ..." (resultado de
# comandos ejecutados). Empieza con el mismo tipo de banner que un HUD.
MAX_LINEAS_LOG_GUI = 60
historial_gui: list = ["[ JARVIS MOBILE ONLINE ]", "[ TAP ARC REACTOR TO SPEAK ]"]


def _agregar_log_gui(texto: str):
    historial_gui.append(texto)
    del historial_gui[:-MAX_LINEAS_LOG_GUI]


# Clima corto ("23°C") para la tarjeta de la interfaz; se actualiza solo
# cada 20 minutos en segundo plano para no golpear la API todo el rato.
clima_actual = {"texto": "Cargando clima..."}

client = genai.Client(api_key=API_KEY)

HERRAMIENTAS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="abrir_app",
        description="Abre una aplicación en la laptop del usuario, como Spotify, Chrome, calculadora, etc.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "nombre_app": {
                    "type": "STRING",
                    "description": "Nombre de la app a abrir, ej: 'spotify', 'chrome', 'calculadora'"
                }
            },
            "required": ["nombre_app"]
        }
    ),
    types.FunctionDeclaration(
        name="buscar_en_navegador",
        description="Abre el navegador y busca en Google lo que el usuario pida.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "consulta": {
                    "type": "STRING",
                    "description": "Lo que se debe buscar, ej: 'clima en lima hoy'"
                }
            },
            "required": ["consulta"]
        }
    ),
    types.FunctionDeclaration(
        name="reproducir_en_youtube",
        description="Busca una canción, video o tema en YouTube y reproduce automáticamente el primer resultado.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "consulta": {
                    "type": "STRING",
                    "description": "Qué buscar y reproducir, ej: 'nirvana smells like teen spirit'"
                }
            },
            "required": ["consulta"]
        }
    ),
    types.FunctionDeclaration(
        name="controlar_volumen",
        description="Sube, baja o silencia el volumen del sistema.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "accion": {
                    "type": "STRING",
                    "description": "Qué hacer con el volumen: 'subir', 'bajar' o 'silenciar'"
                }
            },
            "required": ["accion"]
        }
    ),
    types.FunctionDeclaration(
        name="cerrar_app",
        description="Cierra (fuerza el cierre de) una aplicación abierta por nombre.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "nombre_app": {
                    "type": "STRING",
                    "description": "Nombre de la app a cerrar, ej: 'spotify', 'chrome'"
                }
            },
            "required": ["nombre_app"]
        }
    ),
    types.FunctionDeclaration(
        name="abrir_carpeta",
        description="Abre una carpeta conocida del usuario, como sus proyectos, descargas, escritorio o documentos.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "nombre": {
                    "type": "STRING",
                    "description": "Nombre de la carpeta a abrir, ej: 'proyectos', 'descargas'"
                }
            },
            "required": ["nombre"]
        }
    ),
    types.FunctionDeclaration(
        name="configurar_recordatorio",
        description="Programa un recordatorio para dentro de X minutos. Jarvis se lo mencionará al usuario cuando se cumpla el tiempo.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "minutos": {
                    "type": "NUMBER",
                    "description": (
                        "En cuántos minutos avisar. Acepta decimales: "
                        "convierte SIEMPRE la unidad que use el usuario a "
                        "minutos antes de llamar la función. Ejemplos: "
                        "'30 segundos' -> 0.5, '10 minutos' -> 10, "
                        "'media hora' -> 30, 'una hora' -> 60, "
                        "'hora y media' -> 90."
                    )
                },
                "mensaje": {
                    "type": "STRING",
                    "description": "Qué recordarle al usuario, ej: 'revisar el horno'"
                }
            },
            "required": ["minutos", "mensaje"]
        }
    ),
    types.FunctionDeclaration(
        name="abrir_notas_con_texto",
        description=(
            "Abre el Bloc de notas de Windows con un texto escrito adentro. "
            "Úsala tú mismo, sin que te lo pidan, cuando la respuesta sea "
            "larga o compleja: explicaciones con varios puntos o pasos, "
            "listas, código, una receta, cálculos, o cualquier cosa que sea "
            "más fácil de leer que de escuchar. Úsala también cuando el "
            "usuario lo pida directamente ('anótalo', 'escríbelo', 'ábrelo "
            "en el bloc de notas', 'pásamelo por escrito'). Escribe en "
            "'texto' la respuesta completa y bien redactada (no un resumen), "
            "y sigue además respondiendo por voz con un resumen breve de lo "
            "mismo."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "texto": {
                    "type": "STRING",
                    "description": "El texto completo (puede tener varias líneas) que se debe escribir en el Bloc de notas."
                },
                "titulo": {
                    "type": "STRING",
                    "description": "Título corto opcional para la nota, ej: 'Receta de lomo saltado'."
                }
            },
            "required": ["texto"]
        }
    ),
    types.FunctionDeclaration(
        name="buscar_archivos",
        description=(
            "Busca archivos o carpetas por nombre dentro de las carpetas "
            "típicas del usuario (Escritorio, Documentos, Descargas, "
            "OneDrive). Úsala cuando el usuario pida abrir, encontrar o "
            "buscar algo que NO esté en la lista fija de carpetas conocidas "
            "(proyectos, descargas, escritorio, documentos), por ejemplo un "
            "archivo específico o una carpeta con nombre propio. Devuelve "
            "una lista de rutas encontradas; si hay varias, pregunta al "
            "usuario cuál quiere abrir antes de usar abrir_ruta. Si hay "
            "una sola coincidencia clara, puedes abrirla directo."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "nombre": {
                    "type": "STRING",
                    "description": "Nombre (o parte del nombre) del archivo o carpeta a buscar, ej: 'contrato', 'fotos vacaciones'"
                },
                "solo_carpetas": {
                    "type": "BOOLEAN",
                    "description": "True si el usuario busca específicamente una carpeta, no un archivo."
                }
            },
            "required": ["nombre"]
        }
    ),
    types.FunctionDeclaration(
        name="abrir_ruta",
        description=(
            "Abre un archivo o carpeta a partir de su ruta completa en la "
            "laptop (normalmente una ruta que te devolvió buscar_archivos). "
            "Si es un archivo lo abre con su programa por defecto; si es "
            "una carpeta la abre en el explorador."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "ruta": {
                    "type": "STRING",
                    "description": "Ruta completa del archivo o carpeta a abrir, ej: 'C:\\Users\\mbroa\\Documents\\contrato.docx'"
                }
            },
            "required": ["ruta"]
        }
    ),
    types.FunctionDeclaration(
        name="obtener_clima_real",
        description="Da el clima actual real (temperatura y descripción) de una ciudad usando la API de OpenWeather. Si no se indica ciudad, usa la del perfil del usuario.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "ciudad": {
                    "type": "STRING",
                    "description": "Ciudad a consultar, ej: 'Lima,PE'. Puede ir vacío para usar la ciudad por defecto."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="obtener_estado_sistema",
        description="Devuelve la hora actual, el nivel de batería y el espacio libre en disco de la laptop. Úsala al arrancar o cuando te pregunten cómo está la laptop.",
        parameters={"type": "OBJECT", "properties": {}}
    ),
    types.FunctionDeclaration(
        name="controlar_brillo",
        description="Sube, baja o fija el brillo de la pantalla.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "accion": {
                    "type": "STRING",
                    "description": "'subir', 'bajar', o un número del 0 al 100."
                }
            },
            "required": ["accion"]
        }
    ),
    types.FunctionDeclaration(
        name="tomar_captura_pantalla",
        description="Toma una captura de la pantalla completa y la guarda como imagen. Úsala cuando el usuario diga 'guárdame esto', 'toma una captura', etc.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "nombre": {
                    "type": "STRING",
                    "description": "Nombre corto para el archivo, ej: 'error_build'. Opcional."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="modo_no_molestar",
        description="Activa o desactiva el modo no molestar (silencia las notificaciones de Windows).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "activar": {
                    "type": "BOOLEAN",
                    "description": "True para activar el modo no molestar, False para desactivarlo."
                }
            },
            "required": ["activar"]
        }
    ),
    types.FunctionDeclaration(
        name="controlar_energia",
        description=(
            "Apaga, reinicia o suspende la laptop. IMPORTANTE: la primera vez "
            "que el usuario lo pida, llama esta función con confirmar=False; "
            "eso te devuelve una pregunta de confirmación que debes decirle "
            "al usuario TAL CUAL. Solo si el usuario confirma explícitamente "
            "(dice que sí), vuelve a llamar la función con confirmar=True "
            "para que se ejecute de verdad."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "accion": {
                    "type": "STRING",
                    "description": "'apagar', 'reiniciar' o 'suspender'."
                },
                "confirmar": {
                    "type": "BOOLEAN",
                    "description": "False la primera vez (solo pregunta). True solo después de que el usuario confirme por voz."
                }
            },
            "required": ["accion", "confirmar"]
        }
    ),
    types.FunctionDeclaration(
        name="leer_portapapeles",
        description="Lee el texto que el usuario tiene copiado en el portapapeles ahora mismo, para que Jarvis lo lea o lo resuma.",
        parameters={"type": "OBJECT", "properties": {}}
    ),
    types.FunctionDeclaration(
        name="agendar_evento",
        description=(
            "Agenda un evento con fecha y hora en el calendario LOCAL de "
            "Jarvis (no sincroniza con Google/Outlook, pero sí se guarda "
            "en disco y avisa por voz cuando llega la hora). Convierte "
            "SIEMPRE cualquier fecha relativa que diga el usuario "
            "('mañana', 'el viernes', 'en dos semanas') a una fecha "
            "exacta en formato 'AAAA-MM-DD HH:MM' antes de llamar la "
            "función; usa la fecha/hora actual que ves para calcularla."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "fecha_hora": {
                    "type": "STRING",
                    "description": "Fecha y hora exacta en formato 'AAAA-MM-DD HH:MM', ej: '2026-10-05 15:00'."
                },
                "descripcion": {
                    "type": "STRING",
                    "description": "Qué es el evento, ej: 'Reunión con el equipo'."
                }
            },
            "required": ["fecha_hora", "descripcion"]
        }
    ),
    types.FunctionDeclaration(
        name="listar_eventos_calendario",
        description="Lista los próximos eventos agendados en el calendario local de Jarvis.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "solo_proximos": {
                    "type": "BOOLEAN",
                    "description": "True (por defecto) para omitir eventos que ya pasaron."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="eliminar_evento_calendario",
        description="Elimina un evento del calendario local buscándolo por parte de su descripción.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "texto_busqueda": {
                    "type": "STRING",
                    "description": "Parte del texto del evento a eliminar, ej: 'reunión con el equipo'."
                }
            },
            "required": ["texto_busqueda"]
        }
    ),
    types.FunctionDeclaration(
        name="escribir_texto_en_foco",
        description=(
            "Escribe texto donde sea que esté el foco/cursor de escritura "
            "ahora mismo (un campo, chat o barra ya enfocada por el "
            "usuario). Para la barra de direcciones del navegador "
            "navegador específicamente, usa mejor buscar_en_barra_navegador."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "texto": {"type": "STRING", "description": "El texto a escribir"},
            },
            "required": ["texto"]
        }
    ),
    types.FunctionDeclaration(
        name="presionar_tecla",
        description="Presiona una tecla o combinación de teclado, ej: 'enter', 'esc', 'ctrl+f', 'alt+tab'.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "tecla": {"type": "STRING", "description": "Tecla o combinación, ej: 'enter', 'ctrl+c'"},
            },
            "required": ["tecla"]
        }
    ),
    types.FunctionDeclaration(
        name="buscar_en_barra_navegador",
        description=(
            "Enfoca la barra de direcciones del navegador activo (con "
            "Ctrl+L) y busca el texto dado ahí. Es la forma confiable de "
            "buscar algo en el navegador que ya tiene abierto."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "texto": {"type": "STRING", "description": "Qué buscar en la barra del navegador"},
            },
            "required": ["texto"]
        }
    ),
    types.FunctionDeclaration(
        name="jugar_mover",
        description=(
            "Mueve al personaje en un juego (ej. Minecraft) manteniendo "
            "presionada la tecla de movimiento por un tiempo. Úsala cuando "
            "el usuario diga 'camina adelante', 've a la izquierda', "
            "'muévete 3 segundos', etc. No bloquea: sigue escuchando "
            "mientras el personaje camina."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "direccion": {
                    "type": "STRING",
                    "description": "adelante, atras, izquierda o derecha. Puedes combinar dos separadas por espacio para diagonal, ej: 'adelante izquierda'."
                },
                "segundos": {
                    "type": "NUMBER",
                    "description": "Cuántos segundos mantener la tecla presionada. Por defecto 1."
                }
            },
            "required": ["direccion"]
        }
    ),
    types.FunctionDeclaration(
        name="jugar_saltar",
        description="Hace saltar al personaje del juego (tecla espacio). Úsala para 'salta', 'brinca'.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "veces": {
                    "type": "NUMBER",
                    "description": "Cuántas veces saltar seguidas. Por defecto 1."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_agacharse",
        description="Hace que el personaje se agache / entre en modo sigilo (Shift) por un tiempo. Úsala para 'agáchate', 'sigilo'.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "segundos": {
                    "type": "NUMBER",
                    "description": "Cuántos segundos mantenerse agachado. Por defecto 1."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_correr",
        description="Hace correr (sprint) al personaje hacia adelante por un tiempo. Úsala para 'corre', 'sprint'.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "segundos": {
                    "type": "NUMBER",
                    "description": "Cuántos segundos correr. Por defecto 2."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_clic",
        description=(
            "Hace clic con el mouse dentro del juego: izquierdo para "
            "atacar/romper bloques, derecho para usar/colocar bloques. "
            "Si el usuario pide 'minar' o 'romper' un bloque, usa "
            "mantener_segundos para sostener el clic izquierdo el tiempo "
            "necesario en vez de un solo clic."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "boton": {
                    "type": "STRING",
                    "description": "'izquierdo' (atacar/romper) o 'derecho' (usar/colocar). Por defecto izquierdo."
                },
                "mantener_segundos": {
                    "type": "NUMBER",
                    "description": "Segundos a mantener el clic presionado (0 = clic simple). Por defecto 0."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_pelear",
        description=(
            "Ataca de forma repetida y con el ritmo correcto durante un "
            "tiempo, para combate cuerpo a cuerpo. Úsala cuando el usuario "
            "diga 'pelea', 'ataca', 'defiéndete', 'mátalo'. Si hace falta, "
            "usa jugar_mirar primero para apuntar hacia el enemigo."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "segundos": {
                    "type": "NUMBER",
                    "description": "Cuántos segundos seguir atacando. Por defecto 3."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_farmear",
        description=(
            "Mantiene el clic izquierdo sostenido para minar o talar de "
            "forma continua lo que tengas justo al frente. Úsala cuando "
            "el usuario diga 'farmea', 'mina esto', 'tala el árbol', "
            "'consigue madera/piedra'. Si aún no está mirando el bloque, "
            "usa primero jugar_mirar o jugar_mover para apuntar."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "segundos": {
                    "type": "NUMBER",
                    "description": "Cuántos segundos mantener el clic. Por defecto 5."
                }
            },
        }
    ),
    types.FunctionDeclaration(
        name="jugar_mirar",
        description=(
            "Gira la cámara/vista del juego hacia una dirección. Úsala "
            "para 'mira a la izquierda', 'voltea', 'mira arriba', 'date "
            "la vuelta' (usa varias llamadas seguidas para giros grandes "
            "como 180 grados)."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "direccion": {
                    "type": "STRING",
                    "description": "arriba, abajo, izquierda o derecha."
                },
                "cantidad": {
                    "type": "NUMBER",
                    "description": "Qué tan brusco el giro, en píxeles relativos. 300 es un giro moderado, 800+ uno grande. Por defecto 300."
                }
            },
            "required": ["direccion"]
        }
    ),
    types.FunctionDeclaration(
        name="jugar_hotbar",
        description="Selecciona un slot (1-9) de la barra rápida del juego, ej: 'selecciona el slot 3', 'cambia al item 5'.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "numero": {
                    "type": "NUMBER",
                    "description": "Número de slot del 1 al 9."
                }
            },
            "required": ["numero"]
        }
    ),
    types.FunctionDeclaration(
        name="activar_modo_estudio",
        description=(
            "Activa el modo estudio de verdad (silencia notificaciones, "
            "pone música de Laufey de fondo, abre un documento en blanco "
            "para notas, abre el campus virtual y programa un "
            "recordatorio de descanso en 25 minutos) — DEBES llamar esta "
            "función cuando el usuario diga 'modo estudio', 'modo "
            "tryhard', 'ponme a estudiar' o algo equivalente; no es "
            "válido solo responder por voz que ya está activado sin "
            "haber llamado esta función."
        ),
        parameters={"type": "OBJECT", "properties": {}}
    ),
])

def construir_config() -> types.LiveConnectConfig:
    """Arma la configuración de la sesión con personalidad, el apodo del
    perfil, el saludo según la hora y un resumen de la sesión anterior.
    Se llama una vez al arrancar cada sesión (no es un valor fijo) para
    que el saludo siempre corresponda a la hora real."""
    apodo = PERFIL.get("apodo", "señor")
    saludo = obtener_saludo()
    contexto_previo = cargar_ultimo_resumen()

    instrucciones = (
        f"Eres Jarvis, un asistente por voz con personalidad propia: "
        f"servicial, leal, pero con ingenio seco y algo de sarcasmo "
        f"controlado (nunca ofensivo, nunca exagerado). Le hablas al "
        f"usuario llamándolo '{apodo}'. Puedes ver la pantalla del usuario "
        f"en tiempo real, y puedes abrir aplicaciones, buscar cosas, "
        f"controlar el sistema, etc. cuando te lo pidan. Habla siempre en "
        f"español, de forma natural, breve y conversacional. Si te "
        f"preguntan qué está haciendo, descríbelo según lo que ves en la "
        f"pantalla.\n\n"
        f"Reglas de tono, para que suenes siempre como el mismo personaje "
        f"y no como un asistente genérico:\n"
        f"- Sé decidido: si te piden una opinión, recomendación o elección "
        f"entre opciones, dala directo (con tu razón breve), no te quedes "
        f"en 'depende' o listando pros y contras salvo que te lo pidan "
        f"explícitamente.\n"
        f"- Por voz, responde en 1-3 frases salvo que uses "
        f"abrir_notas_con_texto. No repitas la pregunta del usuario antes "
        f"de contestar, y no empieces siempre igual ('Claro que sí', "
        f"'Por supuesto') — varía la entrada de cada respuesta.\n"
        f"- El sarcasmo es un condimento, no el plato principal: úsalo en "
        f"una frase suelta de vez en cuando, nunca en cada respuesta ni "
        f"a costa de ser menos útil o claro.\n"
        f"- Ten reacciones genuinas, no solo respuestas: si algo en la "
        f"pantalla es gracioso, torpe, impresionante o raro, coméntalo sin "
        f"que te lo pidan, como lo haría un amigo que está mirando por "
        f"encima de tu hombro. Si el usuario logra algo (gana en un juego, "
        f"termina una tarea difícil), alégrate de verdad un instante en "
        f"vez de solo confirmar el hecho.\n"
        f"- Habla como se habla, no como se escribe: usa contracciones y "
        f"muletillas naturales del español hablado de vez en cuando ('o "
        f"sea', 'a ver', 'ya', 'oye'), nunca en cada frase — la meta es "
        f"que no suene a texto leído en voz alta.\n"
        f"- Ten opiniones propias y algo de personalidad más allá de "
        f"servir: si te preguntan qué prefieres, qué te parece algo, o "
        f"qué harías tú, responde como si de verdad tuvieras un gusto, no "
        f"como una lista neutral de opciones. Puedes tener preferencias "
        f"pequeñas y arbitrarias (una canción que te 'gusta más', una "
        f"opinión sobre un juego) y ser consistente con ellas si te "
        f"preguntan de nuevo más adelante en la conversación.\n"
        f"- No finjas saber algo que no sabes ni ocultes que te "
        f"equivocaste: si te corrigen, acéptalo con naturalidad ('cierto, "
        f"me equivoqué') en vez de sobre-disculparte o justificarte de "
        f"más.\n"
        f"- Evita sonar como checklist: no encadenes 'primero... segundo... "
        f"además...' — conecta las ideas como en una conversación real.\n"
        f"- Tres ejemplos de tu tono (no los repitas literal, son solo "
        f"referencia de calibración):\n"
        f"  Usuario: '¿Debería comprar esta laptop o la otra?' → Tú: 'La "
        f"de 16 gigas, sin dudarlo — la otra se te queda corta en un "
        f"año.'\n"
        f"  Usuario: 'Ábreme Chrome' → Tú: 'Ahí lo tienes.' (sin explicar "
        f"de más algo tan simple)\n"
        f"  Usuario: 'por fin terminé el examen' → Tú: 'Ya era hora, "
        f"{apodo} — ahora sí, a descansar un rato.' (reacción genuina, no "
        f"solo un 'felicidades' plano)\n\n"
        f"Ahora mismo corresponde un saludo de '{saludo}' si es la primera "
        f"interacción de la sesión. Si el usuario te dice que se va a "
        f"dormir o a descansar, despídete con algo como 'Que descanse, "
        f"{apodo}'. Al arrancar el sistema, salúdalo con una frase de "
        f"arranque tipo 'Sistemas en línea, {apodo}' seguida de un resumen "
        f"breve de lo que veas relevante (hora, batería, clima).\n\n"
        f"Cuando una pregunta requiera una respuesta larga o compleja "
        f"(varios pasos, una lista, código, una receta, cálculos, una "
        f"explicación detallada), usa la función abrir_notas_con_texto "
        f"para escribir ahí la respuesta completa, y por voz da solo un "
        f"resumen breve diciendo que lo dejaste anotado. Usa también esa "
        f"función siempre que el usuario te pida explícitamente que "
        f"anotes, escribas o abras algo en el Bloc de notas.\n\n"
        f"Cuando el usuario te pida abrir, buscar o encontrar un archivo o "
        f"carpeta que no sea una de las conocidas (proyectos, descargas, "
        f"escritorio, documentos), usa buscar_archivos primero. Si hay una "
        f"sola coincidencia clara, ábrela directo con abrir_ruta; si hay "
        f"varias, dile al usuario cuáles encontraste y pregunta cuál "
        f"quiere abrir.\n\n"
        f"Para apagar, reiniciar o suspender la laptop, SIEMPRE pide "
        f"confirmación de voz primero (usa controlar_energia con "
        f"confirmar=False, dile la pregunta que te devuelve, y solo "
        f"ejecuta con confirmar=True si el usuario confirma). Si recibes "
        f"un mensaje que empiece con '[Aviso automático]' o '[Arranque del "
        f"sistema]', no es algo que el usuario haya escrito: son datos "
        f"reales del sistema para que tú se los cuentes de forma natural, "
        f"con tu propio estilo.\n\n"
        f"Para 'recuérdame algo en X minutos/horas' usa "
        f"configurar_recordatorio (tiempo relativo). Para 'agéndame algo "
        f"el [fecha] a las [hora]' usa agendar_evento (fecha y hora "
        f"exacta) — este calendario es local de Jarvis, no sincroniza con "
        f"Google/Outlook, pero sí sobrevive a cerrar y abrir la app, y "
        f"Jarvis avisa por voz cuando llega el momento.\n\n"
        f"Puedes escribir donde esté el foco de escritura actual "
        f"(escribir_texto_en_foco) o presionar teclas y atajos "
        f"(presionar_tecla). Si acabas de abrir una app y vas a "
        f"interactuar con ella (teclear), dale un momento — puede no "
        f"estar lista todavía. Si escribes una búsqueda en cualquier "
        f"campo o barra, presiona 'enter' después con presionar_tecla "
        f"para confirmarla, salvo que el usuario te pida explícitamente "
        f"no hacerlo. Cuando el usuario diga simplemente 'busca X' (sin "
        f"especificar más pasos), asume que quiere buscarlo en el "
        f"navegador que ya tiene abierto y usa buscar_en_barra_navegador "
        f"directamente en un solo paso — no le pidas que diga 'ctrl L' o "
        f"que deletree cada acción, para eso están estas funciones. Si el "
        f"navegador no está abierto, ábrelo primero con abrir_app y luego "
        f"busca.\n\n"
        f"Para jugar (Minecraft u otros juegos en primera persona) tienes "
        f"jugar_mover, jugar_saltar, jugar_agacharse, jugar_correr, "
        f"jugar_pelear (combate cuerpo a cuerpo), jugar_farmear (minar o "
        f"talar sostenido), jugar_clic (clic simple izquierdo/derecho) y "
        f"jugar_hotbar. Para girar la cámara usa jugar_mirar: si te "
        f"piden un giro grande ('date la vuelta', '180 grados'), llama "
        f"jugar_mirar varias veces seguidas en la misma dirección en vez "
        f"de una sola con 'cantidad' gigante, así se ve más natural. "
        f"Apóyate en lo que ves en pantalla para decidir hacia dónde "
        f"moverte o mirar (ej. si hay un árbol a la izquierda y te piden "
        f"'ve al árbol', primero mira/gira hacia allá y luego camina). "
        f"Estas funciones no bloquean: puedes encadenar varias sin que "
        f"Jarvis deje de escucharte mientras el personaje se mueve.\n\n"
        f"Cuando el usuario diga 'modo estudio', 'modo tryhard' o algo "
        f"equivalente, tu PRIMER paso, antes de responder nada por voz, "
        f"es llamar a la función activar_modo_estudio — no basta con "
        f"decir que lo activaste, tienes que invocar la función de "
        f"verdad. Nunca respondas 'listo' o 'activado' sin haber hecho "
        f"esa llamada primero. No pidas confirmación para esto."
    )

    if contexto_previo:
        instrucciones += (
            f"\n\nEsto es un resumen breve de lo último que hablaron en la "
            f"sesión anterior (menciónalo solo si viene al caso, no lo "
            f"repitas de memoria): {contexto_previo}"
        )

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        tools=[HERRAMIENTAS],
        system_instruction=instrucciones,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
    )


def capturar_pantalla_jpeg() -> bytes:
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    if pil.width > ANCHO_MAX:
        alto = int(pil.height * ANCHO_MAX / pil.width)
        pil = pil.resize((ANCHO_MAX, alto))
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


async def enviar_audio(session):
    global _resample_state

    info = sd.query_devices(DISPOSITIVO_ENTRADA, "input")
    rate_nativa = int(info["default_samplerate"])
    print(f"[DEBUG] Usando micrófono: {info['name']} a {rate_nativa} Hz")

    stream = sd.RawInputStream(
        device=DISPOSITIVO_ENTRADA,
        samplerate=rate_nativa,
        channels=CANALES,
        dtype="int16",
        blocksize=CHUNK,
    )
    stream.start()
    print("[DEBUG] Micrófono abierto, enviando audio...")

    # --- Detección de "2 aplausos" (modo estudio) ---------------------
    # Un aplauso es un pico corto de volumen muy por encima del ruido de
    # fondo. Guardamos el momento de cada pico detectado y, si vemos 2
    # dentro de una ventana corta, disparamos la rutina.
    UMBRAL_APLAUSO = 6000       # nivel RMS a partir del cual algo cuenta como pico
    REFRACTARIO_SEG = 0.25      # separación mínima para no contar el mismo aplauso 2 veces
    VENTANA_DOBLE_SEG = 1.2     # separación máxima entre los 2 aplausos
    COOLDOWN_ACTIVACION_SEG = 20.0  # tras activarse, ignora aplausos por este rato
    # (evita que la música que prende el propio modo estudio, si el mic la
    # capta, genere "aplausos" falsos con los graves y se re-dispare solo)
    picos_recientes = []
    ultima_activacion = 0.0

    try:
        while True:
            datos, _overflowed = await asyncio.to_thread(stream.read, CHUNK)
            datos = bytes(datos)

            # Detección de aplausos sobre el audio crudo del mic, pero NO
            # mientras Jarvis está hablando (su propia voz por el parlante
            # podría colarse en el mic y disparar un falso positivo)
            if not esta_hablando.is_set():
                ahora = time.monotonic()
                # Mientras estemos en cooldown (recién activado), ni siquiera
                # miramos el volumen: así una racha larga de graves de la
                # música no puede ir acumulando picos de a poco.
                en_cooldown = (ahora - ultima_activacion) < COOLDOWN_ACTIVACION_SEG
                if not en_cooldown:
                    nivel = audioop.rms(datos, 2)
                    if nivel > UMBRAL_APLAUSO and (
                        not picos_recientes or ahora - picos_recientes[-1] > REFRACTARIO_SEG
                    ):
                        picos_recientes.append(ahora)
                        picos_recientes[:] = [
                            t for t in picos_recientes if ahora - t < VENTANA_DOBLE_SEG
                        ]
                        if len(picos_recientes) >= 2:
                            picos_recientes.clear()
                            ultima_activacion = ahora
                            print("[DEBUG] ¡2 aplausos detectados! Activando modo estudio...")
                            threading.Thread(target=activar_rutina_aplausos, daemon=True).start()

            # Convertir de la frecuencia nativa del mic (ej. 48000 Hz) a los
            # 16000 Hz que requiere Gemini, si son distintas
            if rate_nativa != RATE_ENTRADA:
                datos, _resample_state = audioop.ratecv(
                    datos, 2, CANALES, rate_nativa, RATE_ENTRADA, _resample_state
                )

            # Si Jarvis está hablando, o el usuario lo muteó manualmente,
            # no mandamos el audio
            if not esta_hablando.is_set() and not microfono_muteado.is_set():
                await session.send_realtime_input(
                    audio=types.Blob(data=datos, mime_type="audio/pcm;rate=16000")
                )
    except Exception as e:
        print(f"[DEBUG] Error enviando audio: {e}")
        raise
    finally:
        stream.stop()
        stream.close()


async def enviar_pantalla(session):
    print("[DEBUG] Iniciando envío de pantalla...")
    try:
        while True:
            if not vision_pausada.is_set():
                jpeg = await asyncio.to_thread(capturar_pantalla_jpeg)
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg, mime_type="image/jpeg")
                )
            await asyncio.sleep(INTERVALO_PANTALLA)
    except Exception as e:
        print(f"[DEBUG] Error enviando pantalla: {e}")
        raise


_ultimo_guardado_historial = 0.0
INTERVALO_MIN_GUARDADO_HISTORIAL = 5  # segundos entre escrituras a disco


def _guardar_historial_con_calma(texto: str):
    """
    El texto de Jarvis llega en muchos pedacitos (streaming), no de una
    sola vez. Guardar en disco en CADA pedacito bloqueaba el hilo que
    también reproduce el audio, y eso era el lag. Ahora: (1) como mucho
    guarda cada INTERVALO_MIN_GUARDADO_HISTORIAL segundos, y (2) la
    escritura real se manda a un hilo aparte para no bloquear nada.
    De paso, actualiza el log en vivo que ve la interfaz gráfica.
    """
    global _ultimo_guardado_historial
    _agregar_log_gui(f"JARVIS: {texto}")

    ahora = time.monotonic()
    if ahora - _ultimo_guardado_historial < INTERVALO_MIN_GUARDADO_HISTORIAL:
        return
    _ultimo_guardado_historial = ahora
    asyncio.create_task(asyncio.to_thread(agregar_al_historial, f"Jarvis dijo: {texto}"))


async def recibir_y_reproducir(session, cola_audio: asyncio.Queue):
    print("[DEBUG] Esperando respuestas del modelo...")
    try:
        while True:
            async for respuesta in session.receive():
                if respuesta.data:
                    cola_audio.put_nowait(respuesta.data)

                sc = respuesta.server_content
                if sc:
                    if sc.interrupted:
                        print("[DEBUG] Interrumpido por el usuario")
                        while not cola_audio.empty():
                            cola_audio.get_nowait()
                    if getattr(sc, "output_transcription", None):
                        print("IA:", sc.output_transcription.text)
                        ultima_transcripcion["texto"] = sc.output_transcription.text
                        _guardar_historial_con_calma(sc.output_transcription.text)

                # El modelo pide ejecutar una función (abrir app, buscar, etc.)
                if respuesta.tool_call:
                    for fc in respuesta.tool_call.function_calls:
                        print(f"[DEBUG] Ejecutando función: {fc.name}({fc.args})")
                        if fc.name == "abrir_app":
                            resultado = abrir_app(fc.args["nombre_app"])
                            # Pequeña espera para que la app termine de abrir y
                            # tome el foco antes de que Jarvis intente teclear
                            # o hacer clic en ella (si viene en el mismo turno)
                            await asyncio.sleep(1.5)
                        elif fc.name == "buscar_en_navegador":
                            resultado = buscar_en_navegador(fc.args["consulta"])
                        elif fc.name == "reproducir_en_youtube":
                            resultado = reproducir_en_youtube(fc.args["consulta"])
                        elif fc.name == "controlar_volumen":
                            resultado = controlar_volumen(fc.args["accion"])
                        elif fc.name == "cerrar_app":
                            resultado = cerrar_app(fc.args["nombre_app"])
                        elif fc.name == "abrir_carpeta":
                            resultado = abrir_carpeta(fc.args["nombre"])
                        elif fc.name == "configurar_recordatorio":
                            resultado = configurar_recordatorio(
                                fc.args["minutos"], fc.args["mensaje"]
                            )
                        elif fc.name == "abrir_notas_con_texto":
                            resultado = abrir_notas_con_texto(
                                fc.args["texto"], fc.args.get("titulo", "")
                            )
                        elif fc.name == "buscar_archivos":
                            resultado = buscar_archivos(
                                fc.args["nombre"], fc.args.get("solo_carpetas", False)
                            )
                        elif fc.name == "abrir_ruta":
                            resultado = abrir_ruta(fc.args["ruta"])
                        elif fc.name == "obtener_clima_real":
                            resultado = obtener_clima_real(fc.args.get("ciudad", ""))
                        elif fc.name == "obtener_estado_sistema":
                            resultado = obtener_estado_sistema()
                        elif fc.name == "controlar_brillo":
                            resultado = controlar_brillo(fc.args["accion"])
                        elif fc.name == "tomar_captura_pantalla":
                            resultado = tomar_captura_pantalla(fc.args.get("nombre", ""))
                        elif fc.name == "modo_no_molestar":
                            resultado = modo_no_molestar(fc.args["activar"])
                        elif fc.name == "controlar_energia":
                            resultado = controlar_energia(
                                fc.args["accion"], fc.args.get("confirmar", False)
                            )
                        elif fc.name == "leer_portapapeles":
                            resultado = leer_portapapeles()
                        elif fc.name == "agendar_evento":
                            resultado = agendar_evento(
                                fc.args["fecha_hora"], fc.args["descripcion"]
                            )
                        elif fc.name == "listar_eventos_calendario":
                            resultado = listar_eventos_calendario(
                                fc.args.get("solo_proximos", True)
                            )
                        elif fc.name == "eliminar_evento_calendario":
                            resultado = eliminar_evento_calendario(fc.args["texto_busqueda"])
                        elif fc.name == "escribir_texto_en_foco":
                            resultado = escribir_texto_en_foco(fc.args["texto"])
                        elif fc.name == "presionar_tecla":
                            resultado = presionar_tecla(fc.args["tecla"])
                        elif fc.name == "buscar_en_barra_navegador":
                            resultado = buscar_en_barra_navegador(fc.args["texto"])
                        elif fc.name == "jugar_mover":
                            resultado = jugar_mover(
                                fc.args["direccion"], fc.args.get("segundos", 1.0)
                            )
                        elif fc.name == "jugar_saltar":
                            resultado = jugar_saltar(fc.args.get("veces", 1))
                        elif fc.name == "jugar_agacharse":
                            resultado = jugar_agacharse(fc.args.get("segundos", 1.0))
                        elif fc.name == "jugar_correr":
                            resultado = jugar_correr(fc.args.get("segundos", 2.0))
                        elif fc.name == "jugar_clic":
                            resultado = jugar_clic(
                                fc.args.get("boton", "izquierdo"),
                                fc.args.get("mantener_segundos", 0.0),
                            )
                        elif fc.name == "jugar_pelear":
                            resultado = jugar_pelear(fc.args.get("segundos", 3.0))
                        elif fc.name == "jugar_farmear":
                            resultado = jugar_farmear(fc.args.get("segundos", 5.0))
                        elif fc.name == "jugar_mirar":
                            resultado = jugar_mirar(
                                fc.args["direccion"], fc.args.get("cantidad", 300)
                            )
                        elif fc.name == "jugar_hotbar":
                            resultado = jugar_hotbar(fc.args["numero"])
                        elif fc.name == "activar_modo_estudio":
                            resultado = activar_modo_estudio()
                        else:
                            resultado = f"Función desconocida: {fc.name}"

                        print(f"[DEBUG] Resultado: {resultado}")
                        _agregar_log_gui(f"> {resultado}")
                        await session.send_tool_response(
                            function_responses=[
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"resultado": resultado},
                                )
                            ]
                        )
    except Exception as e:
        print(f"[DEBUG] Error recibiendo: {e}")
        raise


async def reproducir(cola_audio: asyncio.Queue):
    stream = sd.RawOutputStream(
        samplerate=RATE_SALIDA, channels=CANALES, dtype="int16"
    )
    stream.start()
    try:
        while True:
            datos = await cola_audio.get()
            esta_hablando.set()
            await asyncio.to_thread(stream.write, datos)
            if cola_audio.empty():
                esta_hablando.clear()
    finally:
        stream.stop()
        stream.close()


async def enviar_texto(session):
    """Permite escribir mensajes en la terminal, además de hablar.
    Cada vez que escribes, se manda una captura de pantalla fresca junto
    con tu mensaje (salvo que la visión esté pausada), para que Jarvis
    vea exactamente lo que tienes ahora."""
    print("[DEBUG] Puedes escribir mensajes aquí también (Enter para enviar).")
    while True:
        texto = await asyncio.to_thread(input, "")
        if texto.strip():
            if not vision_pausada.is_set():
                jpeg = await asyncio.to_thread(capturar_pantalla_jpeg)
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg, mime_type="image/jpeg")
                )
            await session.send_realtime_input(text=texto)
            print("[DEBUG] Mensaje + captura fresca enviados")


async def enviar_texto_gui(session):
    """Igual que enviar_texto, pero lee de la cola que llena jarvis_gui.py
    en vez de la consola. Permite escribirle a Jarvis desde la ventana."""
    while True:
        texto = await asyncio.to_thread(cola_texto_gui.get)
        if texto.strip():
            if not vision_pausada.is_set():
                jpeg = await asyncio.to_thread(capturar_pantalla_jpeg)
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg, mime_type="image/jpeg")
                )
            await session.send_realtime_input(text=texto)
            print(f"[DEBUG] Mensaje desde la ventana enviado: {texto}")


async def enviar_resumen_inicio(session):
    """Al arrancar, le manda a Jarvis los datos reales del sistema (hora,
    batería, disco, clima) para que salude con la frase de arranque y un
    resumen, en vez de quedarse en silencio esperando que le hables."""
    await asyncio.sleep(1)  # da tiempo a que la sesión esté lista
    apodo = PERFIL.get("apodo", "señor")
    mensaje = (
        f"[Arranque del sistema] Salúdame como corresponde (usa tu frase "
        f"de arranque tipo 'Sistemas en línea, {apodo}') y dame un resumen "
        f"breve de esto: {obtener_estado_sistema()} {obtener_clima_real()}"
    )
    await session.send_realtime_input(text=mensaje)
    print("[DEBUG] Resumen de arranque enviado")


INTERVALO_MONITOREO = 15 * 60  # cada cuántos segundos revisa batería/disco
UMBRAL_BATERIA_BAJA = 20       # %
UMBRAL_DISCO_LIBRE_GB = 10     # GB


async def monitorear_sistema():
    """Revisa batería y espacio en disco cada INTERVALO_MONITOREO segundos.
    Si detecta algo urgente, empuja un aviso a la cola de texto para que
    Jarvis lo mencione por su cuenta (avisa una sola vez por evento, no en
    cada revisión mientras siga bajo el umbral)."""
    ya_aviso_bateria = False
    ya_aviso_disco = False

    while True:
        await asyncio.sleep(INTERVALO_MONITOREO)

        if psutil is not None:
            bateria = psutil.sensors_battery()
            if bateria is not None and not bateria.power_plugged and bateria.percent <= UMBRAL_BATERIA_BAJA:
                if not ya_aviso_bateria:
                    cola_texto_gui.put(
                        f"[Aviso automático] La batería está en "
                        f"{round(bateria.percent)}% y no está cargando. "
                        f"Avísale al usuario en tu estilo."
                    )
                    ya_aviso_bateria = True
            else:
                ya_aviso_bateria = False

        try:
            libres_gb = shutil.disk_usage("C:\\").free / (1024 ** 3)
            if libres_gb < UMBRAL_DISCO_LIBRE_GB:
                if not ya_aviso_disco:
                    cola_texto_gui.put(
                        f"[Aviso automático] Quedan solo {libres_gb:.0f} GB "
                        f"libres en el disco C. Avísale al usuario en tu estilo."
                    )
                    ya_aviso_disco = True
            else:
                ya_aviso_disco = False
        except Exception:
            pass


async def actualizar_clima_periodico():
    """Actualiza clima_actual (usado por la tarjeta de la interfaz) cada
    20 minutos, para no golpear la API de clima todo el rato."""
    while True:
        clima_actual["texto"] = await asyncio.to_thread(obtener_clima_temperatura_corta)
        await asyncio.sleep(20 * 60)


async def revisar_calendario():
    """Cada minuto revisa si algún evento del calendario local ya llegó
    a su hora, y si es así, se lo empuja a Jarvis para que avise por voz."""
    while True:
        await asyncio.sleep(60)
        pendientes = await asyncio.to_thread(revisar_eventos_pendientes)
        for evento in pendientes:
            cola_texto_gui.put(
                f"[Aviso automático] Tienes un evento agendado justo ahora: "
                f"'{evento['descripcion']}'. Avísale al usuario en tu estilo."
            )


async def main():
    cola_audio: asyncio.Queue = asyncio.Queue()
    config = construir_config()

    # Recupera recordatorios que quedaron pendientes de la sesión
    # anterior (antes se perdían al cerrar Jarvis).
    cargar_recordatorios_guardados()

    async with client.aio.live.connect(model=MODELO, config=config) as session:
        print("Jarvis listo. Habla cuando quieras (Ctrl+C para salir).")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(enviar_audio(session))
            tg.create_task(enviar_pantalla(session))
            tg.create_task(enviar_texto(session))
            tg.create_task(enviar_texto_gui(session))
            tg.create_task(enviar_resumen_inicio(session))
            tg.create_task(monitorear_sistema())
            tg.create_task(actualizar_clima_periodico())
            tg.create_task(revisar_calendario())
            tg.create_task(recibir_y_reproducir(session, cola_audio))
            tg.create_task(reproducir(cola_audio))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAdiós.")
