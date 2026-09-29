#!/usr/bin/env python3
"""fetch_fixture.py - download ONE real file from the internet into _fixtures/<kind>/ and record its provenance.

Wave 4 (Ian, 2026-09-14): "start from the start to end for every page, such as in connection pages, where you have
to search in the internet any files then upload it". The seven upload pages are walked with REAL files - a CMMS /
SAP-PM export or OEM manual (integrations), a nameplate or fault photo (logbook), a spare-part photo (inventory),
listing photos (marketplace, marketplace-seller), a maintenance-technician resume (resume), a short audio clip
(voice-journal). Each is fetched ONCE, here, and every fetch leaves a receipt in `_fixtures/<kind>/manifest.json`:
source URL, licence, author, sha256, bytes, mime, fetched date, the note that says what it is. The binary is
gitignored; the manifest is tracked (the vehicle-docs pattern, feedback_real_documents_taught_the_miner_eight_lessons).
`_fixtures/` is excluded from the Vercel deployment (.vercelignore) so nothing here can ever be served.

  python tools/fetch_fixture.py --kind fault-photo --url https://... --license "CC BY-SA 4.0" --author "..." \
      --note "600V DC marine motor nameplate, Fireboat Firefighter" [--name nameplate.jpg]
  python tools/fetch_fixture.py --list             # every fixture on disk with its provenance
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "_fixtures"
KINDS = ("cmms-export", "fault-photo", "part-photo", "listing-photo", "technician-resume", "audio-clip")
UA = "WorkHiveFixtureFetch/1.0 (+https://workhiveph.com; fixture provenance for a maintenance platform's tests)"


def _manifest(kind: str) -> tuple[Path, dict]:
    p = FIXTURES / kind / "manifest.json"
    if p.exists():
        return p, json.loads(p.read_text(encoding="utf-8"))
    return p, {"_doc": ("Provenance for the real internet-sourced files in this directory (wave 4). The files are "
                        "gitignored; this manifest is tracked. Written only by tools/fetch_fixture.py."),
               "kind": kind, "files": []}


def fetch(kind: str, url: str, license_: str, author: str, note: str, name: str | None = None) -> dict:
    if kind not in KINDS:
        raise SystemExit(f"unknown kind {kind!r}; one of {KINDS}")
    d = FIXTURES / kind
    d.mkdir(parents=True, exist_ok=True)
    fname = name or urllib.parse.unquote(url.split("?")[0].rsplit("/", 1)[-1])
    fname = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in fname)[:120]
    out = d / fname
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        mime = r.headers.get("Content-Type", "").split(";")[0]
    if not data:
        raise SystemExit(f"empty response from {url}")
    out.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    entry = {"file": fname, "source_url": url, "license": license_, "author": author, "note": note,
             "mime": mime, "bytes": len(data), "sha256": sha,
             "fetched": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    mp, m = _manifest(kind)
    m["files"] = [f for f in m["files"] if f.get("file") != fname] + [entry]
    tmp = mp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, mp)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=KINDS)
    ap.add_argument("--url")
    ap.add_argument("--license", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--name", default=None)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for kind in KINDS:
            mp, m = _manifest(kind)
            for f in m["files"]:
                present = (FIXTURES / kind / f["file"]).exists()
                print(f"  {kind:18} {f['file'][:48]:50} {f['bytes']:>9} B  {f['license'][:14]:14} "
                      f"{'on disk' if present else 'MISSING (re-fetch)'}  <- {f['source_url'][:70]}")
        return 0
    if not (a.kind and a.url):
        ap.error("--kind and --url are required (or --list)")
    e = fetch(a.kind, a.url, a.license, a.author, a.note, a.name)
    print(f"fetched {a.kind}/{e['file']} ({e['bytes']} B, {e['mime']}, sha256 {e['sha256'][:12]}...) - provenance recorded")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
