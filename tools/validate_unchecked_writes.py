#!/usr/bin/env python3
"""unchecked-writes - an edge function that WRITES must look at whether the write landed.

WHY THIS EXISTS (2026-09-09, found by walking cmms-webhook-receiver's contract live). That function
answered `{"ok":true,"event":"work_order.completed"}` to a correctly HMAC-signed SAP payload and persisted
NOTHING - no external_sync row, no logbook entry. The cause was one line:

    await db.from("external_sync").upsert(syncRow, { onConflict: ... });   // result never read

`external_sync.status` is CHECK-constrained to Open/Closed/Cancelled and the payload carried TECO, so the
write was rejected - and because the error was discarded, the function reported success AND logged nothing,
so the failure could not even be diagnosed afterwards. For an inbound integration that is the worst
possible shape: the sending system is told the work order landed, never retries, and the plant's completed
work disappears. Five more writes in the same file had the identical shape.

WHAT THIS SCANS. Every `supabase/functions/*/index.ts`, for a write call - insert / update / upsert /
delete / rpc - whose result is thrown away: the statement is `await db.from(...).write(...)` with no
destructure of `error`, no assignment, no `.then(`, and no enclosing `try`. Those four are the ways a
result CAN be inspected; anything else is a write nobody looks at.

WHAT IT DELIBERATELY DOES NOT FLAG:
  - a write already inside a try/catch (the catch is the check)
  - a write whose result is assigned or destructured, however it is later used
  - `.select(` reads, which have their own empty-vs-failed discipline elsewhere
  - anything under a line carrying `unchecked-write-allow`, for a write whose failure genuinely does not
    change what the caller should do - it must say WHY on that line, the same contract as
    `empty-catch-allow` and `canonical-allow` in this codebase.

Forward-only, like the other ratchets here: the baseline is the count this file was born with, and it may
only go DOWN. A new unchecked write fails the gate.

    python tools/validate_unchecked_writes.py            # gate
    python tools/validate_unchecked_writes.py --list     # every finding, with its line
"""
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = ROOT / "unchecked_writes_baseline.json"
LIST = "--list" in sys.argv

WRITE = re.compile(r"\.(insert|update|upsert|delete)\s*\(")
# the four shapes that DO look at the result
CHECKED = re.compile(r"(const\s*\{[^}]*\berror\b|let\s*\{[^}]*\berror\b|=\s*await\s|\.then\s*\(|return\s+await\s)")
ALLOW = re.compile(r"unchecked-write-allow")


def enclosing_try(lines, idx):
    """Is this line inside a try block? Walk back counting braces to the nearest `try {`."""
    depth = 0
    for i in range(idx, max(-1, idx - 60), -1):
        ln = lines[i]
        depth += ln.count("}") - ln.count("{")
        if depth < 0 and re.search(r"\btry\s*\{", ln):
            return True
        if depth < 0:
            depth = 0
    return False


def scan():
    findings = []
    for fn_dir in sorted((ROOT / "supabase" / "functions").glob("*/index.ts")):
        lines = fn_dir.read_text(encoding="utf-8", errors="replace").split("\n")
        for i, ln in enumerate(lines):
            if not WRITE.search(ln):
                continue
            # ★A CHAINED CALL'S CHECK LIVES ON THE LINE THAT STARTS THE STATEMENT (2026-09-09). The first
            # version began reading at the line holding `.update(` and joined FORWARD, so a fixed write
            # written the normal way -
            #     const { error: e } = await db.from("logbook")
            #       .update({ ... })
            #       .eq("id", id);
            # - was still reported unchecked: the destructure is on the line ABOVE the match. The gate
            # would have nagged about the very repair it asked for, which is how a gate teaches people to
            # ignore it. Walk BACK to the statement's real start first, then forward to its close.
            # ...and a continuation is not only a leading dot. embed-entry writes
            #     const { error } = conflictKey
            #       ? await db.from(table).upsert(row, ...)
            #       : await db.from(table).insert(row);
            # where the branches begin with `?` and `:` - so a dot-only walk stopped short and reported an
            # ALREADY-CHECKED write. Second false positive of the same shape in this gate; the rule is now
            # stated once, over every token a wrapped statement can begin with.
            CONT = (".", "?", ":", "&&", "||", ")", "}")
            start = i
            while start > 0 and lines[start].lstrip().startswith(CONT):
                start -= 1
            stmt = lines[start]
            j = start
            while (j + 1 < len(lines)
                   and (stmt.count("(") > stmt.count(")") or lines[j + 1].lstrip().startswith(CONT))
                   and j - start < 12):
                j += 1
                stmt += " " + lines[j].strip()
            if not re.search(r"\bawait\b", stmt) and "=" not in stmt:
                continue
            if CHECKED.search(stmt) or ALLOW.search(stmt) or ALLOW.search(lines[max(0, i - 1)]):
                continue
            if enclosing_try(lines, i):
                continue
            findings.append((fn_dir.parent.name, i + 1, ln.strip()[:100]))
    return findings


def main() -> int:
    findings = scan()
    n = len(findings)
    baseline = None
    if BASELINE_FILE.is_file():
        try:
            baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8")).get("count")
        except Exception:
            baseline = None

    if LIST or (baseline is not None and n > baseline):
        for fn, line, src in findings:
            print(f"    {fn}:{line}  {src}")
        print()

    if baseline is None:
        BASELINE_FILE.write_text(json.dumps({"count": n, "born": "2026-09-09"}, indent=2), encoding="utf-8")
        print(f"  baseline written: {n} unchecked write(s) across the edge functions")
        print("  FORWARD-ONLY from here: this number may fall, never rise.")
        return 0

    if n > baseline:
        print(f"FAIL unchecked-writes - {n} unchecked write(s), up from the {baseline} baseline. A write "
              "whose result nobody reads can fail while the function answers ok - which is how "
              "cmms-webhook-receiver told a CMMS its work orders had landed while persisting nothing. "
              "Destructure { error } and act on it, or mark the line `unchecked-write-allow` with the "
              "reason its failure changes nothing.")
        return 1

    if n < baseline:
        BASELINE_FILE.write_text(json.dumps({"count": n, "born": "2026-09-09"}, indent=2), encoding="utf-8")
        print(f"PASS unchecked-writes - {n} unchecked write(s), DOWN from {baseline}; ratchet tightened.")
        return 0

    print(f"PASS unchecked-writes - {n} unchecked write(s), at the {baseline} baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
