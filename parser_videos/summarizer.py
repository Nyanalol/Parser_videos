"""Genera un resumen en Markdown a partir de una transcripción usando GPT.

El usuario puede indicar instrucciones personalizadas (tono, enfoque, formato...).
Si no indica nada, se usa un prompt por defecto que produce un resumen claro y
estructurado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from openai import OpenAI

from . import config

ProgressCallback = Callable[[str], None]

# Instrucciones por defecto si el usuario no escribe nada en el campo de prompt.
DEFAULT_PROMPT = (
    "Resume el contenido de forma clara y estructurada. Incluye una breve "
    "introducción con la idea principal, los puntos clave en una lista y, si "
    "procede, las conclusiones. Tono neutro y profesional."
)

# Mensaje de sistema que fija el rol y el formato de salida.
_SYSTEM = (
    "Eres un asistente experto en sintetizar el contenido de vídeos a partir de "
    "su transcripción. Devuelves siempre Markdown bien formado, sin envolverlo "
    "en bloques de código. No inventas información que no esté en la "
    "transcripción."
)

# Idiomas disponibles para el resumen. La clave es lo que se muestra en la GUI.
LANGUAGE_CHOICES = {
    "Español": "es",
    "Inglés": "en",
    "Mismo que el vídeo": None,
}


def _language_instruction(language_name: Optional[str]) -> str:
    if not language_name or language_name == "Mismo que el vídeo":
        return "Escribe el resumen en el mismo idioma que la transcripción."
    return f"Escribe el resumen en {language_name}."


def summarize(
    transcript: str,
    title: str,
    source_url: str,
    custom_prompt: str = "",
    summary_language: Optional[str] = None,
    ranges_label: str = "",
    on_progress: Optional[ProgressCallback] = None,
) -> str:
    """Resume la transcripción y devuelve el documento en Markdown.

    - `custom_prompt`: instrucciones del usuario; si está vacío se usa el por defecto.
    - `summary_language`: nombre del idioma (clave de LANGUAGE_CHOICES) o None.
    - `ranges_label`: descripción de los fragmentos procesados (para la cabecera).
    """
    if not config.api_key_present():
        raise RuntimeError("Falta OPENAI_API_KEY. Configúrala en el archivo .env.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    config.ensure_dirs()
    instrucciones = (custom_prompt or "").strip() or DEFAULT_PROMPT

    user_msg = (
        f"{instrucciones}\n\n"
        f"{_language_instruction(summary_language)}\n\n"
        f"Título del vídeo: {title}\n"
        "--- TRANSCRIPCIÓN ---\n"
        f"{transcript}\n"
        "--- FIN DE LA TRANSCRIPCIÓN ---"
    )

    _log("Generando resumen con OpenAI...")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    cuerpo = response.choices[0].message.content.strip()

    # Cabecera con metadatos.
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    cabecera = [f"# {title}", "", f"- **Fuente:** {source_url}", f"- **Generado:** {fecha}"]
    if ranges_label:
        cabecera.append(f"- **Fragmentos procesados:** {ranges_label}")
    cabecera += ["", "---", ""]
    return "\n".join(cabecera) + cuerpo + "\n"
