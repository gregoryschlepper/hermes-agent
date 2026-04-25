#!/usr/bin/env bash
#
# luke.example.sh — Start-Wrapper für Hermes Agent (Template)
#
# Zweck: Beim ersten Start des Tages einmalig Maintenance-Aufgaben anstoßen
#        bevor Hermes selbst gestartet wird.
#
# Verwendung: Dieses Skript nach luke.sh kopieren, Platzhalter ersetzen,
#             ins PATH legen und statt 'hermes' als Startbefehl verwenden.
#             Z.B.: luke.sh "some-task"  →  alles läuft durch, dann exec hermes "some-task"
#
# ---------------------------------------------------------------------------

# =============================================================================
# VARIABLEN — Alle Platzhalter Müssen ersetzt werden
# =============================================================================

# Pfad zur Hermes-Binary. Kann auch einfach "hermes" sein,
# wenn Hermes im PATH gefunden wird.
HERMES_BIN="/path/to/hermes"

# Python-Interpreter — z.B. aus einem venv:
PYTHON_BIN="/path/to/python"

# Project/Documentation Guard: Schützt Code- und Projektstruktur.
# Wird 30 Min nach Start via systemd-run --user geplant.
PROJECT_GUARD="/path/to/project_guard.py"

# Optional: Guard-State-Datei — speichert den letzten Guard-Status.
# Falls nicht benötigt, leer lassen.
PROJECT_GUARD_STATE="/path/to/guard-state"

# Optional: Health-Check-Skript — prüft Systemintegrität.
# Wird nur ausgeführt, wenn es existiert und ausführbar ist.
HEALTH_CHECK="/path/to/health_check.sh"

# Optional: Cleanup Ops — Dry-Run räumt temporäre Dateien auf.
CLEANUP_OPS="/path/to/cleanup_ops.py"

# Optional: Archive Hygiene — Dry-Run prüft Archivkonsistenz.
ARCHIVE_HYGIENE="/path/to/archive_hygiene.py"

# Optional: Daily Cost Report — API-Kosten des Vortags.
DAILY_COST_REPORT="/path/to/daily_cost_report.py"

# =============================================================================
# JOBS-VERZEICHNIS (generisch)
# =============================================================================
# Alternativ können alle Job-Skripte aus einem gemeinsamen Verzeichnis
# geladen werden. Setze dies auf ops/jobs/ in deiner Hermes-Installation.
# JOBS_DIR="${HERMES_HOME}/ops/jobs"
# Wenn JOBS_DIR gesetzt ist, überschreiben die einzelnen Pfade darunter
# nicht mehr explizit gesetzt werden — JOBS_DIR hat Vorrang.
if [[ -n "${JOBS_DIR:-}" && -d "$JOBS_DIR" ]]; then
    HEALTH_CHECK="${HEALTH_CHECK:-$JOBS_DIR/health_check.sh}"
    CLEANUP_OPS="${CLEANUP_OPS:-$JOBS_DIR/cleanup_ops.py}"
    ARCHIVE_HYGIENE="${ARCHIVE_HYGIENE:-$JOBS_DIR/archive_hygiene.py}"
    DAILY_COST_REPORT="${DAILY_COST_REPORT:-$JOBS_DIR/daily_cost_report.py}"
fi

# =============================================================================
# MARKER-LOGIK: First-Start-of-Day
# =============================================================================

# Temporäres Verzeichnis für Marker-Files (wird beim Boot gelöscht).
MARKER_DIR="${XDG_RUNTIME_DIR:-/tmp}/hermes-start-wrapper"
mkdir -p "$MARKER_DIR"

# Heutiger Tag als YYYYMMDD — Marker-Dateien tragen dieses Datum.
TODAY=$(date +%Y%m%d)

# Marker-Dateien — jeweils eine pro Phase.
MARKER_HEALTH="${MARKER_DIR}/health-${TODAY}"
MARKER_CLEANUP="${MARKER_DIR}/cleanup-${TODAY}"
MARKER_ARCHIVE="${MARKER_DIR}/archive-${TODAY}"
MARKER_GUARD="${MARKER_DIR}/guard-${TODAY}"

# =============================================================================
# Phase 1: Health-Check (einmal pro Tag)
# =============================================================================
# Prüft die Systemintegrität. Optional — wird nur ausgeführt, wenn
# das Health-Check-Skript existiert und ausführbar ist.
if [[ -n "$HEALTH_CHECK" && -x "$HEALTH_CHECK" && ! -f "$MARKER_HEALTH" ]]; then
    echo "[start-wrapper] Phase 1: Running health check..."
    "$HEALTH_CHECK"
    if [[ $? -ne 0 ]]; then
        echo "[start-wrapper] WARNING: Health check exited with non-zero status"
    fi
    touch "$MARKER_HEALTH"
fi

# =============================================================================
# Phase 2: Cleanup Ops Dry-Run (einmal pro Tag, optional)
# =============================================================================
# Zeigt an, welche temporären Dateien oder Caches bereinigt
# werden könnten — ohne etwas zu löschen.
if [[ -n "$CLEANUP_OPS" && (! -f "$MARKER_CLEANUP") ]]; then
    echo "[start-wrapper] Phase 2: Cleanup Ops dry-run..."
    "$PYTHON_BIN" "$CLEANUP_OPS" --dry-run
    touch "$MARKER_CLEANUP"
fi

# =============================================================================
# Phase 3: Archive Hygiene Dry-Run (einmal pro Tag, optional)
# =============================================================================
# Prüft die Konsistenz von Log- und Session-Archiven im Dry-Run-Modus.
if [[ -n "$ARCHIVE_HYGIENE" && (! -f "$MARKER_ARCHIVE") ]]; then
    echo "[start-wrapper] Phase 3: Archive hygiene dry-run..."
    "$PYTHON_BIN" "$ARCHIVE_HYGIENE" --dry-run
    touch "$MARKER_ARCHIVE"
fi

# =============================================================================
# Phase 4: Daily Cost Report (einmal pro Tag, optional)
# =============================================================================
# Zeigt die API-Kosten des Vortags — Hauptchat + Auxiliary kombiniert.
# Das Script schreibt Terminal-Output und Markdown-Report.
if [[ -n "$DAILY_COST_REPORT" && -f "$DAILY_COST_REPORT" ]]; then
    echo "[start-wrapper] Phase 4: Running daily cost report..."
    "$PYTHON_BIN" "$DAILY_COST_REPORT"
    if [[ $? -ne 0 ]]; then
        echo "[start-wrapper] WARNING: Cost report exited with non-zero status"
    fi
fi

# =============================================================================
# Phase 5: Project/Documentation Guard Planung (einmal pro Tag)
# =============================================================================
# Der Project/Documentation Guard wird 30 Minuten nach dem Start
# geplant — genug Zeit, dass erste Arbeitsphase abgeschlossen ist.
# Guard-Planung findet nur statt, wenn noch kein Marker für heute existiert.
if [[ -n "$PROJECT_GUARD" && (! -f "$MARKER_GUARD") ]]; then
    echo "[start-wrapper] Phase 4: Scheduling project guard for +30 minutes..."

    GUARD_CMD=(
        "$PYTHON_BIN" "$PROJECT_GUARD"
        --guard-full
    )

    # Optional: Guard-State-Datei mitübergeben, falls gesetzt.
    if [[ -n "$PROJECT_GUARD_STATE" ]]; then
        GUARD_CMD+=(--state-file "$PROJECT_GUARD_STATE")
    fi

    systemd-run --user --on-active=30m \
        --unit=hermes-project-guard-daily \
        --description="Hermes Project/Documentation Guard (${TODAY})" \
        "${GUARD_CMD[@]}"

    # Marker setzen, damit die Planung heute nicht wiederholt wird.
    touch "$MARKER_GUARD"
    echo "[start-wrapper] Guard scheduled. Will run ~30 minutes after start."
fi

# =============================================================================
# EXEC: Hermes Agent starten
# =============================================================================
# Übergibt alle Argumente unverändert an die Hermes-Binary.
echo "[start-wrapper] All phases complete. Starting Hermes..."
exec "$HERMES_BIN" "$@"
