"""Caché en disco de transcripciones completas de vídeos.

La clave depende del id del vídeo, el modelo de transcripción y el idioma
forzado (si lo hubiera). Así, si se vuelve a pedir el mismo vídeo, se reutiliza
la transcripción guardada en lugar de descargar y transcribir de nuevo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import config


def _cache_key(video_id: str, language: Optional[str]) -> str:
    lang = language or "auto"
    # El modelo forma parte de la clave por si se cambia en el futuro.
    return f"{video_id}__{config.TRANSCRIBE_MODEL}__{lang}"


def _cache_path(video_id: str, language: Optional[str]) -> Path:
    return config.CACHE_DIR / f"{_cache_key(video_id, language)}.json"


def load_segments(video_id: str, language: Optional[str]) -> Optional[dict]:
    """Devuelve los datos cacheados {title, url, source, segments} o None."""
    path = _cache_path(video_id, language)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_segments(
    video_id: str,
    language: Optional[str],
    title: str,
    url: str,
    segments: list[dict],
    source: str = "whisper",
) -> None:
    """Guarda la transcripción completa del vídeo en la caché.

    `source` indica de dónde salió la transcripción: "whisper" o "subtitles".
    """
    config.ensure_dirs()
    data = {
        "video_id": video_id,
        "title": title,
        "url": url,
        "source": source,
        "segments": segments,
    }
    _cache_path(video_id, language).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_cached() -> list[dict]:
    """Lista las transcripciones cacheadas (para el historial de la app).

    Devuelve dicts con title, url, source y la ruta del archivo de caché,
    ordenados por fecha de modificación (más recientes primero).
    """
    if not config.CACHE_DIR.exists():
        return []
    items: list[dict] = []
    for p in config.CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append({
            "title": data.get("title", p.stem),
            "url": data.get("url", ""),
            "source": data.get("source", "whisper"),
            "mtime": p.stat().st_mtime,
            "path": str(p),
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items
