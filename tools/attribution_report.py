#!/usr/bin/env python3
"""Attribution reporting tool.

Scans fetch traces and paper records to produce a per-source attribution report.
Outputs machine-readable JSON and a human-readable Markdown summary.

Primary data: data/traces/*_fetch.json (episodes run after session 9 observability build).
Fallback: data/papers/{episode_id}.json for older episodes without fetch traces.

Usage:
    PYTHONPATH=. .venv/bin/python3 tools/attribution_report.py [--since YYYY-MM-DD] [--output-dir PATH]
"""
import argparse
import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from core.config import DATA_DIR

logger = logging.getLogger(__name__)

_EPISODE_ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}")


def _infer_source(arxiv_id: str) -> str:
    """Best-effort source inference from arxiv_id prefix (used for pre-trace episodes)."""
    if _ARXIV_ID_RE.match(arxiv_id):
        return "arxiv"
    if arxiv_id.startswith("s2:"):
        return "semantic_scholar"
    if arxiv_id.startswith("W") and arxiv_id[1:].isdigit():
        return "openalex"
    if arxiv_id.startswith("doi:"):
        return "doi-based"
    return "unknown"


def _episode_date_from_id(episode_id: str) -> date | None:
    m = _EPISODE_ID_RE.match(episode_id)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _source_label(source: str) -> str:
    return {
        "arxiv": "arXiv",
        "openalex": "OpenAlex",
        "crossref": "Crossref",
        "plos": "PLOS",
        "springer": "Springer Nature",
        "ieee": "IEEE Xplore",
        "semantic_scholar": "Semantic Scholar",
        "doi-based": "DOI-based (source unknown)",
        "unknown": "Unknown",
    }.get(source.lower(), source)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_fetch_traces() -> list[dict]:
    traces_dir = DATA_DIR / "traces"
    traces = []
    for path in sorted(traces_dir.glob("*_fetch.json")):
        try:
            with open(path) as f:
                traces.append(json.load(f))
        except Exception as exc:
            logger.warning("Could not load trace %s: %s", path.name, exc)
    return traces


def _load_papers_for_episode(episode_id: str) -> dict[str, dict]:
    """Load papers JSON for an episode, keyed by arxiv_id."""
    path = DATA_DIR / "papers" / f"{episode_id}.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return {p["arxiv_id"]: p for p in json.load(f)}
    except Exception as exc:
        logger.warning("Could not load papers for %s: %s", episode_id, exc)
        return {}


def _episode_ids_without_traces(traced_episodes: set[str]) -> list[str]:
    """Return episode IDs that have a papers JSON but no fetch trace."""
    papers_dir = DATA_DIR / "papers"
    ids = []
    for path in sorted(papers_dir.glob("*.json")):
        name = path.stem
        # Skip _episode suffix files and .gitkeep
        if name.endswith("_episode") or name.startswith("."):
            continue
        # Skip anchor sidecar files
        if name.startswith("anchor_"):
            continue
        if name not in traced_episodes:
            ids.append(name)
    return ids


# ---------------------------------------------------------------------------
# Attribution record construction
# ---------------------------------------------------------------------------

def _record_from_paper(paper: dict, episode_id: str, source: str, episode_date: date | None) -> dict:
    return {
        "episode_id": episode_id,
        "episode_date": episode_date.isoformat() if episode_date else None,
        "source": source,
        "arxiv_id": paper.get("arxiv_id", ""),
        "doi": paper.get("doi"),
        "title": paper.get("title", ""),
        "license": paper.get("license"),
        "authors": paper.get("authors") or [],
    }


def build_records(traces: list[dict], since: date | None) -> list[dict]:
    """Build attribution records from all available data sources."""
    records: list[dict] = []
    traced_episode_ids: set[str] = set()

    # Primary path: fetch traces
    for trace in traces:
        episode_id = trace.get("episode_id", "")
        traced_episode_ids.add(episode_id)

        created_at_str = trace.get("created_at", "")
        try:
            episode_date = datetime.fromisoformat(created_at_str).date()
        except (ValueError, TypeError):
            episode_date = _episode_date_from_id(episode_id)

        if since and episode_date and episode_date < since:
            continue

        source = trace.get("source", "unknown")
        selected_ids = set(trace.get("selected_arxiv_ids") or [])
        papers_by_id = _load_papers_for_episode(episode_id)

        for arxiv_id in selected_ids:
            paper = papers_by_id.get(arxiv_id) or {"arxiv_id": arxiv_id}
            records.append(_record_from_paper(paper, episode_id, source, episode_date))

    # Fallback path: older episodes with no fetch trace
    for episode_id in _episode_ids_without_traces(traced_episode_ids):
        episode_date = _episode_date_from_id(episode_id)

        if since and episode_date and episode_date < since:
            continue

        papers_by_id = _load_papers_for_episode(episode_id)
        if not papers_by_id:
            continue

        for paper in papers_by_id.values():
            source = _infer_source(paper.get("arxiv_id", ""))
            records.append(_record_from_paper(paper, episode_id, source, episode_date))

    return records


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------

def summarize(records: list[dict]) -> dict[str, dict]:
    """Group records by source and compute summary statistics."""
    by_source: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_source[rec["source"]].append(rec)

    summary = {}
    for source, recs in sorted(by_source.items()):
        episodes = {r["episode_id"] for r in recs}
        license_counts: dict[str, int] = defaultdict(int)
        doi_count = 0
        for r in recs:
            license_counts[r["license"] or "unknown"] += 1
            if r.get("doi"):
                doi_count += 1

        summary[source] = {
            "source_label": _source_label(source),
            "episode_count": len(episodes),
            "paper_count": len(recs),
            "papers_with_doi": doi_count,
            "license_breakdown": dict(sorted(license_counts.items(), key=lambda x: -x[1])),
            "papers": sorted(recs, key=lambda r: r.get("episode_date") or ""),
        }

    return summary


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_markdown(summary: dict[str, dict], since: date | None, generated: date) -> str:
    all_episodes = {r["episode_id"] for data in summary.values() for r in data["papers"]}
    total_papers = sum(d["paper_count"] for d in summary.values())

    lines = [
        "# PapersPod Attribution Report",
        "",
        f"Generated: {generated.isoformat()}",
    ]
    if since:
        lines.append(f"Period: {since.isoformat()} — {generated.isoformat()}")
    lines += [
        "",
        "## Overview",
        "",
        f"- Total episodes: {len(all_episodes)}",
        f"- Total papers cited: {total_papers}",
        f"- Sources: {len(summary)}",
        "",
        "---",
        "",
    ]

    for source, data in summary.items():
        doi_note = f" ({data['papers_with_doi']} with DOI)" if data["papers_with_doi"] else ""
        lines += [
            f"## {data['source_label']}",
            "",
            f"- Episodes: {data['episode_count']}",
            f"- Papers cited: {data['paper_count']}{doi_note}",
        ]
        if data["license_breakdown"]:
            lines.append("- License breakdown:")
            for lic, count in data["license_breakdown"].items():
                lines.append(f"  - `{lic}`: {count}")
        lines += ["", "### Papers", ""]

        for rec in data["papers"]:
            title = rec["title"][:80] or rec["arxiv_id"]
            doi = rec.get("doi")
            doi_str = f" — [DOI: {doi}](https://doi.org/{doi})" if doi else ""
            lic = rec.get("license") or "unknown"
            lines.append(f"- **{title}**{doi_str}")
            lines.append(
                f"  Episode: `{rec['episode_id']}` | "
                f"Date: {rec.get('episode_date') or 'unknown'} | "
                f"License: `{lic}`"
            )
            lines.append("")

        lines += ["---", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Generate a PapersPod attribution report.")
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Only include episodes on or after this date",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DATA_DIR / "reports"),
        metavar="PATH",
        help="Directory to write report files (default: data/reports/)",
    )
    args = parser.parse_args()

    since: date | None = None
    if args.since:
        try:
            since = date.fromisoformat(args.since)
        except ValueError:
            parser.error(f"Invalid date for --since: {args.since!r} (expected YYYY-MM-DD)")

    traces = _load_fetch_traces()
    records = build_records(traces, since=since)

    if not records:
        print("No attribution records found. Run at least one episode first.")
        return

    summary = summarize(records)
    today = date.today()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"attribution_{today.isoformat()}.json"
    md_path = output_dir / f"attribution_{today.isoformat()}.md"

    with open(json_path, "w") as f:
        json.dump(
            {"generated": today.isoformat(), "since": since.isoformat() if since else None, "summary": summary},
            f, indent=2, default=str,
        )

    md_path.write_text(render_markdown(summary, since=since, generated=today), encoding="utf-8")

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print()
    print(f"{'Source':<25} {'Papers':>6}  {'Episodes':>8}  {'DOIs':>5}")
    print("-" * 50)
    for data in summary.values():
        print(
            f"{data['source_label']:<25} {data['paper_count']:>6}  "
            f"{data['episode_count']:>8}  {data['papers_with_doi']:>5}"
        )


if __name__ == "__main__":
    main()
