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

Se abre la ventana de la aplicación: pega la URL del vídeo, elige el idioma del
resumen y pulsa **Procesar**. El resultado se guarda en la carpeta `output/`.

## Estructura del proyecto

```
parser_videos/
├── __init__.py
├── __main__.py        # Punto de entrada (lanza la GUI)
├── config.py          # Configuración y carga de .env
├── ffmpeg_utils.py    # Localiza el binario de ffmpeg embebido
├── downloader.py      # Descarga de audio con yt-dlp
├── transcriber.py     # Transcripción con Whisper (+ troceo de archivos grandes)
├── summarizer.py      # Resumen con GPT y generación del .md
├── pipeline.py        # Orquesta descarga -> transcripción -> resumen
└── gui.py             # Interfaz CustomTkinter
```

## Estado

Proyecto en construcción por bloques de tareas. Ver historial de commits.
