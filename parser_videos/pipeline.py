"""Orquesta el proceso completo: descarga, transcripción, rangos y resumen.

Soporta:
  - Un único vídeo o varios vídeos combinados en un solo resumen.
  - Rangos de tiempo por vídeo (campo vacío = vídeo completo).
  - Caché: si un vídeo ya se transcribió, se reutiliza sin volver a parsearlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import cache, config, downloader, summarizer, timeranges, transcriber

ProgressCallback = Callable[[str], None]


@dataclass
class VideoRequest:
    """Un vídeo a procesar y, opcionalmente, los rangos que interesan de él."""

    url: str
    ranges_text: str = ""


@dataclass
class PipelineResult:
    output_path: Path
    markdown: str
    transcript: str
    titles: list[str] = field(default_factory=list)


def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip().strip(".")
    return name[:120] or "resumen"


def _process_one(
    req: VideoRequest,
    transcribe_language: Optional[str],
    on_progress: Optional[ProgressCallback],
) -> tuple[str, str, str]:
    """Procesa un vídeo y devuelve (título, url, texto_de_los_rangos)."""

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    ranges = timeranges.parse_ranges(req.ranges_text)

    # 1) Metadatos (sin descargar).
    info = downloader.probe(req.url)
    _log(f"Vídeo: {info.title}")

    # 2) ¿Tenemos ya la transcripción en caché?
    cached = cache.load_segments(info.video_id, transcribe_language)
    if cached:
        _log("Transcripción encontrada en caché; se reutiliza.")
        segments = cached["segments"]
    else:
        # 3) Descargar audio (también cacheado por id) y transcribir.
        result = downloader.download_audio(req.url, info=info, on_progress=on_progress)
        segments = transcriber.transcribe_segments(
            result.audio_path, language=transcribe_language, on_progress=on_progress
        )
        cache.save_segments(
            info.video_id, transcribe_language, info.title, info.webpage_url, segments
        )

    # 4) Aplicar rangos (filtrado de segmentos, instantáneo).
    seleccion = timeranges.filter_segments(segments, ranges)
    texto = transcriber.segments_to_text(seleccion)
    if not texto:
        raise RuntimeError(
            f"No se obtuvo texto para '{info.title}'. Revisa los rangos indicados."
        )
    return info.title, info.webpage_url, texto


def process(
    requests: list[VideoRequest],
    custom_prompt: str = "",
    summary_language: Optional[str] = None,
    transcribe_language: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> PipelineResult:
    """Procesa uno o varios vídeos y genera un único resumen en Markdown."""
    if not requests:
        raise ValueError("No se indicó ningún vídeo.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    config.ensure_dirs()

    titulos: list[str] = []
    urls: list[str] = []
    bloques: list[str] = []
    etiquetas_rangos: list[str] = []

    for i, req in enumerate(requests, start=1):
        _log(f"[{i}/{len(requests)}] Procesando vídeo...")
        titulo, url, texto = _process_one(req, transcribe_language, on_progress)
        titulos.append(titulo)
        urls.append(url)
        etiquetas_rangos.append(timeranges.ranges_label(timeranges.parse_ranges(req.ranges_text)))
        if len(requests) > 1:
            bloques.append(f"### Vídeo {i}: {titulo}\n{texto}")
        else:
            bloques.append(texto)

    transcript = "\n\n".join(bloques)

    # Título y fuente del documento final.
    if len(requests) == 1:
        titulo_doc = titulos[0]
        fuente = urls[0]
        ranges_label = etiquetas_rangos[0]
    else:
        titulo_doc = f"Resumen combinado de {len(requests)} vídeos"
        fuente = " | ".join(urls)
        ranges_label = "; ".join(
            f"{t} [{r}]" for t, r in zip(titulos, etiquetas_rangos)
        )

    # Guardar la transcripción combinada por si se quiere consultar.
    transcript_path = config.OUTPUT_DIR / f"{_sanitize(titulo_doc)}.transcripcion.txt"
    transcript_path.write_text(transcript, encoding="utf-8")

    # Resumen.
    summary = summarizer.summarize(
        transcript=transcript,
        title=titulo_doc,
        source_url=fuente,
        custom_prompt=custom_prompt,
        summary_language=summary_language,
        ranges_label=ranges_label,
        on_progress=on_progress,
    )

    _log("¡Listo!")
    return PipelineResult(
        output_path=summary.output_path,
        markdown=summary.markdown,
        transcript=transcript,
        titles=titulos,
    )
