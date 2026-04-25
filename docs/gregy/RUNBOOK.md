# HERMES / Luke – Operator Runbook

Stand: 2026-04-25  
Ablageziel im Fork: `docs/gregy/RUNBOOK.md`  
Zweck: Bedienung, Checks, Update-/Git-Abläufe, Fehlerbilder und sichere Arbeitsmuster für Gregorys Luke-Setup.

---

## Inhaltsverzeichnis

1. [Source of Truth](#1-source-of-truth)
2. [Schnellcheck](#2-schnellcheck)
3. [Git/Fork/Branches](#3-gitforkbranches)
4. [Update-Ablauf für Hermes-Upstream](#4-update-ablauf-für-hermes-upstream)
5. [Konfiguration](#5-konfiguration)
6. [Iteration Budget](#6-iteration-budget)
7. [Token- und Kostenlogging](#7-token--und-kostenlogging)
8. [Approval/TUI](#8-approvaltui)
9. [Dokumentationspflege](#9-dokumentationspflege)
10. [Remote-/Projektkontexte](#10-remote-projektkontexte)
11. [ChromeBrowser / Browser-Observer](#11-chromebrowser--browser-observer)
12. [Häufige Fehlerbilder](#12-häufige-fehlerbilder)
13. [Abnahmecheckliste](#13-abnahmecheckliste)
14. [Offene Punkte](#14-offene-punkte)

---

## 1. Source of Truth

Aktuelle Betriebswahrheit:

| Element | Wahrheit |
|---|---|
| Live-Repo | `~/.hermes/hermes-agent` |
| Branch | `live` |
| GitHub-Fork | `git@github.com:gregoryschlepper/hermes-agent.git` |
| Upstream | `git@github.com:NousResearch/hermes-agent.git` |
| Aktueller Live-Commit | `30c7ab4d feat: log auxiliary token usage` |
| Upstream-Basis | `v2026.4.23` / Hermes Agent `v0.11.0` |
| Backup vor v0.11 | `backup/live-before-v011-20260424` |

Die früher dokumentierte separate Arbeitskopie `/home/gregory/AI/LUKE/src/hermes-agent-fork` existiert aktuell nicht. Nicht verwenden, nicht in neue Anweisungen übernehmen.

---

## 2. Schnellcheck

Lokal auf GregyPC:

```bash
hermes --version
```

Erwartung:

```text
Hermes Agent v0.11.0 (2026.4.23)
```

Git-Stand prüfen:

```bash
git -C ~/.hermes/hermes-agent branch --show-current
git -C ~/.hermes/hermes-agent status --short
git -C ~/.hermes/hermes-agent log --oneline -5
```

Erwartung:

- Branch `live`
- Working Tree sauber
- oben `30c7ab4d feat: log auxiliary token usage`

Remote prüfen:

```bash
git -C ~/.hermes/hermes-agent ls-remote --heads origin live
```

Erwartung:

```text
30c7ab4d... refs/heads/live
```

---

## 3. Git/Fork/Branches

Bekannte Branches:

| Branch | Bedeutung |
|---|---|
| `live` | aktueller produktiver Luke-Stand |
| `backup/live-before-v011-20260424` | Sicherung vor v0.11-Reapply |
| `test/v011-reapply` | Testbranch für v0.11-Reapply; aktuell identisch mit `live` |
| `test/v011-merge` | alter Merge-Versuch; nicht als produktiver Stand verwenden |
| `main` | alter upstream-main-Trackingstand, weit hinter Upstream; nicht operative Wahrheit |

Regeln:

- Nicht blind `hermes update` verwenden, solange `~/.hermes/hermes-agent` zugleich der Fork-/Live-Stand ist.
- Upstream-Updates kontrolliert über Git und Testbranch prüfen.
- Vor Force-Push immer Remote-Divergenz prüfen.
- `force-with-lease` nur nach Sichtprüfung und nur, wenn Remote-Inhalt ersetzt werden soll.

---

## 4. Update-Ablauf für Hermes-Upstream

Bewährter Ablauf von v0.10.0 auf v0.11.0:

1. Backup von `~/.hermes` erstellen.
2. Working Tree prüfen.
3. Lokale Patches sichern/stashen.
4. Upstream tags holen.
5. Release-Tag prüfen.
6. Testbranch vom Release-Tag anlegen.
7. Eigene Luke-Commits einzeln cherry-picken.
8. Konflikte klein lösen.
9. Syntax/Doctor/TUI prüfen.
10. `live` erst danach auf Testbranch setzen.
11. `origin/live` erst nach Vergleich pushen.

Wichtige Erkenntnis:

- Der alte `rescue`-Commit wurde nicht übernommen.
- Die beiden echten Luke-Commits wurden neu auf v0.11.0 angewendet.
- Der GLM-FlashX-Tokenlogging-Patch wurde nach v0.11.0 wieder angewendet und committed.

---

## 5. Konfiguration

Wichtige Datei:

```text
~/.hermes/config.yaml
```

Wichtige bekannte Werte:

```yaml
agent:
  max_turns: 40
```

Review-/Aux-Konfiguration:

```yaml
memory:
  review:
    model: glm-4.7-flashx
    provider: zai

skills:
  review:
    model: glm-4.7-flashx
    provider: zai
```

Regel:

> Vor Config-Änderungen immer konkreten Key prüfen, Backup erstellen und erst dann ändern.

---

## 6. Iteration Budget

Der sichtbare Terminal-/TUI-Abbruch `Iteration budget exhausted (20/20)` kam nicht von `HERMES_MAX_ITERATIONS=90`, sondern vom Config-Key:

```yaml
agent:
  max_turns: 20
```

Dieser Wert wurde auf `40` gesetzt.

Priorität laut Analyse:

1. CLI-Argument `--max-turns`
2. `CLI_CONFIG["agent"]["max_turns"]`
3. legacy root-level `max_turns`
4. `HERMES_MAX_ITERATIONS`
5. Default

Folge:

`HERMES_MAX_ITERATIONS=90` greift nicht, solange `agent.max_turns` gesetzt ist.

---

## 7. Token- und Kostenlogging

Der GLM-FlashX Auxiliary Tokenlogging-Patch ist wieder integriert.

Commit:

```text
30c7ab4d feat: log auxiliary token usage
```

Wichtige Datei:

```text
agent/auxiliary_client.py
```

Logziel:

```text
~/.hermes/logs/auxiliary_calls.jsonl
```

Vor dem Commit wurde geprüft:

- `python3 -m py_compile agent/auxiliary_client.py`
- `git diff --check`
- doppelte Initialisierung in `call_llm()` wurde entfernt

Regel:

> Tokenlogging-Patches nicht blind bei Upstream-Updates verlieren. Vor Updates immer als Patch und/oder Stash sichern.

---

## 8. Approval/TUI

Problem unter v0.10.0:

- Dangerous-Command-Approval zeigte `[o]nce`, `[s]ession`, `[a]lways`, `[d]eny`.
- Eingabe funktionierte nicht zuverlässig.
- Nach Timeout war die TUI teilweise blockiert.

Status nach v0.11.0:

- neue TUI/Approval-Bedienung mit nummerierten Optionen
- `Allow once` erfolgreich getestet
- Approval-Dialog ist bedienbar

Trotzdem gelten weiter die Arbeitsregeln:

- keine Heredocs für nicht-triviale Python-/Shell-Logik
- keine Pipe-to-Interpreter-Kommandos
- keine überlangen Einzeiler
- lieber Datei schreiben, zeigen, prüfen, dann ausführen

---

## 9. Dokumentationspflege

Für Luke/Hermes gilt:

> Nach jeder Änderung am Hermes-Fork prüft Luke, ob `docs/gregy/README.md`, `docs/gregy/RUNBOOK.md` oder `docs/gregy/CHANGELOG.md` aktualisiert werden müssen.

Aufteilung:

| Datei | Pflegegrund |
|---|---|
| `docs/gregy/README.md` | Projektziel, Betriebswahrheit, aktueller Live-Stand |
| `docs/gregy/RUNBOOK.md` | Update-, Git-, Config-, Approval-, Fehler- und Betriebsabläufe |
| `docs/gregy/CHANGELOG.md` | lokale Luke-/Fork-Änderungen und Entscheidungsverlauf |

Wichtig:

- Nicht die upstream-nahe Root-README mit Gregory-spezifischen Regeln belasten.
- Gregory-spezifische Betreiber-Doku gehört nach `docs/gregy/`.
- Vor jedem Commit Doku-Impact prüfen.

---

## 10. Remote-/Projektkontexte

### VERITAS

Verbindliche Pfadregel:

| Name | Bedeutung |
|---|---|
| `LOCAL_VERITAS_MATERIAL` | `/home/gregory/KI/VERITAS` auf GregyPC |
| `VERITAS_VPS_CODE` | `/home/gregory/AI/VERITAS` auf SSH-Host `veritas` |

Regeln:

- Git-/Code-Arbeiten an VERITAS erfolgen auf dem VPS-Pfad.
- Lokaler Pfad ist Material-/Doku-Spiegel.
- Nicht lokal `/home/gregory/AI/VERITAS` annehmen; dieser Pfad existiert lokal nicht mehr.
- Vor SSH-Arbeit immer Host und Pfad prüfen.

---

## 11. ChromeBrowser / Browser-Observer

Stage-1-Experiment:

```text
/home/gregory/.local/bin/browser-observer/
```

Status:

- extern abgelegt
- nicht im Hermes-Fork committed
- aktuell ruhend
- kein offener Git-Stand

Grund:

Der Nutzen ist aktuell nicht ausreichend. Das Experiment bleibt als externer Versuch dokumentiert, aber nicht Teil des produktiven Forks.

---

## 12. Häufige Fehlerbilder

### 12.1 Falscher Host / gleicher Pfad

Symptom:

`/home/gregory/AI/VERITAS` scheint mal Git-Repo, mal Materialordner zu sein.

Ursache:

Gleicher Pfadname auf unterschiedlichen Maschinen.

Korrektur:

- lokal: `/home/gregory/KI/VERITAS`
- VPS: `/home/gregory/AI/VERITAS`

### 12.2 Hermes startet nicht wegen SyntaxError

Symptom:

```text
SyntaxError: invalid syntax
<<<<<<< HEAD
```

Ursache:

Git-Konfliktmarker in Python-Datei während Cherry-Pick/Merge.

Lösung:

- Konfliktmarker entfernen
- beide gewünschten Inhalte bewusst zusammenführen
- `python3 -m py_compile ...`
- `git diff --check`
- erst dann `git add` / `cherry-pick --continue`

### 12.3 Hermes wirkt langsam

Mögliche Ursache:

Nicht Hermes selbst, sondern parallele CPU-Last, z. B. ASR-Worker:

```text
transcribe_audio.py --limit ...
```

Prüfen:

```bash
ps -eo pid,%cpu,%mem,comm --sort=-%cpu | head -12
```

### 12.4 Approval-Schleife

Ursachen:

- Heredoc
- Inline-Python
- `rm`/`unzip`/kombinierte Shell-Kommandos
- zu breite Toolketten

Lösung:

- Muster stoppen
- kleinteilig neu planen
- Datei-basierte Ausführung bevorzugen

---

## 13. Abnahmecheckliste

Ein Luke-/Hermes-Fork-Stand gilt nur sauber, wenn:

- [ ] `git status --short` leer ist.
- [ ] Branch bewusst ist.
- [ ] `hermes --version` funktioniert.
- [ ] relevante Python-Dateien syntaktisch geprüft wurden.
- [ ] Approval/TUI bei riskanten Kommandos bedienbar ist.
- [ ] lokale Patches entweder committed, gestasht oder dokumentiert sind.
- [ ] `origin/live` auf den gewünschten Live-Commit zeigt.
- [ ] Doku unter `docs/gregy/` nachgezogen ist.
- [ ] keine falschen Projektpfade verwendet wurden.

---

## 14. Offene Punkte

- Prüfen, ob `test/v011-reapply` nach Stabilisierung gelöscht oder als Referenz behalten wird.
- Prüfen, ob `test/v011-merge` gelöscht werden soll.
- Decide: Browser-Observer dauerhaft verwerfen, ruhend lassen oder später neu bewerten.
- Daily/weekly Doku-/Fork-Healthcheck für Luke definieren.
- Weitere Token-/Kostenmetriken aus `auxiliary_calls.jsonl` auswerten.
- Eventuelle upstream-kompatible Form des Tokenlogging-Patches prüfen.
