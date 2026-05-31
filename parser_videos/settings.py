"""Preferencias del usuario persistentes entre sesiones.

Se guardan en un pequeño JSON en la carpeta del proyecto para recordar las
últimas opciones elegidas en la interfaz (idiomas, extensión, modelo, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"

# Valores por defecto si aún no hay archivo de preferencias.
DEFAULTS: dict[str, Any] = {
    "summary_language": "Español",
    "audio_language": "Detección automática",
    "length_level": "Equilibrado",
    "template": "General",
    "model": "gpt-4o-mini",
    "custom_prompt": "",
}


def load() -> dict[str, Any]:
    """Devuelve las preferencias guardadas, completadas con los valores por defecto."""
    data = dict(DEFAULTS)
    try:
        if _SETTINGS_PATH.exists():
            data.update(json.loads(_SETTINGS_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    return data


def save(values: dict[str, Any]) -> None:
    """Guarda (fusionando) las preferencias indicadas."""
    data = load()
    data.update(values)
    try:
        _SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
