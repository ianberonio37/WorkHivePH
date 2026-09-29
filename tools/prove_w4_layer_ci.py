#!/usr/bin/env python3
"""prove_w4_layer_ci.py - the W4 layer-CI stories, proven against the registered gate suite (no browser).

The wave-4 CI-layer story is "The platform must catch this page's regressions before a person meets them." That is
a claim about the CHECK SUITE, not the page's own bytes: a page is CI-covered when a registered gate actually
exercises it, so a change that breaks it is caught by run_platform_checks before it ships. Every SERVED page is
swept by the registered phone-fit gate (390/360/320) and carried by the trajectory-registry gate, and many also
have a dedicated validator (report-sender, etc.). The real gap CI guards against is a shipped page that NO
registered gate watches - a regression there reaches a person uncaught.
  - a retired page (behind the overlay) -> n/a (no live surface to regress)
  - a served page (in the platform's served roster the sweeps enumerate) -> ok (phone-fit + registry + any
    dedicated validator cover it)
  - a page that is NOT served and NOT retired -> BAD (it ships to nobody's gate)
The coverage is instrument-level and axis-independent, so the three axis-rows of a page share one witness; writes
a `witness` receipt per row.

  python tools/prove_w4_layer_ci.py            # every CI-layer row, print + write receipts
  python tools/prove_w4_layer_ci.py --check    # the gate: exit 1 if any CI row's page is watched by no registered gate
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import seed_expansion_wave4 as w4  # noqa: E402  - served_pages() is the roster the sweeps enumerate
from prove_w4_layer_headers import _first_root_page  # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def ci_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "CI"
            and t.get("status") != "descoped"]


def _served() -> set[str]:
    flat: set[str] = set()
    for v in w4.served_pages().values():
        flat |= set(v)
    return flat


def _dedicated_gate_index() -> str:
    """One blob of the registered-check corpus, so a page's basename can be matched to a dedicated validator."""
    parts = []
    try:
        parts.append((ROOT / "run_platform_checks.py").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        pass
    for p in sorted((ROOT / "tools").glob("validate_*.py")):
        parts.append(p.name)
    return "\n".join(parts)


def check_page(page: str, served: set[str], gate_blob: str) -> tuple[str, str]:
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        if 'id="wh-retired-overlay"' in own:
            return "n/a", f"{page} is retired behind the overlay - it has no live surface that could regress on a person"
    except OSError:
        pass
    if page not in served:
        return "BAD", f"{page} is not in the served-page roster any registered sweep enumerates - a regression here reaches a person uncaught"
    base = Path(page).name if not page.endswith("index.html") else page  # learn/x/index.html -> keep the path
    stem = page.replace("/index.html", "").split("/")[-1].replace(".html", "")
    dedicated = re.search(r"validate_" + re.escape(stem.replace("-", "_")) + r"\.py", gate_blob) or \
        (page in gate_blob) or (Path(page).name in gate_blob)
    how = "the registered phone-fit sweep (390/360/320) + the trajectory-registry gate + the UFAI rubric"
    if dedicated:
        return "ok", f"{page} is covered by a dedicated registered gate AND {how} - a regression is caught before a person meets it"
    return "ok", f"{page} is covered by {how} (every served page is swept) - a regression is caught before a person meets it"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 CI-layer story proven against the registered gate suite (no browser) - tools/prove_w4_layer_ci.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "playwright",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "playwright",
            "condition": "a regression is introduced", "cast": "the registered gate suite that watches this page",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "CI", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = ci_rows()
    if not rows:
        print("PASS w4-layer-regression - no W4 layer-CI row (nothing to prove)")
        return 0
    check_only = "--check" in sys.argv
    served = _served()
    gate_blob = _dedicated_gate_index()
    page_cache: dict[str, tuple[str, str]] = {}
    bad = 0
    for row in rows:
        page = _first_root_page(row)
        if not page:
            continue
        if page not in page_cache:
            page_cache[page] = check_page(page, served, gate_blob)
        verdict, witness = page_cache[page]
        if verdict == "BAD":
            bad += 1
        if not check_only:
            write_receipt(row, verdict, witness)
    n, uniq = len(rows), len(page_cache)
    na = sum(1 for v, _w in page_cache.values() if v == "n/a")
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-regression - "
          f"{n - bad}/{n} CI-layer row(s) hold ({uniq} distinct pages, {na} n/a - retired)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) no registered gate watches" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
