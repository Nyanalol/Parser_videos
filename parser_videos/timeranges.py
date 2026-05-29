"""Análisis de rangos de tiempo y extracción de fragmentos de audio.

Permite al usuario indicar qué partes del vídeo quiere procesar, por ejemplo:

    14:34-16:34, 20:00-21:30
    1:02:10 - 1:05:00
    90-120          (segundos sueltos también valen)

Cada rango se interpreta como "inicio-fin". Si el campo está vacío se procesa
el vídeo completo.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ffmpeg_utils import get_ffmpeg_exe


@dataclass(frozen=True)
class TimeRange:
    """Un rango de tiempo en segundos."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"El fin ({self.end}s) debe ser mayor que el inicio ({self.start}s)."
            )

    @property
    def label(self) -> str:
        return f"{_fmt(self.start)}-{_fmt(self.end)}"


def _fmt(seconds: float) -> str:
    """Formatea segundos como H:MM:SS o M:SS."""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_timestamp(text: str) -> float:
    """Convierte 'H:MM:SS', 'M:SS' o 'SS' (admite decimales) a segundos."""
    text = text.strip()
    if not text:
        raise ValueError("Marca de tiempo vacía.")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Marca de tiempo no válida: '{text}'")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"Marca de tiempo no válida: '{text}'")
    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def parse_ranges(text: str) -> list[TimeRange]:
    """Parsea una cadena de rangos separados por comas.

    Devuelve lista vacía si `text` está vacío (= vídeo completo).
    """
    text = (text or "").strip()
    if not text:
        return []

    ranges: list[TimeRange] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" not in chunk:
            raise ValueError(
                f"Rango no válido: '{chunk}'. Usa el formato inicio-fin, p.ej. 14:34-16:34."
            )
        start_str, end_str = chunk.split("-", 1)
        ranges.append(
            TimeRange(parse_timestamp(start_str), parse_timestamp(end_str))
        )
    return ranges


def extract_ranges(
    audio_path: Path,
    ranges: list[TimeRange],
    workdir: Optional[Path] = None,
) -> Path:
    """Extrae y concatena los rangos indicados del audio en un único MP3.

    Si `ranges` está vacío devuelve el audio original sin tocar.
    """
    if not ranges:
        return audio_path

    ffmpeg = get_ffmpeg_exe()
    target_dir = workdir or Path(tempfile.mkdtemp(prefix="ranges_"))
    target_dir.mkdir(parents=True, exist_ok=True)

    piezas: list[Path] = []
    for i, r in enumerate(ranges):
        out = target_dir / f"range_{i:03d}.mp3"
        cmd = [
            ffmpeg, "-y",
            "-ss", str(r.start),
            "-to", str(r.end),
            "-i", str(audio_path),
            "-ac", "1",
            "-b:a", "64k",
            str(out),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if out.exists() and out.stat().st_size > 0:
            piezas.append(out)

    if not piezas:
        raise RuntimeError("No se pudo extraer ningún fragmento de los rangos dados.")

    if len(piezas) == 1:
        return piezas[0]

    # Concatenar las piezas en un solo archivo con el demuxer concat de ffmpeg.
    lista = target_dir / "concat.txt"
    lista.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in piezas), encoding="utf-8"
    )
    combinado = target_dir / "combinado.mp3"
    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista),
        "-c", "copy",
        str(combinado),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return combinado
