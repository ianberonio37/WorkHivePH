#!/usr/bin/env python3
"""T43 (2026-08-25): the param-route registry — every ?param a served page actually reads.

A shareable link's contract lives in these params (the paramless-walk lesson: a walk without
the param is a DIFFERENT page). This enumerates `.get('<param>')` reads from the served root
pages so the deep-link cold-start sweep (T43) has a COMPLETE, regenerable denominator no one
can shrink silently. Generated, never hand-edited: re-run after adding a param reader.

Usage:
  python tools/build_param_route_registry.py           # writes substrate/reference/param_route_registry.json
  python tools/build_param_route_registry.py --check   # exits 1 if the file on disk is stale
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "substrate" / "reference" / "param_route_registry.json"
GET_RX = re.compile(r"\.get\('([a-z_]+)'\)")
# fixture/backup pages are not served surface
SKIP_RX = re.compile(r"(backup|-test|_fixtures|design-system)", re.I)


def build():
    reg = {}
    for f in sorted(ROOT.glob("*.html")):
        if SKIP_RX.search(f.name):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        params = sorted(set(GET_RX.findall(text)))
        if params:
            reg[f.name] = params
    return {
        "_meta": {
            "generator": "tools/build_param_route_registry.py",
            "note": "every ?param each served root page reads (URLSearchParams .get). "
                    "T43's sweep denominator: cold-start x auth-state per (page, param).",
        },
        "routes": reg,
        "total_pages": len(reg),
        "total_params": sum(len(v) for v in reg.values()),
    }


def main():
    data = build()
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        on_disk = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if on_disk != payload:
            print(f"STALE: {OUT.name} does not match source enumeration — re-run the generator")
            sys.exit(1)
        print(f"OK: {OUT.name} current ({data['total_pages']} pages, {data['total_params']} params)")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(OUT)  # atomic: never leave a truncated registry (open-w-truncates lesson)
    print(f"wrote {OUT.relative_to(ROOT)} — {data['total_pages']} pages, {data['total_params']} params")


if __name__ == "__main__":
    main()
