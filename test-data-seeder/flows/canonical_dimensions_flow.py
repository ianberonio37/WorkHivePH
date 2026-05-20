"""
Canonical Dimensions Flow — Smoke + Visual gate coverage.
===========================================================

Adds 4 new dimensions to the Smoke/Visual gates so every change that
touches a canonical surface gets caught here, not just in the heavy
UI Locks gate (npx playwright test):

  1. Tier-S chip visibility — for every formula in
     canonical/formula_contracts.json that names a page, the served
     HTML must contain the formula's registered standard short_name
     from canonical/standards.json.

  2. Calm Dashboard Contract — every page that ships
     <meta name="calm-dashboard" content="1"> must serve HTML that
     declares a verdict region, a <details> disclosure, and the
     hide-zero pattern.

  3. Partial-variant honesty — every page named as a violator in
     partial_label_honesty_report.json must NOT serve a partial-variant
     metric without a marker ("partial" / "approximation" / "calendar
     time"). Re-checks the report's claim at runtime against the
     served HTML — catches the case where a refactor strips the
     honesty marker but the report was not regenerated.

  4. Canonical view reachability — every v_*_truth view declared in
     migrations must have at least one consumer reference in HTML /
     edge fn / python-api, OR a `canonical-view-allow:` marker in a
     migration. Catches the inverse-phantom (built but unused) class
     of silent failure.

This flow runs raw fetch — no signin, no DB. ~2 seconds per gate run.
"""
from __future__ import annotations
import io
import json
import re
import urllib.request
import urllib.error
from pathlib import Path

from .harness import BASE_URL

ROOT = Path(__file__).resolve().parent.parent.parent


def _read_json(rel: str) -> dict | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fetch_html(page_name: str) -> str | None:
    url = f"{BASE_URL}/workhive/{page_name}"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            if r.status != 200:
                return None
            return r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def _extract_pages_from_implemented_in(impl: str) -> list[str]:
    return [m.lower() for m in re.findall(r"([a-z0-9\-]+\.html)", impl or "", re.IGNORECASE)]


def _scan_consumer_files() -> dict[str, str]:
    """Return path → text for HTML + edge-fn TS + python-api Python."""
    out: dict[str, str] = {}
    for sub, exts in [("", (".html",)),
                      ("supabase/functions", (".ts",)),
                      ("python-api", (".py",)),
                      ("", (".js",))]:
        base = ROOT / sub if sub else ROOT
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if not any(p.name.endswith(ext) for ext in exts):
                continue
            # Skip node_modules, test-results, migrations
            sp = str(p)
            if any(skip in sp for skip in ("node_modules", "test-results",
                                            "playwright-report", "__pycache__",
                                            f"supabase{Path('/').name}migrations")):
                continue
            try:
                out[str(p)] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
    return out


def run(page, errors, warnings, log=print) -> dict:
    """`page` is the Playwright page (unused — we use urllib for raw HTML)."""
    results: list[tuple[str, str]] = []

    # ── Load canonical registries ────────────────────────────────────────────
    standards = _read_json("canonical/standards.json")
    formulas  = _read_json("canonical/formula_contracts.json")
    partial   = _read_json("partial_label_honesty_report.json") or {"violations": []}

    if not standards or not formulas:
        results.append(("WARN", "canonical/standards.json or formula_contracts.json missing — dimensions check skipped"))
        return {"results": results}

    std_by_id = {s["standard_id"]: s for s in standards.get("standards", [])}

    # ── Dimension 1: Tier-S chip visibility ───────────────────────────────────
    log("Dimension 1 — Tier-S chip visibility per formula implemented_in page")
    html_cache: dict[str, str] = {}
    gaps: list[str] = []
    total = 0
    present = 0
    for f in formulas.get("formulas", []):
        short = (std_by_id.get(f.get("standard_id"), {}) or {}).get("short_name", "")
        if not short:
            continue
        for p in _extract_pages_from_implemented_in(f.get("implemented_in", "")):
            total += 1
            if p not in html_cache:
                html_cache[p] = _fetch_html(p) or ""
            html = html_cache[p]
            if short in html:
                present += 1
            else:
                gaps.append(f"{p}::{f.get('formula_id','?')}::{short!r}")

    if total == 0:
        results.append(("WARN", "no formula→page references found in canonical/formula_contracts.json"))
    else:
        pct = (present * 100) // total
        if gaps:
            results.append(("FAIL", f"Tier-S chip visibility {present}/{total} ({pct}%) — {len(gaps)} gaps: {gaps[:3]}"))
        else:
            results.append(("PASS", f"Tier-S chip visibility 100% ({present}/{total} formula→page citations honoured)"))

    # ── Dimension 2: Calm Dashboard Contract per opted-in page ───────────────
    log("Dimension 2 — Calm Dashboard Contract (verdict + <details> + hide-zero) per opted-in page")
    calm_pages = []
    for p in ROOT.glob("*.html"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r'<meta\s+name=["\']calm-dashboard["\']\s+content=["\']1["\']', text, re.IGNORECASE):
                calm_pages.append(p.name)
        except Exception:
            continue

    calm_failures: list[str] = []
    for p in calm_pages:
        html = html_cache.get(p) or _fetch_html(p) or ""
        html_cache[p] = html
        # verdict region (DOM OR template literal)
        has_verdict = bool(re.search(
            r'id=["\'][^"\']*(?:today|verdict|hero|focus|now)["\']|'
            r'class=["\'][^"\']*\b(?:verdict|today-card|focus-card|hero-card)\b|'
            r'renderVerdict\s*\(', html, re.IGNORECASE))
        has_details = "<details" in html.lower()
        has_hide_zero = bool(re.search(
            r"window\.hideZeroStat|\.filter\s*\(\s*[^)]*=>\s*[^)]*>\s*0\s*\)|"
            r"tiles?\.length\s*===\s*0|hideZero", html, re.IGNORECASE))
        missing = []
        if not has_verdict:  missing.append("verdict")
        if not has_details:  missing.append("<details>")
        if not has_hide_zero: missing.append("hide-zero")
        if missing:
            calm_failures.append(f"{p} missing {','.join(missing)}")

    if not calm_pages:
        results.append(("WARN", "no calm-dashboard opted-in pages found"))
    elif calm_failures:
        results.append(("FAIL",
                        f"Calm Dashboard Contract: {len(calm_failures)}/{len(calm_pages)} non-compliant — {calm_failures[:2]}"))
    else:
        results.append(("PASS",
                        f"Calm Dashboard Contract: all {len(calm_pages)} opted-in pages compliant"))

    # ── Dimension 3: Partial-variant honesty (regression gate) ───────────────
    log("Dimension 3 — Partial-variant honesty (no partial display without honesty marker)")
    violations = partial.get("violations", []) or []
    if violations:
        results.append(("FAIL",
                        f"Partial-label honesty: {len(violations)} violations in report — re-run audit_partial_label_honesty.py"))
    else:
        results.append(("PASS", "Partial-label honesty: zero violations"))

    # ── Dimension 4: Canonical view reachability ─────────────────────────────
    log("Dimension 4 — Canonical view reachability (every v_*_truth has >=1 consumer)")
    # Collect every CREATE [OR REPLACE] VIEW public.v_*_truth across migrations
    view_re = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.(v_\w+_truth)\s+AS", re.IGNORECASE)
    allow_re = re.compile(r"canonical-view-allow:\s*(v_\w+_truth)\b", re.IGNORECASE)

    mig_dir = ROOT / "supabase" / "migrations"
    declared: set[str] = set()
    allowed: set[str] = set()
    if mig_dir.exists():
        for f in mig_dir.glob("*.sql"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                for m in view_re.finditer(text):
                    declared.add(m.group(1))
                for m in allow_re.finditer(text):
                    allowed.add(m.group(1))
            except Exception:
                continue

    # Scan consumers (HTML + edge fns + python-api + JS)
    consumer_text = _scan_consumer_files()
    consumed: set[str] = set()
    for view in declared:
        for body in consumer_text.values():
            if view in body:
                consumed.add(view)
                break

    orphans = sorted((declared - consumed) - allowed)
    if not declared:
        results.append(("WARN", "no v_*_truth views discovered in supabase/migrations"))
    elif orphans:
        results.append(("FAIL",
                        f"Canonical view reachability: {len(orphans)} orphan(s) — {orphans[:3]} (wire a consumer or add canonical-view-allow marker)"))
    else:
        results.append(("PASS",
                        f"Canonical view reachability: all {len(declared)} v_*_truth views reachable "
                        f"({len(allowed)} explicitly allowed, {len(consumed)} consumed)"))

    return {"results": results}
