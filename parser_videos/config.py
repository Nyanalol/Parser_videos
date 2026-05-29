"""Configuración central de la aplicación.

Carga las variables de entorno desde un archivo `.env` (si existe) y expone
los ajustes que usa el resto del programa.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga el .env situado en la raíz del proyecto (un nivel por encima del paquete).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _desktop_dir() -> Path:
    """Localiza el escritorio del usuario (soporta redirección a OneDrive).

    En Windows lo lee del registro; si falla, usa ~/Desktop.
    """
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        value, _ = winreg.QueryValueEx(key, "Desktop")
        path = Path(os.path.expandvars(value))
        if path.exists():
            return path
    except Exception:
        pass
    return Path.home() / "Desktop"


# Carpetas de trabajo.
DOWNLOADS_DIR = _PROJECT_ROOT / "downloads"
CACHE_DIR = _PROJECT_ROOT / ".cache"
# Los resúmenes se guardan en una carpeta del escritorio, fácil de encontrar.
OUTPUT_DIR = _desktop_dir() / "Transcripciones Videos"

# Clave y modelos de OpenAI.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini").strip()
TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1").strip()

# Límite de tamaño de la API de Whisper (25 MB). Usamos un umbral algo menor
# para dejar margen y trocear el audio antes de superarlo.
WHISPER_MAX_BYTES = 25 * 1024 * 1024
CHUNK_TARGET_BYTES = 24 * 1024 * 1024


def ensure_dirs() -> None:
    """Crea las carpetas de trabajo si no existen."""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def api_key_present() -> bool:
    """Indica si hay una clave de OpenAI configurada."""
    return bool(OPENAI_API_KEY)
