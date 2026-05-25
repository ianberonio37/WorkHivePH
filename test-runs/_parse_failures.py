"""Parse playwright-report.json into actionable failure buckets.

Buckets:
  A) network-flake (Failed to fetch / cdn.jsdelivr / net::ERR)
  B) sentinel-content drift (sentinel scenario titles)
  C) real regressions (everything else)

Usage:  python test-runs/_parse_failures.py
Writes: test-runs/failures_<RUNID>.json + .md summary
"""
from __future__ import annotations
import json, os, re, sys, collections, pathlib

# Windows console safety per CLAUDE.md / cp1252 guard
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "playwright-report.json"
RUNID = (ROOT / "test-runs" / "_last_run_id.txt").read_text().strip()
OUT_JSON = ROOT / "test-runs" / f"failures_{RUNID}.json"
OUT_MD = ROOT / "test-runs" / f"failures_{RUNID}.md"

NETWORK_PAT = re.compile(
    r"(Failed to fetch|cdn\.jsdelivr|net::ERR_|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|browser closed|"
    r"Target page.*closed|Connection closed)", re.IGNORECASE)
SENTINEL_PAT = re.compile(r"sentinel scenarios|sentinel_|sentinel-", re.IGNORECASE)
TIMEOUT_PAT = re.compile(r"timed?[\s_-]?out|Test timeout of", re.IGNORECASE)

def walk(node, file_path, out):
    fp = node.get("file") or file_path
    for spec in node.get("specs", []) or []:
        for test in spec.get("tests", []) or []:
            results = test.get("results") or []
            if not results:
                continue
            last = results[-1]
            status = last.get("status")
            if status not in ("failed", "timedOut"):
                continue
            err = (last.get("error") or {})
            err_msg = err.get("message") or ""
            err_stack = err.get("stack") or ""
            full = (err_msg + "\n" + err_stack).strip()
            full_oneline = re.sub(r"\s+", " ", full)[:600]
            out.append({
                "file": fp,
                "title": spec.get("title", ""),
                "fulltitle": " > ".join(
                    [s for s in [node.get("title"), spec.get("title")] if s]),
                "line": spec.get("line"),
                "status": status,
                "duration_ms": last.get("duration"),
                "error": full_oneline,
            })
    for sub in node.get("suites", []) or []:
        walk(sub, fp, out)

def main():
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    failures = []
    for s in data.get("suites", []) or []:
        walk(s, s.get("file"), failures)
    # bucket
    flake, sentinel, real = [], [], []
    for f in failures:
        if NETWORK_PAT.search(f["error"]):
            flake.append(f)
        elif SENTINEL_PAT.search(f["fulltitle"]) or SENTINEL_PAT.search(f["title"]):
            sentinel.append(f)
        else:
            real.append(f)

    by_file = collections.Counter(f["file"] for f in failures)

    OUT_JSON.write_text(json.dumps({
        "run_id": RUNID,
        "total_failed": len(failures),
        "flake": flake,
        "sentinel": sentinel,
        "real": real,
        "by_file": dict(by_file.most_common()),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append(f"# Playwright failure triage — run {RUNID}")
    md.append("")
    md.append(f"- Total failed/timedOut: **{len(failures)}**")
    md.append(f"- Bucket A (network-flake / infra): **{len(flake)}**")
    md.append(f"- Bucket B (sentinel-content drift): **{len(sentinel)}**")
    md.append(f"- Bucket C (real regressions): **{len(real)}**")
    md.append("")
    md.append("## Top files by failure count")
    md.append("")
    md.append("| Count | File |")
    md.append("|---|---|")
    for fn, n in by_file.most_common(30):
        md.append(f"| {n} | `{fn}` |")
    md.append("")
    for name, items in [("A. Network / flake", flake),
                        ("B. Sentinel content", sentinel),
                        ("C. Real regressions", real)]:
        md.append(f"## {name}  ({len(items)})")
        md.append("")
        # group by file inside each bucket
        by_f = collections.defaultdict(list)
        for it in items:
            by_f[it["file"]].append(it)
        for fn, lst in sorted(by_f.items(), key=lambda kv: -len(kv[1])):
            md.append(f"### `{fn}`  ({len(lst)})")
            for it in lst[:15]:
                md.append(f"- L{it['line']} — {it['title']}")
                if it["error"]:
                    md.append(f"  - err: `{it['error'][:200]}`")
            if len(lst) > 15:
                md.append(f"  - ... +{len(lst)-15} more")
            md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT_JSON.name} and {OUT_MD.name}")
    print(f"Totals: failed={len(failures)} | flake={len(flake)} | sentinel={len(sentinel)} | real={len(real)}")

if __name__ == "__main__":
    main()
