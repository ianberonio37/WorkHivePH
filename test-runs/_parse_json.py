"""Parse a Playwright JSON report into failure buckets."""
from __future__ import annotations
import json, re, sys, collections, pathlib, argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("json_path")
ap.add_argument("--out-prefix", default=None)
args = ap.parse_args()

ROOT = pathlib.Path(__file__).resolve().parent.parent
json_path = pathlib.Path(args.json_path)
out_prefix = args.out_prefix or json_path.stem
out_json = ROOT / "test-runs" / f"failures_{out_prefix}.json"
out_md   = ROOT / "test-runs" / f"failures_{out_prefix}.md"

data = json.loads(json_path.read_text(encoding="utf-8-sig"))

failures = []

def walk(node, file_path):
    fp = node.get("file") or file_path
    for spec in node.get("specs", []) or []:
        for t in spec.get("tests", []) or []:
            results = t.get("results") or []
            if not results:
                continue
            last = results[-1]
            status = last.get("status")
            if status not in ("failed", "timedOut", "interrupted"):
                continue
            errs = last.get("errors") or ([last.get("error")] if last.get("error") else [])
            messages = []
            for e in errs:
                if not e:
                    continue
                msg = (e.get("message") or "") + " " + (e.get("stack") or "")
                msg = re.sub(r"\x1b\[[0-9;]*m", "", msg)  # strip ANSI
                msg = re.sub(r"\s+", " ", msg).strip()
                if msg:
                    messages.append(msg)
            err_flat = " || ".join(messages)[:800]
            failures.append({
                "file": (fp or "").replace("\\", "/"),
                "title": spec.get("title", ""),
                "line": spec.get("line"),
                "status": status,
                "duration_ms": last.get("duration"),
                "error": err_flat,
            })
    for sub in node.get("suites", []) or []:
        walk(sub, fp)

for s in data.get("suites", []) or []:
    walk(s, s.get("file"))

NETWORK_PAT = re.compile(
    r"(Failed to fetch|cdn\.jsdelivr|net::ERR_|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|"
    r"Target page.*closed|Connection closed)", re.IGNORECASE)
FIXTURE_PAT = re.compile(r"_fixtures\.ts|wh_last_worker|sign-?in failed", re.IGNORECASE)
SENTINEL_PAT = re.compile(r"sentinel scenario", re.IGNORECASE)
TIMEOUT_PAT  = re.compile(r"Test timeout|Timeout \d+ms exceeded", re.IGNORECASE)

flake, fixture, sentinel, real = [], [], [], []
for f in failures:
    blob = (f["title"] + " " + f["error"]).lower()
    if NETWORK_PAT.search(blob):
        flake.append(f)
    elif FIXTURE_PAT.search(blob):
        fixture.append(f)
    elif SENTINEL_PAT.search(f["title"]):
        sentinel.append(f)
    else:
        real.append(f)

by_file = collections.Counter(f["file"] for f in failures)

out_json.write_text(json.dumps({
    "total_failed": len(failures),
    "stats": data.get("stats"),
    "flake": flake,
    "fixture": fixture,
    "sentinel": sentinel,
    "real": real,
    "by_file": dict(by_file.most_common()),
}, indent=2, ensure_ascii=False), encoding="utf-8")

md = [f"# Triage — {out_prefix}", ""]
md.append(f"- stats: {data.get('stats')}")
md.append(f"- total failures: **{len(failures)}**")
md.append(f"  - A. Network / flake:        **{len(flake)}**")
md.append(f"  - F. Fixture sign-in:        **{len(fixture)}**")
md.append(f"  - B. Sentinel content drift: **{len(sentinel)}**")
md.append(f"  - C. Real regressions:       **{len(real)}**")
md.append("")
md.append("## Top failing files")
md.append("| Count | File |")
md.append("|---|---|")
for fn, n in by_file.most_common(40):
    md.append(f"| {n} | `{fn}` |")
md.append("")
for name, items in [("A. Network / flake", flake),
                    ("F. Fixture sign-in", fixture),
                    ("B. Sentinel content drift", sentinel),
                    ("C. Real regressions", real)]:
    md.append(f"## {name}  ({len(items)})")
    md.append("")
    by_f = collections.defaultdict(list)
    for it in items:
        by_f[it["file"]].append(it)
    for fn, lst in sorted(by_f.items(), key=lambda kv: -len(kv[1])):
        md.append(f"### `{fn}`  ({len(lst)})")
        for it in lst[:10]:
            md.append(f"- L{it['line']} — {it['title']}")
            if it["error"]:
                md.append(f"  - err: `{it['error'][:220]}`")
        if len(lst) > 10:
            md.append(f"  - ... +{len(lst)-10} more")
        md.append("")

out_md.write_text("\n".join(md), encoding="utf-8")
print(f"Wrote {out_json.name} / {out_md.name}")
print(f"Failed={len(failures)} | flake={len(flake)} | fixture={len(fixture)} | "
      f"sentinel={len(sentinel)} | real={len(real)}")
