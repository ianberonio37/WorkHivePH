"""
Envelope Return-Shape Validator (L0, P1 roadmap 2026-05-27 turn 7).
=====================================================================
The original `validate_envelope_conformance.py` checks IMPORT-only — every
fn that imports `_shared/envelope.ts` counts as adopted. After turn 5's
bulk import patch, all 56 fns import the envelope but only ~1-5 actually
RETURN the envelope shape (i.e. call `ok(ctx, ...)` / `fail(ctx, ...)`).

This validator measures TRUE adoption: fns that import AND call ok()/fail().
Floor ratchet — count can only grow.

Exit codes:
  0  adopters ≥ floor
  1  adopters < floor (a fn dropped its envelope return)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "envelope_return_shape_report.json"
BASELINE = ROOT / "envelope_return_shape_baseline.json"

CHECK_NAMES = ["envelope_return_shape"]

IMPORT_RE = re.compile(r'from\s+["\']\.\./_shared/envelope\.ts["\']')
OK_CALL_RE = re.compile(r"\breturn\s+ok\s*\(\s*ctx\s*,")
FAIL_CALL_RE = re.compile(r"\breturn\s+fail\s*\(\s*ctx\s*,")


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "adopters": [], "error": "no functions dir"}
    fns, adopters = [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"): continue
        index = entry / "index.ts"
        if not index.exists(): continue
        text = index.read_text(encoding="utf-8", errors="replace")
        imports = bool(IMPORT_RE.search(text))
        ok_calls   = len(OK_CALL_RE.findall(text))
        fail_calls = len(FAIL_CALL_RE.findall(text))
        row = {
            "fn":          entry.name,
            "imports":     imports,
            "ok_calls":    ok_calls,
            "fail_calls":  fail_calls,
        }
        fns.append(row)
        # True adoption: at least one ok(ctx, ...) call (the success path
        # actually returns the envelope shape).
        if imports and ok_calls >= 1:
            adopters.append(entry.name)
    return {"fns": fns, "adopters": adopters}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_adopters = len(result["adopters"])

    floor = n_adopters
    if BASELINE.exists():
        try: floor = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("adopters", n_adopters))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"adopters": n_adopters}), encoding="utf-8")

    print(f"Envelope return-shape adoption: {n_adopters} fn(s) actually call ok(ctx, ...) (floor {floor}).")
    print(f"  Adopters: {', '.join(result['adopters']) or '(none)'}")
    if n_adopters < floor:
        print(f"\033[91mFAIL: adoption dropped {floor} → {n_adopters} — a fn stopped returning the envelope.\033[0m")
        return 1
    if n_adopters > floor:
        BASELINE.write_text(json.dumps({"adopters": n_adopters}), encoding="utf-8")
        print(f"\033[92mPASS: floor lifted {floor} → {n_adopters}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
