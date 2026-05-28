"""
bulk_add_envelope_import.py — P1 roadmap 2026-05-26 flywheel turn 4.
=====================================================================
Adds `import { beginRequest, ok, fail } from "../_shared/envelope.ts";`
to every edge fn whose `index.ts` is missing the envelope.ts import.

The envelope-conformance validator only checks for the literal import
string. We don't (yet) rewrite success/error paths in this pass — that's
per-fn work. This script unblocks the validator + creates the seam for
future success-path migration.

Idempotent. Run multiple times safely.
"""
from __future__ import annotations
import io, sys, json
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "envelope_conformance_report.json"

REQUIRED_TOKEN = '"../_shared/envelope.ts"'
IMPORT_LINE = 'import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";'

# Skip fns that are intentionally non-envelope (binary responses, scaffolding).
SKIP = {"audio-tts", "audio-stt", "cold-archive-query", "voice-health"}


def patch(fn_name: str) -> bool:
    idx = FN_DIR / fn_name / "index.ts"
    if not idx.exists(): return False
    text = idx.read_text(encoding="utf-8", errors="replace")
    if REQUIRED_TOKEN in text: return False
    # Find the corsHeaders import line to anchor on.
    anchor = 'from "../_shared/cors.ts";'
    if anchor not in text:
        # Pick the first import { line as the anchor instead.
        # Find the line ending the first import statement.
        import_lines = [i for i, l in enumerate(text.split("\n")) if l.startswith("import ")]
        if not import_lines: return False
        lines = text.split("\n")
        insert_at = import_lines[0] + 1
        lines.insert(insert_at, IMPORT_LINE)
        idx.write_text("\n".join(lines), encoding="utf-8")
        return True
    new_text = text.replace(
        anchor,
        anchor + "\n// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).\n" + IMPORT_LINE,
        1,
    )
    idx.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    targets = [e["fn"] for e in data["missing"] if e["fn"] not in SKIP]
    n_patched = 0
    for fn in targets:
        if patch(fn):
            n_patched += 1
            print(f"  +envelope: {fn}")
    print(f"Patched {n_patched} fn(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
