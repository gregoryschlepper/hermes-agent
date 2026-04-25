#!/usr/bin/env python3
"""luke_daily_cost_report.py — Kombinierter Tages-Kostenreport für Luke.

Liest Hermes-Rohlogs:
  - main_calls.jsonl     (Hauptchat: Qwen via OpenRouter)
  - auxiliary_calls.jsonl (Auxiliary: GLM-FlashX, Reviews, Background)

Erzeugt:
  - Terminal-Ausgabe
  - Markdown-Report: ~/.hermes/ops/reports/daily/luke_daily_cost_report_YYYY-MM-DD.md

Modus:
  --date YYYY-MM-DD   Datum (default: gestern)

Regeln:
  Nur lesend. Keine Logs ändern. Kein Netzwerk. Kein Git. Keine Secrets.
  Fehlende Dateien sind kein Fehler — mit vorhandenen Quellen rechnen.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Pfade ──
MAIN_LOG = Path.home() / ".hermes" / "logs" / "main_calls.jsonl"
AUX_LOG = Path.home() / ".hermes" / "logs" / "auxiliary_calls.jsonl"
DAILY_REPORT_DIR = Path.home() / ".hermes" / "ops" / "reports" / "daily"


def parse_date_arg(date_str: str | None) -> str:
    """Return YYYY-MM-DD für den Report-Tag."""
    if date_str:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def load_jsonl(log_file: Path) -> list[dict]:
    """Liest alle Records aus einer JSONL-Datei, überspringt fehlerhafte Zeilen."""
    if not log_file.exists():
        return []
    records = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def normalize_record(rec: dict, source: str) -> dict:
    """Normalisiert ein Record aus main oder aux auf ein gemeinsames Schema."""
    model = (
        rec.get("model")
        or rec.get("resolved_model")
        or rec.get("configured_model")
        or "unbekannt"
    )

    status = rec.get("status", "unknown")
    is_error = status in ("error", "failed") or rec.get("error_message") is not None

    return {
        "source": source,
        "source_mode": rec.get("source_mode", ""),
        "model": model,
        "is_error": is_error,
        "input_tokens": int(rec.get("input_tokens", 0) or 0),
        "output_tokens": int(rec.get("output_tokens", 0) or 0),
        "cache_read_tokens": int(rec.get("cache_read_tokens", 0) or 0),
        "cache_write_tokens": int(rec.get("cache_write_tokens", 0) or 0),
        "reasoning_tokens": int(rec.get("reasoning_tokens", 0) or 0),
        "total_tokens": int(rec.get("total_tokens", 0) or 0),
        "estimated_cost_usd": float(rec.get("estimated_cost_usd", 0) or 0),
    }


def filter_by_date(records: list[dict], target_date: str) -> list[dict]:
    """Filtert Records auf den Zieltag (UTC)."""
    filtered = []
    for rec in records:
        ts = rec.get("started_at", 0)
        if not ts:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        if dt.strftime("%Y-%m-%d") == target_date:
            filtered.append(rec)
    return filtered


def aggregate(records: list[dict]) -> dict:
    """Gruppiert nach (source, model), summiert Werte."""
    groups = defaultdict(lambda: {
        "source": "",
        "model": "",
        "calls": 0,
        "error_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    })

    for rec in records:
        key = (rec["source"], rec["model"])
        agg = groups[key]
        agg["source"] = rec["source"]
        agg["model"] = rec["model"]
        agg["calls"] += 1
        if rec["is_error"]:
            agg["error_calls"] += 1
        agg["input_tokens"] += rec["input_tokens"]
        agg["output_tokens"] += rec["output_tokens"]
        agg["cache_read_tokens"] += rec["cache_read_tokens"]
        agg["cache_write_tokens"] += rec["cache_write_tokens"]
        agg["reasoning_tokens"] += rec["reasoning_tokens"]
        agg["total_tokens"] += rec["total_tokens"]
        agg["estimated_cost_usd"] += rec["estimated_cost_usd"]

    return dict(groups)


def calc_cache_hit_ratio(agg: dict) -> float:
    """cache_read_tokens / (input_tokens + cache_read_tokens) * 100"""
    denom = agg["input_tokens"] + agg["cache_read_tokens"]
    if denom == 0:
        return 0.0
    return (agg["cache_read_tokens"] / denom) * 100


def fmt_num(n: int) -> str:
    """Zahl mit Tausender-Trennzeichen."""
    return f"{n:,}"


def build_report(date_str: str, groups: dict, main_missing: bool, aux_missing: bool) -> str:
    """Baut Terminal- und Markdown-Report."""
    lines = []
    lines.append(f"📊 Luke API-Kosten-Report — {date_str}")
    lines.append("")

    if main_missing:
        lines.append("⚠ main_calls.jsonl nicht vorhanden — Hauptchat-Daten fehlen komplett")
        lines.append("")
    if aux_missing:
        lines.append("⚠ auxiliary_calls.jsonl nicht vorhanden — Auxiliary-Daten fehlen vollständig")
        lines.append("")

    if not groups:
        lines.append("Keine Daten für diesen Tag.")
        return "\n".join(lines)

    # Sortieren: zuerst main, dann auxiliary; innerhalb je Modellalphabetisch
    sorted_keys = sorted(groups.keys(), key=lambda k: (0 if k[0] == "main" else 1, k[1]))

    # Spaltenbreiten berechnen
    header = "Quelle/Modell            Calls  Errors   Input Token   Output Token   Cached Read  Cache-Hit   Kosten ($)"
    col_w = [26, 7, 7, 14, 14, 13, 11, 10]

    def row(source_short: str, model_short: str, calls: int, errors: int,
            inp: int, out: int, cached: int, ratio: float, cost: float) -> str:
        label = f"{source_short} {model_short}"
        if len(label) > 24:
            label = label[:22] + ".."
        return (f"{label:<24s} {calls:>5d}  {errors:>5d}  {fmt_num(inp):>12s}  "
                f"{fmt_num(out):>12s}  {fmt_num(cached):>11s}  {ratio:>5.1f} %  {cost:>9.6f}")

    lines.append(header)
    lines.append("=" * len(header))

    total_calls = 0
    total_errors = 0
    total_inp = 0
    total_out = 0
    total_cached = 0
    total_cost = 0.0

    for key in sorted_keys:
        agg = groups[key]
        source_short = "main" if key[0] == "main" else "aux"
        model_short = agg["model"]

        ratio = calc_cache_hit_ratio(agg)

        lines.append(row(source_short, model_short,
                         agg["calls"], agg["error_calls"],
                         agg["input_tokens"], agg["output_tokens"],
                         agg["cache_read_tokens"], ratio,
                         agg["estimated_cost_usd"]))

        total_calls += agg["calls"]
        total_errors += agg["error_calls"]
        total_inp += agg["input_tokens"]
        total_out += agg["output_tokens"]
        total_cached += agg["cache_read_tokens"]
        total_cost += agg["estimated_cost_usd"]

    lines.append("-" * len(header))
    total_ratio = calc_cache_hit_ratio({
        "input_tokens": total_inp,
        "cache_read_tokens": total_cached,
    })
    lines.append(row("Gesamt", "", total_calls, total_errors,
                     total_inp, total_out, total_cached, total_ratio, total_cost))

    return "\n".join(lines)


def save_markdown(date_str: str, report_text: str, report_dir: Path) -> Path:
    """Speichert den Report als Markdown im angegebenen Verzeichnis."""
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"luke_daily_cost_report_{date_str}.md"
    md_lines = [
        f"# Luke API-Kosten-Report — {date_str}",
        "",
        "```",
        report_text,
        "```",
        ""
    ]
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    return report_file


def save_extra_report(date_str: str, report_text: str, extra_dir: Path) -> Path | None:
    """Speichert den Report zusätzlich unter extra_dir/YYYY-MM/.

    Bei Fehler: Warnung auf stderr, None zurückgeben.
    """
    try:
        month_str = date_str[:7]  # "2026-04"
        month_dir = extra_dir / month_str
        return save_markdown(date_str, report_text, month_dir)
    except Exception as e:
        print(f"Warnung: Extra-Ausgabe fehlgeschlagen: {e}", file=sys.stderr)
        print(f"  Standardreport wurde trotzdem geschrieben.", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Luke Tages-Kosten-Report (kombiniert)")
    parser.add_argument("--date", type=str, default=None,
                        help="Datum YYYY-MM-DD (default: gestern)")
    parser.add_argument("--extra-output-dir", type=str, default=None,
                        help="Zusätzlicher Ausgabepfad. Report wird zusätzlich nach "
                             "<PATH>/YYYY-MM/ gespeichert.")
    args = parser.parse_args()

    target_date = parse_date_arg(args.date)

    # Daten laden
    main_records = load_jsonl(MAIN_LOG)
    aux_records = load_jsonl(AUX_LOG)

    main_missing = not main_records
    aux_missing = not aux_records

    # Auf Datum filtern
    main_day = filter_by_date(main_records, target_date)
    aux_day = filter_by_date(aux_records, target_date)

    # Anzeigename für die Quelle
    for r in main_day:
        r["source"] = "main"
    for r in aux_day:
        r["source"] = "aux"

    # Normalisieren
    all_normalized = []
    for r in main_day:
        all_normalized.append(normalize_record(r, "main"))
    for r in aux_day:
        all_normalized.append(normalize_record(r, "aux"))

    if not all_normalized:
        print(f"Keine Daten für {target_date}")
        return 0

    # Aggregieren
    groups = aggregate(all_normalized)

    # Report bauen
    report = build_report(target_date, groups, main_missing, aux_missing)

    print(report)
    print()
    report_file = save_markdown(target_date, report, DAILY_REPORT_DIR)
    print(f"Markdown-Report gespeichert: {report_file}")

    # Zusätzliche Business/Ausgabe-Ablage falls gesetzt
    if args.extra_output_dir:
        extra_path = save_extra_report(target_date, report, Path(args.extra_output_dir))
        if extra_path:
            print(f"Zusätzliche Ausgabe gespeichert: {extra_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
