# Cost Reports — API-Kosten-Reporting für Hermes

Kombinierter Tages-Kostenreport aus zwei JSONL-Logquellen.

## Zielgruppe

VibeCoder und Power-User, die nachvollziehen wollen, wie viele API-Calls ihre
Hermes-Instanz verursacht und welche Kosten dabei anfallen.

## Was wird geloggt?

### main_calls.jsonl (Hauptchat)
Jeder API-Call des Hauptchats (z. B. Qwen via OpenRouter) wird persistiert.
Enthält: Modell, Provider, Tokenzahlen, geschätzte Kosten, Session-IDs.
**Keine** Prompts, Antworten, API-Keys oder Header.

### auxiliary_calls.jsonl (Auxiliary / Background)
Jeder Background-Call (z. B. GLM-FlashX für Memory/Skill-Reviews) wird
persistiert. Gleiches Schema: technische Felder, keine Inhalte.

## Script

```
python3 luke_daily_cost_report.py [--date YYYY-MM-DD]
```

Ohne `--date` wird gestern als Report-Tag verwendet.

## Ausgabe

- Terminal: kompakte Tabelle mit Calls, Errors, Tokens, Cache-Hit, Kosten
- Markdown-Datei: `~/.hermes/ops/reports/daily/luke_daily_cost_report_YYYY-MM-DD.md`

## Zusätzliche Ausgabe (Business / zweiter Pfad)

Neben der Standard-Ablage kann ein zweiter Ausgabepfad angegeben werden:

```
python3 luke_daily_cost_report.py --date 2026-04-25 --extra-output-dir /path/to/business/reports
```

Schreibt zusätzlich nach:
```
/path/to/business/reports/2026-04/luke_daily_cost_report_2026-04-25.md
```

- Monatsordner `YYYY-MM` wird automatisch angelegt
- Alte Reports werden nie gelöscht
- Falls die Extra-Ablage fehlschlägt: Warnung auf stderr, Standardreport trotzdem geschrieben

## Gruppierung

Ergebnisse werden nach Quelle (main / auxiliary) und Modell gruppiert.
Eine Gesamtzeile summiert alle Gruppen.

## Sicherheit

- **Nur lesend** — Logs werden nie verändert
- Keine Prompts, Antworten, Nachrichten oder Secrets
- Kein Netzwerk, kein Git
- Fehlende Dateien sind kein Fehler — mit vorhandenen Quellen rechnen
