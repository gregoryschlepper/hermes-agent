# `luke.example.sh` — Start-Wrapper für Hermes Agent

## Zweck

Ein Start-Wrapper-Skript, das beim **ersten Start des Tages** einmalig
Maintenance-Aufgaben anstößt, bevor Hermes Agent selbst gestartet wird.
Nachfolgende Starts am selben Tag überschreiten diese Phasen einfach,
weil Marker-Files das bereits erledigte Kennzeichnen.

## Phasen

| Phase | Beschreibung | Wann | Optional |
|-------|-------------|------|----------|
| **1** | Health-Check | Einmal/Tag | Ja (nur wenn Skript existiert + ausführbar) |
| **2** | Cleanup Ops (Dry-Run) | Einmal/Tag | Ja |
| **3** | Archive Hygiene Dry-Run | Einmal/Tag | Ja |
| **4** | Daily Cost Report | Einmal/Tag | Ja |
| **5** | Project/Documentation Guard (+30m geplant) | Einmal/Tag | Ja |
| **EXEC** | `exec hermes "$@"` | Immer | Nein |

### JOBS_DIR

Jobs können aus einem gemeinsamen Verzeichnis geladen werden:

```bash
JOBS_DIR="/path/to/hermes/ops/jobs"
```

Wenn `JOBS_DIR` gesetzt ist, werden die Job-Pfade automatisch auf
`${JOBS_DIR}/health_check.sh`, `${JOBS_DIR}/cleanup_ops.py`,
`${JOBS_DIR}/archive_hygiene.py`, `${JOBS_DIR}/daily_cost_report.py`
gesetzt. Das Wrapper-Skript bleibt so schlank wie möglich —
es orchestriert nur, die Logik liegt in den separaten Job-Scripts.

### +30-Minuten-Guard

Phase 4 plant den **Project/Documentation Guard** 30 Minuten nach dem
Start des Wrappers via `systemd-run --user --on-active=30m`. So läuft
der Guard nicht sofort, sondern erst nachdem die erste Arbeitsphase
abgeschlossen ist — mit dem vollständigen `--guard-full` Modus.

### Health / Cleanup / Archive

Alle drei werden als **Dry-Run** ausgeführt:
- **Health-Check**: Prüft Systemintegrität (kann echte Checks durchführen)
- **Cleanup Ops**: Zeigt an, was bereinigt werden könnte, ohne zu löschen
- **Archive Hygiene**: Prüft Archivkonsistenz ohne Änderungen

### Marker-Logik

Jede Phase erstellt ein Marker-File in `$XDG_RUNTIME_DIR/hermes-start-wrapper/`
mit dem heutigen Datum im Namen (z.B. `health-20260425`). Beim nächsten
Start am selben Tag existiert das Marker-File und die Phase wird
übersprungen.

## Installation

```bash
# 1. Kopieren
cp scripts/start_wrapper/luke.example.sh ~/bin/luke.sh

# 2. Platzhalter ersetzen
nano ~/bin/luke.sh

# 3. Ausführbar machen
chmod +x ~/bin/luke.sh
```

## Anpassung

1. **Pfade ersetzen**: Alle `/path/to/...`-Platzhalter am Anfang
   des Skripts mit echten Pfaden füllen.
2. **Optionale Komponenten**: Falls Health-Check, Cleanup Ops,
   Archive Hygiene oder Project Guard nicht benötigt werden,
   die entsprechende Variable leer lassen (`""`).
3. **Ins PATH legen**: Das angepasste Skript in ein Verzeichnis
   im PATH verschieben (z.B. `~/bin/`) oder den absoluten Pfad
   verwenden.

## Verwendung

Statt `hermes` direkt aufzurufen, wird der Wrapper verwendet:

```bash
# Direkt
luke.sh "Review session from today"

# Mit Gateway
luke.sh --gateway telegram
```

Der Wrapper führt alle Maintenance-Phasen durch (falls Marker nicht
existieren) und übergibt dann alle Argumente unverändert an Hermes
via `exec "$HERMES_BIN" "$@"`.

## Voraussetzungen

- **bash** 4+
- **systemd** (User-Slice) für die +30-Minuten-Guard-Planung
- Optional: Health-Check, Cleanup Ops, Archive Hygiene Skripte

## Hinweis

Dieses Template ist **generisch** und für jeden Hermes-User geeignet.
Es enthält keine persönlichen Pfade oder benutzerspezifischen
Konfigurationen.
