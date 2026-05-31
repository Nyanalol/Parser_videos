"""Descarga el audio de un vídeo a partir de su URL usando yt-dlp.

Extrae solo la pista de audio y la convierte a MP3 mono a bitrate moderado
para que los archivos sean pequeños (importante por el límite de 25 MB de
Whisper) sin perder inteligibilidad del habla.

El audio se guarda con el id del vídeo como nombre, de modo que si ya se
descargó antes no se vuelve a descargar (caché de audio).
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from yt_dlp import YoutubeDL

from . import config
from .ffmpeg_utils import get_ffmpeg_exe

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


def is_local_path(s: str) -> bool:
    """Indica si la entrada es un archivo local existente (no una URL)."""
    try:
        return Path(s).expanduser().exists()
    except OSError:
        return False


def _convert_to_mp3(source_path: Path, audio_path: Path) -> None:
    """Convierte cualquier archivo de audio/vídeo a MP3 mono 64k con ffmpeg."""
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-i", str(source_path),
        "-vn", "-ac", "1", "-b:a", f"{_AUDIO_BITRATE}k",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not audio_path.exists():
        raise RuntimeError(f"Fallo al convertir el audio con ffmpeg:\n{proc.stderr[-500:]}")


def probe(url: str) -> VideoInfo:
    """Obtiene los metadatos del vídeo/archivo sin descargar el audio."""
    if is_local_path(url):
        p = Path(url).expanduser().resolve()
        vid = "local_" + hashlib.md5(str(p).encode("utf-8")).hexdigest()[:12]
        return VideoInfo(
            video_id=vid, title=p.stem, duration_seconds=None, webpage_url=str(p)
        )

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


def expand_playlist(url: str) -> list[str]:
    """Si la URL es una playlist/canal, devuelve las URLs de sus vídeos.

    Para una URL de un único vídeo (o un archivo local) devuelve [url].
    """
    if is_local_path(url):
        return [url]
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return [url]
    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        return [url]
    urls = []
    for e in entries:
        if not e:
            continue
        u = e.get("url") or e.get("webpage_url") or e.get("id")
        if u:
            urls.append(u)
    return urls or [url]


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

    # Archivo local: convertimos directamente, sin descargar nada.
    if is_local_path(url):
        _log("Extrayendo audio del archivo local...")
        _convert_to_mp3(Path(url).expanduser().resolve(), audio_path)
        _log("Audio listo.")
        return DownloadResult(audio_path=audio_path, info=info)

    def _hook(d: dict) -> None:
        if d.get("status") == "downloading":
            pct = d.get("_percent_str", "").strip()
            if pct:
                _log(f"Descargando audio... {pct}")
        elif d.get("status") == "finished":
            _log("Descarga completada, convirtiendo a MP3...")

    # Descargamos la mejor pista de audio SIN postprocesar. No usamos el
    # postprocesador de yt-dlp porque requiere ffprobe (que imageio-ffmpeg no
    # incluye); la conversión a MP3 la hacemos nosotros con ffmpeg.
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(config.DOWNLOADS_DIR / "%(id)s.source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
    }

    with YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(url, download=True)

    # Ruta real del archivo descargado.
    source_path: Optional[Path] = None
    downloads = result.get("requested_downloads") if isinstance(result, dict) else None
    if downloads:
        fp = downloads[0].get("filepath")
        if fp:
            source_path = Path(fp)
    if source_path is None or not source_path.exists():
        # Respaldo: buscar por patrón {id}.source.*
        matches = list(config.DOWNLOADS_DIR.glob(f"{info.video_id}.source.*"))
        source_path = matches[0] if matches else None
    if source_path is None or not source_path.exists():
        raise FileNotFoundError("No se encontró el audio descargado por yt-dlp.")

    # Convertir a MP3 mono 64 kbps con nuestro ffmpeg.
    _convert_to_mp3(source_path, audio_path)

    # Limpiar el archivo fuente original.
    try:
        source_path.unlink()
    except OSError:
        pass

    _log("Audio listo.")
    return DownloadResult(audio_path=audio_path, info=info)
