#!/usr/bin/env python3
"""Cost and token usage summary tool.

Reads run manifests from data/traces/*_manifest.json and produces aggregate
cost/token reports. Each manifest row maps 1-to-1 with a cost_events DB row
(see tools/cost_events.sql); at production this tool queries the DB instead.

Usage:
    PYTHONPATH=. .venv/bin/python3 tools/cost_summary.py
    PYTHONPATH=. .venv/bin/python3 tools/cost_summary.py --since 2026-01-01
    PYTHONPATH=. .venv/bin/python3 tools/cost_summary.py --group-by month
    PYTHONPATH=. .venv/bin/python3 tools/cost_summary.py --group-by source
    PYTHONPATH=. .venv/bin/python3 tools/cost_summary.py --group-by voice_provider
"""
import argparse
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from core.config import DATA_DIR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Manifest loading + schema mapping
# ---------------------------------------------------------------------------

def _load_manifests() -> list[dict]:
    traces_dir = DATA_DIR / "traces"
    manifests = []
    for path in sorted(traces_dir.glob("*_manifest.json")):
        try:
            with open(path) as f:
                manifests.append(json.load(f))
        except Exception as exc:
            logger.warning("Could not load manifest %s: %s", path.name, exc)
    return manifests


def _manifest_to_event(m: dict) -> dict:
    """Map a manifest dict to a flat event dict matching the cost_events schema."""
    params = m.get("parameters") or {}
    tokens = m.get("tokens") or {}
    costs = m.get("costs_usd") or {}
    tts = m.get("tts") or {}
    timings = m.get("stage_timings_seconds") or {}

    created_at_str = m.get("created_at", "")
    try:
        created_at = datetime.fromisoformat(created_at_str)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        created_at = None

    return {
        "episode_id":              m.get("episode_id", ""),
        "user_id":                 m.get("user_id"),
        "created_at":              created_at,
        "topic":                   params.get("topic"),
        "source":                  params.get("source"),
        "expertise_level":         params.get("expertise_level"),
        "max_papers":              params.get("max_papers"),
        "anchor_paper":            ",".join(params.get("anchor_papers") or []) or params.get("anchor_paper"),
        "tokens_input":            tokens.get("input", 0),
        "tokens_output":           tokens.get("output", 0),
        "cost_claude_input":       costs.get("claude_input", 0.0),
        "cost_claude_output":      costs.get("claude_output", 0.0),
        "cost_claude":             costs.get("claude_total", 0.0),
        "cost_tts":                costs.get("tts", 0.0),
        "cost_total":              costs.get("total", 0.0),
        "tts_provider_requested":  tts.get("provider_requested") or params.get("voice_provider_requested"),
        "tts_provider_used":       tts.get("provider_used"),
        "tts_fallback_occurred":   tts.get("fallback_occurred", False),
        "tts_characters":          tts.get("characters", 0),
        "runtime_seconds":         m.get("stage_timings_seconds_total"),
        "trace_reasoning":         m.get("trace_reasoning", False),
        "commercial_mode":         m.get("commercial_mode", False),
        "warnings":                m.get("warnings", []),
    }


def build_events(manifests: list[dict], since: date | None) -> list[dict]:
    events = []
    for m in manifests:
        ev = _manifest_to_event(m)
        if since and ev["created_at"] and ev["created_at"].date() < since:
            continue
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _agg(events: list[dict]) -> dict:
    """Compute aggregate totals over a list of events."""
    n = len(events)
    if n == 0:
        return {
            "episode_count": 0,
            "tokens_input": 0, "tokens_output": 0,
            "cost_claude": 0.0, "cost_tts": 0.0, "cost_total": 0.0,
            "avg_cost_total": 0.0, "tts_characters": 0,
            "fallback_count": 0,
        }
    return {
        "episode_count":   n,
        "tokens_input":    sum(e["tokens_input"] for e in events),
        "tokens_output":   sum(e["tokens_output"] for e in events),
        "cost_claude":     sum(e["cost_claude"] for e in events),
        "cost_tts":        sum(e["cost_tts"] for e in events),
        "cost_total":      sum(e["cost_total"] for e in events),
        "avg_cost_total":  sum(e["cost_total"] for e in events) / n,
        "tts_characters":  sum(e["tts_characters"] for e in events),
        "fallback_count":  sum(1 for e in events if e["tts_fallback_occurred"]),
    }


def _group_key(event: dict, group_by: str) -> str:
    if group_by == "month":
        dt = event.get("created_at")
        return dt.strftime("%Y-%m") if dt else "unknown"
    if group_by == "source":
        return event.get("source") or "unknown"
    if group_by == "voice_provider":
        return event.get("tts_provider_used") or "unknown"
    return "all"


def summarize(events: list[dict], group_by: str | None) -> dict:
    totals = _agg(events)

    grouped: dict[str, dict] = {}
    if group_by:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for ev in events:
            buckets[_group_key(ev, group_by)].append(ev)
        for key in sorted(buckets):
            grouped[key] = _agg(buckets[key])

    return {"totals": totals, "grouped": grouped, "group_by": group_by}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _cost_row(label: str, agg: dict, show_avg: bool = False) -> list[str]:
    avg = f"  avg/ep ${agg['avg_cost_total']:.4f}" if show_avg and agg["episode_count"] else ""
    fallback = f"  ({agg['fallback_count']} fallback)" if agg.get("fallback_count") else ""
    return [
        f"  {label:<22}  "
        f"eps {agg['episode_count']:>4}  "
        f"tok {agg['tokens_input']:>8,}in {agg['tokens_output']:>7,}out  "
        f"claude ${agg['cost_claude']:>7.4f}  "
        f"tts ${agg['cost_tts']:>7.4f}  "
        f"total ${agg['cost_total']:>7.4f}"
        f"{avg}{fallback}"
    ]


def render_markdown(summary: dict, since: date | None, generated: date) -> str:
    totals = summary["totals"]
    grouped = summary["grouped"]
    group_by = summary["group_by"]

    lines = [
        "# PapersPod Cost Summary",
        "",
        f"Generated: {generated.isoformat()}",
    ]
    if since:
        lines.append(f"Period: {since.isoformat()} — {generated.isoformat()}")
    lines += [
        "",
        "## Totals",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Episodes | {totals['episode_count']} |",
        f"| Tokens in | {totals['tokens_input']:,} |",
        f"| Tokens out | {totals['tokens_output']:,} |",
        f"| Claude cost | ${totals['cost_claude']:.4f} |",
        f"| TTS cost | ${totals['cost_tts']:.4f} |",
        f"| **Total cost** | **${totals['cost_total']:.4f}** |",
        f"| Avg cost/episode | ${totals['avg_cost_total']:.4f} |",
        f"| TTS characters | {totals['tts_characters']:,} |",
        f"| TTS fallbacks | {totals['fallback_count']} |",
        "",
    ]

    if grouped:
        label = group_by.replace("_", " ").title()
        lines += [f"## By {label}", "", f"| {label} | Episodes | Tokens in | Tokens out | Claude | TTS | Total | Avg/ep |", "|---|---|---|---|---|---|---|---|"]
        for key, agg in grouped.items():
            lines.append(
                f"| {key} | {agg['episode_count']} | "
                f"{agg['tokens_input']:,} | {agg['tokens_output']:,} | "
                f"${agg['cost_claude']:.4f} | ${agg['cost_tts']:.4f} | "
                f"${agg['cost_total']:.4f} | ${agg['avg_cost_total']:.4f} |"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Summarize PapersPod cost and token usage.")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="Only include episodes on or after this date")
    parser.add_argument(
        "--group-by",
        choices=["month", "source", "voice_provider"],
        metavar="DIMENSION",
        help="Group breakdown by: month, source, voice_provider",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DATA_DIR / "reports"),
        metavar="PATH",
        help="Directory to write report files (default: data/reports/)",
    )
    parser.add_argument("--no-output", action="store_true", help="Print to stdout only, do not write files")
    args = parser.parse_args()

    since: date | None = None
    if args.since:
        try:
            since = date.fromisoformat(args.since)
        except ValueError:
            parser.error(f"Invalid date for --since: {args.since!r} (expected YYYY-MM-DD)")

    manifests = _load_manifests()
    events = build_events(manifests, since=since)

    if not events:
        msg = "No cost records found."
        if not manifests:
            msg += " No manifests in data/traces/ — run at least one episode first."
        elif since:
            msg += f" No episodes on or after {since.isoformat()}."
        print(msg)
        return

    summary = summarize(events, group_by=args.group_by)
    today = date.today()
    totals = summary["totals"]
    grouped = summary["grouped"]

    # Terminal output
    print()
    print(f"  PapersPod Cost Summary" + (f"  (since {since.isoformat()})" if since else ""))
    print(f"  {today.isoformat()}")
    print()
    print(f"  Episodes    : {totals['episode_count']}")
    print(f"  Tokens      : {totals['tokens_input']:,} in / {totals['tokens_output']:,} out")
    print(f"  Claude      : ${totals['cost_claude']:.4f}")
    print(f"  TTS         : ${totals['cost_tts']:.4f}  ({totals['tts_characters']:,} chars)")
    if totals["fallback_count"]:
        print(f"  TTS fallback: {totals['fallback_count']} episode(s)")
    print(f"  Total       : ${totals['cost_total']:.4f}")
    print(f"  Avg/episode : ${totals['avg_cost_total']:.4f}")

    if grouped:
        dim = (args.group_by or "").replace("_", " ")
        print()
        print(f"  Breakdown by {dim}:")
        print(f"  {'':22}  {'eps':>4}  {'tok-in':>8}  {'tok-out':>7}  {'claude':>8}  {'tts':>8}  {'total':>8}  {'avg/ep':>8}")
        print("  " + "-" * 86)
        for key, agg in grouped.items():
            print(
                f"  {key:<22}  {agg['episode_count']:>4}  "
                f"{agg['tokens_input']:>8,}  {agg['tokens_output']:>7,}  "
                f"${agg['cost_claude']:>7.4f}  ${agg['cost_tts']:>7.4f}  "
                f"${agg['cost_total']:>7.4f}  ${agg['avg_cost_total']:>7.4f}"
            )
    print()

    if args.no_output:
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_{args.group_by}" if args.group_by else ""
    json_path = output_dir / f"cost_summary_{today.isoformat()}{suffix}.json"
    md_path   = output_dir / f"cost_summary_{today.isoformat()}{suffix}.md"

    with open(json_path, "w") as f:
        json.dump(
            {
                "generated": today.isoformat(),
                "since": since.isoformat() if since else None,
                "group_by": args.group_by,
                "totals": totals,
                "grouped": grouped,
            },
            f, indent=2, default=str,
        )

    md_path.write_text(render_markdown(summary, since=since, generated=today), encoding="utf-8")

    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


if __name__ == "__main__":
    main()
