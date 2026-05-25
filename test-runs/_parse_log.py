"""Parse the UTF-16 Playwright list-reporter log into failure buckets.

The list reporter writes lines like:
     ok   123 [chromium] : tests\file.spec.ts:LL:CC : suite > title (Ns)
     x    124 [chromium] : tests\file.spec.ts:LL:CC : suite > title (Ns)

After the per-test rows, Playwright prints a "X) tests\file:LL:CC > ..." block
for every failure with the actual stack trace. We capture both: the row index
for ordering and the trace for bucketing.
"""
from __future__ import annotations
import re, sys, json, collections, pathlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNID = (ROOT / "test-runs" / "_last_run_id.txt").read_text().strip()
LOG = ROOT / "test-runs" / f"run_{RUNID}.log"
OUT_JSON = ROOT / "test-runs" / f"failures_{RUNID}.json"
OUT_MD = ROOT / "test-runs" / f"failures_{RUNID}.md"

# Log is UTF-16 LE (PS Tee-Object default on 5.1)
raw = LOG.read_bytes()
if raw.startswith(b"\xff\xfe"):
    text = raw.decode("utf-16-le", errors="replace")
elif raw.startswith(b"\xfe\xff"):
    text = raw.decode("utf-16-be", errors="replace")
else:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-16-le", errors="replace")

# Strip BOM if leftover
text = text.replace("﻿", "")

ROW_PAT = re.compile(
    r"^\s+(ok|x)\s+(\d+)\s+\[chromium\]\s+›\s+(\S+):(\d+):\d+\s+›\s+(.+?)\s+\(\d+(?:\.\d+)?[ms]+\)\s*$",
    re.MULTILINE)

rows = []
for m in ROW_PAT.finditer(text):
    status, idx, fp, line, title = m.groups()
    rows.append({
        "idx": int(idx),
        "status": "passed" if status == "ok" else "failed",
        "file": fp.strip().replace("\\", "/"),
        "line": int(line),
        "title": title.strip(),
    })

# Detail blocks come after: "  N) ...\n" with an error block. The list reporter
# emits a Z-numbered failure block followed by the error. Pattern is:
#   "  1)  [chromium] > tests\\foo.spec.ts:LL:CC > Suite > Title --"
# Then several indented lines including "Error: ..." and a stack.
#
# We split text by lines starting with whitespace+digits+")" and capture each block.
BLOCK_HEAD = re.compile(
    r"^\s+\d+\)\s+\[chromium\]\s+›\s+(\S+):(\d+):\d+\s+›\s+(.+?)\s*$",
    re.MULTILINE)
heads = list(BLOCK_HEAD.finditer(text))
detail_for = {}
for i, m in enumerate(heads):
    end = heads[i+1].start() if i+1 < len(heads) else len(text)
    block = text[m.end():end]
    # one-line normalised error (first 600 chars)
    flat = re.sub(r"\s+", " ", block).strip()[:600]
    fp = m.group(1).strip().replace("\\", "/")
    ln = int(m.group(2))
    title = m.group(3).strip()
    detail_for[(fp, ln, title)] = flat

failed = []
for r in rows:
    if r["status"] != "failed":
        continue
    key = (r["file"], r["line"], r["title"])
    err = detail_for.get(key, "")
    failed.append({**r, "error": err})

# Categorisation
NETWORK_PAT = re.compile(
    r"(Failed to fetch|cdn\.jsdelivr|net::ERR_|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|"
    r"Target page.*closed|page\.goto.*timeout|Connection closed|"
    r"Timeout 15000ms exceeded.*navigation)", re.IGNORECASE)
SENTINEL_PAT = re.compile(r"sentinel scenario", re.IGNORECASE)

flake, sentinel, real = [], [], []
for f in failed:
    blob = (f["title"] + " " + f["error"]).lower()
    if NETWORK_PAT.search(blob):
        flake.append(f)
    elif SENTINEL_PAT.search(f["title"]):
        sentinel.append(f)
    else:
        real.append(f)

by_file = collections.Counter(f["file"] for f in failed)

OUT_JSON.write_text(json.dumps({
    "run_id": RUNID,
    "total_rows": len(rows),
    "total_passed": sum(1 for r in rows if r["status"] == "passed"),
    "total_failed": len(failed),
    "flake": flake,
    "sentinel": sentinel,
    "real": real,
    "by_file": dict(by_file.most_common()),
}, indent=2, ensure_ascii=False), encoding="utf-8")

md = [f"# Playwright failure triage — run {RUNID}", ""]
md.append(f"- Total rows captured: **{len(rows)}**")
md.append(f"- Passed: **{sum(1 for r in rows if r['status']=='passed')}**")
md.append(f"- Failed: **{len(failed)}**")
md.append(f"  - A. Network / flake: **{len(flake)}**")
md.append(f"  - B. Sentinel content drift: **{len(sentinel)}**")
md.append(f"  - C. Real regressions: **{len(real)}**")
md.append("")
md.append("## Top failing files")
md.append("")
md.append("| Count | File |")
md.append("|---|---|")
for fn, n in by_file.most_common(40):
    md.append(f"| {n} | `{fn}` |")
md.append("")
for name, items in [("A. Network / flake", flake),
                    ("B. Sentinel content drift", sentinel),
                    ("C. Real regressions", real)]:
    md.append(f"## {name}  ({len(items)})")
    md.append("")
    by_f = collections.defaultdict(list)
    for it in items:
        by_f[it["file"]].append(it)
    for fn, lst in sorted(by_f.items(), key=lambda kv: -len(kv[1])):
        md.append(f"### `{fn}`  ({len(lst)})")
        for it in lst[:12]:
            md.append(f"- L{it['line']} — {it['title']}")
            if it["error"]:
                md.append(f"  - err: `{it['error'][:200]}`")
        if len(lst) > 12:
            md.append(f"  - ... +{len(lst)-12} more")
        md.append("")

OUT_MD.write_text("\n".join(md), encoding="utf-8")
print(f"Wrote {OUT_JSON.name} and {OUT_MD.name}")
print(f"Rows={len(rows)}  Passed={sum(1 for r in rows if r['status']=='passed')}  "
      f"Failed={len(failed)}  Flake={len(flake)}  Sentinel={len(sentinel)}  Real={len(real)}")
