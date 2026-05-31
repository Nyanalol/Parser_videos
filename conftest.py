"""Asegura que el paquete parser_videos es importable al ejecutar pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
