# Project Guard — Einrichtung

## Abhängigkeiten

- **Python 3.10+**
- **PyYAML** — YAML-Parser für die Projekt-Konfiguration

### PyYAML installieren

```bash
# Im Projekt-virtualenv (empfohlen)
pip install pyyaml

# Oder systemweit
pip3 install pyyaml
```

## Schritte

### 1. Verzeichnis anlegen

Das Verzeichnis `scripts/project_guard/` existiert bereits im Repo. Wenn du einen eigenen Fork pflegst:

```bash
mkdir -p scripts/project_guard
```

### 2. projects.yaml erstellen

Kopiere die Beispiel-Datei und passe sie an deine Projekte an:

```bash
cp scripts/project_guard/projects.example.yaml scripts/project_guard/projects.yaml
```

Öffne `projects.yaml` und ersetze alle `/path/to/`-Platzhalter durch echte Pfade, sowie `myserver` durch deinen SSH-Alias.

### 3. Erster Testlauf

```bash
cd /path/to/hermes-agent
python3 scripts/project_guard/project_guard.py --check
```

### 4. Cron-Integration (optional)

Automatischer Check alle 30 Minuten via Crontab:

```bash
crontab -e
```

Füge folgende Zeile hinzu:

```cron
*/30 * * * * cd /path/to/hermes-agent && /usr/bin/python3 scripts/project_guard/project_guard.py --guard-full >> /path/to/logs/project_guard.log 2>&1
```

### 5. systemd-Integration (optional)

Alternativ als systemd-Service + Timer:

**Service-Datei** (`~/.config/systemd/user/project-guard.service`):

```ini
[Unit]
Description=Project Guard — Git Status & Doc Checker

[Service]
Type=oneshot
WorkingDirectory=/path/to/hermes-agent
ExecStart=/usr/bin/python3 scripts/project_guard/project_guard.py --guard-full
StandardOutput=append:/path/to/logs/project_guard.log
StandardError=append:/path/to/logs/project_guard.log
```

**Timer-Datei** (`~/.config/systemd/user/project-guard.timer`):

```ini
[Unit]
Description=Project Guard Timer

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

Aktivieren:

```bash
systemctl --user daemon-reload
systemctl --user enable --now project-guard.timer
systemctl --user status project-guard.timer
```

### Alternativer systemd-run (Einzeiler)

Für einmalige oder ad-hoc Ausführung via systemd-run:

```bash
systemd-run --user --on-calendar="*:0/30" \
  --unit=project-guard \
  --working-directory=/path/to/hermes-agent \
  /usr/bin/python3 scripts/project_guard/project_guard.py --guard-full
```

## Struktur

```
scripts/project_guard/
├── project_guard.py                # Hauptskript (noch zu erstellen)
├── projects.yaml           # Deine Konfiguration (gitignore'd)
├── projects.example.yaml   # Diese Datei — Referenz
├── README.md               # Dieses Repo
└── INSTALL.md              # Diese Datei
```

> **Hinweis:** `projects.yaml` gehört nicht ins Repo. Trage es in `.gitignore` ein:
> ```
> scripts/project_guard/projects.yaml
> ```
