# Laedt alle Wertpapierdokumente aus der DKB-Postbox herunter (Abrechnungen,
# Ertragsgutschriften, Kosteninformationen, Depotauszuege ...) und speichert
# Konten-/Depotuebersicht und aktuelle Depotpositionen als JSON.
#
# Aufruf:  .\download-wertpapiere.ps1 [-OutDir <pfad>]
#
# Login (Friendly-Captcha-Workaround, dkb-robo Issue #92): Es oeffnet sich
# Microsoft Edge. Dort EINMAL normal bei DKB einloggen und in der App freigeben.
# Bereits geladene PDFs werden uebersprungen - nach Abbruch einfach neu starten.

param(
    [string]$OutDir = (Join-Path $PSScriptRoot "downloads")
)

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py (Join-Path $PSScriptRoot "dkb_browser.py") $OutDir
