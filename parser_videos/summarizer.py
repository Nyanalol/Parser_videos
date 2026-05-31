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
from .usage import CostTracker

ProgressCallback = Callable[[str], None]

# Modelos de chat disponibles en la interfaz (calidad vs coste).
MODEL_CHOICES = ["gpt-4o-mini", "gpt-4o"]

# Plantillas de tipo de resumen. Cada una añade instrucciones de formato/enfoque.
TEMPLATE_CHOICES = {
    "General": "",
    "Acta de reunión": (
        "Formatea el resultado como un ACTA DE REUNIÓN con estas secciones: "
        "**Asistentes/Participantes** (si se mencionan), **Temas tratados**, "
        "**Decisiones tomadas** y **Tareas/acciones** (con responsable si se dice)."
    ),
    "Tutorial paso a paso": (
        "Formatea el resultado como un TUTORIAL: una lista numerada de pasos "
        "claros y accionables en orden, más una sección de **Requisitos previos** "
        "y otra de **Consejos/errores comunes** si aparecen."
    ),
    "Apuntes de estudio": (
        "Formatea como APUNTES DE ESTUDIO: conceptos clave con definiciones, "
        "ideas principales jerarquizadas y una sección final de **Preguntas de "
        "repaso** para autoevaluarse."
    ),
    "Puntos accionables": (
        "Extrae solo los PUNTOS ACCIONABLES: una lista de tareas concretas y "
        "recomendaciones prácticas que se puedan llevar a cabo, sin relleno."
    ),
    "Receta": (
        "Si el contenido es una receta, formatea con **Ingredientes** (lista con "
        "cantidades) y **Elaboración** (pasos numerados), más tiempos y raciones "
        "si se mencionan."
    ),
}
DEFAULT_TEMPLATE = "General"

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


def _chat(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    cost: Optional[CostTracker] = None,
) -> str:
    """Hace una llamada de chat y devuelve el texto, registrando el coste."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    if cost is not None and getattr(response, "usage", None):
        cost.add_chat(response.usage.prompt_tokens, response.usage.completion_tokens)
    return response.choices[0].message.content.strip()


# Límite aproximado de caracteres de transcripción por encima del cual conviene
# resumir de forma jerárquica (map-reduce) en lugar de en una sola llamada.
LONG_TRANSCRIPT_CHARS = 48_000


def _build_user_msg(
    transcript: str,
    title: str,
    custom_prompt: str,
    summary_language: Optional[str],
    length_level: str,
    template: str,
) -> str:
    instrucciones = (custom_prompt or "").strip() or DEFAULT_PROMPT
    length = LENGTH_CHOICES.get(length_level, LENGTH_CHOICES[DEFAULT_LENGTH])
    template_instr = TEMPLATE_CHOICES.get(template, "")
    bloques = [instrucciones]
    if template_instr:
        bloques.append(f"PLANTILLA: {template_instr}")
    bloques.append(f"EXTENSIÓN REQUERIDA: {length['instruction']}")
    bloques.append(_language_instruction(summary_language))
    bloques.append(
        f"Título del vídeo: {title}\n"
        "--- TRANSCRIPCIÓN ---\n"
        f"{transcript}\n"
        "--- FIN DE LA TRANSCRIPCIÓN ---"
    )
    return "\n\n".join(bloques)


def _summarize_hierarchical(
    client: OpenAI,
    model: str,
    transcript: str,
    title: str,
    summary_language: Optional[str],
    cost: Optional[CostTracker],
    log: Callable[[str], None],
) -> str:
    """Resume transcripciones largas por partes y luego combina (map-reduce)."""
    # Trocear por caracteres respetando líneas.
    trozos: list[str] = []
    actual: list[str] = []
    largo = 0
    for linea in transcript.splitlines():
        actual.append(linea)
        largo += len(linea) + 1
        if largo >= LONG_TRANSCRIPT_CHARS // 2:
            trozos.append("\n".join(actual))
            actual, largo = [], 0
    if actual:
        trozos.append("\n".join(actual))

    log(f"Transcripción larga: resumiendo en {len(trozos)} partes (map-reduce)...")
    parciales = []
    for i, t in enumerate(trozos, start=1):
        log(f"  Resumiendo parte {i}/{len(trozos)}...")
        u = (
            "Resume de forma fiel y detallada esta PARTE de la transcripción de un "
            f"vídeo ('{title}'), conservando todos los puntos importantes. "
            f"{_language_instruction(summary_language)}\n\n{t}"
        )
        parciales.append(_chat(client, model, _SYSTEM, u, 1500, cost))
    return "\n\n".join(parciales)


def summarize(
    transcript: str,
    title: str,
    source_url: str,
    custom_prompt: str = "",
    summary_language: Optional[str] = None,
    length_level: str = DEFAULT_LENGTH,
    template: str = DEFAULT_TEMPLATE,
    model: Optional[str] = None,
    ranges_label: str = "",
    cost: Optional[CostTracker] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> str:
    """Resume la transcripción y devuelve el documento en Markdown.

    - `custom_prompt`: instrucciones del usuario; si está vacío se usa el por defecto.
    - `summary_language`: nombre del idioma (clave de LANGUAGE_CHOICES) o None.
    - `length_level`: extensión deseada (clave de LENGTH_CHOICES).
    - `template`: plantilla de formato (clave de TEMPLATE_CHOICES).
    - `model`: modelo de chat; si es None usa el de config.
    - `cost`: acumulador opcional de coste.
    """
    if not config.api_key_present():
        raise RuntimeError("Falta OPENAI_API_KEY. Configúrala en el archivo .env.")

    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    config.ensure_dirs()
    model = model or config.SUMMARY_MODEL
    if cost is not None:
        cost.model = model
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    # Para transcripciones muy largas, primero condensamos por partes.
    texto = transcript
    if len(transcript) > LONG_TRANSCRIPT_CHARS:
        texto = _summarize_hierarchical(
            client, model, transcript, title, summary_language, cost, _log
        )

    length = LENGTH_CHOICES.get(length_level, LENGTH_CHOICES[DEFAULT_LENGTH])
    user_msg = _build_user_msg(
        texto, title, custom_prompt, summary_language, length_level, template
    )

    _log("Generando resumen con OpenAI...")
    cuerpo = _chat(client, model, _SYSTEM, user_msg, length["max_tokens"], cost)

    # Cabecera con metadatos.
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    cabecera = [f"# {title}", "", f"- **Fuente:** {source_url}", f"- **Generado:** {fecha}"]
    if ranges_label:
        cabecera.append(f"- **Fragmentos procesados:** {ranges_label}")
    cabecera += ["", "---", ""]
    return "\n".join(cabecera) + cuerpo + "\n"
