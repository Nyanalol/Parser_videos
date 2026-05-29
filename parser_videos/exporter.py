"""Exporta el resultado a las distintas carpetas/formatos del escritorio.

Genera, para cada resumen:
  - Markdown/<título>.md         -> el resumen en Markdown
  - Obsidian/<título>.md         -> copia para el vault de Obsidian
  - HTML/<título>.html           -> el resumen renderizado para el navegador
  - Transcripciones/<título>.txt -> la transcripción usada
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import markdown as md

from . import config


@dataclass
class ExportResult:
    md_path: Path
    obsidian_path: Path
    html_path: Path
    transcript_path: Path


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip().strip(".")
    return name[:120] or "resumen"


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.65; max-width: 820px; margin: 40px auto; padding: 0 20px;
    color: #1a1a1a; background: #fff;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #e6e6e6; background: #1e1e1e; }}
    a {{ color: #6db3ff; }}
    code, pre {{ background: #2a2a2a; }}
    hr {{ border-color: #444; }}
  }}
  h1, h2, h3 {{ line-height: 1.25; }}
  h1 {{ border-bottom: 2px solid #4a90e2; padding-bottom: .3em; }}
  code {{ background: #f0f0f0; padding: .15em .35em; border-radius: 4px; font-size: .9em; }}
  pre {{ background: #f0f0f0; padding: 12px; border-radius: 8px; overflow:auto; }}
  blockquote {{ border-left: 4px solid #4a90e2; margin: 0; padding-left: 16px; color: #666; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _to_html(title: str, markdown_text: str) -> str:
    body = md.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br", "toc"],
    )
    return _HTML_TEMPLATE.format(title=title, body=body)


def export(title: str, markdown_text: str, transcript: str) -> ExportResult:
    """Escribe los cuatro archivos y devuelve sus rutas."""
    config.ensure_dirs()
    name = sanitize_filename(title)

    md_path = config.MD_DIR / f"{name}.md"
    md_path.write_text(markdown_text, encoding="utf-8")

    obsidian_path = config.OBSIDIAN_DIR / f"{name}.md"
    obsidian_path.write_text(markdown_text, encoding="utf-8")

    html_path = config.HTML_DIR / f"{name}.html"
    html_path.write_text(_to_html(title, markdown_text), encoding="utf-8")

    transcript_path = config.TRANSCRIPTS_DIR / f"{name}.txt"
    transcript_path.write_text(transcript, encoding="utf-8")

    return ExportResult(
        md_path=md_path,
        obsidian_path=obsidian_path,
        html_path=html_path,
        transcript_path=transcript_path,
    )
