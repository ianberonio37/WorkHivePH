#!/usr/bin/env python3
"""T50 (2026-08-25): the destructive-control registry — every confirm-gated action, from source.

The J3/whConfirm sweep needs a denominator no one can shrink silently: every place a page asks
"are you sure" IS a destructive/irreversible control by the platform's own judgment. Enumerated
from whConfirm(/whPrompt( call sites (the ONE confirm vocabulary — S4) with the first line of
each message, so the proportionality sweep can audit consequence-naming per entry.

Usage:
  python tools/build_destructive_control_registry.py           # writes the registry
  python tools/build_destructive_control_registry.py --check   # exits 1 if stale
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "substrate" / "reference" / "destructive_control_registry.json"
CALL_RX = re.compile(r"wh(?:Confirm|Prompt)\(\s*(?:`([^`]{0,160})|'([^']{0,160})|\"([^\"]{0,160}))")
SKIP_RX = re.compile(r"(backup|-test|_fixtures|design-system)", re.I)


def build():
    reg = {}
    for f in sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("*.js"))):
        if SKIP_RX.search(f.name):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        entries = []
        for m in CALL_RX.finditer(text):
            msg = next(g for g in m.groups() if g is not None)
            line = text.count("\n", 0, m.start()) + 1
            entries.append({"line": line, "message_head": msg.strip()[:140]})
        if entries:
            reg[f.name] = entries
    return {
        "_meta": {
            "generator": "tools/build_destructive_control_registry.py",
            "note": "every whConfirm/whPrompt call site (the platform's own are-you-sure vocabulary). "
                    "T50's denominator: audit each entry for consequence-naming + proportionality + undo.",
        },
        "controls": reg,
        "total_files": len(reg),
        "total_controls": sum(len(v) for v in reg.values()),
    }


def main():
    data = build()
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        on_disk = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if on_disk != payload:
            print(f"STALE: {OUT.name} does not match source — re-run the generator")
            sys.exit(1)
        print(f"OK: {OUT.name} current ({data['total_files']} files, {data['total_controls']} controls)")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(OUT)  # atomic (open-w-truncates lesson)
    print(f"wrote {OUT.relative_to(ROOT)} — {data['total_files']} files, {data['total_controls']} controls")


if __name__ == "__main__":
    main()
