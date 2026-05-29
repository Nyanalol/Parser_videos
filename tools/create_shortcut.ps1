# Crea (o regenera) el acceso directo de Parser Videos en el escritorio.
#
# Apunta al pythonw.exe del entorno virtual y lanza 'python -m parser_videos'
# sin abrir consola. Usa el icono de assets/icon.ico.
#
# Uso:   powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$icon = Join-Path $projectRoot "assets\icon.ico"

if (-not (Test-Path $pythonw)) {
    Write-Error "No se encontro $pythonw. Crea el entorno virtual e instala dependencias primero."
    exit 1
}

# Carpeta de salida en el escritorio.
$desktop = [Environment]::GetFolderPath("Desktop")
$outDir = Join-Path $desktop "Transcripciones Videos"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
    Write-Host "Carpeta de salida creada: $outDir"
}

# Acceso directo.
$lnkPath = Join-Path $desktop "Parser Videos.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m parser_videos"
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = $icon
$shortcut.Description = "Transcribe y resume videos desde una URL"
$shortcut.Save()

Write-Host "Acceso directo creado: $lnkPath"
