"""
Arc X - Family C (Recall vs Recognition) SCANNER  [HARD proxies]
================================================================
Deterministic enumeration of the three Family-C cognitive-load defect types
across the whole feature-page set (the registry-mined denominator), so X2 is
driven by a MEASURED %, not vibes. See COGNITIVE_LOAD_II_ROADMAP.md Family C.

  C2  Placeholder-as-label  [HARD]
        An <input>/<textarea> carries a `placeholder` but has NO persistent
        accessible name (no <label for>, no wrapping <label>, no aria-label /
        aria-labelledby). The field name vanishes the moment the user types -
        pure recall. Fix = a persistent visible <label> or an aria-label;
        placeholder becomes an example only.

  C1  Recall-dependent entity input  [HARD, conservative]
        A free-text data-ENTRY input whose label/placeholder/id names an
        ENUMERABLE entity (asset / equipment / machine / part / SKU / work-order /
        technician / assignee / supplier) with NO adjacent picker (no `list=`
        datalist, not a <select>, no role=combobox). The user must recall an exact
        identifier instead of recognising it from a list. Fix = searchable
        picker / <datalist> / autocomplete.
        NOTE: live list-FILTER search boxes are RECOGNITION aids, not recall, and
        are EXCLUDED (id/placeholder mentions search/filter/find, or type=search).

  C3  No external memory for status  [presence HARD; salience SOFT->judge]
        Scanned per known record-card surface: a record/list card must surface a
        status / last-action / timestamp element so the user need not remember
        where a job stands. Presence is gated; whether the state shown is the
        *right* salient one is SOFT (Ian's eye).  (C3 presence is asserted by the
        gate against named surfaces, not free-scanned here - left as a registry.)

Exemption (per element line, mirrors the platform convention):  arc-x-c-allow

Usage:  python tools/validate_arc_x_cfamily.py [--json]
Output: arc_x_cfamily_report.json  (machine-readable denominator + per-type lists)
This is a SCANNER (always exit 0) - the ratchet/teeth live in
validate_arc_x_cognitive.py once a type is driven to floor and locked.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "arc_x_cfamily_report.json"
BASELINE = ROOT / "arc_x_baseline.json"


def _c1_exempt() -> dict:
    """page#id -> reason for the C1 candidates that adversarial classification
    confirmed are NOT recall-dependent (definition-of-own-identity / NL-note /
    live-filter). Loaded from arc_x_baseline.json so the exemption set is
    auditable + version-controlled, not buried in the scanner."""
    try:
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for e in base.get("c1_exempt", []):
        out[f'{e["page"]}#{e.get("id","")}'] = e.get("reason", "")
    return out

# ---- input types that are NOT free-text data fields (no placeholder-label concern) ----
NON_TEXT_TYPES = {"hidden", "checkbox", "radio", "range", "file", "color",
                  "submit", "button", "reset", "image"}

# ---- C1: enumerable-entity keywords that imply "recall an exact identifier" ----
ENTITY_RX = re.compile(
    r"\b(asset(?:\s*tag)?|equipment|machine|part\s*(?:no|number|#)?|sku|"
    r"work[\s-]*order|wo\s*#|technician|assignee|assigned\s*to|supplier|vendor|"
    r"serial\s*(?:no|number)?|model\s*(?:no|number)?)\b", re.IGNORECASE)
# things that mean "this is a live filter / recognition search", excluded from C1
FILTER_RX = re.compile(r"\b(search|filter|find|lookup|query)\b", re.IGNORECASE)

INPUT_RX = re.compile(r"<(input|textarea)\b([^>]*)>", re.IGNORECASE)
ATTR_RX  = lambda name: re.compile(name + r'\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)
PLACEHOLDER_RX = ATTR_RX("placeholder")
ARIA_LABEL_RX  = re.compile(r'\baria-label(?:ledby)?\s*=\s*["\'][^"\']', re.IGNORECASE)
ID_RX    = ATTR_RX("id")
TYPE_RX  = ATTR_RX("type")
LIST_RX  = re.compile(r'\blist\s*=\s*["\']', re.IGNORECASE)
ROLE_COMBO_RX = re.compile(r'\brole\s*=\s*["\']combobox', re.IGNORECASE)


def _attr(tag: str, rx) -> str | None:
    m = rx.search(tag)
    return m.group(2) if m else None


def _has_label_for(body: str, input_id: str) -> bool:
    if not input_id:
        return False
    return re.search(r'<label\b[^>]*\bfor\s*=\s*["\']' + re.escape(input_id) + r'["\']',
                     body, re.IGNORECASE) is not None


def _wrapped_in_label(body: str, start: int) -> bool:
    """True if the input at `start` sits inside a <label>...</label> (the label
    opens before it and closes after it with no intervening </label>)."""
    before = body[:start]
    last_open = before.rfind("<label")
    if last_open == -1:
        return False
    last_close = before.rfind("</label>")
    return last_open > last_close  # an unclosed <label> is open around us


def _pages() -> list[Path]:
    out = []
    for p in sorted(ROOT.glob("*.html")):
        n = p.name.lower()
        if n.startswith("_"): continue
        if "backup" in n or ".bak" in n or n.endswith("-test.html") or n.endswith(".old.html"): continue
        out.append(p)
    return out


def scan_page(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    c2, c1 = [], []
    for m in INPUT_RX.finditer(body):
        tag = m.group(0)
        attrs = m.group(2)
        line_window = body[max(0, m.start()-2): m.end()+2]
        if "arc-x-c-allow" in body[max(0, m.start()-160): m.end()+160]:
            continue
        itype = (_attr(tag, TYPE_RX) or "text").lower()
        if m.group(1).lower() == "input" and itype in NON_TEXT_TYPES:
            continue
        placeholder = _attr(tag, PLACEHOLDER_RX)
        input_id = _attr(tag, ID_RX) or ""
        has_aria = bool(ARIA_LABEL_RX.search(tag))
        has_label = has_aria or _has_label_for(body, input_id) or _wrapped_in_label(body, m.start())
        line_no = body.count("\n", 0, m.start()) + 1

        # ---- C2: placeholder present, no persistent accessible name ----
        if placeholder and not has_label:
            c2.append({"page": path.name, "line": line_no, "id": input_id,
                       "placeholder": placeholder[:60], "tag": tag[:140]})

        # ---- C1: entity-naming free-text ENTRY field with no picker ----
        if itype in ("text", "", "search") or m.group(1).lower() == "textarea":
            haystack = " ".join(filter(None, [placeholder, input_id,
                                              _attr(tag, re.compile(r'name\s*=\s*(["\'])(.*?)\1'))]))
            if (ENTITY_RX.search(haystack) and not FILTER_RX.search(haystack)
                    and itype != "search"
                    and not LIST_RX.search(tag) and not ROLE_COMBO_RX.search(tag)):
                c1.append({"page": path.name, "line": line_no, "id": input_id,
                           "placeholder": (placeholder or "")[:60], "tag": tag[:140]})
    return {"c2": c2, "c1": c1}


def main() -> int:
    pages = _pages()
    exempt = _c1_exempt()
    all_c2, all_c1 = [], []
    for p in pages:
        r = scan_page(p)
        all_c2.extend(r["c2"]); all_c1.extend(r["c1"])

    # split raw C1 candidates into verified-exempt vs real (un-triaged) violations
    c1_real, c1_exempt_hits = [], []
    for s in all_c1:
        key = f'{s["page"]}#{s["id"]}'
        if key in exempt:
            c1_exempt_hits.append({**s, "exempt_reason": exempt[key]})
        else:
            c1_real.append(s)

    report = {
        "arc": "X", "family": "C", "scanner": "arc_x_cfamily",
        "pages_scanned": len(pages),
        "c2_placeholder_as_label": {"count": len(all_c2), "sites": all_c2},
        "c1_recall_entity_input":  {
            "raw_candidates": len(all_c1),
            "exempt": len(c1_exempt_hits),
            "real_violations": len(c1_real),
            "sites_real": c1_real,
            "sites_exempt": c1_exempt_hits,
        },
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 0

    print("\nArc X - Family C (Recall vs Recognition) Scanner")
    print("=" * 60)
    print(f"  pages scanned:              {len(pages)}")
    print(f"  C2 placeholder-as-label:    {len(all_c2)}")
    print(f"  C1 raw candidates:          {len(all_c1)}  (exempt {len(c1_exempt_hits)} · REAL {len(c1_real)})")
    print("\n  -- C2 violations --")
    for i in all_c2:
        print(f"    {i['page']}:{i['line']}  id={i['id'] or '(none)'}  ph={i['placeholder']!r}")
    if not all_c2:
        print("    (none)")
    print("\n  -- C1 REAL violations (un-triaged, need a picker) --")
    for i in c1_real:
        print(f"    {i['page']}:{i['line']}  id={i['id'] or '(none)'}  ph={i['placeholder']!r}")
    if not c1_real:
        print("    (none — all candidates fixed or classified-exempt)")

    # Ratchet at floor: C2 placeholder-as-label and un-triaged C1 are both at 0.
    # Any regression (a new placeholder-only input, or a new entity-naming free-text
    # field with no picker AND no exemption) FAILS. New C1 candidates are not silently
    # ignored - they must be triaged (fixed with a picker, or added to c1_exempt with
    # a reason) before this passes again.
    fail = len(all_c2) > 0 or len(c1_real) > 0
    if fail:
        print(f"\n  FAIL — C2={len(all_c2)} (floor 0) · C1 real={len(c1_real)} (floor 0). "
              f"Fix or triage the new site(s) above.")
    else:
        print(f"\n  PASS — C2 at floor (0) · C1 real at floor (0, {len(c1_exempt_hits)} classified-exempt).")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
