"""Transcribe audio usando la API de Whisper de OpenAI.

Devuelve los segmentos con marcas de tiempo (inicio/fin/texto), lo que permite:
  - cachear la transcripción completa del vídeo una sola vez, y
  - aplicar luego rangos de tiempo filtrando segmentos, sin re-transcribir.

Si el archivo supera el límite de 25 MB de la API, lo trocea por tiempo con
ffmpeg, transcribe cada trozo y corrige las marcas de tiempo con el offset del
trozo antes de unirlos.
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

# Un segmento es un dict: {"start": float, "end": float, "text": str}
Segment = dict


def _probe_duration(audio_path: Path) -> Optional[float]:
    """Obtiene la duración en segundos del audio usando ffmpeg."""
    ffmpeg = get_ffmpeg_exe()
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", str(audio_path)], capture_output=True, text=True
        )
        for line in proc.stderr.splitlines():
            line = line.strip()
            if line.startswith("Duration:"):
                ts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = ts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return None


def _split_audio(audio_path: Path, num_chunks: int, workdir: Path) -> list[tuple[Path, float]]:
    """Divide el audio en trozos. Devuelve (ruta, offset_en_segundos) por trozo."""
    duration = _probe_duration(audio_path)
    if not duration:
        raise RuntimeError("No se pudo determinar la duración del audio para trocearlo.")

    ffmpeg = get_ffmpeg_exe()
    chunk_seconds = math.ceil(duration / num_chunks)
    chunks: list[tuple[Path, float]] = []

    for i in range(num_chunks):
        start = i * chunk_seconds
        out = workdir / f"chunk_{i:03d}.mp3"
        cmd = [
            ffmpeg, "-y", "-ss", str(start), "-t", str(chunk_seconds),
            "-i", str(audio_path), "-ac", "1", "-b:a", "64k", str(out),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if out.exists() and out.stat().st_size > 0:
            chunks.append((out, float(start)))

    if not chunks:
        raise RuntimeError("El troceado de audio no produjo ningún archivo.")
    return chunks


def _transcribe_file(
    client: OpenAI, audio_path: Path, language: Optional[str], offset: float = 0.0
) -> list[Segment]:
    """Transcribe un archivo y devuelve sus segmentos con offset aplicado."""
    with open(audio_path, "rb") as f:
        kwargs = {
            "model": config.TRANSCRIBE_MODEL,
            "file": f,
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)

    segments: list[Segment] = []
    raw_segments = getattr(result, "segments", None) or []
    if raw_segments:
        for seg in raw_segments:
            start = getattr(seg, "start", None)
            end = getattr(seg, "end", None)
            text = getattr(seg, "text", "")
            if start is None:  # por si llega como dict
                start, end, text = seg.get("start"), seg.get("end"), seg.get("text", "")
            segments.append(
                {"start": float(start) + offset, "end": float(end) + offset, "text": text.strip()}
            )
    else:
        # Sin segmentos: usamos el texto completo como un único segmento.
        text = getattr(result, "text", "") or ""
        segments.append({"start": offset, "end": offset, "text": text.strip()})
    return segments


def transcribe_segments(
    audio_path: Path,
    language: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> list[Segment]:
    """Transcribe un archivo completo y devuelve la lista de segmentos.

    `language` es un código ISO-639-1 opcional (p.ej. "es"). Si es None, Whisper
    detecta el idioma automáticamente.
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
        return _transcribe_file(client, audio_path, language)

    num_chunks = math.ceil(size / config.CHUNK_TARGET_BYTES)
    _log(f"Audio grande ({size / 1024 / 1024:.1f} MB); dividiendo en {num_chunks} partes...")

    segments: list[Segment] = []
    with tempfile.TemporaryDirectory() as tmp:
        chunks = _split_audio(audio_path, num_chunks, Path(tmp))
        for idx, (chunk, offset) in enumerate(chunks, start=1):
            _log(f"Transcribiendo parte {idx}/{len(chunks)}...")
            segments.extend(_transcribe_file(client, chunk, language, offset))
    return segments


def segments_to_text(segments: list[Segment]) -> str:
    """Une el texto de una lista de segmentos en un solo bloque."""
    return "\n".join(s["text"] for s in segments if s.get("text")).strip()
