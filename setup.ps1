# Einmalige Einrichtung: virtuelle Python-Umgebung anlegen und Abhaengigkeiten installieren.
# Benoetigt Python 3.9+ und Microsoft Edge (unter Windows vorinstalliert).

$ErrorActionPreference = "Stop"
$venv = Join-Path $PSScriptRoot ".venv"

if (-not (Test-Path $venv)) { python -m venv $venv }
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\python.exe") -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host "`nEinrichtung fertig. Starten mit: .\download-wertpapiere.ps1" -ForegroundColor Green
