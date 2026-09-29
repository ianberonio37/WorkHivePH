"""Find controls whose ACCESSIBLE NAME is still English on the Filipino render.

★WHY THIS EXISTS, AND WHY IT READS THE WALK RATHER THAN THE SOURCE (design lens copy, 2026-09-22,
W46045 + W45940). Two app surfaces in a row shipped a page that translated everything a sighted
reader sees and almost nothing a screen reader announces:

  skillmatrix.html  fil announced "Mga Skill", "Bawasan ang target", "I-save ang Mga Target"
                    ... and "Export my skill record to CSV".
  inventory.html    fil announced "Magdagdag ng Part", "Gamitin", "Mag-restock"
                    ... and "Open item details" x9, "Filter parts by category",
                    "Below reorder: source this part from other plants on the Marketplace" x3,
                    and five more.

Both pages call _t('English','Filipino') for their prose - inventory.html forty-one times - so the
i18n works. What has no translation path is an attribute written as a literal in markup: there is
nowhere to put a function call. It lands on the readers least able to route around it, because a
sighted worker infers a button from its icon and a screen-reader user gets the page in Filipino and
the controls in English.

★I WROTE THE STATIC VERSION OF THIS FIRST AND THREW IT AWAY, which is the point. Scanning the HTML
for English aria-label/title/placeholder over-reported twice in its first run:

  * it flagged `aria-label="Export the current inventory to CSV"` on a page where that attribute is
    REASSIGNED at runtime by a window._t init block - the fix had already landed and the source
    literal is simply what the init overwrites;
  * it flagged `aria-label="Open ${escHtml(disc)}"`, a template interpolation, as prose.

A static reader cannot see runtime assignment and cannot tell an interpolation from a sentence. The
instrument that caught the defect in the first place was the WALK - `controlNames` in the fil step,
which is the rendered accessible name after every init and every template has run. So this reads
that. Kin of the recorded lesson about a detector that read a stylesheet which only exists on paper.

HOW IT DECIDES. For a walk that has both an `en` and a `fil` step of the same page, a control is
reported when its fil name is BYTE-IDENTICAL to its en name and the name looks like English prose.
Identical-and-prose is the signal; everything else is left alone:

  * Brand and proper nouns ("WorkHive home", "PM Scheduler", "Analytics", "Voice Journal") - a name
    that is the same in both languages is correct, so a short Title-Case token is not reported.
  * Loanwords Filipino uses unchanged ("Resume", "Home", "Privacy", "Terms").
  * Anything already different between en and fil - that is a translation, working.

Read-only. Prints a report; changes nothing.

    python tools/find_untranslated_control_names.py                 # every banked walk
    python tools/find_untranslated_control_names.py --id W45940
    python tools/find_untranslated_control_names.py --json out.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = ROOT / ".tmp" / "w4_steps"

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# A name worth translating is PROSE: several words, or one long descriptive phrase.
# A short Title-Case token is a product or brand name and is correct unchanged.
_WORD = re.compile(r"[A-Za-z]{2,}")
_FIL_HINT = re.compile(
    r"\b(ang|ng|sa|mga|ay|para|iyong|mo|ito|hindi|walang|kung|nang|bago|pa|ito|na)\b", re.I)
# names that are the same in both languages by design
_PROPER = re.compile(
    r"^(WorkHive|PM Scheduler|Analytics|Voice Journal|Resume|Home|Privacy|Terms|Marketplace|"
    r"Hive Board|Community|Learn|Impact|EN|FIL|CSV|PDF|QR)\b")


# An EXAMPLE VALUE shown in a field is not prose to translate - an address, a handle, a URL
# fragment. "you@email.com" and "your.handle (without m.me/)" are the same in every language.
_EXAMPLE_VALUE = re.compile(r"@|https?://|\bwww\.|m\.me/|\.com\b|\.ph\b|^\+?\d")


def _looks_english_prose(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 8:
        return False
    if _EXAMPLE_VALUE.search(s):
        return False                         # an example address/handle, not a label
    if _FIL_HINT.search(s):
        return False                         # already Filipino
    if _PROPER.match(s):
        return False                         # brand / product name, same in both
    words = _WORD.findall(s)
    if len(words) < 2:
        return False
    # a lowercase function word is the strongest signal that this is a SENTENCE, not a label
    return any(w.islower() for w in words)


def scan_walk(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    # the steps file is a bare LIST of steps; the walk id is the filename. `degraded` is absent
    # (None) on the plain steps rather than False, so truthiness is the test, not equality.
    steps = d if isinstance(d, list) else (d.get("steps") or [])
    if not steps:
        return None
    walk_id = p.stem
    pages = [s.get("page") for s in steps if s.get("measures")]
    page = pages[0] if pages else (steps[-1].get("page") or "")
    en = fil = None
    for s in steps:
        if s.get("page") != page or s.get("degraded"):   # None/False both mean "not degraded"
            continue
        names = ((s.get("measures") or {}).get("controlNames")) or []
        if not names:
            continue
        if s.get("lang") == "en" and en is None:
            en = names
        elif s.get("lang") == "fil" and fil is None:
            fil = names
    if not en or not fil:
        return None
    same = [n for a, n in zip(en, fil) if a == n and _looks_english_prose(n)]
    # collapse repeats (a per-row control appears once per row)
    seen: dict[str, int] = {}
    for n in same:
        seen[n] = seen.get(n, 0) + 1
    return {"id": walk_id, "page": page, "controls": len(en),
            "untranslated": sorted(seen.items(), key=lambda kv: -kv[1])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="one walk id, e.g. W45940")
    ap.add_argument("--json", help="write the full report here")
    a = ap.parse_args()

    # `<ID>.json` and `<ID>.steps.json` are the same walk written twice; keep one.
    files = ([STEPS / f"{a.id}.json"] if a.id
             else sorted(f for f in STEPS.glob("W*.json") if not f.stem.endswith(".steps")))
    reports = [r for r in (scan_walk(f) for f in files if f.exists()) if r]

    print("  UNTRANSLATED CONTROL NAMES - what a Filipino screen-reader user still hears in English")
    print("  " + "=" * 76)
    hit = [r for r in reports if r["untranslated"]]
    for r in sorted(hit, key=lambda r: -sum(n for _, n in r["untranslated"])):
        total = sum(n for _, n in r["untranslated"])
        print("  %-8s %-34s %3d of %3d controls" % (r["id"], r["page"][:34], total, r["controls"]))
        for name, n in r["untranslated"][:6]:
            print("       x%-3d %s" % (n, name[:66]))
        if len(r["untranslated"]) > 6:
            print("       ... and %d more distinct" % (len(r["untranslated"]) - 6))
    print("  " + "-" * 76)
    print("  walks with an en+fil pair: %d   |   clean: %d   |   with findings: %d"
          % (len(reports), len(reports) - len(hit), len(hit)))
    if a.json:
        Path(a.json).write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  report written to", a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
