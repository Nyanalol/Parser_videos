# Parser Videos

Aplicación de escritorio para Windows que, a partir de la URL de un vídeo (YouTube
y otras webs soportadas por `yt-dlp`):

1. **Descarga** el audio del vídeo.
2. **Transcribe** lo que se dice usando la API de Whisper de OpenAI.
3. **Resume** el contenido y lo guarda en un archivo `.md`.

## Requisitos

- Python 3.10 o superior (probado con 3.14).
- Una clave de API de OpenAI.
- Conexión a internet.

No necesitas instalar `ffmpeg` aparte: se incluye mediante el paquete
`imageio-ffmpeg`.

## Instalación

```powershell
# 1. Clonar el repositorio
git clone https://github.com/Nyanalol/Parser_videos.git
cd Parser_videos

# 2. Crear y activar un entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar la clave de OpenAI
copy .env.example .env
# Edita .env y pon tu OPENAI_API_KEY
```

## Uso

```powershell
python -m parser_videos
```

Se abre la ventana de la aplicación:

1. Añade una o varias URLs (botón **＋ Añadir vídeo**). Si pones varias, sus
   contenidos se **combinan en un único resumen**.
2. Opcional: en cada vídeo, indica **rangos de tiempo** para procesar solo
   ciertos fragmentos, p.ej. `14:34-16:34, 20:00-21:30`. Vacío = vídeo completo.
3. Elige el **idioma del resumen** y, si quieres, el idioma del audio.
4. Escribe **instrucciones para el resumen** (tono, enfoque, formato...). Si lo
   dejas vacío se usa un prompt por defecto.
5. Pulsa **Procesar**.

El resultado se guarda en la carpeta `Transcripciones Videos` del escritorio,
organizado en subcarpetas:
- `Markdown/Título.md` — el resumen en Markdown.
- `HTML/Título.html` — el resumen renderizado (doble clic = se abre en el navegador).
- `Obsidian/Título.md` — copia para usar como vault de Obsidian.
- `Transcripciones/Título.txt` — la transcripción usada.

### Funciones destacadas

- **Caché**: cada vídeo se transcribe una sola vez. Si lo vuelves a usar (aunque
  cambies los rangos o el prompt), se reutiliza la transcripción guardada en
  `.cache/` y no se consume Whisper de nuevo.
- **Rangos por segmentos**: como se guardan las marcas de tiempo, cambiar los
  rangos es instantáneo y gratis.
- **Sin ffmpeg manual**: se usa el binario embebido de `imageio-ffmpeg`.

## Estructura del proyecto

```
parser_videos/
├── __init__.py
├── __main__.py        # Punto de entrada (lanza la GUI)
├── config.py          # Configuración, rutas y carga de .env
├── ffmpeg_utils.py    # Localiza el binario de ffmpeg embebido
├── downloader.py      # probe() + descarga de audio con yt-dlp (cacheado por id)
├── transcriber.py     # Transcripción con Whisper en segmentos (+ troceo >25MB)
├── timeranges.py      # Parseo de rangos y filtrado de segmentos por tiempo
├── cache.py           # Caché en disco de transcripciones completas
├── summarizer.py      # Resumen con GPT y generación del .md
├── pipeline.py        # Orquesta todo (mono y multi-vídeo)
└── gui.py             # Interfaz CustomTkinter
```

## Funciones

- **Subtítulos de YouTube**: si el vídeo trae subtítulos, se usan en vez de
  Whisper (gratis e instantáneo).
- **Extensión del resumen**: muy breve → exhaustivo.
- **Plantillas**: general, acta de reunión, tutorial, apuntes de estudio,
  puntos accionables, receta.
- **Modelo seleccionable**: `gpt-4o-mini` (barato) o `gpt-4o` (máxima calidad).
- **Rangos de tiempo** por vídeo y **varios vídeos combinados** en un resumen.
- **Playlists/canales**: se expanden automáticamente.
- **Archivos locales**: además de URLs, acepta rutas de audio/vídeo del disco.
- **Resumen jerárquico (map-reduce)** para transcripciones muy largas.
- **Índice con marcas de tiempo clicables** (YouTube).
- **Caché** de transcripciones e **historial** de vídeos procesados.
- **Chat / Q&A** sobre el vídeo (RAG).
- **Estimación de coste** por ejecución y **limpieza** de descargas.
- Exporta a **Markdown, HTML y Obsidian**; recuerda tus últimas opciones.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Empaquetado a .exe (opcional)

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1
```

El ejecutable queda en `dist/ParserVideos/`. Coloca tu `.env` junto al `.exe`.

## Estado

Proyecto construido por bloques de tareas. Ver historial de commits.
