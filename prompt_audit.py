"""
WorkHive Weekly AI Visibility Prompt Audit
==========================================
Run this Mondays. Walks through each target query in prompt_audit_queries.json,
asks you whether ChatGPT, Perplexity, Gemini, and Claude cited WorkHive for
that query, and logs the result to prompt_audit_results/<YYYY-MM-DD>.csv.

After 4+ weeks of data you can plot the trend and see which AI engines are
discovering WorkHive first and which queries still need more off-site
authority signal.

Usage:
    python prompt_audit.py             # interactive run, all engines
    python prompt_audit.py --engine chatgpt   # only one engine
    python prompt_audit.py --resume    # resume mid-week if interrupted
    python prompt_audit.py --report    # trend report from prior weeks
"""
import json
import csv
import os
import sys
from datetime import datetime, date
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
QUERIES_FILE = ROOT / "prompt_audit_queries.json"
RESULTS_DIR = ROOT / "prompt_audit_results"
RESULTS_DIR.mkdir(exist_ok=True)

ENGINES = ["chatgpt", "perplexity", "gemini", "claude"]

# ANSI colors for terminal feedback
def bold(s): return f"\033[1m{s}\033[0m"
def green(s): return f"\033[92m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def red(s): return f"\033[91m{s}\033[0m"
def dim(s): return f"\033[2m{s}\033[0m"
def cyan(s): return f"\033[96m{s}\033[0m"


def load_queries():
    """Load target queries from JSON."""
    with open(QUERIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def today_csv_path():
    return RESULTS_DIR / f"{date.today().isoformat()}.csv"


def load_existing_results():
    """Resume support: load any rows already saved today."""
    path = today_csv_path()
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["query_id"], row["engine"])
            out[key] = row
    return out


def save_results(rows):
    """Write all rows for today's audit."""
    path = today_csv_path()
    fields = ["date", "query_id", "category", "query", "engine", "cited", "position", "notes"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def prompt_one_query(q, engine, prior=None):
    """Walk the user through one (query, engine) check."""
    print()
    print(cyan(f"  [{engine.upper()}]"))
    print(f"  Query: {bold(q['query'])}")
    print(dim(f"  Expected cite: {q['expected_cite']}"))
    print(dim(f"  Open {engine}, paste the query, then come back."))
    if prior:
        print(yellow(f"  (Already logged: cited={prior['cited']}, position={prior['position']})"))
        if input(dim("  Re-log? [y/N]: ")).strip().lower() != "y":
            return None

    cited = ""
    while cited not in ("y", "n", "p"):
        cited = input("  Was WorkHive cited?  y=yes  n=no  p=partial (mentioned, no link): ").strip().lower()

    position = ""
    if cited == "y":
        position = input("  Position in answer (1=first, 2=middle, 3=footer/sources, blank=skip): ").strip()

    notes = input(dim("  Notes (optional): ")).strip()

    return {
        "date": date.today().isoformat(),
        "query_id": q["id"],
        "category": q["category"],
        "query": q["query"],
        "engine": engine,
        "cited": cited,
        "position": position,
        "notes": notes,
    }


def run_audit(engine_filter=None, resume=False):
    """Interactive walk through every (query, engine) pair."""
    data = load_queries()
    queries = data["queries"]
    existing = load_existing_results() if resume else {}

    engines = [engine_filter] if engine_filter else ENGINES
    total_checks = len(queries) * len(engines)
    done = sum(1 for _ in existing.values())

    print(bold(f"\n  WorkHive AI Visibility Audit  ({date.today().isoformat()})"))
    print(f"  Queries: {len(queries)}  Engines: {', '.join(engines)}  Total checks: {total_checks}")
    if existing:
        print(yellow(f"  Resuming: {done} checks already logged today"))
    print()

    rows = list(existing.values())
    for i, q in enumerate(queries, 1):
        print(bold(f"\n  --- Query {i}/{len(queries)}: {q['id']} ({q['category']}) ---"))
        for engine in engines:
            key = (q["id"], engine)
            row = prompt_one_query(q, engine, prior=existing.get(key))
            if row is None:
                continue  # user kept existing
            # remove any prior row for this key
            rows = [r for r in rows if (r["query_id"], r["engine"]) != key]
            rows.append(row)
            save_results(rows)  # save after each entry for resume safety

    print(green(f"\n  Done. Results saved to {today_csv_path().name}"))
    print_summary(rows)


def print_summary(rows):
    """Per-engine and per-category cited count."""
    print(bold("\n  This week's summary:"))
    by_engine = {}
    for r in rows:
        by_engine.setdefault(r["engine"], {"y": 0, "n": 0, "p": 0})[r["cited"]] += 1

    print(f"  {'ENGINE':12} {'CITED':>6} {'PARTIAL':>8} {'NOT':>5} {'TOTAL':>6}")
    print(f"  {'-'*12} {'-'*6:>6} {'-'*8:>8} {'-'*5:>5} {'-'*6:>6}")
    for engine, counts in by_engine.items():
        total = sum(counts.values())
        cited_pct = (counts["y"] / total * 100) if total else 0
        line = f"  {engine:12} {counts['y']:>6} {counts['p']:>8} {counts['n']:>5} {total:>6}"
        if cited_pct >= 30:
            line += green(f"  ({cited_pct:.0f}% cited)")
        elif cited_pct >= 10:
            line += yellow(f"  ({cited_pct:.0f}% cited)")
        else:
            line += red(f"  ({cited_pct:.0f}% cited)")
        print(line)


def report_trend():
    """Print trend across all saved weekly audits."""
    files = sorted(RESULTS_DIR.glob("*.csv"))
    if not files:
        print(red("  No prior audits found. Run the audit first."))
        return

    print(bold(f"\n  Trend across {len(files)} weekly audits"))
    print(f"  {'DATE':12} {'ENGINE':12} {'CITED':>6} {'TOTAL':>6} {'%':>6}")
    print(f"  {'-'*12} {'-'*12} {'-'*6} {'-'*6} {'-'*6}")
    for path in files:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_engine = {}
        for r in rows:
            by_engine.setdefault(r["engine"], {"y": 0, "total": 0})
            by_engine[r["engine"]]["total"] += 1
            if r["cited"] == "y":
                by_engine[r["engine"]]["y"] += 1
        for engine, c in by_engine.items():
            pct = (c["y"] / c["total"] * 100) if c["total"] else 0
            print(f"  {path.stem:12} {engine:12} {c['y']:>6} {c['total']:>6} {pct:>5.0f}%")
        print()


def main():
    args = sys.argv[1:]
    if "--report" in args:
        report_trend()
        return
    if "--resume" in args:
        run_audit(resume=True)
        return
    engine = None
    if "--engine" in args:
        i = args.index("--engine")
        if i + 1 < len(args):
            engine = args[i + 1]
            if engine not in ENGINES:
                print(red(f"  Unknown engine: {engine}. Use one of: {', '.join(ENGINES)}"))
                sys.exit(1)
    run_audit(engine_filter=engine)


if __name__ == "__main__":
    main()
