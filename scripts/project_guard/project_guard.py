#!/usr/bin/env python3
"""
Project Guard – Stufe 1: Check-Modus
Project Guard – Stufe 2: Doc-Mirror-Sync (--sync-doc-mirror)
Project Guard – Stufe 3: Auto-Doc-Commit (--auto-doc-commit)

Stufe 1: Prüft git-Projekte auf Status, Divergenz und Forbidden Files.
Stufe 2: Synchronisiert Dokumentationsdateien aus Remote-Repos in lokale Spiegel.
Stufe 3: Commit und Push von dokumentierten Änderungen, nur für erlaubte Doku-Pfade.
Keine Code-Commits, kein Force-Push, keine Wildcard-Adds.
"""

import argparse
import hashlib
import re
import shlex
from shlex import quote as shlex_quote
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


# ──────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_cmd(cmd: str, workdir: str = None, ssh_alias: str = None, timeout: int = 15) -> tuple[int, str, str]:
    """Befehl lokal oder via SSH ausführen. Returns (returncode, stdout, stderr)."""
    try:
        if ssh_alias:
            remote_cmd = f"cd {workdir} 2>/dev/null && {cmd}" if workdir else cmd
            result = subprocess.run(
                ["ssh", ssh_alias, remote_cmd],
                capture_output=True, text=True, timeout=timeout
            )
        else:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=workdir, timeout=timeout
            )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def file_hash(filepath: Path) -> str:
    """SHA256-Hash einer lokalen Datei, oder leerer String wenn nicht vorhanden."""
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return ""


def file_hash_remote(filepath: Path, ssh_alias: str, remote_dir: str) -> str:
    """SHA256-Hash einer Datei auf Remote via SSH."""
    filename = filepath.name
    remote_cmd = f"cd {remote_dir} 2>/dev/null && sha256sum {filename}"
    rc, out, err = run_cmd(remote_cmd, ssh_alias=ssh_alias)
    if rc != 0:
        return ""
    # Output-Format: "<hash>  <filename>"
    parts = out.split()
    return parts[0] if parts else ""


def scp_file(ssh_alias: str, remote_dir: str, filename: str, local_dest: Path) -> tuple[int, str]:
    """Eine einzelne Datei von Remote per scp holen. Returns (rc, msg)."""
    source = f"{ssh_alias}:{remote_dir}/{filename}"
    dest = str(local_dest)
    try:
        result = subprocess.run(
            ["scp", "-q", source, dest],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return 0, "OK"
        return result.returncode, result.stderr.strip() or f"scp rc={result.returncode}"
    except subprocess.TimeoutExpired:
        return -1, "scp timed out"
    except Exception as e:
        return -1, str(e)


# ──────────────────────────────────────────────
# Stufe 1: Check-Modus
# ──────────────────────────────────────────────

def check_project(proj: dict, forbidden_patterns: list[str], defaults: dict) -> list[str]:
    """Projekt prüfen. Returns Liste mit [STATUS, detailzeilen...]."""
    lines = []
    path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)
    remote_name = proj.get("remote", defaults.get("remote", "origin"))
    remote_branch = proj.get("remote_branch", defaults.get("remote_branch", "main"))
    name = proj.get("name", path)
    mirror = proj.get("mirror", {})

    # Repo erreichbar?
    rc, out, err = run_cmd("git rev-parse --is-inside-work-tree 2>/dev/null", workdir=path, ssh_alias=ssh_alias)
    if rc != 0:
        return [f"ERROR", f"  ERROR: Kein git-Repo oder nicht erreichbar ({path})"]

    # Aktueller Branch
    rc, branch, _ = run_cmd("git rev-parse --abbrev-ref HEAD", workdir=path, ssh_alias=ssh_alias)
    branch_info = f"  Branch: {branch}" if rc == 0 else "  Branch: (detached)"

    # git status --short
    rc, status, _ = run_cmd("git status --short", workdir=path, ssh_alias=ssh_alias)
    is_dirty = rc == 0 and len(status) > 0

    # Remote vorhanden?
    rc, remotes, _ = run_cmd(f"git remote get-url {remote_name}", workdir=path, ssh_alias=ssh_alias)
    has_remote = rc == 0

    # Ahead/Behind
    state = "OK"
    ahead_behind = ""
    if has_remote and branch and branch != "HEAD":
        ref = remote_branch or branch
        rc, ab, _ = run_cmd(
            f"git rev-list --left-right --count {remote_name}/{ref}...HEAD",
            workdir=path, ssh_alias=ssh_alias
        )
        if rc == 0:
            parts = ab.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
                if ahead > 0 and behind > 0:
                    state = "DIVERGED"
                    ahead_behind = f"  +{ahead} / -{behind}"
                elif ahead > 0:
                    state = "AHEAD"
                    ahead_behind = f"  +{ahead} ahead"
                elif behind > 0:
                    state = "BEHIND"
                    ahead_behind = f"  -{behind} behind"

    if is_dirty:
        state = "DIRTY"

    lines.append(branch_info)
    if is_dirty:
        dirty_lines = status.splitlines()
        lines.append(f"  Geändert: {len(dirty_lines)} Datei(en)")
        for dl in dirty_lines[:3]:
            lines.append(f"    {dl.strip()}")

    if state in ("AHEAD", "BEHIND", "DIVERGED"):
        lines.append(f"  Remote ({remote_name}/{remote_branch or branch}):{ahead_behind}")

    # Forbidden Patterns
    if forbidden_patterns and is_dirty:
        forbidden_hits = []
        for pattern in forbidden_patterns:
            rc, matches, _ = run_cmd(
                f"git status --short | grep -E '{pattern}' || true",
                workdir=path, ssh_alias=ssh_alias
            )
            if matches:
                forbidden_hits.append(matches)
        if forbidden_hits:
            lines.append("  ⚠ Forbidden matches:")
            for fh in forbidden_hits:
                for hit in fh.strip().splitlines()[:3]:
                    lines.append(f"    {hit.strip()}")

    # Mirror Hashvergleich (nur lesend in Check-Modus)
    if mirror.get("enabled"):
        mirror_path = mirror.get("local_path", "")
        mirror_files = mirror.get("files", [])
        if mirror_path and mirror_files:
            mismatches = []
            for mf in mirror_files:
                if ssh_alias:
                    remote_hash = file_hash_remote(Path(mf), ssh_alias, path)
                else:
                    remote_hash = file_hash(Path(path) / mf)
                mirror_hash = file_hash(Path(mirror_path) / mf)
                if remote_hash != mirror_hash:
                    mismatches.append(mf)
            if mismatches:
                if state == "OK":
                    state = "MIRROR_OUTDATED"
                lines.append(f"  ⚠ Mirror abweicht: {', '.join(mismatches)}")
            elif mirror_path:
                lines.append(f"  Mirror: aktuell")

    return [state] + lines


# ──────────────────────────────────────────────
# Stufe 2: Doc-Mirror-Sync
# ──────────────────────────────────────────────

def sync_doc_mirror(proj: dict) -> list[str]:
    """
    Synchronisiert Dokumentationsdateien aus einem Remote-Repo
    in einen lokalen Dokumentationsspiegel.

    Sicherheitsregeln:
    - Nur Dateien aus mirror.files kopieren
    - Vor Überschreiben Backup anlegen
    - Keine rm, keine Wildcards
    - Bei SSH- oder Hash-Fehler: Abbruch
    """
    lines = []
    name = proj.get("name", proj.get("path", "unknown"))
    ssh_alias = proj.get("ssh_alias", None)
    remote_dir = proj.get("path")
    mirror = proj.get("mirror", {})
    local_path = mirror.get("local_path", "")
    mirror_files = mirror.get("files", [])

    if not mirror_files or not local_path:
        return ["SKIP", f"  Mirror nicht konfiguriert"]

    local_dir = Path(local_path)

    # Prüfe ob Mirror-Verzeichnis existiert
    if not local_dir.is_dir():
        return ["ERROR", f"  Mirror-Verzeichnis nicht vorhanden: {local_path}"]

    # Phase 1: Hashes vergleichen (Remote → Local)
    mismatches = []
    missing_local = []
    for mf in mirror_files:
        if ssh_alias:
            remote_hash = file_hash_remote(Path(mf), ssh_alias, remote_dir)
        else:
            remote_hash = file_hash(Path(remote_dir) / mf)

        if not remote_hash:
            lines.append(f"  ERROR: Remote-Hash nicht ermittelbar für {mf}")
            return ["ERROR"] + lines

        local_file = local_dir / mf
        local_hash = file_hash(local_file)

        if remote_hash != local_hash:
            if local_hash == "":
                missing_local.append(mf)
            mismatches.append(mf)

    if not mismatches:
        return ["MIRROR_OK", f"  Alle {len(mirror_files)} Dateien aktuell"]

    lines.append(f"  {len(mismatches)} Datei(en) abweicht: {', '.join(mismatches)}")

    # Phase 2: Backup anlegen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = local_dir / f"_project_guard_backup_{timestamp}"
    lines.append(f"  Backup → {backup_dir.name}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    for mf in mismatches:
        src = local_dir / mf
        if src.exists():
            shutil.copy2(src, backup_dir / mf)
            lines.append(f"    {mf} → gesichert")
        else:
            lines.append(f"    {mf} → fehlt lokal (wird neu erstellt)")

    # Phase 3: Abweichende Dateien per scp holen
    copied = []
    failed = []
    for mf in mismatches:
        dest = local_dir / mf
        rc, msg = scp_file(ssh_alias, remote_dir, mf, dest)
        if rc == 0:
            copied.append(mf)
        else:
            failed.append((mf, msg))

    if failed:
        lines.append(f"  ⚠ Fehlgeschlagen:")
        for mf, msg in failed:
            lines.append(f"    {mf}: {msg}")
        return ["ERROR"] + lines

    # Phase 4: Hashes erneut prüfen (Verifikation)
    verify_ok = True
    for mf in copied:
        if ssh_alias:
            remote_hash = file_hash_remote(Path(mf), ssh_alias, remote_dir)
        else:
            remote_hash = file_hash(Path(remote_dir) / mf)
        new_local_hash = file_hash(local_dir / mf)
        if remote_hash != new_local_hash:
            lines.append(f"  ⚠ Hash-Mismatch nach Sync: {mf}")
            verify_ok = False

    if verify_ok and not failed:
        return ["SYNC_OK", f"  {len(copied)} Datei(en) synchronisiert: {', '.join(copied)}"]

    return ["ERROR"] + lines


# ──────────────────────────────────────────────
# Stufe 3: Auto-Doc-Commit
# ──────────────────────────────────────────────

def _is_file_in_allowed_paths(filename: str, allowed_paths: list[str]) -> bool:
    """Prüft, ob eine Datei in den erlaubten Doku-Pfaden liegt."""
    for ap in allowed_paths:
        # Direkter Treffer (z.B. README.md == README.md)
        if filename == ap:
            return True
        # Datei im Unterordner (z.B. docs/foo.md startet mit docs/)
        if ap.endswith("/") and filename.startswith(ap):
            return True
        # Datei im Unterordner (z.B. docs/foo.md, ap = docs/)
        if ap.endswith("/") and "/" in filename:
            parts = filename.rsplit("/", 1)
            if parts[0] == ap.rstrip("/"):
                return True
    return False


def _parse_status_lines(status_output: str) -> list[tuple[str, str]]:
    """Parse git status --short Output. Returns [(XY, filename), ...]."""
    result = []
    for line in status_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            result.append((parts[0], parts[1]))
        elif len(parts) == 1:
            # Edge case: renamed files etc.
            result.append((parts[0], ""))
    return result


def auto_doc_commit(proj: dict, forbidden_patterns: list[str], defaults: dict) -> list[str]:
    """
    Automatische Doku-Commits mit strengen Grenzen.
    Nur für Projekte mit auto_doc.enabled=true.
    """
    lines = []
    path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)
    remote_name = proj.get("remote", defaults.get("remote", "origin"))
    remote_branch = proj.get("remote_branch", defaults.get("remote_branch", "main"))
    name = proj.get("name", path)
    auto_doc = proj.get("auto_doc", {})
    mirror = proj.get("mirror", {})

    if not auto_doc.get("enabled"):
        return ["SKIP", f"  auto_doc nicht aktiv für {name}"]

    allowed_paths = auto_doc.get("allowed_paths", [])
    auto_push = auto_doc.get("auto_push_clean_ahead", False)

    # Repo erreichbar?
    rc, out, err = run_cmd("git rev-parse --is-inside-work-tree 2>/dev/null", workdir=path, ssh_alias=ssh_alias)
    if rc != 0:
        return ["ERROR", f"  Kein git-Repo: {path}"]

    # Status --short
    rc, status, _ = run_cmd("git status --short", workdir=path, ssh_alias=ssh_alias)

    if rc != 0 or not status:
        # Working tree sauber
        rc_branch, branch_out, _ = run_cmd("git rev-parse --abbrev-ref HEAD", workdir=path, ssh_alias=ssh_alias)
        branch = branch_out if rc_branch == 0 else "(detached)"
        
        # Ahead/Behind prüfen
        ref = remote_branch or branch
        if branch and branch != "HEAD":
            rc, ab, _ = run_cmd(
                f"git rev-list --left-right --count {remote_name}/{ref}...HEAD",
                workdir=path, ssh_alias=ssh_alias
            )
            if rc == 0:
                parts = ab.split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
                    if ahead > 0 and behind > 0:
                        return ["DIVERGED", f"  Branch {branch} diverged (+{ahead}/-{behind})"]
                    elif ahead > 0:
                        if auto_push:
                            rc_push, _, err_push = run_cmd(
                                f"git push {remote_name} {branch}",
                                workdir=path, ssh_alias=ssh_alias, timeout=30
                            )
                            if rc_push == 0:
                                return ["PUSHED", f"  +{ahead} commits gepusht"]
                            return ["PUSH_ERROR", f"  Push fehlgeschlagen: {err_push}"]
                        return ["AHEAD", f"  +{ahead} ahead (auto_push aus)"]
                    elif behind > 0:
                        return ["BEHIND", f"  -{behind} behind"]
        return ["OK", f"  Branch: {branch}, working tree sauber"]

    # Dirty: Dateien parsen
    status_entries = _parse_status_lines(status)
    all_files = set()
    for xy, fn in status_entries:
        if fn:
            all_files.add(fn)

    if not all_files:
        return ["OK", "  Keine relevanten Änderungen im status"]

    # Prüfe: forbidden patterns
    forbidden_found = []
    for pattern in forbidden_patterns:
        for fn in all_files:
            if re.search(pattern, fn):
                forbidden_found.append(fn)
    if forbidden_found:
        return ["FORBIDDEN", f"  ⚠ Verbotene Datei(en): {', '.join(forbidden_found)}"]

    # Prüfe: alle Dateien in allowed_paths?
    allowed_files = []
    disallowed_files = []
    for fn in sorted(all_files):
        if _is_file_in_allowed_paths(fn, allowed_paths):
            allowed_files.append(fn)
        else:
            disallowed_files.append(fn)

    if disallowed_files:
        return ["DIRTY_NON_DOC",
                f"  {len(disallowed_files)} Datei(en) außerhalb Doku-Scope: {', '.join(disallowed_files[:5])}"]

    if not allowed_files:
        return ["OK", "  Keine erlaubten Doku-Dateien geändert"]

    # Nur erlaubte Doku-Dateien → git diff --check
    rc, diff_check, _ = run_cmd("git diff --check", workdir=path, ssh_alias=ssh_alias)
    if diff_check:
        lines.append(f"  git diff --check Warnungen:")
        for wl in diff_check.splitlines()[:3]:
            lines.append(f"    {wl.strip()}")

    # Stage nur die erlaubten Dateien (explizit, kein Wildcard)
    staged = []
    for fn in allowed_files:
        rc, _, err_a = run_cmd(f"git add -- {fn}", workdir=path, ssh_alias=ssh_alias)
        if rc == 0:
            staged.append(fn)
        else:
            lines.append(f"  ⚠ Stage fehlgeschlagen: {fn}: {err_a}")

    if not staged:
        return ["ERROR", "  Keine Dateien gestaged"]

    # Commit
    commit_msg = "docs: update project documentation"
    rc, _, err_c = run_cmd(
        f'git commit -m "{commit_msg}" -- ' + " ".join(shlex_quote(f) for f in staged),
        workdir=path, ssh_alias=ssh_alias
    )
    if rc != 0:
        return ["COMMIT_ERROR", f"  Commit fehlgeschlagen: {err_c}"]

    lines.append(f"  Commit erstellt:")
    # Commit-Hash holen
    rc, commit_hash, _ = run_cmd("git log -1 --format=%h", workdir=path, ssh_alias=ssh_alias)
    if rc == 0:
        lines.append(f"    {commit_hash} {commit_msg}")
    lines.append(f"    Dateien: {', '.join(staged)}")

    # Push
    rc, branch, _ = run_cmd("git rev-parse --abbrev-ref HEAD", workdir=path, ssh_alias=ssh_alias)
    branch = branch if rc == 0 else remote_branch
    rc_push, _, err_push = run_cmd(
        f"git push {remote_name} {branch}",
        workdir=path, ssh_alias=ssh_alias, timeout=30
    )
    if rc_push == 0:
        lines.append(f"  Push → {remote_name}/{branch}: OK")
    else:
        lines.append(f"  ⚠ Push fehlgeschlagen: {err_push}")

    # Nach Push: Mirror sync wenn enabled
    if mirror.get("enabled"):
        lines.append("  Mirror-Sync nach Commit/Push:")
        sync_result = sync_doc_mirror(proj)
        lines.extend(sync_result[1:])

    return ["COMMITTED"] + lines


# ──────────────────────────────────────────────
# Stufe 4a: Doc-Current-Sync (--sync-doc-current)
# ──────────────────────────────────────────────

def sync_doc_current(proj: dict) -> list[str]:
    """
    Kopiert konfigurierte Doku-Dateien aus dem Repo nach
    <local_documentation_path>/aktuell/.

    - Nur documentation.enabled=true Projekte
    - Nur explizite repo_doc_paths
    - Keine Wildcards, keine Löschungen
    - Fehlende Dateien: melden, nicht abbrechen (außer alle fehlen)
    - Hash-Vergleich vorher/nachher
    """
    lines = []
    name = proj.get("name", proj.get("path", "unknown"))
    doc_cfg = proj.get("documentation", {})

    if not doc_cfg.get("enabled"):
        return ["DOC_SYNC_SKIP", f"  documentation nicht aktiv"]

    repo_doc_paths = doc_cfg.get("repo_doc_paths", [])
    local_base = doc_cfg.get("local_documentation_path", "")
    current_subdir = doc_cfg.get("current_subdir", "aktuell")

    if not repo_doc_paths:
        return ["DOC_SKIP", f"  Keine repo_doc_paths konfiguriert"]
    if not local_base:
        return ["DOC_SYNC_ERROR", f"  Kein local_documentation_path konfiguriert"]

    local_dir = Path(local_base) / current_subdir
    local_dir.mkdir(parents=True, exist_ok=True)

    repo_path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)

    copied = []
    missing = []
    failed = []
    unchanged = []

    for doc_path in repo_doc_paths:
        # Quell-Datei
        if ssh_alias:
            src_hash = file_hash_remote(Path(doc_path), ssh_alias, repo_path)
        else:
            src_hash = file_hash(Path(repo_path) / doc_path)

        if not src_hash:
            missing.append(doc_path)
            continue

        # Ziel-Datei
        dest = local_dir / Path(doc_path).name
        dest_hash = file_hash(dest)

        if src_hash == dest_hash:
            unchanged.append(doc_path)
            continue

        # Hash abweicht oder Ziel fehlt → kopieren
        if ssh_alias:
            rc, msg = scp_file(ssh_alias, repo_path, doc_path, dest)
            if rc != 0:
                failed.append((doc_path, msg))
                continue
        else:
            try:
                shutil.copy2(Path(repo_path) / doc_path, dest)
            except Exception as e:
                failed.append((doc_path, str(e)))
                continue

        # Verifikation: Hash nach Kopie prüfen
        new_dest_hash = file_hash(dest)
        if new_dest_hash == src_hash:
            copied.append(doc_path)
        else:
            failed.append((doc_path, "Hash-Mismatch nach Kopie"))

    # Ergebnis auswerten
    if failed and not copied and not unchanged:
        return ["DOC_SYNC_ERROR"] + [f"  Alle Dateien fehlg."] + [
            f"    {f}: {m}" for f, m in failed
        ]

    if copied or missing:
        lines.append(f"  Kopiert: {len(copied)} | Unverändert: {len(unchanged)} | Fehlend: {len(missing)}")
        if copied:
            lines.append(f"    Kopiert: {', '.join(copied)}")
        if missing:
            lines.append(f"    Fehlend (Remote): {', '.join(missing)}")
        if failed:
            lines.append(f"    Fehler: {', '.join(f for f, _ in failed)}")
            return ["DOC_SYNC_WARN"] + lines
        return ["DOC_SYNC_UPDATED"] + lines

    return ["DOC_SYNC_OK", f"  Alle {len(unchanged)} Dateien aktuell"]


# ──────────────────────────────────────────────
# Stufe 4b: Monatsordner vorbereiten
# ──────────────────────────────────────────────


def prepare_monthly_folders(proj: dict) -> list[str]:
    """
    Legt den aktuellen Monatsordner unter local_documentation_path an.
    Noch keine Guard-Ausgabe schreiben, nur Ordnerstruktur.
    """
    lines = []
    name = proj.get("name", proj.get("path", "unknown"))
    doc_cfg = proj.get("documentation", {})

    if not doc_cfg.get("enabled"):
        return ["MONTHLY_SKIP", f"  documentation nicht aktiv"]

    local_base = doc_cfg.get("local_documentation_path", "")
    monthly_format = doc_cfg.get("monthly_subdir_format", "%Y-%m")

    if not local_base:
        return ["MONTHLY_ERROR", f"  Kein local_documentation_path"]

    monthly_dir = Path(local_base) / datetime.now().strftime(monthly_format)
    monthly_dir.mkdir(parents=True, exist_ok=True)
    lines.append(f"  Ordner: {monthly_dir}")
    return ["MONTHLY_OK"] + lines


# ──────────────────────────────────────────────
# Stufe 1c: Doc-Impact-Check (--doc-impact-check)
# ──────────────────────────────────────────────

def write_doc_task(proj: dict, check_result: dict) -> tuple[str, str]:
    """
    Schreibt einen konkreten Doku-Auftrag als Markdown-Datei in den Monatsordner:
    <local_documentation_path>/<YYYY-MM>/doc-task-YYYY-MM-DD-HHMMSS.md

    Nur bei DOC_REQUIRED (und optional DOC_UNKNOWN).
    Bei DOC_OK: nicht aufrufen.

    Returns (state, filepath)
    """
    name = proj.get("name", proj.get("path", "unknown"))
    doc_cfg = proj.get("documentation", {})

    if not doc_cfg.get("enabled"):
        return "SKIP_TASK", ""

    local_base = doc_cfg.get("local_documentation_path", "")
    monthly_format = doc_cfg.get("monthly_subdir_format", "%Y-%m")

    if not local_base:
        return "SKIP_TASK", ""

    state = check_result.get("state", "UNKNOWN")
    if state not in ("DOC_REQUIRED", "DOC_UNKNOWN"):
        return "SKIP_TASK", ""

    monthly_dir = Path(local_base) / datetime.now().strftime(monthly_format)
    monthly_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"doc-task-{timestamp}.md"
    filepath = monthly_dir / filename

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    files_list = check_result.get("files", [])
    commits_list = check_result.get("commits", [])
    repo_doc_paths = check_result.get("repo_doc_paths", [])
    last_doc_hash = check_result.get("last_doc_hash")

    # Branch ermitteln
    path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)
    rc, branch, _ = run_cmd("git rev-parse --abbrev-ref HEAD", workdir=path, ssh_alias=ssh_alias)
    branch_info = branch if rc == 0 else "(unbekannt)"

    lines = []
    lines.append(f"# Documentation Guard – Doku-Auftrag")
    lines.append(f"")
    lines.append(f"**Timestamp:** {now_str}")
    lines.append(f"**Projekt:** {name}")
    lines.append(f"**Branch:** {branch_info}")
    lines.append(f"**Status:** {state}")
    lines.append(f"")

    if last_doc_hash:
        lines.append(f"**Letzter Doku-Commit:** `{last_doc_hash[:10]}`")
        lines.append(f"")

    if commits_list:
        lines.append("## Betroffene Commits")
        lines.append("")
        for c in commits_list:
            lines.append(f"- {c}")
        lines.append("")

    if files_list:
        lines.append("## Betroffene Dateien (außerhalb Doku-Scope)")
        lines.append("")
        for f in files_list:
            lines.append(f"- `{f}`")
        lines.append("")

    if repo_doc_paths:
        lines.append("## Konfigurierte Doku-Pfade (repo_doc_paths)")
        lines.append("")
        for p in repo_doc_paths:
            lines.append(f"- `{p}`")
        lines.append("")

    lines.append("## Aufgabe an Luke")
    lines.append("")
    lines.append(
        "Aktualisiere die Projektdokumentation passend zu den genannten Code-/Funktionsänderungen. "
        "Prüfe mindestens CHANGELOG und RUNBOOK. "
        "README nur ändern, wenn ein bestehender Übersichtsabschnitt betroffen ist."
    )
    lines.append("")

    lines.append("## Sicherheitsnotiz")
    lines.append("")
    lines.append("Keine .env-Dateien ändern. Keine Secrets ausgeben.")
    lines.append("")

    content = "\n".join(lines) + "\n"

    try:
        filepath.write_text(content, encoding="utf-8")
        return "TASK_CREATED", str(filepath)
    except Exception as e:
        return "TASK_ERROR", str(e)


def doc_impact_check(proj: dict) -> dict:
    """
    Prüft ob seit dem letzten Doku-Commit Code-Änderungen erfolgten,
    die keine Doku-Änderungen sind.

    Returns dict mit:
      state: DOC_OK, DOC_REQUIRED, DOC_UNKNOWN, ERROR
      details: list[str]
      files: list[str]  # betroffene non-doc Dateien (max 10)
      commits: list[str] # betroffene commits (max 5)
      last_doc_hash: str | None
    """
    name = proj.get("name", proj.get("path", "unknown"))
    doc_cfg = proj.get("documentation", {})
    path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)

    if not doc_cfg.get("enabled"):
        return {"state": "SKIP", "details": ["  documentation nicht aktiv"], "files": [], "commits": [], "last_doc_hash": None}
    if not doc_cfg.get("doc_required_for_code_changes"):
        return {"state": "SKIP", "details": ["  doc_required_for_code_changes=false"], "files": [], "commits": [], "last_doc_hash": None}

    repo_doc_paths = doc_cfg.get("repo_doc_paths", [])
    details = []
    affected_files = []
    affected_commits = []
    last_doc_hash = None

    # 1. Letzten Doku-Commit ermitteln
    doc_paths_str = " ".join(shlex_quote(p) for p in repo_doc_paths)
    rc, last_doc_hash, _ = run_cmd(
        f"git log -1 --format=%H -- {doc_paths_str}",
        workdir=path, ssh_alias=ssh_alias
    )

    if rc != 0 or not last_doc_hash:
        details.append(f"  Kein Doku-Commit gefunden")
        return {"state": "DOC_UNKNOWN", "details": details, "files": [], "commits": [], "last_doc_hash": None}

    last_doc_hash_value = last_doc_hash
    details.append(f"  Letzter Doku-Commit: {last_doc_hash_value[:10]}")

    # 2. Änderungen seit letztem Doku-Commit bis HEAD
    rc, changed_files, _ = run_cmd(
        f"git diff --name-only {last_doc_hash} HEAD",
        workdir=path, ssh_alias=ssh_alias
    )

    if rc != 0:
        details.append(f"  ERROR: git diff fehlgeschlagen")
        return {"state": "ERROR", "details": details, "files": [], "commits": [], "last_doc_hash": last_doc_hash_value}

    if not changed_files:
        return {"state": "DOC_OK", "details": details + ["  Keine Änderungen seit letztem Doku-Commit"], "files": [], "commits": [], "last_doc_hash": last_doc_hash_value}

    # 3. Non-Doc-Dateien filtern
    # repo_doc_paths können sowohl "file.md" als auch "dir/" sein
    def is_doc_file(fpath: str) -> bool:
        for dp in repo_doc_paths:
            if dp.endswith("/"):
                if fpath == dp.rstrip("/") or fpath.startswith(dp):
                    return True
            else:
                if fpath == dp:
                    return True
        return False

    non_doc = [f for f in changed_files.splitlines() if f and not is_doc_file(f)]

    if not non_doc:
        details.append(f"  {len(changed_files.splitlines())} Dateien geändert, aber alle im Doku-Scope")
        return {"state": "DOC_OK", "details": details, "files": [], "commits": [], "last_doc_hash": last_doc_hash_value}

    # 4. Betroffene Commits ermitteln
    # Commits zwischen last_doc_hash und HEAD die non-doc Dateien berührt haben
    non_doc_quoted = " ".join(shlex_quote(f) for f in non_doc)
    rc, commits_raw, _ = run_cmd(
        f"git log --format=%h\\ %s {last_doc_hash}..HEAD -- {non_doc_quoted}",
        workdir=path, ssh_alias=ssh_alias
    )

    if rc == 0 and commits_raw:
        affected_commits = commits_raw.strip().splitlines()[:5]

    affected_files = non_doc[:10]

    details.append(f"  DOC_REQUIRED: {len(non_doc)} Datei(en) außerhalb Doku-Scope geändert")
    details.append(f"  Commits seit letztem Doku-Commit ({last_doc_hash[:10]}):")
    for c in affected_commits:
        details.append(f"    {c}")

    return {
        "state": "DOC_REQUIRED",
        "details": details,
        "files": [f for f in non_doc[:20]],
        "commits": affected_commits,
        "last_doc_hash": last_doc_hash_value,
        "repo_doc_paths": repo_doc_paths
    }


def write_monthly_guard_log(proj: dict, check_result: dict, sync_result: list[str]) -> tuple[str, str]:
    """
    Schreibt eine Markdown-Guard-Ausgabe in den Monatsordner:
    <local_documentation_path>/<YYYY-MM>/guard-YYYY-MM-DD-HHMMSS.md

    Returns (state, filepath)
    """
    name = proj.get("name", proj.get("path", "unknown"))
    doc_cfg = proj.get("documentation", {})

    if not doc_cfg.get("enabled"):
        return "SKIP_LOG", ""

    local_base = doc_cfg.get("local_documentation_path", "")
    monthly_format = doc_cfg.get("monthly_subdir_format", "%Y-%m")

    if not local_base:
        return "SKIP_LOG", ""

    monthly_dir = Path(local_base) / datetime.now().strftime(monthly_format)
    monthly_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"guard-{timestamp}.md"
    filepath = monthly_dir / filename

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = check_result.get("state", "UNKNOWN")
    files_list = check_result.get("files", [])
    commits_list = check_result.get("commits", [])
    details = check_result.get("details", [])

    # Branch ermitteln
    path = proj.get("path")
    ssh_alias = proj.get("ssh_alias", None)
    rc, branch, _ = run_cmd("git rev-parse --abbrev-ref HEAD", workdir=path, ssh_alias=ssh_alias)
    branch_info = branch if rc == 0 else "(unbekannt)"

    lines = []
    lines.append(f"# Documentation Guard – {name}")
    lines.append(f"")
    lines.append(f"**Timestamp:** {now_str}")
    lines.append(f"**Projekt:** {name}")
    lines.append(f"**Branch:** {branch_info}")
    lines.append(f"**Ergebnis:** {state}")
    lines.append(f"")

    # Detail-Zeilen aus dem Check
    if details:
        lines.append("## Details")
        lines.append("")
        for d in details:
            lines.append(d.strip())
        lines.append("")

    # Betroffene Dateien
    if files_list:
        lines.append("## Betroffene Dateien (außerhalb Doku-Scope)")
        lines.append("")
        for f in files_list:
            lines.append(f"- `{f}`")
        lines.append("")

    # Betroffene Commits
    if commits_list:
        lines.append("## Betroffene Commits")
        lines.append("")
        for c in commits_list:
            lines.append(f"- {c}")
        lines.append("")

    # Doc-Sync Status
    if sync_result:
        sync_state = sync_result[0] if sync_result else "N/A"
        lines.append(f"## Doc-Sync")
        lines.append("")
        lines.append(f"**Status:** {sync_state}")
        lines.append("")

    content = "\n".join(lines) + "\n"

    try:
        filepath.write_text(content, encoding="utf-8")
        return "LOG_OK", str(filepath)
    except Exception as e:
        return "LOG_ERROR", str(e)


def run_doc_impact_check(config_path: str):
    config = load_config(config_path)
    projects = config.get("projects", [])
    print(f"Doc-Impact-Check (--doc-impact-check)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 42)

    ok_count = 0
    required_count = 0
    unknown_count = 0
    error_count = 0
    skipped = 0

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))

        # Doc-Impact-Check
        result = doc_impact_check(proj)
        state = result["state"]
        details = result["details"]
        files = result["files"]

        print(f"\n{name}: {state}")
        for d in details:
            print(d)

        if files:
            print(f"  Dateien (max 10):")
            for f in files[:10]:
                print(f"    {f}")

        # Doc-Sync parallel ausführen für vollständigen Guard-Log
        sync_result = sync_doc_current(proj)

        # Monats-Guard-Ausgabe schreiben
        log_state, log_path = write_monthly_guard_log(proj, result, sync_result)
        if log_state == "LOG_OK":
            print(f"  Guard-Log: {log_path}")

        # Doku-Auftrag schreiben bei DOC_REQUIRED oder DOC_UNKNOWN
        task_state, task_path = write_doc_task(proj, result)
        if task_state in ("TASK_CREATED", "TASK_ERROR"):
            print(f"  Doku-Auftrag: {task_path if task_state == 'TASK_CREATED' else task_path}")

        # Summary
        if state == "DOC_OK":
            ok_count += 1
        elif state == "DOC_REQUIRED":
            required_count += 1
        elif state == "DOC_UNKNOWN":
            unknown_count += 1
        elif state == "ERROR":
            error_count += 1
        else:
            skipped += 1

    print(f"\n{'=' * 42}")
    print("Impact-Check Zusammenfassung:")
    print(f"  Doku aktuell (DOC_OK): {ok_count}")
    print(f"  Doku erforderlich (DOC_REQUIRED): {required_count}")
    print(f"  Unbekannt (DOC_UNKNOWN): {unknown_count}")
    print(f"  Fehler: {error_count}")
    print(f"  Übersprungen: {skipped}")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def run_sync_doc_current(config_path: str):
    config = load_config(config_path)
    projects = config.get("projects", [])
    print(f"Doc-Current-Sync (--sync-doc-current)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 42)

    updated = 0
    ok = 0
    skipped = 0
    errors = 0
    warns = 0

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))

        # Erst sync, dann Monatsordner
        result = sync_doc_current(proj)
        state = result[0]
        detail = result[1:]

        print(f"\n{name} (Doc-Sync): {state}")
        for line in detail:
            print(line)

        if state == "DOC_SYNC_UPDATED":
            updated += 1
        elif state == "DOC_SYNC_OK":
            ok += 1
        elif state in ("DOC_SYNC_SKIP", "DOC_SKIP"):
            skipped += 1
        elif state == "DOC_SYNC_WARN":
            warns += 1
        else:
            errors += 1

        # Monatsordner vorbereiten
        monthly_result = prepare_monthly_folders(proj)
        m_state = monthly_result[0]
        m_detail = monthly_result[1:]
        if m_state not in ("MONTHLY_SKIP",):
            print(f"\n{name} (Monatsordner): {m_state}")
            for line in m_detail:
                print(line)

    print(f"\n{'=' * 42}")
    print("Sync-Zusammenfassung:")
    print(f"  Aktualisiert: {updated}")
    print(f"  Bereits aktuell: {ok}")
    print(f"  Warnungen: {warns}")
    print(f"  Fehler: {errors}")
    print(f"  Übersprungen: {skipped}")


def run_check(config_path: str):
    config = load_config(config_path)
    projects = config.get("projects", [])
    forbidden_patterns = config.get("global", {}).get("forbidden_patterns", [])
    defaults = config.get("global", {}).get("defaults", {})

    print(f"Project Guard (Check-Modus)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 42)

    summary = {"OK": 0, "DIRTY": 0, "AHEAD": 0, "BEHIND": 0, "DIVERGED": 0,
               "MIRROR_OUTDATED": 0, "MIRROR_OK": 0, "ERROR": 0, "SKIP": 0}

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))
        result = check_project(proj, forbidden_patterns, defaults)
        state = result[0]
        detail = result[1:]
        summary[state] = summary.get(state, 0) + 1

        print(f"\n{name}: {state}")
        for line in detail[:5]:
            print(line)

    print(f"\n{'=' * 42}")
    print("Zusammenfassung:")
    for state, count in summary.items():
        if count > 0:
            print(f"  {state}: {count}")


def run_sync(config_path: str):
    config = load_config(config_path)
    projects = config.get("projects", [])
    print(f"Project Guard Stufe 2 (Doc-Mirror-Sync)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 42)

    sync_count = 0
    error_count = 0
    ok_count = 0

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))
        mirror = proj.get("mirror", {})

        if not mirror.get("enabled"):
            print(f"\n{name}: SKIP (mirror nicht aktiv)")
            continue

        result = sync_doc_mirror(proj)
        state = result[0]
        detail = result[1:]

        print(f"\n{name}: {state}")
        for line in detail:
            print(line)

        if state == "SYNC_OK":
            sync_count += 1
        elif state == "MIRROR_OK":
            ok_count += 1
        else:
            error_count += 1

    print(f"\n{'=' * 42}")
    print("Sync-Zusammenfassung:")
    print(f"  Aktualisiert: {sync_count}")
    print(f"  Bereits aktuell: {ok_count}")
    print(f"  Fehler / Abbruch: {error_count}")


def run_auto_doc_commit(config_path: str):
    config = load_config(config_path)
    projects = config.get("projects", [])
    forbidden_patterns = config.get("global", {}).get("forbidden_patterns", [])
    defaults = config.get("global", {}).get("defaults", {})

    print(f"Project Guard Stufe 3 (Auto-Doc-Commit)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 42)

    committed = 0
    error_count = 0
    ok_count = 0
    skip_count = 0
    pushed = 0

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))
        result = auto_doc_commit(proj, forbidden_patterns, defaults)
        state = result[0]
        detail = result[1:]

        print(f"\n{name}: {state}")
        for line in detail:
            print(line)

        if state in ("COMMITTED",):
            committed += 1
            if any("Push" in l and "OK" in l for l in detail):
                pushed += 1
        elif state in ("OK", "PUSHED"):
            ok_count += 1
        elif state == "SKIP":
            skip_count += 1
        else:
            error_count += 1

    print(f"\n{'=' * 42}")
    print("Auto-Doc-Commit Zusammenfassung:")
    print(f"  Sauber / OK: {ok_count}")
    print(f"  Committed: {committed}")
    print(f"  Gepusht: {pushed}")
    print(f"  Übersprungen: {skip_count}")
    print(f"  Fehler / Blockiert: {error_count}")


# ──────────────────────────────────────────────
# Stufe DG-3: Guard-Full (--guard-full)
# ──────────────────────────────────────────────

def run_guard_full(config_path: str):
    """
    Kombinierter Vollmodus:
    1. Check (--check)
    2. Auto-Doc-Commit (--auto-doc-commit)
    3. Doc-Impact-Check + Guard-Log + Doc-Task
    4. Doc-Current-Sync + Monatsordner
    """
    config = load_config(config_path)
    projects = config.get("projects", [])
    forbidden_patterns = config.get("global", {}).get("forbidden_patterns", [])
    defaults = config.get("global", {}).get("defaults", {})

    print(f"Documentation Guard – Vollmodus (--guard-full)")
    print(f"Projekte: {len(projects)} | Konfiguration: {config_path}")
    print("=" * 50)

    guard_log_paths = []
    task_log_paths = []

    for proj in projects:
        name = proj.get("name", proj.get("path", "unknown"))
        print(f"\n{'=' * 50}")
        print(f"Projekt: {name}")
        print(f"{'=' * 50}")

        # Phase 1: Check
        result = check_project(proj, forbidden_patterns, defaults)
        check_state = result[0]
        check_details = result[1:]
        print(f"\n  [Check]: {check_state}")
        for line in check_details[:5]:
            print(f"    {line}")
        if len(check_details) > 5:
            print(f"    ... +{len(check_details) - 5} Zeilen")

        # Phase 2: Auto-Doc-Commit
        auto_doc = proj.get("auto_doc", {})
        if auto_doc.get("enabled"):
            adc_result = auto_doc_commit(proj, forbidden_patterns, defaults)
            adc_state = adc_result[0]
            adc_details = adc_result[1:]
            print(f"\n  [Auto-Doc]: {adc_state}")
            for line in adc_details[:3]:
                print(f"    {line}")
            if len(adc_details) > 3:
                print(f"    ... +{len(adc_details) - 3} Zeilen")
        else:
            adc_state = "DISABLED"
            print(f"\n  [Auto-Doc]: DISABLED")

        # Check auf Non-Doc-Änderungen: wenn dirty mit Code-Dateien → kein Doc-Commit
        # (auto_doc_commit macht das bereits intern via DIRTY_NON_DOC)

        # Phase 3: Doc-Impact-Check
        impact_result = doc_impact_check(proj)
        impact_state = impact_result["state"]
        impact_details = impact_result["details"]
        impact_files = impact_result["files"]
        impact_commits = impact_result["commits"]

        print(f"\n  [Doc-Impact]: {impact_state}")
        for d in impact_details[:5]:
            print(f"    {d}")
        if impact_files:
            print(f"    Betroffene Dateien ({min(len(impact_files), 20)}):")
            for f in impact_files[:20]:
                print(f"      {f}")
        if impact_commits:
            print(f"    Betroffene Commits:")
            for c in impact_commits:
                print(f"      {c}")

        # Phase 4: Doc-Current-Sync
        sync_result = sync_doc_current(proj)
        sync_state = sync_result[0]
        sync_details = sync_result[1:]

        print(f"\n  [Doc-Sync]: {sync_state}")
        for line in sync_details[:3]:
            print(f"    {line}")

        # Phase 5: Monatliche Ordner + Guard-Log schreiben
        monthly_result = prepare_monthly_folders(proj)
        log_state, log_path = write_monthly_guard_log(proj, impact_result, sync_result)
        if log_state == "LOG_OK":
            print(f"\n  [Guard-Log]: {log_path}")
            guard_log_paths.append(log_path)

        # Phase 6: Doc-Task bei DOC_REQUIRED/DOC_UNKNOWN
        task_state_out, task_path = write_doc_task(proj, impact_result)
        if task_state_out == "TASK_CREATED":
            print(f"  [Doc-Task]: {task_path}")
            task_log_paths.append(task_path)
        elif task_state_out == "TASK_ERROR":
            print(f"  [Doc-Task] FEHLER: {task_path}")

    # Gesamtzusammenfassung
    print(f"\n{'=' * 50}")
    print("Gesamtzusammenfassung")
    print(f"{'=' * 50}")
    print(f"  Guard-Logs: {len(guard_log_paths)}")
    for gp in guard_log_paths:
        print(f"    {gp}")
    if task_log_paths:
        print(f"  Doc-Tasks: {len(task_log_paths)}")
        for tp in task_log_paths:
            print(f"    {tp}")
    else:
        print(f"  Doc-Tasks: keine (keine Doku-Schuld)")


def main():
    parser = argparse.ArgumentParser(description="Project Guard – Git-Status-Checker & Doc-Mirror-Sync")
    parser.add_argument("--config", default=str(Path.home() / ".config/project_guard/projects.yaml"),
                        help="Pfad zur projects.yaml")
    parser.add_argument("--check", action="store_true", help="Check-Modus ausführen")
    parser.add_argument("--sync-doc-mirror", action="store_true", help="Doc-Mirror synchronisieren (Stufe 2)")
    parser.add_argument("--auto-doc-commit", action="store_true", help="Auto-Doc-Commit (Stufe 3)")
    parser.add_argument("--sync-doc-current", action="store_true", help="Doc-Current-Sync (Stufe 4a) + Monatsordner (Stufe 4b)")
    parser.add_argument("--doc-impact-check", action="store_true", help="Doc-Impact-Check (Stufe 1c) + Monats-Guard-Log")
    parser.add_argument("--guard-full", action="store_true", help="Vollmodus: Check + Auto-Doc + Impact + Sync + Guard-Log")
    args = parser.parse_args()

    if not args.check and not args.sync_doc_mirror and not args.auto_doc_commit and not args.sync_doc_current and not args.doc_impact_check and not args.guard_full:
        print("Verwende: project_guard.py --check  ODER  --sync-doc-mirror  ODER  --auto-doc-commit")
        sys.exit(1)

    if args.guard_full:
        run_guard_full(args.config)

    if args.sync_doc_current:
        run_sync_doc_current(args.config)

    if args.doc_impact_check:
        run_doc_impact_check(args.config)

    if args.check:
        run_check(args.config)

    if args.sync_doc_mirror:
        run_sync(args.config)

    if args.auto_doc_commit:
        run_auto_doc_commit(args.config)


if __name__ == "__main__":
    main()
