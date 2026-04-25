# HERMES / Luke – Changelog

Stand: 2026-04-25  
Ablageziel im Fork: `docs/gregy/CHANGELOG.md`  
Zweck: nachvollziehbare Chronik der lokalen Luke-/Hermes-Fork-Änderungen und Betriebsentscheidungen.

---

## 2026-04-25 – 0.3-docs-git-ready

### Anlass

Die bisherige Dokumentation 0.2 war vor dem v0.11-Update und vor der Klärung der realen Fork-/Live-Struktur entstanden. Mehrere Aussagen waren veraltet.

### Korrekturen

- Separate Fork-Arbeitskopie `/home/gregory/AI/LUKE/src/hermes-agent-fork` aus der Betriebswahrheit entfernt.
- Aktuelle Wahrheit dokumentiert: `~/.hermes/hermes-agent` ist Live-Repo und Fork-Arbeitskopie zugleich.
- Ablageziel für Gregory-spezifische Luke-Doku auf `docs/gregy/` gesetzt.
- Hermes v0.11.0 / `v2026.4.23` als aktuelle Upstream-Basis dokumentiert.
- Live-Commit `30c7ab4d` als aktueller produktiver Stand dokumentiert.
- `origin/live` auf `30c7ab4d` als gepushter Fork-Stand dokumentiert.
- `agent.max_turns: 40` als aktuelles Terminal-/TUI-Iteration-Budget dokumentiert.
- GLM-FlashX Auxiliary Tokenlogging als integrierter Patch dokumentiert.
- ChromeBrowser/Browser-Observer Stage 1 als externes, ruhendes Experiment dokumentiert.
- VERITAS-Pfadregel aufgenommen:
  - lokal: `/home/gregory/KI/VERITAS`
  - VPS: `veritas:/home/gregory/AI/VERITAS`

### Ergebnis

Die Dokumentation ist jetzt bereit, im Hermes-Fork unter `docs/gregy/` versioniert zu werden.

---

## 2026-04-25 – Hermes v0.11.0 auf live übernommen

### Ausgangslage

Hermes lief vorher auf v0.10.0. Die alte TUI/Approval-Bedienung blockierte bei Dangerous-Command-Abfragen und machte weitere Arbeit unsicher.

### Vorgehen

- Backup von `~/.hermes` erstellt.
- Lokaler GLM-FlashX-Tokenlogging-Patch gesichert und gestasht.
- Upstream-Tags geholt.
- Release-Tag `v2026.4.23` als Hermes Agent `v0.11.0` identifiziert.
- Testbranch `test/v011-reapply` vom Release-Tag angelegt.
- Relevante lokale Luke-Commits einzeln neu angewendet.
- Konflikt in `hermes_cli/config.py` manuell aufgelöst.
- Syntax/Doctor/TUI geprüft.
- `live` auf den Teststand gesetzt.
- `origin/live` nach Sichtprüfung mit `--force-with-lease` aktualisiert.

### Ergebnis

Aktueller Stand:

```text
30c7ab4d feat: log auxiliary token usage
5a6f03e1 Slim down background reviews with minimal toolsets and capped history
6bede920 Add configurable models for memory and skill background reviews
bf196a3f v2026.4.23 / Hermes v0.11.0
```

---

## 2026-04-25 – Approval/TUI-Problem gelöst

### Problem

In v0.10.0 war der Approval-Dialog im Terminal teilweise nicht bedienbar. Nach Timeout wurde der Befehl verweigert, und die TUI konnte blockiert wirken.

### Lösung

Das kontrollierte Update auf v0.11.0 brachte die neue TUI/Approval-Bedienung. Ein Test mit `Allow once` funktionierte.

### Ergebnis

Riskante Befehle können wieder sichtbar und bedienbar freigegeben oder verweigert werden.

---

## 2026-04-25 – GLM-FlashX Auxiliary Tokenlogging integriert

### Anlass

Luke soll Kosten und Tokenverbrauch interner Auxiliary-/Background-Aufrufe nachvollziehbar machen.

### Änderung

Commit:

```text
30c7ab4d feat: log auxiliary token usage
```

Betroffene Datei:

```text
agent/auxiliary_client.py
```

Logdatei:

```text
~/.hermes/logs/auxiliary_calls.jsonl
```

### Prüfung

- Patch zunächst als Datei und Stash gesichert.
- Nach v0.11.0 wieder angewendet.
- Konfliktfrei angewendet.
- Doppelte Initialisierung in `call_llm()` entfernt.
- `py_compile` und `git diff --check` bestanden.

---

## 2026-04-25 – Iteration Budget auf 40 gesetzt

### Befund

Der sichtbare Abbruch `Iteration budget exhausted (20/20)` kam nicht aus `HERMES_MAX_ITERATIONS=90`, sondern aus:

```yaml
agent:
  max_turns: 20
```

### Änderung

`agent.max_turns` wurde auf `40` gesetzt.

### Bewertung

40 gibt Luke mehr Luft für reale Arbeitsläufe, ohne direkt auf 90 hochzugehen.

---

## 2026-04-25 – ChromeBrowser Stage 1 ruhend gestellt

### Befund

Ein ChromeBrowser-/Browser-Observer-Experiment wurde extern angelegt unter:

```text
/home/gregory/.local/bin/browser-observer/
```

### Ergebnis

- nicht im Hermes-Fork committed
- kein offener Git-Stand
- aktuell ruhend
- kein Revert nötig

### Begründung

Der Nutzen war im aktuellen Arbeitsfluss nicht ausreichend.

---

## 2026-04-25 – VERITAS-Git und Doku-Spiegel geklärt

### Kontext

Bei VERITAS gab es eine Verwechslung durch denselben Pfadnamen auf zwei Maschinen.

### Korrektur

- Lokaler Materialordner auf GregyPC:

```text
/home/gregory/KI/VERITAS
```

- Echte Codebasis auf dem VERITAS-VPS:

```text
veritas:/home/gregory/AI/VERITAS
```

### Ergebnis

Diese Pfadregel wurde in Luke gespeichert und in die Hermes-Dokumentation übernommen.

---

## 2026-04-24 – 0.2-docs-cleanup

### Anlass

Der erste Dokumentationsstand war für `0.1-initial-docs` tragfähig, hatte aber Korrekturbedarf.

### Ergebnis

Die Hermes-/Luke-Dokumentation wurde auf drei Kernartefakte begrenzt: `README.md`, `RUNBOOK.md`, `CHANGELOG.md`. ASR-/Lanz-Precht-Inhalte wurden aus der Hermes-Doku entfernt und VERITAS zugeordnet.

---

## 2026-04-19 bis 2026-04-24 – Vorlaufentscheidungen

### Hermes als Power-User-Agent

Hermes wurde als persönlicher Power-User-Agent für Gregory bewertet, nicht als direkte FORGE-Basis.

### Eigener Linux-User verworfen

Ein vollständig eigener Linux-User wurde verworfen, weil Luke dadurch zu stark von Gregorys realer Arbeitswelt getrennt wäre.

### Kosten- und Gedächtnismodell

Das dreischichtige Modell bleibt gültig:

1. Daily Layer: schnell, günstig, direkt
2. Growth Layer: gezielte Reflexion, Skills, Muster
3. Deep Layer: Honcho, seltene Meta-/Beziehungsarbeit

### Dokumentationsgrenze zu VERITAS

VERITAS-, ASR- und Lanz/Precht-Arbeitspfade gehören nicht in das Hermes-Runbook. Sie können Luke betreffen, bleiben aber fachlich eigene Projekt-Dokumentation.

---

## Aktuell bekannte offene Punkte

1. `docs/gregy/` im Hermes-Fork einspielen, committen und pushen.
2. Prüfen, ob `test/v011-reapply` und `test/v011-merge` bereinigt werden sollen.
3. Browser-Observer später bewusst neu bewerten oder löschen.
4. Daily/weekly Doku-/Fork-Healthcheck definieren.
5. Tokenlogging-Auswertung für `auxiliary_calls.jsonl` bauen oder dokumentieren.
6. Optional prüfen, ob Tokenlogging upstream-fähig gemacht werden soll.
