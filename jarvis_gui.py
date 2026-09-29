"""
jarvis_gui.py
-------------
HUD estilo "arco reactor" para Jarvis: círculo central que pulsa y unos
arcos exteriores que rotan solos, reloj en vivo, panel de conversación
tipo terminal, pestañas (CHAT / EVENTS / CMD CTR / CAL) y tarjetas con
clima real + horas del mundo abajo.

Usa toda la lógica de jarvis_live.py por debajo (audio, pantalla, API) —
esto es solo la "cara" nueva.

Uso:
    Configura tus variables de entorno (GEMINI_API_KEY, YOUTUBE_API_KEY,
    OPENWEATHER_API_KEY opcional) como ya lo haces, y luego:
        py -3.12 jarvis_gui.py
"""
import asyncio
import datetime
import math
import threading
import tkinter as tk

import jarvis_live as jl  # reutiliza toda la lógica de audio/video/API


def iniciar_jarvis_en_hilo():
    """Corre el asyncio principal de Jarvis en un hilo aparte, para no
    bloquear la ventana gráfica."""
    def hilo():
        asyncio.run(jl.main())
    threading.Thread(target=hilo, daemon=True).start()


def _oscurecer(color_hex: str, factor: float) -> str:
    """Oscurece un color hex mezclándolo hacia negro (0 = igual, 1 = negro).
    Se usa para el halo exterior del núcleo (una versión 'apagada' del
    color principal, en vez de un color fijo)."""
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    r = int(r * (1 - factor))
    g = int(g * (1 - factor))
    b = int(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


class VentanaJarvis(tk.Tk):
    # Paleta HUD: fondo casi negro, paneles azul-noche, acentos cian
    # (escuchando/en espera), ámbar (hablando) y rojo (muteado/alerta).
    COLOR_FONDO = "#03060d"
    COLOR_PANEL = "#0a0f1c"
    COLOR_BORDE = "#12293b"
    COLOR_CIAN = "#22d3ee"
    COLOR_CIAN_TENUE = "#0e4a5c"
    COLOR_AMBAR = "#fbbf24"
    COLOR_ROJO = "#f87171"
    COLOR_VERDE = "#34d399"
    COLOR_TEXTO = "#cfe8f3"
    COLOR_TEXTO_TENUE = "#4c6b7a"

    def __init__(self):
        super().__init__()
        self.title("J.A.R.V.I.S.")
        self.geometry("380x780")
        self.configure(bg=self.COLOR_FONDO)
        self.resizable(False, False)

        self.fuente_mono = ("Consolas", 9)
        self.fuente_mono_chica = ("Consolas", 8)

        self._construir_encabezado()
        self._construir_reactor()
        self._construir_estado()
        self._construir_pestanas()
        self._construir_panel_chat()
        self._construir_panel_eventos()
        self._construir_panel_cmd()
        self._construir_panel_cal()
        self._construir_tarjetas_inferiores()

        self._mostrar_pestana("chat")

        self._fase_pulso = 0.0
        self._fase_arco = 0.0
        self._lineas_mostradas = -1

        self._animar()
        self._tick_reloj()
        self._actualizar_tarjetas()
        self._refrescar_paneles()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_encabezado(self):
        marco = tk.Frame(self, bg=self.COLOR_FONDO)
        marco.pack(fill="x", pady=(14, 4))
        tk.Label(
            marco, text="LAROSSA GROUP — COMMAND INTERFACE",
            fg=self.COLOR_TEXTO_TENUE, bg=self.COLOR_FONDO, font=("Consolas", 8)
        ).pack()
        self.label_reloj = tk.Label(
            marco, text="00:00:00", fg=self.COLOR_CIAN, bg=self.COLOR_FONDO,
            font=("Consolas", 13, "bold")
        )
        self.label_reloj.pack(pady=(2, 0))

    def _construir_reactor(self):
        self.canvas = tk.Canvas(
            self, width=220, height=210, bg=self.COLOR_FONDO, highlightthickness=0
        )
        self.canvas.pack(pady=(6, 4))
        self._cx, self._cy = 110, 105

        cx, cy = self._cx, self._cy
        # Arcos decorativos que rotan solos, dan el look "reactor"
        self.arco_ext_1 = self.canvas.create_arc(
            cx - 92, cy - 92, cx + 92, cy + 92,
            start=0, extent=100, style="arc", outline=self.COLOR_CIAN_TENUE, width=2
        )
        self.arco_ext_2 = self.canvas.create_arc(
            cx - 92, cy - 92, cx + 92, cy + 92,
            start=180, extent=100, style="arc", outline=self.COLOR_CIAN_TENUE, width=2
        )
        self.arco_med = self.canvas.create_arc(
            cx - 72, cy - 72, cx + 72, cy + 72,
            start=40, extent=60, style="arc", outline=self.COLOR_CIAN_TENUE, width=1
        )

        # Núcleo con "halo" (círculo grande y tenue detrás del central,
        # simulando el brillo) + un punto blanco al centro
        self.nucleo_halo = self.canvas.create_oval(0, 0, 0, 0, fill=self.COLOR_CIAN_TENUE, outline="")
        self.nucleo = self.canvas.create_oval(0, 0, 0, 0, fill=self.COLOR_CIAN, outline="")
        self.nucleo_brillo = self.canvas.create_oval(0, 0, 0, 0, fill="#eafdff", outline="")

    def _construir_estado(self):
        self.label_estado = tk.Label(
            self, text="● STANDING BY", fg=self.COLOR_VERDE, bg=self.COLOR_FONDO,
            font=("Consolas", 10, "bold")
        )
        self.label_estado.pack(pady=(0, 10))

    def _construir_pestanas(self):
        marco = tk.Frame(self, bg=self.COLOR_FONDO)
        marco.pack(fill="x", padx=16)
        self.botones_tab = {}
        for clave, etiqueta in (("chat", "CHAT"), ("eventos", "EVENTS"),
                                 ("cmd", "CMD CTR"), ("cal", "CAL")):
            boton = tk.Button(
                marco, text=etiqueta, font=("Consolas", 8, "bold"),
                bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO_TENUE, relief="flat",
                activebackground=self.COLOR_PANEL, activeforeground=self.COLOR_CIAN,
                bd=0, padx=6, pady=6, command=lambda c=clave: self._mostrar_pestana(c)
            )
            boton.pack(side="left", expand=True, fill="x", padx=1)
            self.botones_tab[clave] = boton

    def _panel_base(self):
        return tk.Frame(self, bg=self.COLOR_PANEL, highlightthickness=1,
                         highlightbackground=self.COLOR_BORDE)

    def _construir_panel_chat(self):
        self.panel_chat = self._panel_base()

        self.texto_log = tk.Text(
            self.panel_chat, height=9, bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO,
            font=self.fuente_mono, relief="flat", wrap="word", state="disabled",
            insertbackground=self.COLOR_TEXTO, padx=4, pady=4
        )
        self.texto_log.pack(fill="both", expand=True, padx=8, pady=8)

        marco_entrada = tk.Frame(self.panel_chat, bg=self.COLOR_PANEL)
        marco_entrada.pack(fill="x", padx=8, pady=(0, 8))

        self.entrada = tk.Entry(
            marco_entrada, font=self.fuente_mono, bg="#050b14", fg=self.COLOR_TEXTO,
            insertbackground=self.COLOR_TEXTO, relief="flat",
            highlightthickness=1, highlightbackground=self.COLOR_BORDE,
            highlightcolor=self.COLOR_CIAN
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self.entrada.bind("<Return>", self._enviar_mensaje)

        self.boton_enviar = tk.Button(
            marco_entrada, text="SEND", command=self._enviar_mensaje,
            bg=self.COLOR_PANEL, fg=self.COLOR_CIAN, relief="flat",
            font=("Consolas", 8, "bold"), padx=10,
            highlightthickness=1, highlightbackground=self.COLOR_CIAN
        )
        self.boton_enviar.pack(side="left", padx=(0, 6))

        self.boton_mic = tk.Button(
            marco_entrada, text="● MIC", command=self._alternar_mute,
            bg=self.COLOR_PANEL, fg=self.COLOR_CIAN, relief="flat",
            font=("Consolas", 8, "bold"), padx=10,
            highlightthickness=1, highlightbackground=self.COLOR_ROJO
        )
        self.boton_mic.pack(side="left", padx=(0, 6))

        self.boton_vision = tk.Button(
            marco_entrada, text="👁", command=self._alternar_vision,
            bg=self.COLOR_PANEL, fg=self.COLOR_CIAN, relief="flat",
            font=("Consolas", 8, "bold"), padx=8,
            highlightthickness=1, highlightbackground=self.COLOR_CIAN
        )
        self.boton_vision.pack(side="left")

    def _construir_panel_eventos(self):
        self.panel_eventos = self._panel_base()
        tk.Label(
            self.panel_eventos, text="RECORDATORIOS PENDIENTES",
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO_TENUE, font=("Consolas", 8, "bold")
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.texto_eventos = tk.Text(
            self.panel_eventos, height=13, bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO,
            font=self.fuente_mono, relief="flat", wrap="word", state="disabled", padx=4, pady=4
        )
        self.texto_eventos.pack(fill="both", expand=True, padx=8, pady=8)

    def _construir_panel_cmd(self):
        self.panel_cmd = self._panel_base()
        tk.Label(
            self.panel_cmd, text="COMMAND CENTER — ÚLTIMAS ACCIONES",
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO_TENUE, font=("Consolas", 8, "bold")
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.texto_cmd = tk.Text(
            self.panel_cmd, height=13, bg=self.COLOR_PANEL, fg=self.COLOR_VERDE,
            font=self.fuente_mono_chica, relief="flat", wrap="word", state="disabled", padx=4, pady=4
        )
        self.texto_cmd.pack(fill="both", expand=True, padx=8, pady=8)

    def _construir_panel_cal(self):
        self.panel_cal = self._panel_base()
        tk.Label(
            self.panel_cal, text="CALENDARIO LOCAL (no sincroniza con Google/Outlook)",
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO_TENUE, font=("Consolas", 8, "bold"),
            wraplength=300, justify="left"
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.texto_cal = tk.Text(
            self.panel_cal, height=13, bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO,
            font=self.fuente_mono, relief="flat", wrap="word", state="disabled", padx=4, pady=4
        )
        self.texto_cal.pack(fill="both", expand=True, padx=8, pady=8)

    def _construir_tarjetas_inferiores(self):
        marco = tk.Frame(self, bg=self.COLOR_FONDO)
        marco.pack(fill="x", padx=16, pady=(10, 14))

        self.tarjetas = {}
        datos = [
            ("clima", "CLIMA"),
            ("hora_local", "HORA LOCAL"),
            ("hora_utc", "UTC"),
            ("hora_tokio", "TOKIO (JST)"),
        ]
        for i, (clave, etiqueta) in enumerate(datos):
            fila, col = divmod(i, 2)
            tarjeta = tk.Frame(marco, bg=self.COLOR_PANEL, highlightthickness=1,
                                highlightbackground=self.COLOR_BORDE)
            tarjeta.grid(row=fila, column=col, sticky="nsew", padx=4, pady=4)
            marco.grid_columnconfigure(col, weight=1)
            tk.Label(tarjeta, text=etiqueta, bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO_TENUE,
                     font=("Consolas", 7)).pack(anchor="w", padx=8, pady=(6, 0))
            valor = tk.Label(tarjeta, text="--", bg=self.COLOR_PANEL, fg=self.COLOR_CIAN,
                              font=("Consolas", 13, "bold"))
            valor.pack(anchor="w", padx=8, pady=(0, 6))
            self.tarjetas[clave] = valor

    # ------------------------------------------------------------------
    # Pestañas
    # ------------------------------------------------------------------
    def _mostrar_pestana(self, clave):
        for panel in (self.panel_chat, self.panel_eventos, self.panel_cmd, self.panel_cal):
            panel.pack_forget()
        for c, boton in self.botones_tab.items():
            boton.config(fg=self.COLOR_CIAN if c == clave else self.COLOR_TEXTO_TENUE)

        panel = {
            "chat": self.panel_chat, "eventos": self.panel_eventos,
            "cmd": self.panel_cmd, "cal": self.panel_cal,
        }[clave]
        panel.pack(fill="both", expand=True, padx=16, pady=(6, 6))
        self._pestana_activa = clave

    # ------------------------------------------------------------------
    # Acciones del usuario
    # ------------------------------------------------------------------
    def _alternar_mute(self):
        if jl.microfono_muteado.is_set():
            jl.microfono_muteado.clear()
            self.boton_mic.config(text="● MIC", fg=self.COLOR_CIAN)
        else:
            jl.microfono_muteado.set()
            self.boton_mic.config(text="🔇", fg=self.COLOR_ROJO)

    def _alternar_vision(self):
        if jl.vision_pausada.is_set():
            jl.vision_pausada.clear()
            self.boton_vision.config(fg=self.COLOR_CIAN)
        else:
            jl.vision_pausada.set()
            self.boton_vision.config(fg=self.COLOR_ROJO)

    def _enviar_mensaje(self, event=None):
        texto = self.entrada.get().strip()
        if texto:
            jl.cola_texto_gui.put(texto)
            self.entrada.delete(0, tk.END)

    # ------------------------------------------------------------------
    # Animación / actualización periódica
    # ------------------------------------------------------------------
    def _animar(self):
        hablando = jl.esta_hablando.is_set()
        muteado = jl.microfono_muteado.is_set()

        self._fase_pulso += 0.22 if hablando else 0.06
        self._fase_arco += 0.03

        base = 34 if hablando else 32
        amplitud = 7 if hablando else 3
        radio = base + math.sin(self._fase_pulso) * amplitud

        if muteado:
            color = self.COLOR_ROJO
            texto_estado, color_estado = "● MIC MUTED", self.COLOR_ROJO
        elif hablando:
            color = self.COLOR_AMBAR
            texto_estado, color_estado = "● RESPONDING", self.COLOR_AMBAR
        else:
            color = self.COLOR_CIAN
            texto_estado, color_estado = "● STANDING BY", self.COLOR_VERDE

        self.label_estado.config(text=texto_estado, fg=color_estado)

        cx, cy = self._cx, self._cy
        self.canvas.coords(self.nucleo_halo, cx - radio - 16, cy - radio - 16, cx + radio + 16, cy + radio + 16)
        self.canvas.coords(self.nucleo, cx - radio, cy - radio, cx + radio, cy + radio)
        self.canvas.coords(self.nucleo_brillo, cx - radio * 0.4, cy - radio * 0.4, cx + radio * 0.4, cy + radio * 0.4)
        self.canvas.itemconfig(self.nucleo_halo, fill=_oscurecer(color, 0.6))
        self.canvas.itemconfig(self.nucleo, fill=color)

        # Los arcos exteriores giran solos todo el rato (más rápido si habla)
        velocidad = 2.2 if hablando else 1.0
        angulo = (self._fase_arco * 40 * velocidad) % 360
        self.canvas.itemconfig(self.arco_ext_1, start=angulo, outline=_oscurecer(color, 0.3))
        self.canvas.itemconfig(self.arco_ext_2, start=(angulo + 180) % 360, outline=_oscurecer(color, 0.3))
        self.canvas.itemconfig(self.arco_med, start=(360 - angulo * 1.5) % 360, outline=_oscurecer(color, 0.5))

        self.after(40, self._animar)

    def _tick_reloj(self):
        self.label_reloj.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_reloj)

    def _actualizar_tarjetas(self):
        ahora_utc = datetime.datetime.now(datetime.timezone.utc)
        ahora_tokio = ahora_utc + datetime.timedelta(hours=9)  # Japón no usa horario de verano

        self.tarjetas["clima"].config(text=jl.clima_actual.get("texto", "--"))
        self.tarjetas["hora_local"].config(text=datetime.datetime.now().strftime("%H:%M"))
        self.tarjetas["hora_utc"].config(text=ahora_utc.strftime("%H:%M"))
        self.tarjetas["hora_tokio"].config(text=ahora_tokio.strftime("%H:%M"))

        self.after(1000, self._actualizar_tarjetas)

    def _refrescar_paneles(self):
        # Panel CHAT + CMD CTR: se redibujan solo si hay líneas nuevas
        lineas = jl.historial_gui
        if len(lineas) != self._lineas_mostradas:
            self.texto_log.config(state="normal")
            self.texto_log.delete("1.0", tk.END)
            for linea in lineas[-40:]:
                self.texto_log.insert(tk.END, linea + "\n")
            self.texto_log.see(tk.END)
            self.texto_log.config(state="disabled")

            self.texto_cmd.config(state="normal")
            self.texto_cmd.delete("1.0", tk.END)
            for linea in lineas[-80:]:
                if linea.startswith("> "):
                    self.texto_cmd.insert(tk.END, linea + "\n")
            self.texto_cmd.see(tk.END)
            self.texto_cmd.config(state="disabled")

            self._lineas_mostradas = len(lineas)

        # Panel EVENTS: recordatorios activos
        pendientes = jl.obtener_recordatorios_activos()
        self.texto_eventos.config(state="normal")
        self.texto_eventos.delete("1.0", tk.END)
        if not pendientes:
            self.texto_eventos.insert(tk.END, "Sin recordatorios pendientes.")
        else:
            for r in pendientes:
                hora = r["hora_disparo"].strftime("%H:%M")
                self.texto_eventos.insert(tk.END, f"[{hora}] {r['mensaje']}\n")
        self.texto_eventos.config(state="disabled")

        # Panel CAL: eventos del calendario local
        eventos = jl.obtener_eventos_calendario_lista()
        self.texto_cal.config(state="normal")
        self.texto_cal.delete("1.0", tk.END)
        if not eventos:
            self.texto_cal.insert(tk.END, "No tienes eventos agendados.")
        else:
            for e in eventos:
                cuando = datetime.datetime.fromisoformat(e["cuando"])
                self.texto_cal.insert(tk.END, f"{cuando.strftime('%d/%m %H:%M')}  {e['descripcion']}\n")
        self.texto_cal.config(state="disabled")

        self.after(2000, self._refrescar_paneles)


if __name__ == "__main__":
    iniciar_jarvis_en_hilo()
    app = VentanaJarvis()
    app.mainloop()
