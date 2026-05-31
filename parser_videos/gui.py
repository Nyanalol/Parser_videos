"""Interfaz gráfica de escritorio (CustomTkinter) para Parser Videos.

Permite añadir una o varias URLs (cada una con sus rangos de tiempo opcionales),
escribir un prompt personalizado para el resumen, elegir idiomas y lanzar el
proceso, mostrando el progreso en tiempo real.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from . import config, summarizer
from .pipeline import VideoRequest, process

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Idiomas para la transcripción del audio (forzar idioma o autodetección).
_AUDIO_LANGS = {"Detección automática": None, "Español": "es", "Inglés": "en"}

# Icono de la aplicación.
_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def _set_app_identity() -> None:
    """Declara una identidad propia en Windows (AppUserModelID).

    Sin esto, la barra de tareas agrupa la ventana de pythonw.exe bajo la
    identidad cacheada de otra app de Python y puede mostrar un icono ajeno.
    """
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Nyana.ParserVideos"
        )
    except Exception:
        pass


class VideoRow(ctk.CTkFrame):
    """Una fila con la URL de un vídeo y sus rangos de tiempo opcionales."""

    def __init__(self, master, on_remove):
        super().__init__(master)
        self.on_remove = on_remove

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        self.url_entry = ctk.CTkEntry(self, placeholder_text="URL del vídeo (YouTube...)")
        self.url_entry.grid(row=0, column=0, padx=(0, 6), pady=4, sticky="ew")

        self.ranges_entry = ctk.CTkEntry(
            self, placeholder_text="Rangos opc. p.ej. 14:34-16:34, 20:00-21:30"
        )
        self.ranges_entry.grid(row=0, column=1, padx=(0, 6), pady=4, sticky="ew")

        self.remove_btn = ctk.CTkButton(
            self, text="✕", width=32, fg_color="#a33", hover_color="#822",
            command=lambda: self.on_remove(self),
        )
        self.remove_btn.grid(row=0, column=2, pady=4)

    def get_request(self) -> Optional[VideoRequest]:
        url = self.url_entry.get().strip()
        if not url:
            return None
        return VideoRequest(url=url, ranges_text=self.ranges_entry.get().strip())


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Parser Videos — transcribe y resume")
        self.geometry("820x780")
        self.minsize(720, 640)
        self.grid_columnconfigure(0, weight=1)
        # La lista de vídeos es la zona que absorbe el espacio sobrante, de modo
        # que los campos de abajo (prompt, log) mantienen siempre su altura.
        self.grid_rowconfigure(2, weight=1)

        # Icono de la ventana (título y barra de tareas).
        if _ICON_PATH.exists():
            try:
                self.iconbitmap(str(_ICON_PATH))
            except Exception:
                pass

        self.rows: list[VideoRow] = []

        # --- Cabecera ---
        ctk.CTkLabel(
            self, text="Parser Videos", font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(16, 0), sticky="w")
        ctk.CTkLabel(
            self,
            text="Añade uno o varios vídeos. Si pones varios, se combinan en un único resumen.",
            text_color="gray",
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        # --- Lista de vídeos (zona elástica) ---
        self.videos_frame = ctk.CTkScrollableFrame(self, label_text="Vídeos", height=120)
        self.videos_frame.grid(row=2, column=0, padx=16, pady=6, sticky="nsew")
        self.videos_frame.grid_columnconfigure(0, weight=1)

        add_btn = ctk.CTkButton(self, text="＋ Añadir vídeo", command=self.add_row)
        add_btn.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="w")

        # --- Opciones ---
        opts = ctk.CTkFrame(self)
        opts.grid(row=4, column=0, padx=16, pady=6, sticky="ew")
        opts.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(opts, text="Idioma del resumen:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.summary_lang = ctk.CTkOptionMenu(opts, values=list(summarizer.LANGUAGE_CHOICES.keys()))
        self.summary_lang.set("Español")
        self.summary_lang.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(opts, text="Idioma del audio:").grid(row=0, column=2, padx=8, pady=8, sticky="w")
        self.audio_lang = ctk.CTkOptionMenu(opts, values=list(_AUDIO_LANGS.keys()))
        self.audio_lang.set("Detección automática")
        self.audio_lang.grid(row=0, column=3, padx=8, pady=8, sticky="w")

        ctk.CTkLabel(opts, text="Extensión del resumen:").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        self.length_level = ctk.CTkOptionMenu(opts, values=list(summarizer.LENGTH_CHOICES.keys()))
        self.length_level.set(summarizer.DEFAULT_LENGTH)
        self.length_level.grid(row=1, column=1, padx=8, pady=8, sticky="w")

        # --- Prompt personalizado ---
        ctk.CTkLabel(self, text="Instrucciones para el resumen (tono, enfoque...). Vacío = por defecto:").grid(
            row=5, column=0, padx=16, pady=(8, 0), sticky="w"
        )
        self.prompt_box = ctk.CTkTextbox(self, height=110)
        self.prompt_box.grid(row=6, column=0, padx=16, pady=6, sticky="ew")
        self.prompt_box.insert("1.0", summarizer.DEFAULT_PROMPT)

        # --- Botón procesar ---
        self.process_btn = ctk.CTkButton(
            self, text="Procesar", height=40, font=ctk.CTkFont(size=15, weight="bold"),
            command=self.on_process,
        )
        self.process_btn.grid(row=7, column=0, padx=16, pady=8, sticky="ew")

        # --- Log de progreso ---
        self.log_box = ctk.CTkTextbox(self, height=150)
        self.log_box.grid(row=8, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.log_box.configure(state="disabled")

        # --- Botones de resultado ---
        self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.result_frame.grid(row=9, column=0, padx=16, pady=(0, 16), sticky="ew")
        self.open_md_btn = ctk.CTkButton(
            self.result_frame, text="Abrir .md", state="disabled", command=self.open_md
        )
        self.open_md_btn.pack(side="left", padx=(0, 8))
        self.open_html_btn = ctk.CTkButton(
            self.result_frame, text="Abrir HTML", state="disabled", command=self.open_html
        )
        self.open_html_btn.pack(side="left", padx=(0, 8))
        self.open_obsidian_btn = ctk.CTkButton(
            self.result_frame, text="Abrir en Obsidian", state="disabled", command=self.open_obsidian
        )
        self.open_obsidian_btn.pack(side="left", padx=(0, 8))
        self.open_dir_btn = ctk.CTkButton(
            self.result_frame, text="Abrir carpeta", state="disabled", command=self.open_dir
        )
        self.open_dir_btn.pack(side="left")

        self._result = None  # PipelineResult tras procesar

        self.add_row()
        if not config.api_key_present():
            self.log("⚠ No hay OPENAI_API_KEY configurada. Edita el archivo .env antes de procesar.")

    # ----- Filas de vídeos -----
    def add_row(self):
        row = VideoRow(self.videos_frame, on_remove=self.remove_row)
        row.grid(row=len(self.rows), column=0, sticky="ew", pady=2)
        self.rows.append(row)

    def remove_row(self, row: VideoRow):
        if len(self.rows) <= 1:
            return  # siempre al menos una fila
        row.destroy()
        self.rows.remove(row)
        for i, r in enumerate(self.rows):
            r.grid(row=i, column=0, sticky="ew", pady=2)

    # ----- Log -----
    def log(self, msg: str):
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)

    # ----- Proceso -----
    def on_process(self):
        if not config.api_key_present():
            self.log("⚠ Falta OPENAI_API_KEY en .env. No se puede continuar.")
            return

        requests = [r for r in (row.get_request() for row in self.rows) if r]
        if not requests:
            self.log("⚠ Añade al menos una URL.")
            return

        custom_prompt = self.prompt_box.get("1.0", "end").strip()
        summary_language = self.summary_lang.get()
        audio_language = _AUDIO_LANGS.get(self.audio_lang.get())
        length_level = self.length_level.get()

        self.process_btn.configure(state="disabled", text="Procesando...")
        for btn in (self.open_md_btn, self.open_html_btn, self.open_obsidian_btn, self.open_dir_btn):
            btn.configure(state="disabled")

        thread = threading.Thread(
            target=self._run,
            args=(requests, custom_prompt, summary_language, audio_language, length_level),
            daemon=True,
        )
        thread.start()

    def _run(self, requests, custom_prompt, summary_language, audio_language, length_level):
        try:
            result = process(
                requests=requests,
                custom_prompt=custom_prompt,
                summary_language=summary_language,
                length_level=length_level,
                transcribe_language=audio_language,
                on_progress=self.log,
            )
            self._result = result
            self.log(f"✔ Markdown: {result.md_path}")
            self.log(f"✔ HTML:     {result.html_path}")
            self.log(f"✔ Obsidian: {result.obsidian_path}")
            self.log(f"✔ Transcripción: {result.transcript_path}")
            self.after(0, self._enable_result_buttons)
        except Exception as exc:  # noqa: BLE001 - mostramos cualquier fallo al usuario
            self.log(f"✖ Error: {exc}")
        finally:
            self.after(0, lambda: self.process_btn.configure(state="normal", text="Procesar"))

    def _enable_result_buttons(self):
        for btn in (self.open_md_btn, self.open_html_btn, self.open_obsidian_btn, self.open_dir_btn):
            btn.configure(state="normal")

    @staticmethod
    def _open(path: Path):
        if path and Path(path).exists():
            os.startfile(path)  # type: ignore[attr-defined]

    def open_md(self):
        if self._result:
            self._open(self._result.md_path)

    def open_html(self):
        if self._result:
            self._open(self._result.html_path)

    def open_obsidian(self):
        """Abre la nota en Obsidian mediante su URI; si falla, abre la carpeta."""
        if not self._result:
            return
        import urllib.parse

        path = str(self._result.obsidian_path)
        uri = "obsidian://open?path=" + urllib.parse.quote(path, safe="")
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
        except Exception:
            self._open(config.OBSIDIAN_DIR)

    def open_dir(self):
        self._open(config.OUTPUT_DIR)


def run():
    _set_app_identity()
    App().mainloop()


if __name__ == "__main__":
    run()
