#!/usr/bin/env python3
"""
validate_ufai_deep_u.py — LOCK the UFAI U-pillar deep-verification fixes (PDDA §11 deepwalk).

WHY: the §11 live deep-probe found the coarse A-Z lens (Z3 = 24px WCAG FLOOR) missed the deeper UFAI
U2 field standard (44px gloved-hand tap goal) + the Z2d responsive-image floor. The fix is a set of
SHARED rules in tokens.css (the ONE file every page loads) so every form control / secondary button /
image on every page meets the field standard. This gate asserts those shared rules STAY — remove one
and every page silently regresses. Static, deterministic, forward-only. Self-test: --selftest.

USAGE: python tools/validate_ufai_deep_u.py [--selftest]
Exit 0 = all shared UFAI-U rules present; 1 = a rule vanished (regression).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
G = "\033[92m"; R = "\033[91m"; X = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "tokens.css"

# each = (name, regex that must match tokens.css, why)
RULES = [
    ("u2_form_44px", r"input\.wh-input[^{]*\{[^}]*min-height:\s*44px",
     "U2: shared form controls (.wh-input/.wh-select) must carry the 44px field tap floor"),
    ("u2_button_44px", r"\.btn-secondary[^{]*\{[^}]*min-height:\s*44px",
     "U2: shared secondary/ghost buttons must carry the 44px field tap floor"),
    ("z2d_img_fluid", r"(^|\})\s*img\s*\{[^}]*max-width:\s*100%",
     "Z2d/A1: the responsive-image reset (img{max-width:100%}) must stay"),
]


_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def check(css: str):
    # ★STRIP CSS COMMENTS FIRST. Fault injection (2026-07-23) proved this gate was toothless: deleting
    # the real `input.wh-input{...min-height:44px}` rule STILL passed, because tokens.css carries an
    # explanatory comment mentioning "(input.wh-input" a few lines above, and the DOTALL regex happily
    # spanned from that comment into the next rule's min-height. A gate that a COMMENT can satisfy is
    # not a lock (third time a comment fooled a scanner this session). Match against code only.
    code = _CSS_COMMENT.sub(" ", css)
    return [(n, why) for n, rx, why in RULES if not re.search(rx, code, re.M | re.S)]


def self_test() -> bool:
    good = "input.wh-input, select.wh-select { min-height: 44px; }\n.btn-secondary { min-height: 44px; }\nimg { max-width: 100%; }"
    bad = "input.wh-input { padding: 8px; }\nimg { border: 0; }"
    ok = not check(good) and len(check(bad)) == 3
    print((G + "selftest PASS — UFAI-U deep lock has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    if not TOKENS.exists():
        print(f"{R}tokens.css not found{X}"); return 1
    missing = check(TOKENS.read_text(encoding="utf-8"))
    if missing:
        print(f"{R}FAIL: UFAI-U deep rule(s) removed from tokens.css:{X}")
        for n, why in missing:
            print(f"  - {n}: {why}")
        return 1
    print(f"{G}PASS — all {len(RULES)} shared UFAI U-pillar deep rules present in tokens.css "
          f"(44px form controls + 44px buttons + responsive img).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
