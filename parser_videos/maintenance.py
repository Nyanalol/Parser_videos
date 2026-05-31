"""Tareas de mantenimiento: limpieza de archivos temporales.

Los audios descargados (carpeta downloads/) se acumulan. La transcripción ya
queda cacheada en .cache/, así que los MP3 pueden borrarse sin perder nada.
"""

from __future__ import annotations

from . import config


def downloads_size_mb() -> float:
    """Tamaño total de la carpeta de descargas en MB."""
    if not config.DOWNLOADS_DIR.exists():
        return 0.0
    total = sum(f.stat().st_size for f in config.DOWNLOADS_DIR.glob("*") if f.is_file())
    return total / (1024 * 1024)


def clean_downloads() -> tuple[int, float]:
    """Borra los audios descargados. Devuelve (nº archivos, MB liberados).

    Es seguro: las transcripciones permanecen en la caché.
    """
    if not config.DOWNLOADS_DIR.exists():
        return 0, 0.0
    freed = 0.0
    count = 0
    for f in config.DOWNLOADS_DIR.glob("*"):
        if f.is_file():
            try:
                size = f.stat().st_size
                f.unlink()
                freed += size
                count += 1
            except OSError:
                pass
    return count, freed / (1024 * 1024)
