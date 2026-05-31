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

# Niveles de extensión del resumen. Cada uno da una instrucción concreta (los
# modelos solo respetan la longitud si se les da una referencia explícita) y un
# tope de tokens acorde. La clave es lo que se muestra en la GUI.
LENGTH_CHOICES = {
    "Muy breve": {
        "instruction": (
            "Resume en muy pocas líneas: un párrafo de 2-3 frases con la idea "
            "principal y, como mucho, 3-5 puntos clave muy concisos. Sé telegráfico."
        ),
        "max_tokens": 400,
    },
    "Equilibrado": {
        "instruction": (
            "Resumen de extensión media (aprox. 250-400 palabras): breve "
            "introducción, los puntos clave en una lista y conclusiones si procede."
        ),
        "max_tokens": 900,
    },
    "Extenso": {
        "instruction": (
            "Resumen detallado (aprox. 600-900 palabras) organizado en secciones "
            "con encabezados, desarrollando cada punto importante con sus matices "
            "y ejemplos mencionados en el vídeo."
        ),
        "max_tokens": 2000,
    },
    "Exhaustivo": {
        "instruction": (
            "Resumen muy completo y minucioso, organizado en secciones con "
            "encabezados y sublistas. Cubre TODOS los temas, argumentos, datos y "
            "ejemplos relevantes de la transcripción, sin dejarte nada importante. "
            "No te limites artificialmente en longitud."
        ),
        "max_tokens": 4000,
    },
}
DEFAULT_LENGTH = "Equilibrado"


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
    length_level: str = DEFAULT_LENGTH,
    ranges_label: str = "",
    on_progress: Optional[ProgressCallback] = None,
) -> str:
    """Resume la transcripción y devuelve el documento en Markdown.

    - `custom_prompt`: instrucciones del usuario; si está vacío se usa el por defecto.
    - `summary_language`: nombre del idioma (clave de LANGUAGE_CHOICES) o None.
    - `length_level`: extensión deseada (clave de LENGTH_CHOICES).
    - `ranges_label`: descripción de los fragmentos procesados (para la cabecera).
    """
    if not config.api_key_present():
        raise RuntimeError("Falta OPENAI_API_KEY. Configúrala en el archivo .env.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    config.ensure_dirs()
    instrucciones = (custom_prompt or "").strip() or DEFAULT_PROMPT
    length = LENGTH_CHOICES.get(length_level, LENGTH_CHOICES[DEFAULT_LENGTH])

    user_msg = (
        f"{instrucciones}\n\n"
        f"EXTENSIÓN REQUERIDA: {length['instruction']}\n\n"
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
        max_tokens=length["max_tokens"],
    )
    cuerpo = response.choices[0].message.content.strip()

    # Cabecera con metadatos.
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    cabecera = [f"# {title}", "", f"- **Fuente:** {source_url}", f"- **Generado:** {fecha}"]
    if ranges_label:
        cabecera.append(f"- **Fragmentos procesados:** {ranges_label}")
    cabecera += ["", "---", ""]
    return "\n".join(cabecera) + cuerpo + "\n"
