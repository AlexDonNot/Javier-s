"""
jarvis_acciones.py
-------------------
Funciones que Jarvis puede ejecutar en tu laptop.
Cada función que quieras que Jarvis pueda "hacer" va aquí, y luego
se la declaras al modelo (ver jarvis_live.py) para que sepa que existe.

Paquetes nuevos que puede que necesites instalar para las funciones de
más abajo (todas son opcionales: si falta alguna, esa función te avisa
en vez de tronar):
    pip install psutil pyperclip wmi pywin32 pyautogui
"""

import ctypes
import datetime
import json
import os
import random
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser

import requests

try:
    import psutil
except ImportError:
    psutil = None

# ---------------------------------------------------------
# Registro de apps conocidas: nombre que dirás por voz -> comando
# para abrirla. Agrega las que uses seguido.
# ---------------------------------------------------------
APPS = {
    "spotify": "spotify",
    "chrome": "chrome",
    "navegador": "chrome",
    "calculadora": "calc",
    "notas": "notepad",
    "bloc de notas": "notepad",
    "explorador de archivos": "explorer",
    "word": "winword",
    "excel": "excel",
}

# Nombre del proceso real (.exe) de cada app, para poder CERRARLA con taskkill.
# Si "cerrar_app" no funciona con alguna app, revisa el nombre exacto del
# proceso en el Administrador de Tareas (pestaña "Detalles") y ajústalo aquí.
PROCESOS = {
    "spotify": "Spotify.exe",
    "chrome": "chrome.exe",
    "navegador": "chrome.exe",
    "calculadora": "CalculatorApp.exe",
    "notas": "notepad.exe",
    "bloc de notas": "notepad.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
}

# Carpetas que Jarvis puede abrir por nombre. AJUSTA ESTAS RUTAS a las tuyas
# reales (la de "proyectos" es solo un ejemplo, cámbiala a donde de verdad
# guardas tus proyectos).
CARPETAS = {
    "proyectos": r"C:\Users\mbroa\OneDrive\jarvis",
    "descargas": os.path.expanduser("~\\Downloads"),
    "escritorio": os.path.expanduser("~\\Desktop"),
    "documentos": os.path.expanduser("~\\Documents"),
}

# Función que se llama para "avisarle" algo a Jarvis (ej. un recordatorio
# cuando se cumple el tiempo). jarvis_live.py la configura al arrancar.
_notificar = None


def set_notificador(func):
    """jarvis_live.py llama esto una vez, al inicio, para que los
    recordatorios sepan cómo mandarle un mensaje a Jarvis."""
    global _notificar
    _notificar = func


def abrir_app(nombre_app: str) -> str:
    """
    Abre una aplicación por nombre. Devuelve un mensaje que Jarvis
    puede usar para confirmarte lo que hizo.
    """
    clave = nombre_app.strip().lower()
    comando = APPS.get(clave)

    if comando is None:
        return (
            f"No reconozco la app '{nombre_app}'. Puedo abrir: "
            + ", ".join(APPS.keys())
        )

    try:
        # "start" es el comando de Windows para abrir programas/atajos
        subprocess.Popen(f"start {comando}", shell=True)
        return f"Abriendo {nombre_app}."
    except Exception as e:
        return f"No pude abrir {nombre_app}: {e}"


def buscar_en_navegador(consulta: str) -> str:
    """
    Abre el navegador default en una búsqueda de Google con la consulta dada.
    Devuelve un mensaje que Jarvis puede usar para confirmarte lo que hizo.
    """
    try:
        consulta_codificada = urllib.parse.quote_plus(consulta)
        url = f"https://www.google.com/search?q={consulta_codificada}"
        webbrowser.open(url)
        return f"Buscando '{consulta}' en el navegador."
    except Exception as e:
        return f"No pude abrir la búsqueda: {e}"


def buscar_en_youtube(consulta: str) -> str:
    """
    Abre el navegador con los resultados de búsqueda de YouTube para la
    consulta dada (no reproduce el primer video automáticamente, pero deja
    los resultados listos para que el usuario elija con un clic).
    """
    try:
        consulta_codificada = urllib.parse.quote_plus(consulta)
        url = f"https://www.youtube.com/results?search_query={consulta_codificada}"
        webbrowser.open(url)
        return f"Buscando '{consulta}' en YouTube."
    except Exception as e:
        return f"No pude abrir la búsqueda en YouTube: {e}"


def reproducir_en_youtube(consulta: str) -> str:
    """
    Busca en YouTube usando la API oficial y abre directo el primer
    resultado, reproduciéndolo automáticamente.
    Requiere la variable de entorno YOUTUBE_API_KEY.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return "Falta configurar YOUTUBE_API_KEY para poder reproducir directo."

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": consulta,
                "type": "video",
                "maxResults": 1,
                "key": api_key,
            },
            timeout=5,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])

        if not items:
            return f"No encontré resultados en YouTube para '{consulta}'."

        video_id = items[0]["id"]["videoId"]
        titulo = items[0]["snippet"]["title"]
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
        return f"Reproduciendo '{titulo}' en YouTube."
    except Exception as e:
        return f"No pude reproducir en YouTube: {e}"


# --- Control de volumen -------------------------------------------------
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF


def _tecla_multimedia(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP


def controlar_volumen(accion: str) -> str:
    """
    Sube, baja o silencia el volumen del sistema.
    accion: "subir", "bajar" o "silenciar".
    """
    accion = accion.strip().lower()
    if "sub" in accion:
        for _ in range(4):
            _tecla_multimedia(_VK_VOLUME_UP)
        return "Subiendo el volumen."
    elif "baj" in accion:
        for _ in range(4):
            _tecla_multimedia(_VK_VOLUME_DOWN)
        return "Bajando el volumen."
    elif "silenci" in accion or "mut" in accion:
        _tecla_multimedia(_VK_VOLUME_MUTE)
        return "Listo, alterné el silencio (mute) del sistema."
    else:
        return f"No entendí qué hacer con el volumen: '{accion}'"


# --- Cerrar aplicaciones --------------------------------------------------
def cerrar_app(nombre_app: str) -> str:
    """Cierra (fuerza el cierre de) una aplicación por nombre."""
    clave = nombre_app.strip().lower()
    proceso = PROCESOS.get(clave)

    if proceso is None:
        return (
            f"No sé el proceso exacto de '{nombre_app}' para cerrarlo. "
            "Puedo cerrar: " + ", ".join(PROCESOS.keys())
        )

    try:
        resultado = subprocess.run(
            ["taskkill", "/IM", proceso, "/F"],
            capture_output=True, text=True
        )
        if resultado.returncode == 0:
            return f"Cerré {nombre_app}."
        else:
            return f"{nombre_app} no parecía estar abierto (o no pude cerrarlo)."
    except Exception as e:
        return f"No pude cerrar {nombre_app}: {e}"


# --- Abrir carpetas -------------------------------------------------------
def abrir_carpeta(nombre: str) -> str:
    """Abre una carpeta conocida (ver diccionario CARPETAS) en el explorador."""
    clave = nombre.strip().lower()
    ruta = CARPETAS.get(clave)

    if ruta is None:
        return (
            f"No reconozco la carpeta '{nombre}'. Conozco: "
            + ", ".join(CARPETAS.keys())
        )

    try:
        os.startfile(ruta)
        return f"Abriendo la carpeta {nombre}."
    except Exception as e:
        return f"No pude abrir la carpeta {nombre}: {e}"


# --- Bloc de notas (para respuestas largas/complejas) ---------------------
# Carpeta donde se guardan las notas que Jarvis abre en el Bloc de notas.
CARPETA_NOTAS = os.path.expanduser("~\\Documents\\Jarvis_Notas")


def abrir_notas_con_texto(texto: str, titulo: str = "") -> str:
    """
    Escribe 'texto' en un archivo .txt nuevo y lo abre con el Bloc de
    notas (notepad), para que el usuario lo pueda leer con calma en vez
    de (o además de) escucharlo por voz.

    Pensado para que Jarvis lo use solo cuando la respuesta amerite verse
    escrita: explicaciones largas, listas, pasos, código, recetas, etc.
    También se usa cuando el usuario lo pide directamente ("anótalo",
    "escríbelo", "ábrelo en el bloc de notas").
    """
    try:
        os.makedirs(CARPETA_NOTAS, exist_ok=True)

        marca_tiempo = time.strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"nota_{marca_tiempo}.txt"
        ruta = os.path.join(CARPETA_NOTAS, nombre_archivo)

        contenido = texto.strip()
        if titulo:
            contenido = f"{titulo}\n{'=' * len(titulo)}\n\n{contenido}"

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)

        # "start" para que se abra en una ventana normal de notepad,
        # igual que el resto de abrir_app()
        subprocess.Popen(f'start notepad "{ruta}"', shell=True)

        return "Listo, lo abrí en el Bloc de notas para que lo puedas leer."
    except Exception as e:
        return f"No pude abrir el Bloc de notas: {e}"


# --- Buscar archivos y carpetas en la laptop -------------------------------
# Carpetas raíz donde Jarvis busca por defecto. No se escanea "todo el
# disco" porque sería lentísimo; agrega o quita rutas según dónde
# realmente guardes tus cosas (ej. una carpeta de otro disco, D:\...).
RAICES_BUSQUEDA = [
    os.path.expanduser("~\\Desktop"),
    os.path.expanduser("~\\Documents"),
    os.path.expanduser("~\\Downloads"),
    os.path.expanduser("~\\OneDrive"),
]

# Carpetas que no vale la pena recorrer (basura, cachés, control de versiones)
CARPETAS_IGNORADAS = {
    "node_modules", ".git", "__pycache__", "$RECYCLE.BIN",
    "System Volume Information", ".venv", "venv",
}

MAX_RESULTADOS_BUSQUEDA = 15
MAX_ARCHIVOS_REVISADOS = 20000  # límite de seguridad para no colgar la búsqueda


def buscar_archivos(nombre: str, solo_carpetas: bool = False) -> str:
    """
    Busca archivos o carpetas cuyo nombre contenga 'nombre' (sin importar
    mayúsculas/minúsculas ni acentos exactos) dentro de las carpetas
    típicas del usuario (Escritorio, Documentos, Descargas, OneDrive).
    Devuelve hasta MAX_RESULTADOS_BUSQUEDA rutas encontradas, para que
    luego se abra la que corresponda con abrir_ruta().
    """
    nombre_buscado = nombre.strip().lower()
    if not nombre_buscado:
        return "Dime qué archivo o carpeta buscar."

    encontrados = []
    revisados = 0

    for raiz in RAICES_BUSQUEDA:
        if not os.path.isdir(raiz):
            continue

        for carpeta_actual, subcarpetas, archivos in os.walk(raiz):
            # No bajar a carpetas basura/pesadas
            subcarpetas[:] = [c for c in subcarpetas if c not in CARPETAS_IGNORADAS]

            for subcarpeta in subcarpetas:
                revisados += 1
                if nombre_buscado in subcarpeta.lower():
                    encontrados.append(os.path.join(carpeta_actual, subcarpeta))

            if not solo_carpetas:
                for archivo in archivos:
                    revisados += 1
                    if nombre_buscado in archivo.lower():
                        encontrados.append(os.path.join(carpeta_actual, archivo))

            if len(encontrados) >= MAX_RESULTADOS_BUSQUEDA or revisados >= MAX_ARCHIVOS_REVISADOS:
                break

        if len(encontrados) >= MAX_RESULTADOS_BUSQUEDA or revisados >= MAX_ARCHIVOS_REVISADOS:
            break

    if not encontrados:
        return f"No encontré nada llamado '{nombre}' en tus carpetas habituales (Escritorio, Documentos, Descargas, OneDrive)."

    lista = "\n".join(f"- {ruta}" for ruta in encontrados[:MAX_RESULTADOS_BUSQUEDA])
    return f"Encontré esto para '{nombre}':\n{lista}"


def abrir_ruta(ruta: str) -> str:
    """
    Abre un archivo o carpeta dada su ruta completa (normalmente una de
    las que devolvió buscar_archivos). Si es un archivo, lo abre con su
    programa por defecto; si es una carpeta, la abre en el explorador.
    """
    ruta = ruta.strip().strip('"')
    if not os.path.exists(ruta):
        return f"No encontré nada en la ruta '{ruta}'."

    try:
        os.startfile(ruta)
        tipo = "la carpeta" if os.path.isdir(ruta) else "el archivo"
        return f"Abriendo {tipo} {os.path.basename(ruta)}."
    except Exception as e:
        return f"No pude abrir '{ruta}': {e}"


# --- Perfil del usuario (para que Jarvis "te conozca") --------------------
# OJO: esto NO se guarda en la carpeta del proyecto (que suele estar
# dentro de OneDrive) sino en una carpeta local del usuario. Guardarlo
# dentro de una carpeta sincronizada hacía que OneDrive detectara el
# archivo cambiando todo el rato y disparara resincronizaciones — eso
# generaba micro-lags/bajones de FPS mientras Jarvis corría.
CARPETA_DATOS_LOCAL = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Jarvis"
)
os.makedirs(CARPETA_DATOS_LOCAL, exist_ok=True)

RUTA_PERFIL = os.path.join(CARPETA_DATOS_LOCAL, "perfil_usuario.json")

PERFIL_POR_DEFECTO = {
    "apodo": "señor",
    "ciudad_clima": "Lima,PE",
    "apps_favoritas": [],
    "rutinas": {},
}


def cargar_perfil() -> dict:
    """Carga (o crea si no existe) perfil_usuario.json con tus
    preferencias: cómo te llama Jarvis, tu ciudad para el clima, etc.
    Edita ese archivo a mano para personalizarlo."""
    if not os.path.exists(RUTA_PERFIL):
        try:
            with open(RUTA_PERFIL, "w", encoding="utf-8") as f:
                json.dump(PERFIL_POR_DEFECTO, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return dict(PERFIL_POR_DEFECTO)

    try:
        with open(RUTA_PERFIL, "r", encoding="utf-8") as f:
            perfil = json.load(f)
        for clave, valor in PERFIL_POR_DEFECTO.items():
            perfil.setdefault(clave, valor)
        return perfil
    except Exception:
        return dict(PERFIL_POR_DEFECTO)


PERFIL = cargar_perfil()


# --- Historial corto entre sesiones ---------------------------------------
# Misma razón que el perfil: fuera de OneDrive, en la carpeta local.
RUTA_HISTORIAL = os.path.join(CARPETA_DATOS_LOCAL, "jarvis_historial.json")
MAX_ENTRADAS_HISTORIAL = 20


def cargar_ultimo_resumen() -> str:
    """Lee lo último que se guardó de la sesión anterior, para dárselo de
    contexto a Jarvis al arrancar (así no empieza siempre 'en blanco')."""
    if not os.path.exists(RUTA_HISTORIAL):
        return ""
    try:
        with open(RUTA_HISTORIAL, "r", encoding="utf-8") as f:
            entradas = json.load(f)
        return " / ".join(entradas[-6:])
    except Exception:
        return ""


def agregar_al_historial(texto: str):
    """Agrega una línea al historial persistente en disco (recorta a las
    últimas MAX_ENTRADAS_HISTORIAL)."""
    texto = (texto or "").strip()
    if not texto:
        return
    entradas = []
    if os.path.exists(RUTA_HISTORIAL):
        try:
            with open(RUTA_HISTORIAL, "r", encoding="utf-8") as f:
                entradas = json.load(f)
        except Exception:
            entradas = []
    entradas.append(texto)
    entradas = entradas[-MAX_ENTRADAS_HISTORIAL:]
    try:
        with open(RUTA_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(entradas, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Saludo según la hora ---------------------------------------------
def obtener_saludo() -> str:
    hora = datetime.datetime.now().hour
    if 5 <= hora < 12:
        return "Buenos días"
    elif 12 <= hora < 19:
        return "Buenas tardes"
    else:
        return "Buenas noches"


# --- Clima real (OpenWeather) ------------------------------------------
def obtener_clima_real(ciudad: str = "") -> str:
    """
    Consulta el clima actual con la API de OpenWeather.
    Requiere la variable de entorno OPENWEATHER_API_KEY
    (gratis en https://openweathermap.org/api).
    """
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        return "Falta configurar OPENWEATHER_API_KEY para darte el clima real."

    ciudad = (ciudad or "").strip() or PERFIL.get("ciudad_clima", "Lima,PE")

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": ciudad, "appid": api_key, "units": "metric", "lang": "es"},
            timeout=5,
        )
        resp.raise_for_status()
        datos = resp.json()
        descripcion = datos["weather"][0]["description"]
        temp = datos["main"]["temp"]
        sensacion = datos["main"]["feels_like"]
        return (
            f"En {ciudad.split(',')[0]} hay {descripcion}, {temp:.0f}°C "
            f"(sensación de {sensacion:.0f}°C)."
        )
    except Exception as e:
        return f"No pude obtener el clima: {e}"


def obtener_clima_temperatura_corta(ciudad: str = "") -> str:
    """Como obtener_clima_real, pero devuelve solo la temperatura corta
    (ej. '23°C'). Pensada para mostrarse en una tarjeta de la interfaz
    gráfica, no para que la use el modelo por voz."""
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        return "N/D"

    ciudad = (ciudad or "").strip() or PERFIL.get("ciudad_clima", "Lima,PE")
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": ciudad, "appid": api_key, "units": "metric", "lang": "es"},
            timeout=5,
        )
        resp.raise_for_status()
        temp = resp.json()["main"]["temp"]
        return f"{temp:.0f}°C"
    except Exception:
        return "N/D"


# --- Estado del sistema (para el resumen al arrancar y avisos) --------
def obtener_estado_sistema() -> str:
    """Resumen corto: hora, batería y espacio libre en disco C."""
    ahora = datetime.datetime.now().strftime("%H:%M")
    partes = [f"Son las {ahora}."]

    if psutil is not None:
        bateria = psutil.sensors_battery()
        if bateria is not None:
            estado = "cargando" if bateria.power_plugged else "sin cargador"
            partes.append(f"Batería al {round(bateria.percent)}% ({estado}).")
    else:
        partes.append("(instala 'psutil' para ver batería y disco.)")

    try:
        uso = shutil.disk_usage("C:\\")
        partes.append(f"Quedan {uso.free / (1024 ** 3):.0f} GB libres en el disco C.")
    except Exception:
        pass

    return " ".join(partes)


# --- Brillo de pantalla --------------------------------------------------
def controlar_brillo(accion) -> str:
    """
    Sube, baja o fija el brillo de la pantalla (0-100).
    'accion' puede ser 'subir', 'bajar', o un número.
    Requiere: pip install wmi pywin32. Solo funciona en pantallas que
    soporten brillo por WMI (típico en laptops; algunos monitores
    externos no lo soportan).
    """
    try:
        import wmi
    except ImportError:
        return "Falta instalar 'wmi' y 'pywin32' (pip install wmi pywin32) para controlar el brillo."

    try:
        conexion = wmi.WMI(namespace="wmi")
        metodos = conexion.WmiMonitorBrightnessMethods()[0]
        brillo_actual = conexion.WmiMonitorBrightness()[0].CurrentBrightness

        texto_accion = str(accion).strip().lower()
        if texto_accion.replace(".", "", 1).isdigit():
            nuevo = max(0, min(100, int(float(texto_accion))))
        elif "sub" in texto_accion:
            nuevo = min(100, brillo_actual + 20)
        elif "baj" in texto_accion:
            nuevo = max(0, brillo_actual - 20)
        else:
            return f"No entendí qué hacer con el brillo: '{accion}'"

        metodos.WmiSetBrightness(nuevo, 0)
        return f"Brillo ajustado a {nuevo}%."
    except Exception as e:
        return f"No pude cambiar el brillo: {e}"


# --- Captura de pantalla --------------------------------------------------
def tomar_captura_pantalla(nombre: str = "") -> str:
    """Toma una captura de pantalla completa y la guarda en
    ~/Pictures/Jarvis_Capturas."""
    try:
        import mss
    except ImportError:
        return "Falta instalar 'mss' para tomar capturas."

    carpeta = os.path.expanduser("~\\Pictures\\Jarvis_Capturas")
    os.makedirs(carpeta, exist_ok=True)
    marca_tiempo = time.strftime("%Y-%m-%d_%H-%M-%S")
    ruta = os.path.join(carpeta, f"{(nombre or 'captura').strip()}_{marca_tiempo}.png")

    try:
        with mss.mss() as sct:
            sct.shot(mon=-1, output=ruta)
        return f"Guardé la captura en {ruta}."
    except Exception as e:
        return f"No pude tomar la captura: {e}"


# --- Modo no molestar (silenciar notificaciones de Windows) --------------
def modo_no_molestar(activar) -> str:
    """Activa/desactiva las notificaciones (toast) de Windows como una
    versión simple de 'no molestar'. activar: True para silenciar."""
    try:
        import winreg
    except ImportError:
        return "Esto solo funciona en Windows."

    if isinstance(activar, str):
        activar = activar.strip().lower() in ("true", "si", "sí", "activar", "on", "1")

    valor = 0 if activar else 1
    try:
        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(clave, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 0, winreg.REG_DWORD, valor)
        winreg.CloseKey(clave)
        return "Modo no molestar activado, silencié las notificaciones." if activar else "Notificaciones reactivadas."
    except Exception as e:
        return f"No pude cambiar el modo no molestar: {e}"


# --- Apagar / reiniciar / suspender (con confirmación) ---------------------
def controlar_energia(accion: str, confirmar=False) -> str:
    """
    Apaga, reinicia o suspende la laptop.
    SIEMPRE pide confirmación primero: si confirmar=False solo devuelve
    una pregunta y NO hace nada. Solo ejecuta si se llama de nuevo con
    confirmar=True, después de que el usuario confirme por voz.
    """
    accion = accion.strip().lower()
    comandos = {
        "apagar": "shutdown /s /t 5",
        "reiniciar": "shutdown /r /t 5",
        "suspender": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    }

    if accion not in comandos:
        return f"No sé cómo '{accion}'. Puedo: apagar, reiniciar o suspender."

    if isinstance(confirmar, str):
        confirmar = confirmar.strip().lower() in ("true", "si", "sí", "1")

    if not confirmar:
        apodo = PERFIL.get("apodo", "señor")
        return f"¿Seguro que quiere que {accion} la laptop, {apodo}? Confírmelo y lo hago."

    try:
        subprocess.Popen(comandos[accion], shell=True)
        return f"Entendido. Voy a {accion} la laptop."
    except Exception as e:
        return f"No pude {accion} la laptop: {e}"


def escribir_texto_en_foco(texto: str) -> str:
    """
    Escribe 'texto' donde sea que esté el foco de escritura ahora mismo
    (un campo, una barra de búsqueda, un chat ya abierto, etc.). Úsala
    DESPUÉS de asegurarte de que el campo correcto ya
    está enfocado.
    """
    try:
        import pyautogui
    except ImportError:
        return "Falta instalar 'pyautogui' (pip install pyautogui) para escribir."

    try:
        pyautogui.write(texto, interval=0.02)
        return "Texto escrito."
    except Exception as e:
        return f"No pude escribir el texto: {e}"


def presionar_tecla(tecla: str) -> str:
    """
    Presiona una tecla o combinación. Ejemplos válidos: 'enter', 'esc',
    'tab', 'ctrl+f', 'ctrl+c', 'alt+tab'.
    """
    try:
        import pyautogui
    except ImportError:
        return "Falta instalar 'pyautogui' (pip install pyautogui) para presionar teclas."

    try:
        teclas = [t.strip() for t in tecla.strip().lower().split("+")]
        if len(teclas) > 1:
            pyautogui.hotkey(*teclas)
        else:
            pyautogui.press(teclas[0])
        return f"Tecla '{tecla}' presionada."
    except Exception as e:
        return f"No pude presionar '{tecla}': {e}"


def buscar_en_barra_navegador(texto: str) -> str:
    """
    Enfoca la barra de direcciones del navegador activo con Ctrl+L
    (funciona en Chrome, Edge y Firefox) y busca 'texto' ahí. Mucho más
    confiable que estimar dónde hacer clic en la barra, porque no
    depende de coordenadas visuales.
    """
    try:
        import pyautogui
    except ImportError:
        return "Falta instalar 'pyautogui' (pip install pyautogui) para esto."

    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.15)
        pyautogui.write(texto, interval=0.02)
        pyautogui.press("enter")
        return f"Busqué '{texto}' en la barra del navegador."
    except Exception as e:
        return f"No pude buscar en la barra del navegador: {e}"


# --- Control de juegos (Minecraft y similares) ------------------------------
# Usa pydirectinput en vez de pyautogui para esto: la mayoría de juegos
# ignoran los eventos de teclado "normales" de Windows (SendInput básico) y
# solo responden a DirectInput, que es justo lo que simula pydirectinput.
# Instalación:  pip install pydirectinput
#
# Todas estas funciones sueltan la tecla o el botón SOLAS en un hilo aparte
# (como ya haces en configurar_recordatorio), así Jarvis no se queda "mudo"
# ni deja de escuchar mientras el personaje camina o mina.

_TECLAS_DIRECCION = {
    "adelante": "w", "arriba": "w", "w": "w",
    "atras": "s", "atrás": "s", "abajo": "s", "s": "s",
    "izquierda": "a", "a": "a",
    "derecha": "d", "d": "d",
}


def _lib_input():
    """pydirectinput si está instalado (mejor para juegos); si no, cae de
    vuelta a pyautogui para que al menos algo funcione."""
    try:
        import pydirectinput
        pydirectinput.PAUSE = 0.0  # sin el delay de 0.1s que trae por defecto
        pydirectinput.FAILSAFE = False
        return pydirectinput
    except ImportError:
        try:
            import pyautogui
            return pyautogui
        except ImportError:
            return None


def jugar_mover(direccion: str, segundos: float = 1.0) -> str:
    """
    Mantiene presionada la tecla de movimiento (W/A/S/D) por 'segundos'.
    'direccion' acepta: adelante, atras, izquierda, derecha, o
    combinaciones separadas por espacio para moverse en diagonal, ej:
    'adelante izquierda'. No bloquea: la tecla se suelta sola en otro hilo.
    """
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para mover el personaje."

    try:
        segundos = float(segundos)
    except (TypeError, ValueError):
        segundos = 1.0
    segundos = max(0.05, min(segundos, 10.0))  # tope de seguridad: 10s

    palabras = direccion.strip().lower().split()
    teclas = [_TECLAS_DIRECCION[p] for p in palabras if p in _TECLAS_DIRECCION]
    if not teclas:
        return f"No reconozco la dirección '{direccion}'. Usa adelante, atrás, izquierda o derecha."

    def _hilo():
        for t in teclas:
            lib.keyDown(t)
        time.sleep(segundos)
        for t in teclas:
            lib.keyUp(t)

    threading.Thread(target=_hilo, daemon=True).start()
    return f"Caminando {direccion} por {segundos:.1f} segundos."


def jugar_saltar(veces: int = 1) -> str:
    """Presiona la tecla de salto (espacio) 'veces' veces seguidas."""
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para saltar."
    try:
        veces = max(1, min(int(veces), 10))
    except (TypeError, ValueError):
        veces = 1

    def _hilo():
        for _ in range(veces):
            lib.press("space")
            time.sleep(0.15)

    threading.Thread(target=_hilo, daemon=True).start()
    return "Saltando." if veces == 1 else f"Saltando {veces} veces."


def jugar_agacharse(segundos: float = 1.0) -> str:
    """Mantiene presionado agacharse/sigilo (Shift izquierdo) por 'segundos'."""
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para agacharte."
    try:
        segundos = max(0.1, min(float(segundos), 10.0))
    except (TypeError, ValueError):
        segundos = 1.0

    def _hilo():
        lib.keyDown("shift")
        time.sleep(segundos)
        lib.keyUp("shift")

    threading.Thread(target=_hilo, daemon=True).start()
    return f"Agachado por {segundos:.1f} segundos."


def jugar_correr(segundos: float = 2.0) -> str:
    """
    Corre hacia adelante manteniendo Ctrl izquierdo (sprint) + W por
    'segundos'. En Minecraft, sprint por defecto es Ctrl+W (o doble W).
    """
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para correr."
    try:
        segundos = max(0.1, min(float(segundos), 10.0))
    except (TypeError, ValueError):
        segundos = 2.0

    def _hilo():
        lib.keyDown("ctrl")
        lib.keyDown("w")
        time.sleep(segundos)
        lib.keyUp("w")
        lib.keyUp("ctrl")

    threading.Thread(target=_hilo, daemon=True).start()
    return f"Corriendo adelante por {segundos:.1f} segundos."


def jugar_clic(boton: str = "izquierdo", mantener_segundos: float = 0.0) -> str:
    """
    Clic con el mouse del juego: 'izquierdo' (atacar/romper bloque) o
    'derecho' (usar/colocar bloque). Si 'mantener_segundos' > 0, mantiene
    el botón presionado ese tiempo (útil para minar un bloque), sin
    bloquear el resto de Jarvis mientras tanto.
    """
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para hacer clic."

    boton = boton.strip().lower()
    boton_lib = "left" if boton in ("izquierdo", "left", "atacar", "romper") else "right"
    try:
        mantener_segundos = max(0.0, min(float(mantener_segundos), 15.0))
    except (TypeError, ValueError):
        mantener_segundos = 0.0

    if mantener_segundos <= 0:
        try:
            lib.click(button=boton_lib)
            return f"Clic {boton} hecho."
        except Exception as e:
            return f"No pude hacer clic: {e}"

    def _hilo():
        lib.mouseDown(button=boton_lib)
        time.sleep(mantener_segundos)
        lib.mouseUp(button=boton_lib)

    threading.Thread(target=_hilo, daemon=True).start()
    return f"Manteniendo clic {boton} por {mantener_segundos:.1f} segundos."


def jugar_mirar(direccion: str, cantidad: int = 300) -> str:
    """
    Gira la cámara del juego (movimiento RELATIVO del mouse), no mueve el
    cursor de Windows a una posición. 'direccion': arriba, abajo,
    izquierda, derecha. 'cantidad' son píxeles relativos aproximados del
    giro (300 = giro moderado; más grande = giro más brusco).
    """
    try:
        cantidad = max(1, min(int(cantidad), 2000))
    except (TypeError, ValueError):
        cantidad = 300

    dx, dy = 0, 0
    direccion = direccion.strip().lower()
    if direccion in ("derecha", "right"):
        dx = cantidad
    elif direccion in ("izquierda", "left"):
        dx = -cantidad
    elif direccion in ("abajo", "down"):
        dy = cantidad
    elif direccion in ("arriba", "up"):
        dy = -cantidad
    else:
        return f"No reconozco la dirección de cámara '{direccion}'."

    try:
        # MOUSEEVENTF_MOVE (0x0001) manda un movimiento RELATIVO del mouse,
        # que es justo lo que leen los juegos en primera persona para
        # rotar la cámara. pyautogui.moveTo/pydirectinput.moveTo mueven el
        # cursor a una posición absoluta de PANTALLA y no sirven aquí,
        # porque dentro del juego no hay un cursor visible que reposicionar.
        ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
        return f"Mirando hacia {direccion}."
    except Exception as e:
        return f"No pude mover la cámara: {e}"


def jugar_pelear(segundos: float = 3.0) -> str:
    """
    Ataca repetidamente con clic izquierdo por 'segundos', con una pausa
    entre golpes cercana al cooldown de ataque de Minecraft (~0.55s, para
    que los golpes salgan a fuerza completa en vez de spamear clics
    débiles). Úsala para 'pelea', 'ataca', 'defiéndete'. No bloquea:
    golpea sola en un hilo aparte mientras Jarvis te sigue escuchando.
    """
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para pelear."
    try:
        segundos = max(0.3, min(float(segundos), 15.0))
    except (TypeError, ValueError):
        segundos = 3.0

    def _hilo():
        fin = time.time() + segundos
        while time.time() < fin:
            lib.click(button="left")
            time.sleep(0.55)

    threading.Thread(target=_hilo, daemon=True).start()
    return f"Peleando por {segundos:.1f} segundos."


def jugar_farmear(segundos: float = 5.0) -> str:
    """
    Mantiene el clic izquierdo presionado por 'segundos' para minar o
    talar de forma continua lo que tengas justo al frente (un bloque, un
    tronco, un cultivo). Úsala para 'farmea', 'mina esto', 'tala el
    árbol'. Si el usuario ya te dijo hacia dónde mirar/caminar, hazlo
    primero con jugar_mirar/jugar_mover y luego llama a esta. No bloquea.
    """
    return jugar_clic("izquierdo", segundos)


def jugar_hotbar(numero) -> str:
    """Selecciona un slot de la barra rápida (hotbar) del 1 al 9."""
    lib = _lib_input()
    if lib is None:
        return "Falta instalar 'pydirectinput' (pip install pydirectinput) para esto."
    try:
        numero = int(numero)
    except (TypeError, ValueError):
        return f"'{numero}' no es un número de slot válido."
    if not (1 <= numero <= 9):
        return "El slot de la barra rápida debe ser del 1 al 9."
    try:
        lib.press(str(numero))
        return f"Slot {numero} seleccionado."
    except Exception as e:
        return f"No pude seleccionar el slot: {e}"


# --- Modo estudio (por voz: "modo tryhard"/"modo estudio", o por 2 aplausos) ---
_ULTIMA_ACTIVACION_MODO_ESTUDIO = 0.0
_COOLDOWN_MODO_ESTUDIO_SEG = 30.0  # evita reabrir todo si se llama 2 veces seguidas


def activar_modo_estudio() -> str:
    """
    Activa el 'modo estudio': silencia notificaciones, pone música de
    fondo de Laufey, abre un documento en blanco para tomar notas, abre
    el campus virtual de la universidad y programa un recordatorio de
    descanso en 25 minutos. Úsala cuando el usuario diga 'modo estudio',
    'modo tryhard', 'ponme a estudiar' o algo similar.
    """
    global _ULTIMA_ACTIVACION_MODO_ESTUDIO

    ahora = time.monotonic()
    segundos_desde_ultima = ahora - _ULTIMA_ACTIVACION_MODO_ESTUDIO
    if segundos_desde_ultima < _COOLDOWN_MODO_ESTUDIO_SEG:
        return (
            "El modo estudio ya está activo (lo prendí hace un momento), "
            "no voy a volver a abrir todo de nuevo."
        )
    _ULTIMA_ACTIVACION_MODO_ESTUDIO = ahora

    try:
        modo_no_molestar(True)

        reproducir_en_youtube("Laufey playlist")

        time.sleep(0.4)
        webbrowser.open_new("https://www.office.com/launch/word")

        time.sleep(0.4)
        webbrowser.open_new(
            "https://virtual.autonoma.edu.pe/Campus/Login.aspx#autonoma"
        )

        configurar_recordatorio(
            25, "Llevas 25 minutos estudiando, tómate un descanso corto."
        )

        return (
            "Modo estudio activado: notificaciones en silencio, música "
            "de Laufey sonando, documento en blanco abierto para tus "
            "notas, el campus virtual abierto y un recordatorio de "
            "descanso en 25 minutos."
        )
    except Exception as e:
        return f"No pude activar el modo estudio: {e}"


def activar_rutina_aplausos() -> str:
    """
    Se dispara automáticamente al detectar 2 aplausos seguidos (ver
    enviar_audio en jarvis_live.py, no es algo que el modelo decida
    llamar). Hace lo mismo que activar_modo_estudio, pero además le
    avisa a Jarvis por texto lo que pasó (porque este disparo no viene
    de una conversación en curso, así que si no, Jarvis no se entera).
    """
    resultado = activar_modo_estudio()
    if _notificar:
        _notificar(
            f"[2 aplausos detectados] Actívate con esto, menciónalo breve "
            f"y con tu estilo: {resultado}"
        )
    return resultado


# --- Portapapeles -----------------------------------------------------
def leer_portapapeles() -> str:
    """Devuelve el texto actual del portapapeles, para que Jarvis lo lea
    o lo resuma."""
    try:
        import pyperclip
    except ImportError:
        return "Falta instalar 'pyperclip' (pip install pyperclip) para leer el portapapeles."

    try:
        contenido = pyperclip.paste()
        if not contenido or not contenido.strip():
            return "El portapapeles está vacío."
        if len(contenido) > 4000:
            contenido = contenido[:4000] + "... (recortado)"
        return contenido
    except Exception as e:
        return f"No pude leer el portapapeles: {e}"


# --- Recordatorios ----------------------------------------------------
# Se guardan en disco (RUTA_RECORDATORIOS) además de en memoria, para que
# NO se pierdan si cierras Jarvis antes de que se cumpla el tiempo. Al
# volver a abrir, cargar_recordatorios_guardados() los reprograma solos.
RECORDATORIOS_ACTIVOS = []  # cada uno: {"mensaje": str, "hora_disparo": datetime.datetime}
RUTA_RECORDATORIOS = os.path.join(CARPETA_DATOS_LOCAL, "recordatorios.json")


def obtener_recordatorios_activos() -> list:
    """Lista de recordatorios aún pendientes (para mostrarlos en la
    interfaz, ej. el panel EVENTS)."""
    ahora = datetime.datetime.now()
    return [r for r in RECORDATORIOS_ACTIVOS if r["hora_disparo"] > ahora]


def _guardar_recordatorios_en_disco():
    """Persiste RECORDATORIOS_ACTIVOS a disco. Se llama cada vez que la
    lista cambia (se agrega uno nuevo o se dispara uno existente)."""
    try:
        datos = [
            {"mensaje": r["mensaje"], "hora_disparo": r["hora_disparo"].isoformat()}
            for r in RECORDATORIOS_ACTIVOS
        ]
        with open(RUTA_RECORDATORIOS, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _programar_recordatorio(mensaje: str, hora_disparo: datetime.datetime):
    """Agrega un recordatorio a la lista activa, lo guarda en disco y
    programa el Timer que avisará cuando llegue la hora. La usan tanto
    configurar_recordatorio() (uno nuevo) como
    cargar_recordatorios_guardados() (al reabrir Jarvis)."""
    entrada = {"mensaje": mensaje, "hora_disparo": hora_disparo}
    RECORDATORIOS_ACTIVOS.append(entrada)
    _guardar_recordatorios_en_disco()

    segundos = max(0.0, (hora_disparo - datetime.datetime.now()).total_seconds())

    def avisar():
        if entrada in RECORDATORIOS_ACTIVOS:
            RECORDATORIOS_ACTIVOS.remove(entrada)
            _guardar_recordatorios_en_disco()
        if _notificar:
            _notificar(
                f"[Recordatorio] Avísale ahora al usuario, en tu propio estilo: {mensaje}"
            )

    threading.Timer(segundos, avisar).start()


def cargar_recordatorios_guardados():
    """Al arrancar Jarvis, recupera los recordatorios que quedaron
    pendientes de la sesión anterior (antes se perdían al cerrar la
    app) y los reprograma. Los que ya vencieron mientras estaba cerrado
    se descartan en silencio, para no acumular avisos atrasados."""
    if not os.path.exists(RUTA_RECORDATORIOS):
        return
    try:
        with open(RUTA_RECORDATORIOS, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    ahora = datetime.datetime.now()
    for item in datos:
        try:
            hora_disparo = datetime.datetime.fromisoformat(item["hora_disparo"])
        except Exception:
            continue
        if hora_disparo > ahora:
            _programar_recordatorio(item["mensaje"], hora_disparo)


def configurar_recordatorio(minutos, mensaje: str) -> str:
    """
    Programa un recordatorio: después de 'minutos', Jarvis te lo va a
    mencionar por voz automáticamente. Sobrevive a cerrar y volver a
    abrir Jarvis (se guarda en disco).

    'minutos' acepta decimales, así que cualquier unidad que use el
    usuario se debe convertir a minutos antes de llamar esta función
    (30 segundos = 0.5, media hora = 30, una hora y media = 90, etc.).
    """
    # La API a veces manda el número como texto ("10") en vez de float.
    # Sin este cast, "10" * 60 generaba un valor inválido para el Timer
    # y el recordatorio simplemente nunca sonaba (por eso solo parecía
    # "funcionar" para 1 minuto).
    try:
        minutos = float(minutos)
    except (TypeError, ValueError):
        return f"No entendí en cuántos minutos avisarte ('{minutos}')."

    if minutos <= 0:
        return "Dime un tiempo mayor a cero para el recordatorio."

    print(f"[DEBUG] Recordatorio programado: {minutos} min - '{mensaje}'")
    hora_disparo = datetime.datetime.now() + datetime.timedelta(minutes=minutos)
    _programar_recordatorio(mensaje, hora_disparo)

    if minutos < 1:
        texto_tiempo = f"{round(minutos * 60)} segundos"
    elif minutos == int(minutos):
        texto_tiempo = f"{int(minutos)} minutos"
    else:
        texto_tiempo = f"{minutos:.1f} minutos"

    return f"Listo, te lo recuerdo en {texto_tiempo}."


# --- Calendario local (agenda con fecha y hora) ---------------------------
# OJO: esto es un calendario PROPIO de Jarvis, guardado en disco. NO se
# sincroniza con Google Calendar/Outlook (eso requiere OAuth, pendiente
# de configurar aparte) — pero sí persiste entre sesiones y Jarvis te
# avisa por voz cuando llega la hora de un evento.
RUTA_CALENDARIO = os.path.join(CARPETA_DATOS_LOCAL, "calendario.json")


def _cargar_calendario() -> list:
    if not os.path.exists(RUTA_CALENDARIO):
        return []
    try:
        with open(RUTA_CALENDARIO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _guardar_calendario(eventos: list):
    try:
        with open(RUTA_CALENDARIO, "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def agendar_evento(fecha_hora: str, descripcion: str) -> str:
    """
    Agenda un evento en el calendario local de Jarvis.
    fecha_hora debe venir en formato 'AAAA-MM-DD HH:MM', ej:
    '2026-10-05 15:00'. Convierte cualquier fecha relativa ('mañana',
    'el viernes que viene') a esa fecha exacta antes de llamar la función.
    """
    try:
        cuando = datetime.datetime.strptime(fecha_hora.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return f"No entendí la fecha/hora '{fecha_hora}'. Debe ser 'AAAA-MM-DD HH:MM'."

    eventos = _cargar_calendario()
    eventos.append({
        "cuando": cuando.isoformat(),
        "descripcion": descripcion.strip(),
        "avisado": False,
    })
    eventos.sort(key=lambda e: e["cuando"])
    _guardar_calendario(eventos)

    return f"Listo, agendé '{descripcion}' para el {cuando.strftime('%d/%m/%Y a las %H:%M')}."


def listar_eventos_calendario(solo_proximos: bool = True) -> str:
    """Lista los eventos del calendario local, en texto (para que
    Jarvis los lea). Si solo_proximos=True, omite los que ya pasaron."""
    eventos = _cargar_calendario()
    if solo_proximos:
        ahora = datetime.datetime.now()
        eventos = [e for e in eventos if datetime.datetime.fromisoformat(e["cuando"]) >= ahora]

    if not eventos:
        return "No tienes eventos agendados."

    eventos.sort(key=lambda e: e["cuando"])
    lineas = []
    for e in eventos:
        cuando = datetime.datetime.fromisoformat(e["cuando"])
        lineas.append(f"- {cuando.strftime('%d/%m %H:%M')}: {e['descripcion']}")
    return "Tus eventos:\n" + "\n".join(lineas)


def eliminar_evento_calendario(texto_busqueda: str) -> str:
    """Elimina el primer evento del calendario cuya descripción contenga
    'texto_busqueda' (sin importar mayúsculas)."""
    eventos = _cargar_calendario()
    texto_busqueda = texto_busqueda.strip().lower()
    for i, e in enumerate(eventos):
        if texto_busqueda in e["descripcion"].lower():
            eliminado = eventos.pop(i)
            _guardar_calendario(eventos)
            return f"Eliminé el evento '{eliminado['descripcion']}'."
    return f"No encontré ningún evento con '{texto_busqueda}'."


def obtener_eventos_calendario_lista() -> list:
    """Versión en lista (no texto) de los eventos próximos, para que la
    interfaz gráfica los muestre directo en la pestaña CAL."""
    eventos = _cargar_calendario()
    ahora = datetime.datetime.now()
    proximos = [e for e in eventos if datetime.datetime.fromisoformat(e["cuando"]) >= ahora]
    proximos.sort(key=lambda e: e["cuando"])
    return proximos


def revisar_eventos_pendientes() -> list:
    """Devuelve los eventos cuya hora ya llegó y aún no se habían
    avisado, y los marca como avisados. Pensada para llamarse cada
    cierto tiempo desde jarvis_live (ej. cada minuto)."""
    eventos = _cargar_calendario()
    ahora = datetime.datetime.now()
    pendientes = []
    cambiado = False
    for e in eventos:
        cuando = datetime.datetime.fromisoformat(e["cuando"])
        if not e.get("avisado") and cuando <= ahora:
            pendientes.append(e)
            e["avisado"] = True
            cambiado = True
    if cambiado:
        _guardar_calendario(eventos)
    return pendientes


if __name__ == "__main__":
    # Prueba rápida: corre este archivo directo para probar las funciones
    print(abrir_app("spotify"))
    print(buscar_en_navegador("clima en lima hoy"))
    print(controlar_volumen("subir"))
    print(abrir_carpeta("descargas"))
