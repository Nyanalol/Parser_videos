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

## Empaquetado a .exe (opcional)

Para distribuir un ejecutable de Windows:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name ParserVideos `
  --collect-all customtkinter `
  --collect-all imageio_ffmpeg `
  -m parser_videos
```

El ejecutable queda en `dist/ParserVideos/`. Coloca tu `.env` junto al `.exe`.

## Estado

Proyecto construido por bloques de tareas. Ver historial de commits.
