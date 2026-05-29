"""Transcribe audio usando la API de Whisper de OpenAI.

Si el archivo supera el límite de 25 MB de la API, lo trocea por tiempo con
ffmpeg, transcribe cada trozo y concatena el texto.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from openai import OpenAI

from . import config
from .ffmpeg_utils import get_ffmpeg_exe

ProgressCallback = Callable[[str], None]


def _probe_duration(audio_path: Path) -> Optional[float]:
    """Obtiene la duración en segundos del audio usando ffmpeg.

    ffmpeg escribe la duración por stderr; la parseamos. Si falla, None.
    """
    ffmpeg = get_ffmpeg_exe()
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", str(audio_path)],
            capture_output=True,
            text=True,
        )
        for line in proc.stderr.splitlines():
            line = line.strip()
            if line.startswith("Duration:"):
                # Formato: "Duration: 00:12:34.56, ..."
                ts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = ts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return None


def _split_audio(audio_path: Path, num_chunks: int, workdir: Path) -> list[Path]:
    """Divide el audio en `num_chunks` trozos iguales por tiempo con ffmpeg."""
    duration = _probe_duration(audio_path)
    if not duration:
        raise RuntimeError(
            "No se pudo determinar la duración del audio para trocearlo."
        )

    ffmpeg = get_ffmpeg_exe()
    chunk_seconds = math.ceil(duration / num_chunks)
    chunks: list[Path] = []

    for i in range(num_chunks):
        start = i * chunk_seconds
        out = workdir / f"chunk_{i:03d}.mp3"
        # -c copy no siempre corta limpio en MP3; re-codificamos a 64k mono
        # para garantizar cortes correctos y tamaños pequeños.
        cmd = [
            ffmpeg, "-y",
            "-ss", str(start),
            "-t", str(chunk_seconds),
            "-i", str(audio_path),
            "-ac", "1",
            "-b:a", "64k",
            str(out),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if out.exists() and out.stat().st_size > 0:
            chunks.append(out)

    if not chunks:
        raise RuntimeError("El troceado de audio no produjo ningún archivo.")
    return chunks


def _transcribe_file(client: OpenAI, audio_path: Path, language: Optional[str]) -> str:
    """Transcribe un único archivo (que cumple el límite de tamaño)."""
    with open(audio_path, "rb") as f:
        kwargs = {
            "model": config.TRANSCRIBE_MODEL,
            "file": f,
            "response_format": "text",
        }
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)
    # Con response_format="text" la respuesta es directamente la cadena.
    return result if isinstance(result, str) else getattr(result, "text", str(result))


def transcribe(
    audio_path: Path,
    language: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> str:
    """Transcribe un archivo de audio devolviendo el texto completo.

    `language` es un código ISO-639-1 opcional (p.ej. "es", "en"). Si es None,
    Whisper detecta el idioma automáticamente.
    """
    if not config.api_key_present():
        raise RuntimeError("Falta OPENAI_API_KEY. Configúrala en el archivo .env.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    size = audio_path.stat().st_size

    if size <= config.WHISPER_MAX_BYTES:
        _log("Transcribiendo audio...")
        return _transcribe_file(client, audio_path, language).strip()

    # Archivo demasiado grande: trocear.
    num_chunks = math.ceil(size / config.CHUNK_TARGET_BYTES)
    _log(f"Audio grande ({size / 1024 / 1024:.1f} MB); dividiendo en {num_chunks} partes...")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        chunks = _split_audio(audio_path, num_chunks, workdir)
        partes: list[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            _log(f"Transcribiendo parte {idx}/{len(chunks)}...")
            partes.append(_transcribe_file(client, chunk, language).strip())

    return "\n".join(p for p in partes if p).strip()
