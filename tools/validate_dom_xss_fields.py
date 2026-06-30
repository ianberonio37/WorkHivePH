#!/usr/bin/env python3
"""
validate_dom_xss_fields.py - Arc R (X-lens, OWASP A03): no UNESCAPED DB free-text field
interpolated into an HTML template literal.
=========================================================================================
validate_xss.py checks that escHtml is *in scope* per page and treats raw interpolation as a
non-failing WARN. Its blind spot (Hunter X, Arc R): a DB-sourced `${asset.machine}` dropped
raw into an `innerHTML` template - next to siblings that DO escape - passes the gate yet is a
worker-injectable stored XSS (rename an asset to `<img src=x onerror=...>`).

This gate closes the blind spot. It flags a BARE member-access interpolation `${obj.field}`
(no function call inside the braces => not escHtml-wrapped) where `field` is a known
free-text DB column, sitting on a line that is clearly an HTML template (contains a tag).
`${escHtml(obj.field)}` / `${e(obj.field)}` never match (they contain `(`), and numeric/enum
fields (mtbf_days, status, count) are not in the untrusted set.

Self-test (--self-test): proves teeth - flags `<span>${a.machine}</span>`, passes
`<span>${escHtml(a.machine)}</span>` and `<span>${a.mtbf_days}</span>`.

Baseline: security_dom_xss_baseline.json (ratchet to 0). Exit 0 = clean / at-or-below baseline.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "security_dom_xss_baseline.json"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_dom_xss_fields"]

# Free-text, WORKER-WRITABLE DB columns that are stored XSS vectors when rendered raw.
# Deliberately HIGH-CONFIDENCE: fields like `label`/`name`/`title`/`desc` are excluded
# because they are overwhelmingly STATIC UI-registry keys (TOOLS nav, hardcoded tiers,
# symbol gallery), not DB free-text - including them only produced false positives. The
# set below is columns a worker types into a record that is later rendered to other users.
UNTRUSTED_FIELDS = {
    "machine", "machine_code", "asset_name", "item_text", "photo",
    "worker_name", "display_name", "author_name", "problem", "root_cause",
    "manufacturer", "model_name", "full_name", "username", "contact_email",
    "headline", "bio", "remarks",
}
# Bare member access inside ${...} with NOTHING else (no call, no operator) => unescaped.
INTERP = re.compile(r"\$\{\s*([A-Za-z_]\w*)\.([A-Za-z_]\w+)\s*\}")
HTML_LINE = re.compile(r"<[a-zA-Z/][^>]*>|<[a-zA-Z]+\s|src=|href=|class=|<span|<div|<p[ >]|<img|<li|<a[ >]|<b>")


def scan_text(text: str) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if "${" not in line or "<" not in line:
            continue
        if not HTML_LINE.search(line):
            continue
        for m in INTERP.finditer(line):
            obj, field = m.group(1), m.group(2)
            if field in UNTRUSTED_FIELDS:
                hits.append((i, f"${{{obj}.{field}}}"))
    return hits


def self_test() -> bool:
    ok = True
    if not scan_text('rows.push(`<span class="v">${a.machine} ok</span>`);'):
        print(f"{R}self-test FAIL: missed bare ${{a.machine}} in HTML.{X}"); ok = False
    if scan_text('rows.push(`<span class="v">${escHtml(a.machine)}</span>`);'):
        print(f"{R}self-test FAIL: flagged escHtml-wrapped field.{X}"); ok = False
    if scan_text('rows.push(`<span class="v">${a.mtbf_days}d</span>`);'):
        print(f"{R}self-test FAIL: flagged a numeric/enum field.{X}"); ok = False
    if scan_text('const s = `Question: ${a.machine}`;'):
        print(f"{R}self-test FAIL: flagged a non-HTML template.{X}"); ok = False
    print((G + "self-test PASS - DB-field XSS detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1
    update = "--update-baseline" in sys.argv

    findings: dict[str, list] = {}
    for p in sorted(ROOT.glob("*.html")):
        if "backup" in p.name or "-test" in p.name:
            continue
        hits = scan_text(p.read_text(encoding="utf-8", errors="replace"))
        if hits:
            findings[p.name] = hits

    total = sum(len(v) for v in findings.values())
    baseline_n = 0
    if BASELINE.exists():
        try:
            baseline_n = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0)
        except Exception:
            baseline_n = 0

    print(f"{B}DOM-XSS DB-field gate (Arc R / X-lens, OWASP A03){X}")
    for fn, hits in findings.items():
        for line, frag in hits:
            print(f"  {R}FAIL{X} {fn}:{line}  {frag} - DB free-text in HTML, wrap in escHtml()")
    print(f"  total unescaped DB-field interpolations: {total}  (baseline {baseline_n})")

    if update:
        BASELINE.write_text(json.dumps({"count": total}, indent=2), encoding="utf-8")
        print(f"{G}baseline updated to {total}.{X}")
        return 0

    if total > baseline_n:
        print(f"{R}FAIL: {total - baseline_n} new unescaped DB-field interpolation(s).{X}")
        return 1
    if total == 0:
        print(f"{G}PASS - no unescaped DB free-text field in any HTML template.{X}")
    else:
        print(f"{Y}at/below baseline ({total}<= {baseline_n}) - ratchet down.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
