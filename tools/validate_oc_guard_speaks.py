#!/usr/bin/env python3
"""oc-guard-speaks — T138: a concurrency guard that says nothing is a lost edit (2026-08-26).

An optimistic-concurrency guard filters an UPDATE on the row's `updated_at`, so a
write loses if somebody else changed the record first. That is the easy half. The
half that decides whether it HELPS is what happens next: if nothing checks that
zero rows changed, the update silently does nothing, the form closes, and the
person walks away believing they saved work that no longer exists. A guard that
returns without speaking is worse than no guard, because it converts a visible
conflict into an invisible loss.

CENSUS, 2026-08-26 — and it CORRECTS this trajectory's recorded belief. The basis
read that logbook amends, community post edits and PM scope edits were "presumed
LAST-WRITE-WINS". They are not: there are TEN hand-rolled guards across EIGHT
pages (asset-hub, community, founder-console, integrations, logbook,
platform-actions, pm-scheduler, project-manager x3), plus inventory through the
central ocUpdate helper. Eleven protected edit surfaces, not two. And every one of
the ten detects the zero-row case AND tells the person.

THE ASSERTION: every `updated_at`-filtered update must, within the same handler,
check for zero rows changed and say something. It does NOT demand migration to
ocUpdate — that is ten rewrites of live edit paths for a refactor, and the
property that protects a person is "the guard speaks", not "the guard is shared".
The install-the-guard lesson still applies to anything NEW: reach for ocUpdate
first. This gate exists so a hand-rolled one cannot ship SILENT.

★AND IT WOULD RATHER MISS THAN LIE. The window is the 40 lines after the filter,
so a guard whose reporting lives further away reads as a miss. That is the safe
direction for a gate whose failure mode would otherwise be a false accusation
about working code.

Usage: python tools/validate_oc_guard_speaks.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

FILTER = re.compile(r"\.eq\(\s*'updated_at'")
# ★AN ORACLE'S VOCABULARY IS PART OF THE ORACLE (2026-09-10). Every alternative below except the last
# two names the RESULT VARIABLE - `data`, `updated`, `rows` - so a guard that calls it anything else was
# invisible. dayplanner.html's new guard reads `if (!uErr && (!hit || !hit.length))`, which is an
# ordinary way to write "zero rows changed", and it was reported as a SILENT guard: the gate said the
# write vanishes without telling anyone, three lines above a showToast that tells them exactly that.
# A false accusation about working code is this gate's own stated worst failure mode, so the zero-check
# is matched on its SHAPE (`!<anything>.length`) rather than on the handful of names the repo happened
# to use first. Deliberately still narrow: `!<ident>` alone is NOT accepted, because `!error` is not a
# zero-row check, and a genuinely silent guard - no zero-check at all - still fails, which is what the
# injected-silent-guard teeth test proves.
ZERO = re.compile(r"length\s*===?\s*0|!\s*data\b|!\s*updated\b|count\s*===?\s*0|\brows?\s*===?\s*0|"
                  r"data\s*&&\s*data\.length|\.length\s*<\s*1|"
                  r"!\s*[A-Za-z_]\w*\.length\b|[A-Za-z_]\w*\s*&&\s*[A-Za-z_]\w*\.length")
SAYS = re.compile(r"showToast|whWriteError|setStatus|textContent\s*=|whConfirm|alert\(")

# ★THE WINDOW IS THE HANDLER, NOT 40 LINES (2026-10-13). The assertion above is "within the same handler", and a
# fixed 40 lines stood in for it. logbook's offline-queue replay notices zero rows at +3 lines and says so in the
# toast after its loop, at +63: a guard that speaks, read as silent. The window is now the rest of the function
# that holds the filter - found by brace-matching the nearest enclosing `function` / arrow body - capped at 150
# lines, and 40 lines when no enclosing function is found. A message in the NEXT function never counts.
_FN_HEAD = re.compile(r"\bfunction\b[^{;]*\{|=>\s*\{")
_STRIP = re.compile(r"//.*$|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")


def _braces(line):
    code = _STRIP.sub("", line)
    return code.count("{") - code.count("}")


def handler_window(lines, i, cap=150, fallback=40):
    """Lines from the filter at i to the end of the innermost function that encloses it."""
    for j in range(i, max(-1, i - 400), -1):
        m = _FN_HEAD.search(lines[j])
        if not m:
            continue
        depth = _braces(lines[j][m.start():])
        k = j
        while depth > 0 and k + 1 < len(lines) and k - i < cap:
            k += 1
            depth += _braces(lines[k])
        if depth <= 0 and k >= i:          # this function closes at or after the filter: it encloses it
            return "\n".join(lines[i: k + 1])
        if depth > 0:                       # ran past the cap without closing: too long to call one handler
            break
    return "\n".join(lines[i: i + fallback])


def main() -> int:
    silent, total = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        lines = io.open(f, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            if not FILTER.search(line):
                continue
            # ★A COMMENT IS NOT A CALL SITE (2026-09-28). dayplanner.html:2789 is a COMMENT explaining
            # the bug this gate exists to catch - "the .update().eq('updated_at', ...) branch was
            # unreachable" - and the gate read it as a real guarded update, found no zero-row check in
            # the 40 lines of prose that follow, and reported the page as silent. The page's ACTUAL
            # guard is line 1101, which the gate passes. So the accusation was against a sentence, and
            # a false accusation about working code is this gate's own stated worst failure mode (see
            # the ZERO note above). Documenting a past defect must not re-open its gate.
            # feedback_quoting_a_comment_is_not_reading_the_code.
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            total += 1
            window = handler_window(lines, i)
            if not (ZERO.search(window) and SAYS.search(window)):
                silent.append(f"{Path(f).name}:{i + 1}")

    central = sum(1 for f in glob.glob(str(ROOT / "*.html"))
                  if "ocUpdate" in io.open(f, encoding="utf-8", errors="replace").read())
    print(f"  updated_at-guarded updates: {total} hand-rolled | pages using central ocUpdate: {central}")

    if silent:
        print("FAIL oc-guard-speaks — a concurrency guard filters the update but never notices it "
              "changed nothing:")
        for s in silent:
            print("    - " + s)
        print("    The write vanishes, the form closes, and the person believes they saved work that no")
        print("    longer exists. Check for zero rows changed and SAY so — or use ocUpdate, which does")
        print("    both. A guard that returns without speaking turns a visible conflict into an")
        print("    invisible loss.")
        return 1
    if total == 0:
        print("PASS oc-guard-speaks — no updated_at-filtered updates found. If that is a surprise, the "
              "guards were removed or renamed; re-point this gate rather than trusting the zero.")
        return 0
    print(f"PASS oc-guard-speaks — all {total} concurrency guards detect a lost race and tell the person.")
    return 0


def self_test() -> int:
    def verdict(src):
        lines = src.split("\n")
        i = next(n for n, l in enumerate(lines) if FILTER.search(l))
        w = handler_window(lines, i)
        return bool(ZERO.search(w) and SAYS.search(w))
    body = "\n".join("      x = x + 1;" for _ in range(55))
    speaks_late = ("async function replay() {\n  let unconfirmed = false;\n  for (const p of q) {\n"
                   "    const r = await db.from('t').update(u).eq('id', p.id)\n      .eq('updated_at', s).select('id');\n"
                   "    if (Array.isArray(r.data) && r.data.length === 0) unconfirmed = true;\n" + body + "\n  }\n"
                   "  if (unconfirmed) showToast('1 edit could not be applied.');\n}\n")
    silent = speaks_late.replace("showToast('1 edit could not be applied.')", "console.warn('x')")
    next_fn = (speaks_late.replace("  if (unconfirmed) showToast('1 edit could not be applied.');\n", "")
               + "function other() {\n  showToast('unrelated');\n}\n")
    cases = [("a guard that speaks 60 lines later, in the same handler, passes", verdict(speaks_late)),
             ("...and the same handler with no message fails", not verdict(silent)),
             ("...and a message in the NEXT function does not count", not verdict(next_fn))]
    for n, ok in cases:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    ok = all(v for _, v in cases)
    print("  self-test: " + ("teeth intact" if ok else "VACUOUS"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
