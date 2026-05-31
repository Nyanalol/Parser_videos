# Empaqueta Parser Videos como ejecutable de Windows con PyInstaller.
#
# Requiere conexión a internet la primera vez (instala pyinstaller).
# Uso:   powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1
#
# Resultado: dist\ParserVideos\ParserVideos.exe
# Recuerda copiar tu archivo .env junto al .exe.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m pip install --upgrade pyinstaller

& $py -m PyInstaller --noconfirm --windowed --name ParserVideos `
    --icon (Join-Path $root "assets\icon.ico") `
    --collect-all customtkinter `
    --collect-all imageio_ffmpeg `
    --collect-all markdown `
    --add-data "$($root)\assets;assets" `
    (Join-Path $root "run_app.py")

Write-Host ""
Write-Host "Listo. Ejecutable en: dist\ParserVideos\ParserVideos.exe"
Write-Host "Copia tu .env junto al .exe antes de usarlo."
