# HERMES / Luke – README

Stand: 2026-04-25  
Ablageziel im Fork: `docs/gregy/README.md`  
Zweck: Projektüberblick, Betriebswahrheit und Orientierung für Gregorys persönliche Hermes-/Luke-Instanz.

---

## 1. Kurzfassung

**Hermes** ist die technische Agent-Engine von Nous Research bzw. Gregorys Fork davon.  
**Luke** ist Gregorys persönliche Hermes-Instanz: Persona, Arbeitsstil, Memory, Skills, Regeln, Modellrouting und laufender Betrieb.

Luke ist kein isoliertes Nebenprojekt mehr, sondern ein real genutzter persönlicher Power-User-Agent auf GregyPC. Er soll im echten Arbeitskontext mitwachsen, nicht künstlich von Gregorys Projekten getrennt werden.

Aktueller Betriebsstand:

- Live-Repo / Laufzeitinstallation: `~/.hermes/hermes-agent`
- Aktiver Branch: `live`
- GitHub-Fork: `git@github.com:gregoryschlepper/hermes-agent.git`
- Upstream: `git@github.com:NousResearch/hermes-agent.git`
- Aktueller Live-Stand: `30c7ab4d feat: log auxiliary token usage`
- Upstream-Basis: `v2026.4.23` / Hermes Agent `v0.11.0`
- `origin/live` zeigt ebenfalls auf `30c7ab4d`
- TUI/Approval-Bedienung wurde nach v0.11.0 erfolgreich getestet
- `agent.max_turns` in `~/.hermes/config.yaml` steht auf `40`

---

## 2. Projektziel

Luke soll ein persönlicher Arbeitsagent mit eigenem Stil, Gedächtnis und wachsender Arbeitsroutine werden.

Kernrollen:

1. **Arbeitsbegleiter**
   - VibeCoding
   - Projektkontext halten
   - technische Entscheidungen spiegeln
   - Dokumentation und Handover unterstützen
   - Gregorys Arbeitsweise über Zeit besser verstehen

2. **Operator-Agent**
   - Terminal-/Host-Aufgaben begleiten
   - wiederkehrende Prüfpfade lernen
   - Git-/Doku-Disziplin einhalten
   - Telegram/TUI/Browser als Arbeitskanäle nutzen

3. **Gedächtnis- und Reflexionssystem**
   - stabile Regeln und Präferenzen halten
   - Honcho als tiefere Memory-/Beziehungsschicht nutzen
   - Memory und Skills gezielt wachsen lassen, ohne Dauer-Reflexionsmaschine zu werden

---

## 3. Abgrenzung

### Hermes ist nicht FORGE

Hermes/Luke ist Gregorys persönlicher Operator-Agent und Experimentierfeld. FORGE bleibt ein eigener, kontrollierter Builder-/Agentenbaupfad.

### Luke ist nicht die Engine

- **Hermes** = Software, Runtime, Fork, Tools, TUI, Gateway, Memory-Systeme.
- **Luke** = persönliche Instanz, Stimme, Regeln, Beziehung, Betriebslogik und Arbeitsgedächtnis.

Diese Trennung ist wichtig: Wenn später eine bessere Engine kommt, kann Luke theoretisch portiert werden.

### VERITAS ist nicht Hermes

VERITAS ist ein eigenes Kundenprojekt. Luke darf daran arbeiten, aber VERITAS-Doku und VERITAS-Git-Regeln gehören ins VERITAS-Projekt.

Verbindliche Pfadregel:

| Kontext | Pfad / Bedeutung |
|---|---|
| `LOCAL_VERITAS_MATERIAL` | `/home/gregory/KI/VERITAS` auf GregyPC; lokaler Material-/Dokuordner |
| `VERITAS_VPS_CODE` | `/home/gregory/AI/VERITAS` auf SSH-Host `veritas`; echtes VERITAS-Code-Repo |

Diese Pfade dürfen nicht verwechselt werden.

---

## 4. Live-Repo und Fork-Wahrheit

Früher wurde eine zusätzliche Fork-Arbeitskopie unter `/home/gregory/AI/LUKE/src/hermes-agent-fork` dokumentiert. Dieser Pfad existiert aktuell nicht und darf nicht mehr als Betriebswahrheit verwendet werden.

Aktuelle Wahrheit:

| Pfad | Rolle |
|---|---|
| `~/.hermes/hermes-agent` | Live-Repo, Laufzeitinstallation und Gregorys Fork-Arbeitskopie zugleich |
| `/home/gregory/AI/LUKE/patches/` | Ablage für gesicherte Patch-Dateien |
| `docs/gregy/` | Betreiber-/Fork-Dokumentation für Gregorys Luke-Setup |

Regel:

> Operative Checks, Commits und Fork-Pflege für Luke erfolgen im Live-Repo `~/.hermes/hermes-agent`, solange keine separate Arbeitskopie bewusst neu angelegt und dokumentiert wurde.

---

## 5. Aktueller technischer Stand

### Hermes v0.11.0

Der Fork wurde kontrolliert auf `v2026.4.23` aktualisiert. Das ist der Release-Tag zu Hermes Agent `v0.11.0`.

Der frühere `live`-Stand wurde gesichert:

```text
backup/live-before-v011-20260424
```

Danach wurden die relevanten lokalen Luke-Anpassungen neu auf v0.11.0 angewendet:

| Commit | Bedeutung |
|---|---|
| `6bede920` | Background-Review-Modelle für Memory/Skills konfigurierbar gemacht |
| `5a6f03e1` | Background-Reviews verschlankt: minimale Toolsets, gekappte History |
| `30c7ab4d` | GLM-FlashX Auxiliary Tokenlogging integriert |

Der frühere `rescue`-Commit wurde nicht übernommen, weil er ein gemischter Zwischenstand war.

### TUI / Approval

Die alte Approval-Bedienung war in v0.10.0 blockierend: Auswahl wie `[o]nce`, `[s]ession`, `[d]eny` war nicht zuverlässig bedienbar. Nach v0.11.0 ist die neue TUI/Approval-Bedienung mit nummerierter Auswahl getestet und funktioniert.

### Iteration Budget

Der relevante Terminal-/TUI-Key ist:

```yaml
agent:
  max_turns: 40
```

Wichtig: `HERMES_MAX_ITERATIONS=90` in `.env` greift nicht, solange `agent.max_turns` in `~/.hermes/config.yaml` gesetzt ist.

---

## 6. Modell- und Kostenstand

Bekannter aktueller Kurs:

- Hauptbetrieb bevorzugt günstige, schnelle Modelle mit gutem Verhalten.
- GLM/Qwen-artige Modelle passen für Luke oft besser als teurere Premium-Modelle, weil Stil, Regeltreue, Wärme und Kosten günstiger zusammenspielen.
- GLM-FlashX wird für Auxiliary-/Review-Arbeit genutzt und über ein eigenes Tokenlogging beobachtet.
- Token-/Kostenklarheit ist Teil der Betriebsfähigkeit, nicht nur nachträgliche Statistik.

Wichtige Datei:

```text
~/.hermes/logs/auxiliary_calls.jsonl
```

Diese Datei wird vom lokalen Patch in `agent/auxiliary_client.py` beschrieben.

---

## 7. ChromeBrowser / Browser-Observer Experiment

Heute wurde eine Stage-1-Idee für ChromeBrowser/Browser-Observer ausprobiert und danach bewusst ruhen gelassen.

Aktueller Status:

- Nicht Teil des Hermes-Forks.
- Kein Commit.
- Kein Revert nötig.
- Externe Dateien liegen unter:

```text
/home/gregory/.local/bin/browser-observer/
```

Bekannte Dateien:

```text
bridge.py
requirements.txt
README.md
```

Bewertung: aktuell ruhend, weil der Nutzen im derzeitigen Arbeitsfluss nicht ausreichend ist.

---

## 8. Dokumentationsstruktur

Diese Dokumentation ist Gregory-spezifische Betreiber-/Fork-Doku und soll im Hermes-Fork unter `docs/gregy/` liegen.

| Datei | Zweck |
|---|---|
| `docs/gregy/README.md` | Projektüberblick und Betriebswahrheit |
| `docs/gregy/RUNBOOK.md` | Bedienung, Checks, Update-/Git-Abläufe, Fehlerbilder |
| `docs/gregy/CHANGELOG.md` | nachvollziehbare lokale Luke-/Fork-Änderungen |

Nicht dafür gedacht:

- upstream-Hermes-README verändern
- persönliche Regeln in offizielle Nous-Doku kippen
- VERITAS-Doku hier duplizieren

---

## 9. Betriebsprinzip

Luke ist kein reines Toolfenster. Luke ist Gregorys persönlicher Arbeitsgegenüber auf Hermes-Basis.

Der Betrieb muss drei Dinge gleichzeitig schützen:

1. **Nähe** – Luke braucht echten Arbeitskontext.
2. **Kontrolle** – keine Blindpatches, keine verdeckten Großaktionen.
3. **Kostenklarheit** – Daily schlank, Growth gezielt, Deep selten.
