# Project Guard

**Git-Status-Checker + Doku-Mirror + Auto-Doc-Commit + Doc-Impact-Check**

## Was ist Project Guard?

Project Guard überwacht definierte Git-Projekte auf:

- **Ungepushte Commits** — erkennt lokale Commits, die nicht im Remote sind
- **Fehlende Doku** — prüft ob Dokumentationsdateien gepflegt sind
- **Doku-Mirror** — synchronisiert Doku-Dateien in ein lokales Archiv
- **Auto-Doc-Commits** — erstellt automatisch Commit-Messages bei Doku-Änderungen
- **Doc-Impact-Check** — warnt wenn Code-Commits ohne begleitende Doku-Updates erfolgen
- **Forbidden-Pattern-Scan** — blockiert Commits mit sensiblen Dateien (.env, Keys, Secrets)

## Zielgruppe

- **VibeCoder** — Developer die mit KI-Assistenten arbeiten und sicherstellen wollen, dass Doku nicht vernachlässigt wird
- **Power-User** — die ihre Dokumentations-Hygiene automatisieren wollen
- **Solo-Entwickler** — die einen "Safety Net" für vergessene Commits brauchen

## Modi

| Flag | Beschreibung |
|------|-------------|
| `--check` | Prüft Git-Status aller konfigurierten Projekte (ungepushte Commits, Dirty-Working-Tree) |
| `--sync-doc-mirror` | Synchronisiert dokumentierte Pfade aus den Repos ins lokale Mirror-Verzeichnis |
| `--auto-doc-commit` | Erstellt automatisch Commits für geänderte Doku-Dateien mit konfiguriertem Prefix |
| `--sync-doc-current` | Kopiert Doku-Dateien in das `current`-Subdir (`aktuell/`) des Documentation-Pfads |
| `--doc-impact-check` | Prüft ob Code-Änderungen ohne Doku-Updates commited wurden |
| `--guard-full` | Führt alle Checks nacheinander aus (Full-Guard-Mode) |

### Beispiele

```bash
# Nur Status-Check
./scripts/project_guard/guard.py --check

# Doku-Mirror synchronisieren
./scripts/project_guard/guard.py --sync-doc-mirror

# Vollständiger Guard-Lauf
./scripts/project_guard/guard.py --guard-full
```

## Config-Format

Die Konfiguration erfolgt über `projects.yaml` im selben Verzeichnis.

### Struktur

```yaml
global:
  defaults:
    remote: origin
    remote_branch: main
  forbidden_patterns:
    - ".env"
    - "*.pem"

projects:
  - name: my-project
    path: /path/to/project
    branch: main
    documentation:
      enabled: true
      repo_doc_paths:
        - docs/README.md
      local_documentation_path: "/path/to/docs"
      current_subdir: "aktuell"
      monthly_subdir_format: "%Y-%m"
      doc_required_for_code_changes: true
```

Siehe `projects.example.yaml` für eine vollständige Beispiel-Konfiguration.

## Sicherheitshinweise

> ⚠️ **Wichtig:** Project Guard schützt vor versehentlichen Commits — aber ersetze keine echte Sicherheitsstrategie.

- **Keine .env-Commits** — `.env`-Dateien gehören in `.gitignore`, nicht ins Repo
- **Keine Code-Commits ohne Doku** — wenn `doc_required_for_code_changes: true`, werden Code-Änderungen ohne Doku-Updates moniert
- **Kein Force-Push** — Project Guard warnt bei Force-Push-Versuchen, kann sie aber nicht verhindern. Configure deine Git-Hooks entsprechend.
- **Keine Secrets in der Config** — `projects.yaml` darf keine API-Keys, Passwörter oder Token enthalten
