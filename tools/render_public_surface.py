#!/usr/bin/env python3
"""
render_public_surface.py — Content Grounding Gate, D1 "derive-and-render".

The outward surfaces (index.html landing, llms.txt, the learn hub) carry FACTS
about the platform — guide/tool counts, article + feature lists, the JSON-LD
featureList, the FAQ/HowTo blocks — that are hand-typed and silently rot. (D0 found
index.html claiming "24 in-depth guides" on one line while linking to "38 guides"
on another.) This renders those facts FROM the auto-derived Platform Catalog
(platform_catalog.py / platform_catalog.json) into MARKER REGIONS, so a fact can
no longer drift: the page is regenerated from the catalog, not hand-kept.

This is the OUTWARD twin of the inward `v_*_truth` canonical-view move: one source
of truth, every surface renders from it.

Marker syntax — an HTML comment pair, valid (and invisible) in .html AND harmless
as literal text in the .txt surfaces:

    <!--CATALOG:guide_count-->38<!--/CATALOG:guide_count-->

The engine ONLY ever rewrites the bytes BETWEEN a matched marker pair. It never
edits prose, never touches an unmarked byte, and is idempotent. A marker whose key
is unknown, or whose inner text != the catalog value, is "render drift" — surfaced
by `--check` (exit 1) and by the gate's `surface_render_drift` validator.

CLI:
    python tools/render_public_surface.py            # --check: report drift, exit 1 if any
    python tools/render_public_surface.py --apply     # rewrite the surfaces from the catalog
    python tools/render_public_surface.py --print      # show the rendered value table
    python tools/render_public_surface.py --self-test  # synthetic, live-state-independent
"""

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_catalog as pc  # noqa: E402  (lives beside this file in tools/)

# Surfaces the generator manages (only their marked regions are machine-rendered).
SURFACES = [ROOT / "index.html", ROOT / "llms.txt", ROOT / "learn" / "index.html"]

# A marker pair whose open key == close key (backreference). Inner is non-greedy
# and may span lines (DOTALL) so a marked region can wrap a multi-line block.
REGION_RE = re.compile(r"<!--CATALOG:([a-z0-9_]+)-->(.*?)<!--/CATALOG:\1-->", re.DOTALL)

# stageData popup tool entries — { name: '...', desc: '...', link: '...', icon: ... }.
# (Stage-level `name:` is followed by `quote:`/`label:`, not `desc:`+`link:`, so this
#  matches the per-stage TOOL entries only.) Source of the landing tool catalog.
_STAGE_TOOL_RE = re.compile(
    r"\{\s*name:\s*'((?:\\.|[^'\\])*)'\s*,\s*desc:\s*'((?:\\.|[^'\\])*)'\s*,\s*link:\s*'([^']+)'",
    re.DOTALL)


_META_DESC_RE = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)


def _page_meta_desc(href: str) -> str:
    """A page's own <meta name=description> — used as the catalog mirror's tool
    description when a back-filled (non-stageData) tool has no catalog capability,
    so no tool renders bare (e.g. ai-quality.html). Page is the source of truth."""
    if not href:
        return ""
    m = _META_DESC_RE.search(_read(ROOT / href.strip().lstrip("/")))
    return m.group(1).strip() if m else ""


def _js_unescape(s: str) -> str:
    """Turn a JS single-quoted string literal's body into plain text."""
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def _esc_html(s: str) -> str:
    """Minimal HTML escape for text rendered into the static mirror."""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def parse_landing_tools(html: str) -> list[tuple[str, str, str]]:
    """The landing tool catalog (name, desc, link) parsed from index.html's
    stageData object — the ONE source the popup also reads."""
    out = []
    for name, desc, link in _STAGE_TOOL_RE.findall(html):
        out.append((_js_unescape(name).strip(), _js_unescape(desc).strip(), link.strip()))
    return out


def build_tool_catalog_mirror(cat: dict, html: str) -> str:
    """The crawlable static mirror of the JS tool catalog — a real <a href> + the
    rich description per tool, derived from stageData (so it can't drift from the
    popup) and back-filled with any ACTIVE catalog tool page that stageData omits
    (so every tool page has >=1 crawlable inbound link). Rendered as <li> items;
    the wrapping <ul>/<section> stay static around the marker."""
    # Links are ROOT-ABSOLUTE (/tool.html) — the platform convention: prod serves at
    # root, and the local "dev URL bridge" rewrites root-absolute <a href> to
    # /workhive/… at runtime (validate_prod_path_leak enforces no committed /workhive/).
    tools = parse_landing_tools(html)
    seen_links = {t[2].strip("/").lower() for t in tools}
    lines: list[str] = []
    for name, desc, link in tools:
        # Colon separator (not an em dash) so the rendered mirror satisfies the
        # standing no-em-dash rule ([[feedback-no-em-dashes]] / validate_em_dash).
        sep = ": " if desc else ""
        href = "/" + _esc_html(link.strip("/"))
        lines.append(f'<li><a href="{href}">{_esc_html(name)}{sep}{_esc_html(desc)}</a></li>')
    # Back-fill active catalog tool pages that stageData never links (e.g. ai-quality).
    for f in cat.get("features", []):
        route = (f.get("route") or "").strip()
        if not route or route == "index.html" or f.get("status") != "active":
            continue
        if route.strip("/").lower() in seen_links:
            continue
        nm = _esc_html((f.get("name") or route).strip())
        desc = (f.get("capability") or "").strip() or _page_meta_desc(route)
        desc = _esc_html(desc)
        sep = ": " if desc else ""   # colon, not em dash (no-em-dash rule)
        lines.append(f'<li><a href="/{_esc_html(route.strip("/"))}">{nm}{sep}{desc}</a></li>')
        seen_links.add(route.strip("/").lower())
    return "\n      " + "\n      ".join(lines) + "\n    "


def render_values(cat: dict | None = None) -> dict[str, str]:
    """The single place the catalog → marker-value mapping lives.

    Grows as D1 widens (counts → lists → featureList → FAQ/HowTo). Every value is
    a string; the engine substitutes it verbatim between the marker pair.
    """
    cat = cat or pc.build_catalog()
    counts = cat.get("counts", {})
    vals: dict[str, str] = {}

    # ── Counts (D1 foundational slice) ──
    if counts.get("learn_articles") is not None:
        vals["guide_count"] = str(counts["learn_articles"])

    # ── Landing tool catalog mirror (P2.5: make the JS-locked catalog crawlable) ──
    # Derived from index.html's own stageData, so the static mirror tracks the popup.
    index_html = _read(ROOT / "index.html")
    if index_html and "<!--CATALOG:tool_catalog_mirror-->" in index_html:
        vals["tool_catalog_mirror"] = build_tool_catalog_mirror(cat, index_html)

    return vals


def _regions(text: str) -> list[tuple[str, str]]:
    """Every (key, current_inner) marker region present in text, in order."""
    return [(m.group(1), m.group(2)) for m in REGION_RE.finditer(text)]


def check_text(text: str, values: dict[str, str], label: str = "") -> list[dict]:
    """Return a list of render-drift issues for one surface's text."""
    issues: list[dict] = []
    for key, inner in _regions(text):
        if key not in values:
            issues.append({"surface": label, "key": key, "kind": "unknown_marker",
                           "reason": f"marker '{key}' has no catalog-derived value"})
        elif inner != values[key]:
            issues.append({"surface": label, "key": key, "kind": "render_drift",
                           "reason": f"marker '{key}' renders {inner!r} but the catalog says {values[key]!r}"})
    return issues


def apply_text(text: str, values: dict[str, str]) -> str:
    """Return text with every KNOWN marker region rewritten to the catalog value.
    Unknown-key markers are left exactly as-is (reported by check, never silently
    blanked)."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            return m.group(0)
        return f"<!--CATALOG:{key}-->{values[key]}<!--/CATALOG:{key}-->"
    return REGION_RE.sub(repl, text)


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def check(values: dict[str, str] | None = None) -> list[dict]:
    """Check every surface on disk. Returns all render-drift issues."""
    values = values if values is not None else render_values()
    issues: list[dict] = []
    for path in SURFACES:
        if not path.exists():
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        issues.extend(check_text(_read(path), values, label=rel))
    return issues


def apply(values: dict[str, str] | None = None) -> list[str]:
    """Rewrite every surface's marked regions from the catalog. Returns the list
    of surfaces actually changed."""
    values = values if values is not None else render_values()
    changed: list[str] = []
    for path in SURFACES:
        if not path.exists():
            continue
        old = _read(path)
        new = apply_text(old, values)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return changed


# ── Self-test (synthetic, live-state-INDEPENDENT — lesson from the gate's own
#    teeth test that broke when live drift was healed) ───────────────────────────

def self_test() -> int:
    fails = 0

    def ck(cond: bool, msg: str):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mrender_public_surface.py --self-test\033[0m")
    print("=" * 55)

    values = {"guide_count": "38"}

    # Drift: inner != value is flagged.
    drifted = "See all <!--CATALOG:guide_count-->24<!--/CATALOG:guide_count--> guides"
    iss = check_text(drifted, values, "synthetic")
    ck(len(iss) == 1 and iss[0]["kind"] == "render_drift", "check FLAGS a stale marker (24 != 38)")

    # Apply heals it, idempotently.
    healed = apply_text(drifted, values)
    ck("<!--CATALOG:guide_count-->38<!--/CATALOG:guide_count-->" in healed, "apply rewrites the region to the catalog value")
    ck(check_text(healed, values, "synthetic") == [], "healed text has zero drift")
    ck(apply_text(healed, values) == healed, "apply is idempotent (no churn on a clean surface)")

    # Prose outside the marker is untouched.
    ck("See all " in healed and " guides" in healed, "prose outside the marker is preserved verbatim")

    # Unknown marker key is reported, never silently blanked.
    unknown = "<!--CATALOG:mystery_key-->x<!--/CATALOG:mystery_key-->"
    ui = check_text(unknown, values, "synthetic")
    ck(len(ui) == 1 and ui[0]["kind"] == "unknown_marker", "unknown marker key is flagged")
    ck(apply_text(unknown, values) == unknown, "unknown marker key is left as-is by apply")

    # The live catalog renders a numeric guide_count (sanity, but not the assertion subject).
    live = render_values()
    ck(live.get("guide_count", "").isdigit(), "live catalog yields a numeric guide_count")

    print("=" * 55)
    if fails == 0:
        print("\033[92m  self-test PASS\033[0m\n")
    else:
        print(f"\033[91m  self-test FAIL — {fails} check(s) failed\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if "--print" in argv:
        for k, v in render_values().items():
            print(f"  {k:20s} = {v}")
        return 0
    if "--apply" in argv:
        changed = apply()
        if changed:
            print("rendered surfaces from catalog:")
            for c in changed:
                print(f"  • {c}")
        else:
            print("no change — all marked regions already match the catalog.")
        return 0
    # default: --check
    issues = check()
    if not issues:
        print("surface render: CLEAN — every marked region matches the catalog.")
        return 0
    print(f"surface render DRIFT — {len(issues)} region(s) out of sync:")
    for i in issues:
        print(f"  • [{i['surface']}] {i['reason']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
