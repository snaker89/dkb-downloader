# dkb-wertpapiere

Lädt alle **Wertpapierdokumente** aus der DKB-Postbox als PDF herunter, zum Beispiel für den Import in
[Portfolio Performance](https://www.portfolio-performance.info/). Dazu gehören Kauf- und Verkaufsabrechnungen,
Ertragsgutschriften, Depotauszüge, Kapitalmaßnahmen und Kosteninformationen.

Das Skript baut auf [dkb-robo](https://github.com/grindsa/dkb-robo) von grindsa auf. Es ersetzt nur den Login,
der seit November 2025 wegen eines Captchas auf der DKB-Login-Seite nicht mehr funktioniert
([Issue #92](https://github.com/grindsa/dkb-robo/issues/92)).

## So funktioniert es

1. Das Skript öffnet ein Microsoft-Edge-Fenster mit der DKB-Login-Seite.
2. Du meldest dich dort ganz normal an: Captcha, Passwort und Freigabe in der DKB-App.
   Benutzername und Passwort bekommt das Skript nie zu sehen.
3. Sobald die Sitzung gültig ist, ruft dkb-robo die DKB-API über diese Browser-Sitzung ab.
   Das läuft über die Playwright-Anfragen des Browser-Kontexts.
4. Läuft das Zugangstoken ab (nach etwa 5 Minuten) oder bricht eine Verbindung ab, lädt das Skript die Seite neu.
   Dabei erneuert die DKB-Webapp das Token, und das Skript versucht es erneut.

Dokumente werden in der Postbox **nicht** als gelesen markiert. Bereits vorhandene PDFs werden übersprungen,
nach einem Abbruch kannst du also einfach neu starten.

## Voraussetzungen

- Windows mit Microsoft Edge
- Python 3.9 oder neuer

## Einrichtung

```powershell
git clone https://github.com/snaker89/dkb-wertpapiere.git
cd dkb-wertpapiere
.\setup.ps1
```

## Benutzung

```powershell
.\download-wertpapiere.ps1                 # Ausgabe nach .\downloads
.\download-wertpapiere.ps1 -OutDir D:\DKB  # eigener Zielordner
```

Ergebnis:

```
downloads/
├── accounts_<zeit>.json                  # Konten- und Depotübersicht
├── depot_<depotnr>_<zeit>.json           # aktuelle Depotpositionen (zum Abgleich)
└── dokumente/Wertpapierdokumente/<depotnr>/
    └── <datum>_<betreff>.pdf
```

## Import in Portfolio Performance

1. Depot und Verrechnungskonto anlegen.
2. *Datei → Importieren → PDF-Dokumente* öffnen und alle PDFs aus `dokumente/Wertpapierdokumente` auswählen.
3. Die erkannten Buchungen prüfen und übernehmen. Kosteninformationen werden nicht erkannt, das ist normal.
4. Die Bestände mit `depot_*.json` abgleichen.

## Hinweise

- Das ist kein offizielles DKB-Werkzeug. Benutzung auf eigene Verantwortung.
  Ändert DKB die Webseite oder die API, kann das Skript jederzeit aufhören zu funktionieren.
- Die heruntergeladenen Dateien enthalten persönliche Finanzdaten. Die `.gitignore` schließt `downloads/`,
  `*.pdf` und `*.json` aus. Lade diese Dateien trotzdem nirgends hoch.
- Getestet mit dkb-robo 0.31.2 und Playwright 1.65.1.

## Danksagung

- [grindsa/dkb-robo](https://github.com/grindsa/dkb-robo) liefert den API-Zugriff, die Postbox-Logik und die
  Depotabfrage.
- Die Idee, den Login an einen echten Browser abzugeben und dessen Sitzung weiterzuverwenden, stammt aus
  [diesem Kommentar](https://github.com/grindsa/dkb-robo/issues/92) von ThomFri in Issue #92.

## Lizenz

[GPL-3.0-or-later](LICENSE), wie dkb-robo.
