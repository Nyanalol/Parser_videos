"""Preguntas y respuestas sobre el contenido de un vídeo (RAG ligero).

Dada la transcripción (segmentos con marcas de tiempo), responde preguntas
citando los momentos relevantes. Para transcripciones cortas mete todo el texto
en el contexto; para las largas usa recuperación por embeddings (RAG).
"""

from __future__ import annotations

import math
from typing import Optional

from openai import OpenAI

from . import config
from .timeranges import _fmt
from .usage import CostTracker

EMBED_MODEL = "text-embedding-3-small"
# Por debajo de este tamaño metemos toda la transcripción en el contexto.
STUFF_CHARS = 24_000
TOP_K = 8


def _make_chunks(segments: list[dict], target_chars: int = 700) -> list[dict]:
    """Agrupa segmentos en fragmentos de ~target_chars conservando el inicio."""
    chunks: list[dict] = []
    buf: list[str] = []
    start = None
    largo = 0
    for seg in segments:
        if start is None:
            start = float(seg.get("start", 0))
        buf.append((seg.get("text") or "").strip())
        largo += len(seg.get("text") or "")
        if largo >= target_chars:
            chunks.append({"start": start, "text": " ".join(buf).strip()})
            buf, start, largo = [], None, 0
    if buf:
        chunks.append({"start": start or 0.0, "text": " ".join(buf).strip()})
    return [c for c in chunks if c["text"]]


def _cosine(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def _format_context(chunks: list[dict]) -> str:
    return "\n".join(f"[{_fmt(c['start'])}] {c['text']}" for c in chunks)


def answer(
    question: str,
    segments: list[dict],
    history: Optional[list[dict]] = None,
    model: Optional[str] = None,
    cost: Optional[CostTracker] = None,
) -> str:
    """Responde una pregunta sobre el vídeo usando su transcripción."""
    if not config.api_key_present():
        raise RuntimeError("Falta OPENAI_API_KEY. Configúrala en el archivo .env.")
    model = model or config.SUMMARY_MODEL
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    full_text = " ".join((s.get("text") or "") for s in segments)
    if len(full_text) <= STUFF_CHARS:
        contexto = _format_context(_make_chunks(segments, 1200))
    else:
        # RAG: embeddings de los fragmentos + la pregunta, y top-k por similitud.
        chunks = _make_chunks(segments, 700)
        textos = [c["text"] for c in chunks]
        emb = client.embeddings.create(model=EMBED_MODEL, input=textos)
        vecs = [d.embedding for d in emb.data]
        qv = client.embeddings.create(model=EMBED_MODEL, input=[question]).data[0].embedding
        ranked = sorted(
            zip(chunks, vecs), key=lambda cv: _cosine(qv, cv[1]), reverse=True
        )
        contexto = _format_context([c for c, _ in ranked[:TOP_K]])

    system = (
        "Respondes preguntas sobre un vídeo usando SOLO su transcripción (con "
        "marcas de tiempo entre corchetes). Si la respuesta no está en la "
        "transcripción, dilo claramente. Cuando sea útil, cita el momento "
        "relevante en formato [m:ss]. Responde en el idioma de la pregunta."
    )
    mensajes = [{"role": "system", "content": system}]
    for turn in (history or []):
        mensajes.append(turn)
    mensajes.append({
        "role": "user",
        "content": (
            f"TRANSCRIPCIÓN (fragmentos):\n{contexto}\n\n"
            f"PREGUNTA: {question}"
        ),
    })

    resp = client.chat.completions.create(
        model=model, messages=mensajes, temperature=0.2, max_tokens=800
    )
    if cost is not None and getattr(resp, "usage", None):
        cost.add_chat(resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return resp.choices[0].message.content.strip()
