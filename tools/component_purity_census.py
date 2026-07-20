#!/usr/bin/env python3
"""
component_purity_census.py — PLATFORM_CENTRALIZATION_ROADMAP C-P0 (Axis 2 · Purity).

Measures how many RAW brand literals live in the shared-chrome SSOT files — a canonical
component that hardcodes `#F7A21B` / `Poppins` instead of `var(--wh-*)` is a hidden drift
source (change the token, the "canonical" component doesn't follow). This is the
"affected detection" the monorepo evidence named: it maps token→consumers so a token
change is safe.

FALLBACK-AWARE (the design note the 2026-07-20 measurement surfaced): the shared chrome
loads tokens.css ASYNC, so it MUST use `var(--wh-orange, #F7A21B)` — a token WITH a hex
fallback — to avoid a first-paint colour flash. That fallback hex is PURE (the token drives
it once loaded; the literal is only the async-load safety net). So this census counts only
RAW hex/Poppins that are NOT inside a var() fallback. Converting a raw `#F7A21B` to
`var(--wh-orange, #F7A21B)` correctly DROPS the impurity count.

Modes:
  (default)  print the per-file board + totals.
  --check    forward-only ratchet vs component_purity_baseline.json: FAIL if impurity ROSE
             (drift up) on any file; auto-tighten the baseline downward on an improvement.
  --write-baseline   (re)write the baseline from the current measurement.
"""
import io
import re
import sys
import json
import argparse
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "component_purity_baseline.json"

# The shared-chrome SSOT file set (Frontend layer — the highest backlog-coupling surfaces,
# per the Fowler evidence: injected on ~30 pages, so a token change here has max blast radius).
# GROWS as other layers open (C-P4 cross-cutting SSOTs, etc.).
SSOT_FILES = [
    "nav-hub.js", "companion-launcher.js", "wh-feedback-fab.js", "connectivity-widget.js",
    "voice-handler.js", "wh-persona.js", "wh-tts.js", "wh-patterns.js",
    "offline-queue.js", "session-timeout.js", "form-autosave.js", "device-fingerprint.js",
    "wayfinding.js", "search-overlay.js", "learn-link.js",
    "wh-help.js", "onboarding.js", "provenance-hover.js", "utils.js",
    "components.css",
]

# Brand hex that HAVE a token in tokens.css :root — a raw one is impure (a token exists for it).
TOKEN_HEX = [
    "F7A21B", "FDB94A", "D88A0E",           # orange / -light / -dark
    "162032", "1F2E45", "2A3D58",           # navy / -mid / -light
    "29B6D9", "1A9ABF", "5FCCE8",           # blue / -dark / -light
    "4ade80", "f87171", "facc15", "a78bfa", # green / red / amber / violet
    # Neutrals + text tints (expansion 2026-07-20) — also canonical tokens.
    "F4F6FA", "7B8794", "A9B6C4", "FCA5A5", "C4B5FD",  # cloud / steel / steel-bright / red-text / violet-text
]
_HEX_RE = re.compile(r"#(" + "|".join(TOKEN_HEX) + r")\b", re.IGNORECASE)
_POPPINS_RE = re.compile(r"['\"]Poppins['\"]|Poppins\s*,")
# A var() call WITH a fallback: var(--token, <fallback up to the first close paren>).
# Anything matched here is the SAFE async-load fallback pattern and is EXCUSED.
_VAR_FALLBACK_RE = re.compile(r"var\(\s*--[a-z0-9-]+\s*,[^)]*", re.IGNORECASE)


def _count(pattern, text):
    return len(pattern.findall(text))


def measure_file(fp: Path):
    text = fp.read_text(encoding="utf-8", errors="replace")
    # A line carrying `purity-allow` is an exempt-with-reason non-CSS literal (e.g. a JS
    # palette data structure / canvas fillStyle where var() cannot resolve). Drop those
    # lines before counting — the reason must be on the same line (matches empty-catch-allow).
    text = "\n".join(ln for ln in text.splitlines() if "purity-allow" not in ln)
    total_hex = _count(_HEX_RE, text)
    total_pop = _count(_POPPINS_RE, text)
    # Excused = brand-literals that appear inside a var(..., <fallback>) — the pure pattern.
    excused_hex = excused_pop = 0
    for fb in _VAR_FALLBACK_RE.findall(text):
        excused_hex += _count(_HEX_RE, fb)
        excused_pop += _count(_POPPINS_RE, fb)
    impure = (total_hex - excused_hex) + (total_pop - excused_pop)
    return {
        "hex_raw": total_hex - excused_hex,
        "poppins_raw": total_pop - excused_pop,
        "excused": excused_hex + excused_pop,
        "impure": max(0, impure),
    }


def census():
    rows, total, pure = {}, 0, 0
    present = 0
    for name in SSOT_FILES:
        fp = ROOT / name
        if not fp.exists():
            continue
        present += 1
        m = measure_file(fp)
        rows[name] = m
        total += m["impure"]
        if m["impure"] == 0:
            pure += 1
    return rows, total, pure, present


def print_board(rows, total, pure, present):
    print("\n" + "=" * 72)
    print("  Component Purity Census (Axis 2 · C-P0) — fallback-aware")
    print("=" * 72)
    print(f"  {'file':<26} {'raw-hex':>8} {'raw-Poppins':>12} {'var-excused':>12} {'IMPURE':>7}")
    for name, m in sorted(rows.items(), key=lambda kv: -kv[1]["impure"]):
        print(f"  {name:<26} {m['hex_raw']:>8} {m['poppins_raw']:>12} {m['excused']:>12} {m['impure']:>7}")
    pct = round(100 * pure / present) if present else 0
    print("  " + "-" * 68)
    print(f"  TOTAL impure literals: {total}   |   pure files: {pure}/{present} ({pct}%)")
    print(f"  Target: 0 impure literals, {present}/{present} pure files.\n")


def do_check():
    rows, total, pure, present = census()
    cur = {n: m["impure"] for n, m in rows.items()}
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"files": cur, "total": total}, indent=2), encoding="utf-8")
        print(f"purity: no baseline — wrote {BASELINE.name} at total={total}. PASS (seeded).")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_files = base.get("files", {})
    risen = [(n, base_files.get(n, 0), c) for n, c in cur.items() if c > base_files.get(n, 0)]
    if risen:
        print("purity: FAIL — impurity ROSE on:")
        for n, b, c in risen:
            print(f"  {n}: {b} -> {c} (a raw brand-literal was added; use var(--wh-*, <fallback>))")
        return 1
    # forward-only: auto-tighten downward on improvement
    improved = total < base.get("total", total)
    if improved or any(c < base_files.get(n, 0) for n, c in cur.items()):
        BASELINE.write_text(json.dumps({"files": cur, "total": total}, indent=2), encoding="utf-8")
        print(f"purity: PASS — improved, baseline tightened to total={total} (pure {pure}/{present}).")
    else:
        print(f"purity: PASS — held at total={total} (pure {pure}/{present}).")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Component purity census (Axis 2 · C-P0).")
    ap.add_argument("--check", action="store_true", help="forward-only ratchet vs baseline")
    ap.add_argument("--write-baseline", action="store_true", help="(re)write the baseline")
    args = ap.parse_args(argv)

    rows, total, pure, present = census()
    if args.write_baseline:
        cur = {n: m["impure"] for n, m in rows.items()}
        BASELINE.write_text(json.dumps({"files": cur, "total": total}, indent=2), encoding="utf-8")
        print_board(rows, total, pure, present)
        print(f"wrote {BASELINE.name} (total={total}).")
        return 0
    if args.check:
        return do_check()
    print_board(rows, total, pure, present)
    return 0


if __name__ == "__main__":
    sys.exit(main())
