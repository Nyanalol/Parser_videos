"""Obtención de subtítulos ya existentes en YouTube (y otras webs).

Si el vídeo trae subtítulos (manuales o automáticos), los descargamos y los
convertimos a segmentos con marcas de tiempo. Así nos saltamos Whisper: es
gratis e instantáneo. Si no hay subtítulos, se devuelve None y el flujo normal
recurre a la transcripción con Whisper.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Optional

from yt_dlp import YoutubeDL

# Segmento: {"start": float, "end": float, "text": str}
Segment = dict

_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(text: str) -> list[Segment]:
    """Parsea un archivo WebVTT a segmentos, limpiando etiquetas y duplicados."""
    segments: list[Segment] = []
    bloques = re.split(r"\n\s*\n", text)
    ultimo_texto = ""
    for bloque in bloques:
        lineas = [l for l in bloque.splitlines() if l.strip()]
        if not lineas:
            continue
        # Buscar la línea con el rango de tiempo.
        idx_tiempo = next((i for i, l in enumerate(lineas) if "-->" in l), None)
        if idx_tiempo is None:
            continue
        marcas = _TS.findall(lineas[idx_tiempo])
        if len(marcas) < 2:
            continue
        start = _ts_to_seconds(*marcas[0])
        end = _ts_to_seconds(*marcas[1])
        # Texto: líneas siguientes, sin etiquetas <...> ni timestamps internos.
        crudo = " ".join(lineas[idx_tiempo + 1:])
        crudo = re.sub(r"<[^>]+>", "", crudo)
        crudo = re.sub(r"\s+", " ", crudo).strip()
        if not crudo or crudo == ultimo_texto:
            continue
        ultimo_texto = crudo
        segments.append({"start": start, "end": end, "text": crudo})
    return segments


def fetch_segments(
    url: str,
    preferred_lang: Optional[str] = None,
) -> Optional[list[Segment]]:
    """Descarga subtítulos del vídeo y los devuelve como segmentos, o None.

    Prefiere subtítulos manuales sobre los automáticos, y el idioma indicado si
    está disponible.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        langs = [preferred_lang] if preferred_lang else ["es", "en"]
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs + [f"{l}.*" for l in langs],
            "subtitlesformat": "vtt",
            "outtmpl": str(tmpdir / "%(id)s.%(ext)s"),
        }
        try:
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception:
            return None

        vtts = list(tmpdir.glob("*.vtt"))
        if not vtts:
            return None

        # Preferir subtítulos manuales (los automáticos suelen incluir el código
        # de idioma seguido de marcas tipo ".es.vtt" igualmente; priorizamos los
        # que NO parezcan autogenerados por nombre, y el idioma preferido).
        def _score(p: Path) -> tuple:
            nombre = p.name.lower()
            auto = "auto" in nombre or "a." in nombre
            lang_ok = preferred_lang and f".{preferred_lang}" in nombre
            return (0 if lang_ok else 1, 0 if not auto else 1, len(nombre))

        vtts.sort(key=_score)
        try:
            contenido = vtts[0].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        segments = _parse_vtt(contenido)
        return segments or None
