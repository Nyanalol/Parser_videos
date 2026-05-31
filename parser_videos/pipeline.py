"""Orquesta el proceso completo: obtención de texto, rangos y resumen.

Para cada entrada (URL o archivo local):
  1. Si es una playlist/canal, se expande en sus vídeos.
  2. Se intenta usar los SUBTÍTULOS de YouTube (gratis); si no hay, se descarga
     el audio y se transcribe con Whisper.
  3. Se cachea la transcripción por id (no se reprocesa dos veces).
  4. Se aplican los rangos de tiempo y se combina/resumen.

Varias entradas (o una playlist) se combinan en un único resumen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import (
    cache,
    config,
    downloader,
    exporter,
    subtitles,
    summarizer,
    timeranges,
    transcriber,
)
from .usage import CostTracker

ProgressCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]


class CancelledError(Exception):
    """Se lanza cuando el usuario cancela el proceso."""


def _check_cancel(cancel_check: Optional[CancelCheck]) -> None:
    if cancel_check and cancel_check():
        raise CancelledError("Proceso cancelado por el usuario.")


@dataclass
class VideoRequest:
    """Un vídeo/archivo a procesar y, opcionalmente, los rangos que interesan."""

    url: str
    ranges_text: str = ""


@dataclass
class PipelineResult:
    md_path: Path
    html_path: Path
    obsidian_path: Path
    transcript_path: Path
    markdown: str
    transcript: str
    cost_usd: float = 0.0
    titles: list[str] = field(default_factory=list)


@dataclass
class _One:
    title: str
    url: str
    text: str
    segments: list
    used_subtitles: bool


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _process_one(
    req: VideoRequest,
    transcribe_language: Optional[str],
    use_subtitles: bool,
    cost: CostTracker,
    on_progress: Optional[ProgressCallback],
) -> _One:
    """Obtiene la transcripción (subtítulos o Whisper) y aplica los rangos."""

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    ranges = timeranges.parse_ranges(req.ranges_text)
    info = downloader.probe(req.url)
    _log(f"Vídeo: {info.title}")

    used_subtitles = False
    cached = cache.load_segments(info.video_id, transcribe_language)
    if cached:
        _log("Transcripción encontrada en caché; se reutiliza.")
        segments = cached["segments"]
        used_subtitles = cached.get("source") == "subtitles"
    else:
        segments = None
        # 1) Intentar subtítulos de YouTube (gratis), salvo archivo local.
        if use_subtitles and not downloader.is_local_path(req.url):
            _log("Buscando subtítulos existentes...")
            segments = subtitles.fetch_segments(req.url, transcribe_language)
            if segments:
                used_subtitles = True
                _log("✔ Subtítulos encontrados; nos saltamos Whisper (gratis).")

        # 2) Si no hay subtítulos, descargar audio y transcribir con Whisper.
        if not segments:
            result = downloader.download_audio(req.url, info=info, on_progress=on_progress)
            segments = transcriber.transcribe_segments(
                result.audio_path, language=transcribe_language, on_progress=on_progress
            )
            if info.duration_seconds:
                cost.add_whisper(info.duration_seconds)

        cache.save_segments(
            info.video_id, transcribe_language, info.title, info.webpage_url,
            segments, source="subtitles" if used_subtitles else "whisper",
        )

    seleccion = timeranges.filter_segments(segments, ranges)
    texto = transcriber.segments_to_text(seleccion)
    if not texto:
        raise RuntimeError(
            f"No se obtuvo texto para '{info.title}'. Revisa los rangos indicados."
        )
    return _One(info.title, info.webpage_url, texto, seleccion, used_subtitles)


def _timestamp_index(segments: list, base_url: str, step: float = 90.0) -> str:
    """Crea un índice con marcas de tiempo clicables (solo YouTube)."""
    if not segments or not _is_youtube(base_url):
        return ""
    sep = "&" if "?" in base_url else "?"
    lineas = ["", "## Índice", ""]
    proximo = 0.0
    for seg in segments:
        start = float(seg.get("start", 0))
        if start < proximo:
            continue
        proximo = start + step
        texto = (seg.get("text") or "").strip()
        if not texto:
            continue
        if len(texto) > 80:
            texto = texto[:77] + "..."
        link = f"{base_url}{sep}t={int(start)}s"
        lineas.append(f"- [{timeranges._fmt(start)}]({link}) {texto}")
    return "\n".join(lineas) + "\n" if len(lineas) > 3 else ""


def process(
    requests: list[VideoRequest],
    custom_prompt: str = "",
    summary_language: Optional[str] = None,
    length_level: str = summarizer.DEFAULT_LENGTH,
    template: str = summarizer.DEFAULT_TEMPLATE,
    model: Optional[str] = None,
    transcribe_language: Optional[str] = None,
    use_subtitles: bool = True,
    add_timestamps: bool = True,
    on_progress: Optional[ProgressCallback] = None,
    cancel_check: Optional[CancelCheck] = None,
) -> PipelineResult:
    """Procesa una o varias entradas y genera un único resumen en Markdown."""
    if not requests:
        raise ValueError("No se indicó ninguna entrada.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    config.ensure_dirs()
    cost = CostTracker(model=model or config.SUMMARY_MODEL)

    # Expandir playlists/canales en sus vídeos.
    expandidas: list[VideoRequest] = []
    for req in requests:
        urls = downloader.expand_playlist(req.url)
        if len(urls) > 1:
            _log(f"Playlist detectada: {len(urls)} vídeos.")
        for u in urls:
            expandidas.append(VideoRequest(url=u, ranges_text=req.ranges_text))

    procesados: list[_One] = []
    for i, req in enumerate(expandidas, start=1):
        _check_cancel(cancel_check)
        _log(f"[{i}/{len(expandidas)}] Procesando...")
        procesados.append(
            _process_one(req, transcribe_language, use_subtitles, cost, on_progress)
        )
    _check_cancel(cancel_check)

    multiple = len(procesados) > 1
    bloques = [
        f"### Vídeo {i}: {p.title}\n{p.text}" if multiple else p.text
        for i, p in enumerate(procesados, start=1)
    ]
    transcript = "\n\n".join(bloques)

    if not multiple:
        titulo_doc, fuente = procesados[0].title, procesados[0].url
        ranges_label = timeranges.ranges_label(timeranges.parse_ranges(expandidas[0].ranges_text))
    else:
        titulo_doc = f"Resumen combinado de {len(procesados)} vídeos"
        fuente = " | ".join(p.url for p in procesados)
        ranges_label = ""

    markdown = summarizer.summarize(
        transcript=transcript,
        title=titulo_doc,
        source_url=fuente,
        custom_prompt=custom_prompt,
        summary_language=summary_language,
        length_level=length_level,
        template=template,
        model=model,
        ranges_label=ranges_label,
        cost=cost,
        on_progress=on_progress,
    )

    # Índice con marcas de tiempo clicables (solo vídeo único de YouTube).
    if add_timestamps and not multiple:
        idx = _timestamp_index(procesados[0].segments, procesados[0].url)
        if idx:
            markdown += "\n" + idx

    _log("Exportando a Markdown, HTML y Obsidian...")
    exp = exporter.export(titulo_doc, markdown, transcript)

    _log(cost.summary())
    _log("¡Listo!")
    return PipelineResult(
        md_path=exp.md_path,
        html_path=exp.html_path,
        obsidian_path=exp.obsidian_path,
        transcript_path=exp.transcript_path,
        markdown=markdown,
        transcript=transcript,
        cost_usd=cost.total_usd,
        titles=[p.title for p in procesados],
    )
