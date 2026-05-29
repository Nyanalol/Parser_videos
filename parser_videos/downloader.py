"""Descarga el audio de un vídeo a partir de su URL usando yt-dlp.

Extrae solo la pista de audio y la convierte a MP3 mono a bitrate moderado
para que los archivos sean pequeños (importante por el límite de 25 MB de
Whisper) sin perder inteligibilidad del habla.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from yt_dlp import YoutubeDL

from . import config
from .ffmpeg_utils import get_ffmpeg_dir

# Bitrate de audio del MP3 resultante. 64 kbps mono es más que suficiente para
# voz y mantiene los archivos pequeños (~28 MB por hora).
_AUDIO_BITRATE = "64"

ProgressCallback = Callable[[str], None]


@dataclass
class DownloadResult:
    """Resultado de una descarga de audio."""

    audio_path: Path
    title: str
    duration_seconds: Optional[float]
    webpage_url: str


def _sanitize(name: str) -> str:
    """Limpia un texto para usarlo como nombre de archivo en Windows."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip().strip(".")
    return name[:120] or "video"


def download_audio(
    url: str,
    on_progress: Optional[ProgressCallback] = None,
) -> DownloadResult:
    """Descarga y extrae el audio del vídeo indicado por `url`.

    Devuelve un DownloadResult con la ruta del MP3 y metadatos básicos.
    """
    config.ensure_dirs()

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    def _hook(d: dict) -> None:
        if d.get("status") == "downloading":
            pct = d.get("_percent_str", "").strip()
            if pct:
                _log(f"Descargando audio... {pct}")
        elif d.get("status") == "finished":
            _log("Descarga completada, extrayendo audio...")

    # Plantilla de salida: usamos el id del vídeo para evitar colisiones; luego
    # renombramos a un nombre legible basado en el título.
    outtmpl = str(config.DOWNLOADS_DIR / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "ffmpeg_location": get_ffmpeg_dir(),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": _AUDIO_BITRATE,
            }
        ],
        # Audio mono: reduce a la mitad el tamaño sin afectar a la transcripción.
        "postprocessor_args": {"FFmpegExtractAudio": ["-ac", "1"]},
    }

    _log("Obteniendo información del vídeo...")
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    video_id = info["id"]
    title = info.get("title") or video_id
    duration = info.get("duration")
    webpage_url = info.get("webpage_url") or url

    produced = config.DOWNLOADS_DIR / f"{video_id}.mp3"
    if not produced.exists():
        raise FileNotFoundError(
            f"No se generó el archivo de audio esperado: {produced}"
        )

    # Renombrar a un nombre legible.
    target = config.DOWNLOADS_DIR / f"{_sanitize(title)}.mp3"
    if target != produced:
        if target.exists():
            target.unlink()
        produced.rename(target)

    _log("Audio listo.")
    return DownloadResult(
        audio_path=target,
        title=title,
        duration_seconds=duration,
        webpage_url=webpage_url,
    )
