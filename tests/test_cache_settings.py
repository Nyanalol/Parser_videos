"""Tests de caché y preferencias usando carpetas temporales."""

from __future__ import annotations

from parser_videos import cache, config, settings, maintenance


def test_cache_guarda_y_carga(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    segs = [{"start": 0, "end": 1, "text": "hola"}]
    cache.save_segments("vid1", "es", "Título", "http://x", segs, source="subtitles")

    data = cache.load_segments("vid1", "es")
    assert data is not None
    assert data["title"] == "Título"
    assert data["source"] == "subtitles"
    assert data["segments"] == segs


def test_cache_miss_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    assert cache.load_segments("noexiste", None) is None


def test_list_cached_ordena_y_lista(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    cache.save_segments("a", None, "A", "u1", [], source="whisper")
    cache.save_segments("b", None, "B", "u2", [], source="subtitles")
    items = cache.list_cached()
    assert {i["title"] for i in items} == {"A", "B"}
    assert all("path" in i and "source" in i for i in items)


def test_settings_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_SETTINGS_PATH", tmp_path / "settings.json")
    # Sin archivo: devuelve los valores por defecto.
    assert settings.load()["length_level"] == settings.DEFAULTS["length_level"]
    # Guarda y recupera.
    settings.save({"length_level": "Exhaustivo", "model": "gpt-4o"})
    data = settings.load()
    assert data["length_level"] == "Exhaustivo"
    assert data["model"] == "gpt-4o"
    # Las claves no tocadas conservan el valor por defecto.
    assert data["summary_language"] == settings.DEFAULTS["summary_language"]


def test_clean_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOWNLOADS_DIR", tmp_path)
    (tmp_path / "a.mp3").write_bytes(b"12345")
    (tmp_path / "b.mp3").write_bytes(b"67")
    n, mb = maintenance.clean_downloads()
    assert n == 2
    assert mb > 0
    assert not list(tmp_path.glob("*.mp3"))
