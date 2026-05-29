"""Localiza el binario de ffmpeg.

Usa el ffmpeg embebido por `imageio-ffmpeg`, de forma que el usuario no necesita
instalar ffmpeg en el sistema. Si por algún motivo no estuviera disponible, cae
en el ffmpeg del PATH (si existe).
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_ffmpeg_exe() -> str:
    """Devuelve la ruta al ejecutable de ffmpeg.

    Lanza RuntimeError si no se encuentra por ningún medio.
    """
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    raise RuntimeError(
        "No se encontró ffmpeg. Instala las dependencias con "
        "'pip install -r requirements.txt' (incluye imageio-ffmpeg)."
    )


def get_ffmpeg_dir() -> str:
    """Devuelve la carpeta que contiene el ejecutable de ffmpeg.

    yt-dlp espera la carpeta, no el ejecutable, en la opción `ffmpeg_location`.
    """
    return str(Path(get_ffmpeg_exe()).parent)
