"""
Arc X - Family B (Choice & Navigation) + E (Feedback & Recovery) SCANNER  [HARD]
================================================================================
Deterministic enumeration of the X3 HARD defect types across the feature-page
set, so X3 is driven by a MEASURED %, not vibes. See COGNITIVE_LOAD_II_ROADMAP.md
Families B + E. (B2-icon-only and aria coverage already live in
validate_icon_button_label.py / validate_aria_label_coverage.py - REUSED, not
re-implemented here. This scanner owns the UN-covered axes.)

  B2  Low information scent  [HARD half]
        A link/button whose ENTIRE visible text is a contentless phrase
        (more / details / here / click here / read more / learn more / view / go /
        see more / show more / continue) with NO object noun and NO aria-label.
        The label doesn't predict its target -> the user must click to find out
        (NN/g info-scent; Krug "don't make me think"). Fix = action+object label.

  B3  Dead-end / no next step  [HARD]
        A rendered EMPTY-STATE / success container (id|class ~ empty-state /
        no-results / .empty / "success") that contains ZERO interactive control
        (no <button>/<a>/role=button inside). A terminal state with nothing to do
        next strands the user (NN/g; GDS one-thing-per-page -> always a next step).
        Fix = every terminal/empty state gets a "what's next" CTA.

  E3  Destructive action without recovery  [HARD]
        A control whose label/handler is destructive (delete / remove / discard /
        clear / wipe) with NO confirm() AND no undo affordance nearby (no
        confirm(, no 'undo' text, no data-confirm). Fix = confirm or undo-toast.

Exemption (per element line):  arc-x-be-allow

Usage:  python tools/validate_arc_x_befamily.py [--json]
Output: arc_x_befamily_report.json
Ratchets at the frozen baseline (exit 1 only on a count ABOVE baseline) so a
newly-surfaced site must be fixed or exempted, but the existing backlog doesn't
block while it's being driven down.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "arc_x_befamily_report.json"
BASELINE = ROOT / "arc_x_befamily_baseline.json"

# ---- B2: contentless link/button labels (full visible text equals one of these) ----
GENERIC_LABELS = {
    "more", "more...", "more…", "details", "details...", "view", "view more",
    "view details", "see", "see more", "see details", "show more", "read more",
    "learn more", "here", "click here", "click", "go", "continue", "open",
    "this", "this link", "link", "read", "find out more", "get started here",
}

A_OR_BUTTON_RE = re.compile(r"<(a|button)\b([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
SVG_RE   = re.compile(r"<svg\b[^>]*>.*?</svg>", re.IGNORECASE | re.DOTALL)
TAG_RE   = re.compile(r"<[^>]+>")
ARIA_RE  = re.compile(r"\baria-label(?:ledby)?\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE)
WS_RE    = re.compile(r"\s+")
ARROWS   = "→›»▸▾▼↓➜➔⟶‹←—–-·•|"

# ---- E3: destructive verbs in a control's text/handler ----
DESTRUCTIVE_RE = re.compile(
    r"\b(delete|remove|discard|wipe|erase|destroy|permanently)\b", re.IGNORECASE)
RECOVERY_RE = re.compile(r"confirm\s*\(|data-confirm|\bundo\b|areYouSure|are you sure|"
                         r"openConfirm|confirmModal|window\.confirm|showConfirm|confirmThen|"
                         r"confirmDialog|\?\s*['\"]|class=['\"][^'\"]*confirm", re.IGNORECASE)
# things that are NOT data-destructive (UI reset / closes a panel / removes an UNSAVED form item)
NOT_DESTRUCTIVE_RE = re.compile(
    r"\b(clear\s+filters?|reset\s+filters?|clear\s+all\s+filters?|close|dismiss|cancel|"
    r"clear\s+search|remove\s+photo|remove\s+image|remove\s+from\s+watchlist)\b|"
    r"watch-remove|toggleWatchlist|\bwatchlist\b",   # a watchlist toggle is REVERSIBLE (re-add = 1 click) -> confirm = confirm-fatigue
    re.IGNORECASE)
ONCLICK_FN_RE = re.compile(r"on(?:click|change|submit)\s*=\s*['\"]\s*([A-Za-z_$][\w$]*)\s*\(", re.IGNORECASE)


def _handler_body(body: str, fn: str) -> str:
    """Best-effort: return ~1800 chars of the named function's definition so we can
    see whether the destructive handler itself confirms/undoes (the confirm rarely
    sits inline on the button; it lives in the handler)."""
    for pat in (r"function\s+" + re.escape(fn) + r"\s*\(",
                r"\b" + re.escape(fn) + r"\s*=\s*(?:async\s*)?(?:function|\()",
                r"\b" + re.escape(fn) + r"\s*\([^)]*\)\s*\{"):
        m = re.search(pat, body)
        if m:
            return body[m.start(): m.start() + 1800]
    return ""


def _visible_text(inner_html: str) -> str:
    t = SVG_RE.sub(" ", inner_html)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.DOTALL)
    t = TAG_RE.sub(" ", t)
    t = t.replace("&amp;", "&").replace("&nbsp;", " ")
    t = "".join(ch for ch in t if ch not in ARROWS)
    return WS_RE.sub(" ", t).strip()


def _pages() -> list[Path]:
    out = []
    for p in sorted(ROOT.glob("*.html")):
        n = p.name.lower()
        if n.startswith("_"): continue
        if "backup" in n or ".bak" in n or n.endswith("-test.html") or n.endswith(".old.html"): continue
        out.append(p)
    return out


def scan_b2(path: Path, body: str) -> list:
    hits = []
    for m in A_OR_BUTTON_RE.finditer(body):
        attrs, inner = m.group(2), m.group(3)
        seg = body[max(0, m.start()-160): m.end()+160]
        if "arc-x-be-allow" in seg:
            continue
        if ARIA_RE.search(attrs):           # aria-label supplies the scent
            continue
        if 'title="' in attrs.lower():       # tooltip supplies some scent (weak, but not contentless)
            continue
        vt = _visible_text(inner).lower().rstrip(".… ")
        if not vt:                           # icon-only -> covered by validate_icon_button_label
            continue
        if vt in GENERIC_LABELS:
            hits.append({"page": path.name,
                         "line": body.count("\n", 0, m.start()) + 1,
                         "tag": m.group(1).lower(), "text": _visible_text(inner)[:40]})
    return hits


# ---- B3: empty-state / terminal container with no next-step control ----
# Top-level empty-state CONTAINERS (not sub-fragments like empty-row/empty-title/empty-icon).
EMPTY_OPEN_RE = re.compile(
    r'<(div|section)\b[^>]*\b(?:id|class)\s*=\s*["\'][^"\']*'
    r'(?:\bempty-state\b|\bno-results\b|\bhonest-empty\b)[^"\']*["\'][^>]*>',
    re.IGNORECASE)
# NOT a dead-end (narrowed with evidence, §4):
#  - intentional maturity/honest-empty blank (CTA-less BY DESIGN -
#    feedback_platform_intentional_blank_states)
#  - FILTERED-empty: the filter/search controls ARE the visible recovery, on-page
#  - LOADING skeletons (transient, not a terminal state)
#  - SUCCESS / all-clear (terminal BY DESIGN - the user WANTS nothing to do)
INTENTIONAL_RE = re.compile(
    r"honest-empty|maturity|come back|not enough (data|history)|check back|once you|"
    r"as you log|gathering data|"                                   # intentional maturity
    r"match (those|your) (filters?|search)|no results|no rows match|no items match|"
    r"no entries match|no posts match|no listings match|no .{0,20} match|"           # filtered
    r"skel\b|skeleton|skel-pulse|\bloading\b|spinner|"              # loading
    r"all clear|all caught up|all set|nothing to review|you'?re all|no flagged",  # success
    re.IGNORECASE)
CTA_IN_RE = re.compile(r"<button\b|<a\b[^>]*\bhref|role=['\"]button|onclick=|data-(?:open|add|new|cta)",
                       re.IGNORECASE)


def _container_inner(body: str, open_match) -> str:
    """Approximate the container's inner HTML by walking balanced <div>/<section>
    tags from the open tag. Caps at 1400 chars (empty states are small)."""
    start = open_match.end()
    depth = 1
    i = start
    tag_iter = re.compile(r"</?(?:div|section)\b", re.IGNORECASE)
    cap = min(len(body), start + 1400)
    for m in tag_iter.finditer(body, start, cap):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return body[start:m.start()]
    return body[start:cap]


def scan_b3(path: Path, body: str) -> list:
    hits = []
    for m in EMPTY_OPEN_RE.finditer(body):
        seg = body[max(0, m.start()-80): m.end()+80]
        if "arc-x-be-allow" in body[max(0, m.start()-160): m.end()+1400]:
            continue
        inner = _container_inner(body, m)
        ctx = m.group(0) + " " + inner
        if INTENTIONAL_RE.search(ctx):            # intentional maturity/honest-empty blank
            continue
        if CTA_IN_RE.search(inner):               # already has a next-step control
            continue
        hits.append({"page": path.name,
                     "line": body.count("\n", 0, m.start()) + 1,
                     "snippet": WS_RE.sub(" ", inner)[:90]})
    return hits


# ---- E2: an inline validation-error element a screen reader never announces ----
# An error region (id="...-error") is "announced" if EITHER a field points at it via
# aria-describedby (field-level error - WCAG 3.3.1) OR it carries role="alert" /
# aria-live (form-level error - announced when populated, WCAG 4.1.3). An error with
# NEITHER is silent to assistive tech = the user can't tell what went wrong (E2 structural).
ERROR_EL_RE = re.compile(
    r'<(?:div|span|p)\b([^>]*\bid\s*=\s*["\']([\w-]*(?:error|err)[\w-]*)["\'][^>]*)>',
    re.IGNORECASE)
ANNOUNCE_RE = re.compile(r'role\s*=\s*["\']alert|aria-live\s*=', re.IGNORECASE)


def scan_e2(path: Path, body: str) -> list:
    hits = []
    for m in ERROR_EL_RE.finditer(body):
        attrs, eid = m.group(1), m.group(2)
        # section-level page banners / detail panels aren't per-form field validation.
        if re.search(r"section|detail|banner|page|global|toast", eid, re.IGNORECASE):
            continue
        if "arc-x-be-allow" in body[max(0, m.start()-160): m.end()+160]:
            continue
        if ANNOUNCE_RE.search(attrs):        # form-level error announced via role=alert/aria-live
            continue
        if re.search(r'aria-describedby\s*=\s*["\'][^"\']*' + re.escape(eid), body, re.IGNORECASE):
            continue                          # field-level error tied to its input
        hits.append({"page": path.name,
                     "line": body.count("\n", 0, m.start()) + 1, "error_id": eid})
    return hits


def scan_e3(path: Path, body: str) -> list:
    hits = []
    for m in A_OR_BUTTON_RE.finditer(body):
        attrs, inner = m.group(2), m.group(3)
        seg = body[max(0, m.start()-200): m.end()+400]
        if "arc-x-be-allow" in seg:
            continue
        label = _visible_text(inner)
        hay = label + " " + attrs
        if not DESTRUCTIVE_RE.search(hay):
            continue
        if NOT_DESTRUCTIVE_RE.search(hay):       # UI reset / close / unsaved-form-item / watchlist
            continue
        if RECOVERY_RE.search(seg):              # confirm/undo right at the control
            continue
        # follow the named onclick handler - the confirm usually lives in its body
        fn_m = ONCLICK_FN_RE.search(attrs)
        if fn_m and RECOVERY_RE.search(_handler_body(body, fn_m.group(1))):
            continue
        hits.append({"page": path.name,
                     "line": body.count("\n", 0, m.start()) + 1,
                     "label": label[:40], "handler": (fn_m.group(1) if fn_m else ""),
                     "attrs": attrs[:80]})
    return hits


def main() -> int:
    pages = _pages()
    b2, b3, e2, e3 = [], [], [], []
    for p in pages:
        raw = p.read_text(encoding="utf-8", errors="replace")
        body = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
        b2 += scan_b2(p, body)
        b3 += scan_b3(p, body)
        e2 += scan_e2(p, body)
        e3 += scan_e3(p, body)

    report = {
        "arc": "X", "family": "B+E", "scanner": "arc_x_befamily",
        "pages_scanned": len(pages),
        "b2_low_scent_label":   {"count": len(b2), "sites": b2},
        "b3_dead_end_no_cta":   {"count": len(b3), "sites": b3},
        "e2_error_not_field_tied": {"count": len(e2), "sites": e2},
        "e3_destructive_no_recovery": {"count": len(e3), "sites": e3},
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 0

    print("\nArc X - Family B+E (Choice/Nav + Feedback/Recovery) Scanner")
    print("=" * 62)
    print(f"  pages scanned:               {len(pages)}")
    print(f"  B2 low-information-scent:    {len(b2)}")
    print(f"  B3 dead-end (no next CTA):   {len(b3)}")
    print(f"  E2 error not field-tied:     {len(e2)}")
    print(f"  E3 destructive-no-recovery:  {len(e3)}")
    print("\n  -- B2 low-scent labels --")
    for i in b2:
        print(f"    {i['page']}:{i['line']}  <{i['tag']}> {i['text']!r}")
    if not b2: print("    (none)")
    print("\n  -- B3 dead-end empty/terminal states (no next-step CTA) --")
    for i in b3:
        print(f"    {i['page']}:{i['line']}  {i['snippet']!r}")
    if not b3: print("    (none)")
    print("\n  -- E3 destructive without confirm/undo --")
    for i in e3:
        print(f"    {i['page']}:{i['line']}  {i['label']!r}")
    if not e3: print("    (none)")

    # GATE only on B2 - the one type this scanner can verify with zero false negatives
    # (an aria-label / object-bearing label is a DOM fact). B3 + E3 raw counts are
    # INFORMATIONAL candidate lists: B3 needs per-site triage (dashboard-maturity vs
    # genuine dead-end) and E3's confirms often live in DELEGATED handlers this static
    # follower can't trace - their VERIFIED locks live in validate_arc_x_cognitive.py
    # (b2_fixed / e3_fixed presence-guards) + arc_x_baseline.json (e3_triage / b3 records).
    print(f"\n  B3/E3 counts are informational candidate lists (verified locks in the HARD gate).")
    # GATE on B2 + E2 - the two types this scanner verifies with zero false negatives
    # (an aria-label / object-bearing label, and role=alert/aria-describedby on an error,
    # are DOM facts). B3 (needs maturity-vs-deadend triage) and E3 (delegated-handler
    # confirms this static follower can't trace) stay informational; their verified locks
    # live in validate_arc_x_cognitive.py + arc_x_baseline.json.
    fail = len(b2) > 0 or len(e2) > 0
    if not fail:
        print(f"  PASS - B2 information-scent (0) + E2 silent-errors (0) at floor.")
        return 0
    print(f"  FAIL - B2={len(b2)} (floor 0) · E2={len(e2)} (floor 0): re-fix or exempt the new site(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
