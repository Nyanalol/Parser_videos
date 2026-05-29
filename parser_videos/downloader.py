"""Descarga el audio de un vídeo a partir de su URL usando yt-dlp.

Extrae solo la pista de audio y la convierte a MP3 mono a bitrate moderado
para que los archivos sean pequeños (importante por el límite de 25 MB de
Whisper) sin perder inteligibilidad del habla.

El audio se guarda con el id del vídeo como nombre, de modo que si ya se
descargó antes no se vuelve a descargar (caché de audio).
"""

from __future__ import annotations

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
class VideoInfo:
    """Metadatos de un vídeo (sin descargar nada)."""

    video_id: str
    title: str
    duration_seconds: Optional[float]
    webpage_url: str


@dataclass
class DownloadResult:
    """Resultado de una descarga de audio."""

    audio_path: Path
    info: VideoInfo


def probe(url: str) -> VideoInfo:
    """Obtiene los metadatos del vídeo sin descargar el audio."""
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info["id"]
    return VideoInfo(
        video_id=video_id,
        title=info.get("title") or video_id,
        duration_seconds=info.get("duration"),
        webpage_url=info.get("webpage_url") or url,
    )


def download_audio(
    url: str,
    info: Optional[VideoInfo] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> DownloadResult:
    """Descarga y extrae el audio del vídeo indicado por `url`.

    Si ya existe el MP3 para ese id, lo reutiliza sin volver a descargar.
    Puede recibir un `info` ya obtenido con probe() para evitar una consulta extra.
    """
    config.ensure_dirs()

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    if info is None:
        _log("Obteniendo información del vídeo...")
        info = probe(url)

    audio_path = config.DOWNLOADS_DIR / f"{info.video_id}.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        _log("Audio ya descargado anteriormente; se reutiliza.")
        return DownloadResult(audio_path=audio_path, info=info)

    def _hook(d: dict) -> None:
        if d.get("status") == "downloading":
            pct = d.get("_percent_str", "").strip()
            if pct:
                _log(f"Descargando audio... {pct}")
        elif d.get("status") == "finished":
            _log("Descarga completada, extrayendo audio...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(config.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
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

    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"No se generó el archivo de audio esperado: {audio_path}"
        )

    _log("Audio listo.")
    return DownloadResult(audio_path=audio_path, info=info)
