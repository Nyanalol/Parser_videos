"""Tests de la lógica pura (sin red ni llamadas a OpenAI)."""

from __future__ import annotations

import pytest

from parser_videos import qa, subtitles, timeranges, usage
from parser_videos import exporter, summarizer, downloader


# ---------- timeranges ----------

def test_parse_timestamp_formatos():
    assert timeranges.parse_timestamp("90") == 90
    assert timeranges.parse_timestamp("1:30") == 90
    assert timeranges.parse_timestamp("1:00:00") == 3600


def test_parse_ranges_vacio_es_video_completo():
    assert timeranges.parse_ranges("") == []
    assert timeranges.parse_ranges("   ") == []


def test_parse_ranges_multiple():
    r = timeranges.parse_ranges("0:10-0:20, 1:00-1:30")
    assert len(r) == 2
    assert r[0].start == 10 and r[0].end == 20
    assert r[1].start == 60 and r[1].end == 90


def test_parse_ranges_invalidos():
    with pytest.raises(ValueError):
        timeranges.parse_ranges("10")  # sin guión
    with pytest.raises(ValueError):
        timeranges.parse_ranges("20-10")  # fin antes que inicio


def test_filter_segments_por_punto_medio():
    segs = [
        {"start": 0, "end": 10, "text": "a"},
        {"start": 10, "end": 20, "text": "b"},
        {"start": 20, "end": 30, "text": "c"},
    ]
    # Punto medio de "a"=5s, "b"=15s, "c"=25s; el rango 3-16 incluye a y b.
    out = timeranges.filter_segments(segs, timeranges.parse_ranges("0:03-0:16"))
    assert [s["text"] for s in out] == ["a", "b"]
    # Un rango 8-16 solo cae sobre el punto medio de "b".
    solo_b = timeranges.filter_segments(segs, timeranges.parse_ranges("0:08-0:16"))
    assert [s["text"] for s in solo_b] == ["b"]


def test_filter_segments_sin_rangos_devuelve_todo():
    segs = [{"start": 0, "end": 1, "text": "x"}]
    assert timeranges.filter_segments(segs, []) == segs


def test_ranges_label():
    assert timeranges.ranges_label([]) == "vídeo completo"
    assert "0:10" in timeranges.ranges_label(timeranges.parse_ranges("0:10-0:20"))


# ---------- subtitles (parseo VTT) ----------

def test_parse_vtt_basico():
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\nHola mundo\n\n"
        "00:00:03.000 --> 00:00:05.000\n<c>Segunda</c> línea\n"
    )
    segs = subtitles._parse_vtt(vtt)
    assert len(segs) == 2
    assert segs[0]["start"] == 1.0 and segs[0]["end"] == 3.0
    assert segs[0]["text"] == "Hola mundo"
    assert segs[1]["text"] == "Segunda línea"  # etiquetas <c> eliminadas


def test_parse_vtt_elimina_duplicados_consecutivos():
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\nrepetido\n\n"
        "00:00:02.000 --> 00:00:03.000\nrepetido\n"
    )
    assert len(subtitles._parse_vtt(vtt)) == 1


# ---------- usage (coste) ----------

def test_cost_tracker_whisper_y_chat():
    c = usage.CostTracker(model="gpt-4o-mini")
    c.add_whisper(120)  # 2 min
    c.add_chat(1_000_000, 0)  # 1M tokens entrada
    esperado = 2 * usage.WHISPER_PER_MIN + usage.CHAT_PRICES["gpt-4o-mini"][0]
    assert c.total_usd == pytest.approx(esperado)


def test_cost_tracker_cache_sin_coste():
    c = usage.CostTracker()
    assert c.total_usd == 0.0
    assert "caché" in c.summary()


# ---------- exporter ----------

def test_sanitize_filename():
    assert exporter.sanitize_filename('a/b:c*?.md') == "a_b_c__.md"
    assert exporter.sanitize_filename("") == "resumen"


def test_to_html_incluye_cuerpo_y_titulo():
    html = exporter._to_html("Mi título", "# Hola\n\n- uno\n- dos")
    assert "<title>Mi título</title>" in html
    assert "<h1" in html and "Hola" in html
    assert "<li>uno</li>" in html


# ---------- summarizer (construcción de prompt) ----------

def test_build_user_msg_incluye_extension_y_plantilla():
    msg = summarizer._build_user_msg(
        "texto", "Título", "", "Español", "Muy breve", "Acta de reunión"
    )
    assert "EXTENSIÓN REQUERIDA" in msg
    assert "ACTA DE REUNIÓN" in msg
    assert "Español" in msg


def test_length_choices_tienen_max_tokens():
    for v in summarizer.LENGTH_CHOICES.values():
        assert "instruction" in v and v["max_tokens"] > 0


# ---------- qa ----------

def test_make_chunks_agrupa():
    segs = [{"start": i, "end": i + 1, "text": "palabra " * 50} for i in range(10)]
    chunks = qa._make_chunks(segs, target_chars=700)
    assert len(chunks) >= 2
    assert all(c["text"] for c in chunks)


def test_cosine():
    assert qa._cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert qa._cosine([1, 0], [0, 1]) == pytest.approx(0.0)


# ---------- downloader ----------

def test_is_local_path(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    assert downloader.is_local_path(str(f)) is True
    assert downloader.is_local_path("https://youtube.com/watch?v=x") is False
