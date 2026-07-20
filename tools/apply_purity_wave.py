#!/usr/bin/env python3
"""
apply_purity_wave.py — PLATFORM_CENTRALIZATION_ROADMAP C-P2 converter (Axis 2 · Purity).

One-shot, idempotent, FALLBACK-preserving: wraps RAW brand literals in the shared-chrome
SSOT files with their token + a hex fallback — `#F7A21B` -> `var(--wh-orange, #F7A21B)`,
`'Poppins', sans-serif` -> `var(--wh-font, 'Poppins', sans-serif)`. The fallback keeps the
async-load first-paint safe (tokens.css is injected async by nav-hub) while making the token
the source of truth. Per-line, so:
  · a line carrying `purity-allow` is SKIPPED (exempt non-CSS literal, e.g. a JS palette),
  · a literal already inside a var(...) is PROTECTED (no double-wrap — idempotent).

Usage: python tools/apply_purity_wave.py [--dry-run] [file ...]
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

HEX_MAP = {
    "F7A21B": "orange", "FDB94A": "orange-light", "D88A0E": "orange-dark",
    "162032": "navy", "1F2E45": "navy-mid", "2A3D58": "navy-light",
    "29B6D9": "blue", "1A9ABF": "blue-dark", "5FCCE8": "blue-light",
    "4ade80": "green", "f87171": "red", "facc15": "amber", "a78bfa": "violet",
    "F4F6FA": "cloud", "7B8794": "steel", "A9B6C4": "steel-bright",
    "FCA5A5": "red-text", "C4B5FD": "violet-text",
}
_HEX_RE = re.compile(r"#(" + "|".join(HEX_MAP) + r")\b", re.IGNORECASE)
_VAR_RE = re.compile(r"var\(\s*--[a-z0-9-]+\s*,[^)]*\)", re.IGNORECASE)
# Longest font-stack forms first so a shorter form never partially matches inside a longer.
_POPPINS_FORMS = [
    "'Poppins', system-ui, -apple-system, sans-serif",
    "'Poppins', system-ui, sans-serif",
    "'Poppins', sans-serif",
]

DEFAULT_FILES = [
    "nav-hub.js", "companion-launcher.js", "wh-feedback-fab.js", "connectivity-widget.js",
    "voice-handler.js", "wh-persona.js", "session-timeout.js", "wayfinding.js",
    "search-overlay.js", "learn-link.js", "wh-help.js", "onboarding.js", "provenance-hover.js",
    "utils.js",
]


def convert_line(line: str) -> str:
    if "purity-allow" in line:
        return line
    # Protect existing var(...) so we never double-wrap (idempotent).
    stash = []
    def _stash(m):
        stash.append(m.group(0))
        return f"\x00{len(stash)-1}\x00"
    protected = _VAR_RE.sub(_stash, line)
    # Wrap bare hex, preserving the ORIGINAL case of the matched literal.
    def _wrap_hex(m):
        raw = m.group(0)              # e.g. "#F7A21B"
        name = HEX_MAP[m.group(1).upper()] if m.group(1).upper() in HEX_MAP else HEX_MAP.get(m.group(1).lower())
        if not name:
            # case-insensitive key lookup fallback
            for k, v in HEX_MAP.items():
                if k.lower() == m.group(1).lower():
                    name = v; break
        return f"var(--wh-{name}, {raw})"
    protected = _HEX_RE.sub(_wrap_hex, protected)
    # Wrap the Poppins font stacks (still-protected vars won't match).
    for form in _POPPINS_FORMS:
        protected = protected.replace(form, f"var(--wh-font, {form})")
    # Restore protected var(...) blocks.
    def _unstash(m):
        return stash[int(m.group(1))]
    return re.sub(r"\x00(\d+)\x00", _unstash, protected)


def process(fp: Path, dry: bool):
    text = fp.read_text(encoding="utf-8", errors="replace")
    out_lines, changed = [], 0
    for ln in text.splitlines(keepends=True):
        nl = ln.rstrip("\n")
        conv = convert_line(nl)
        if conv != nl:
            changed += 1
        out_lines.append(conv + ("\n" if ln.endswith("\n") else ""))
    if changed and not dry:
        fp.write_text("".join(out_lines), encoding="utf-8")
    return changed


def main(argv):
    dry = "--dry-run" in argv
    files = [a for a in argv if not a.startswith("--")] or DEFAULT_FILES
    total = 0
    for name in files:
        fp = ROOT / name
        if not fp.exists():
            print(f"  skip (absent): {name}"); continue
        n = process(fp, dry)
        total += n
        print(f"  {'would change' if dry else 'changed'} {n:>3} line(s): {name}")
    print(f"\n{'DRY-RUN — no writes.' if dry else 'APPLIED.'} {total} line(s) across {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
