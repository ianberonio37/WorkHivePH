#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_prover_signin_guard.py — a prover that does not CHECK its sign-in fabricates every auth-gated reading.

THE DEFECT, and why it is the most expensive kind. `live_page_journeys.signIn()` RETURNS `{ok:false, err}`
on failure; it does not throw. So

    await signIn(ctx, 'supervisor');            // <- failure sails straight through
    await signIn(ctx).catch(() => {});          // <- .catch never even fires on that path

leave the walk SIGNED OUT. Every auth-gated page then redirects to index, and the prover measures a redirect
stub: "N call(s) failed and the page said NOTHING about it", "no busy indicator", "0 rows". Those readings are
indistinguishable from real findings, and they are banked as evidence. A false RED gets argued with; a false
GREEN - or a false finding - gets believed, because the next reader sees a measured cell and moves on.

Measured 2026-08-20 in prove_failure_injection.mjs: analytics-report (369 chars) and engineering-design (1845
chars) were both reported as silently failing, and both simply redirect when signed out.

★THIS IS THE THIRD TIME THE SAME CLASS HAS BEEN FOUND, WHICH IS WHY IT IS A TOOL AND NOT AN EDIT. The project
already recorded "59 call sites across 48 files" and fixed ONE file; inside that file, one call site was
converted and its sibling nine lines down was left swallowed. Today's sweep still finds 62. A lesson that
lands in one applier is a lesson that has not landed
([[feedback_fifty_nine_provers_discard_their_sign_in]], [[feedback_the_lesson_landed_in_the_small_applier_only]]).

THE FIX is `assertSignedIn`, which already exists and is already correct:
    if (r && r.anon) return r;                      // an ANON walk is legitimate and passes
    if (!r || !r.ok) throw new Error('SIGN-IN FAILED: ... refusing to walk signed-out')
so wrapping is safe for public-page provers too - it only refuses a walk that MEANT to be signed in and is not.

WHAT IT WILL NOT TOUCH, deliberately:
  · `live_page_journeys.mjs` itself - it DEFINES signIn/assertSignedIn and retries internally, reading `.ok`.
  · a site whose result is CAPTURED (`const si = await signIn(...)`) - the author may check it; rewriting that
    could change control flow. Those are REPORTED for a human read instead of edited.
  · anything already wrapped in assertSignedIn.

  python tools/fix_prover_signin_guard.py --check
  python tools/fix_prover_signin_guard.py --apply
"""
from __future__ import annotations

import glob
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
# Both modules DEFINE signIn and their own contract-matching assertSignedIn, and both read the result
# themselves (live_page_journeys retries on `.ok` across four attempts). A definition is not a call site.
SKIP_FILES = {"live_page_journeys.mjs", "prover_harness.mjs",
              # a harness test whose whole purpose is to exercise signIn's return value directly
              "test_prover_signin_key.mjs"}

CALL = re.compile(r"await\s+signIn\s*\(")
CAPTURED = re.compile(r"(?:const|let|var)\s+\w+\s*=\s*await\s+signIn\s*\(\s*$")


def match_paren(s: str, open_idx: int) -> int:
    """Index of the ')' that closes the '(' at open_idx, skipping strings and template literals."""
    depth, i, n = 0, open_idx, len(s)
    quote = None
    while i < n:
        c = s[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def sites(src: str) -> list[tuple[int, int, bool]]:
    """(call_start, close_paren, captured) for each `await signIn(` in the file."""
    out = []
    for m in CALL.finditer(src):
        if "assertSignedIn" in src[max(0, m.start() - 40):m.start()]:
            continue
        close = match_paren(src, src.index("(", m.start()))
        if close < 0:
            continue
        captured = bool(CAPTURED.search(src[max(0, m.start() - 60):m.end()]))
        out.append((m.start(), close, captured))
    return out


def rewrite(src: str) -> tuple[str, int, int]:
    """Wrap every uncaptured site. Returns (new_src, wrapped, reported_captured)."""
    found = sites(src)
    todo = [s for s in found if not s[2]]
    captured = len(found) - len(todo)
    # right to left, so earlier offsets stay valid
    for start, close, _ in sorted(todo, key=lambda t: -t[0]):
        inner_open = src.index("(", start)
        call = src[start:close + 1]                       # 'await signIn(...)'
        body = call[call.index("(" ):]                    # '(...)'
        # a trailing `.catch(...)` on the same expression is now dead weight AND actively misleading,
        # because it is what made the old fix look done; drop it when it is the no-op shape.
        tail = src[close + 1:close + 1 + 200]
        dead = re.match(r"\s*\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)", tail)
        end = close + 1 + (dead.end() if dead else 0)
        src = src[:start] + "await assertSignedIn(signIn" + body + ")" + src[end:]
    if todo and "assertSignedIn" not in src.split("\n\n")[0] + src[:4000]:
        pass
    return src, len(todo), captured


def ensure_import(src: str) -> str:
    """The file must import assertSignedIn from wherever it already imports signIn."""
    if re.search(r"import\s*\{[^}]*\bassertSignedIn\b[^}]*\}", src):
        return src
    m = re.search(r"import\s*\{([^}]*\bsignIn\b[^}]*)\}\s*from\s*(['\"][^'\"]+['\"])\s*;", src)
    if not m:
        return src
    names = m.group(1)
    pad = " " if names.endswith(" ") else ""
    return src[:m.start(1)] + names.rstrip() + ", assertSignedIn" + pad + src[m.end(1):]


def captured_unchecked(src: str) -> list[tuple[int, str]]:
    """Sites that CAPTURE the sign-in result and then never read it.

    *THE GATE MUST CATCH BOTH SHAPES, because the worst instance found was this one and the first version of
    this tool would have walked straight past it. `prove_shared_handover.mjs` assigned `const inB = await
    signIn(page, B)` and read `inB` nowhere - while its sibling twelve lines up correctly aborted on
    `inA !== 'ok'`. Everything after that line asks whether worker B can see worker A's draft, so a failed
    second sign-in leaves a SIGNED-OUT page, the sentinel is absent for that reason alone, and the prover
    reports NO LEAK. A leak test that passes because nobody was logged in is a false green on precisely the
    property it exists to defend. 23 captured sites were audited by hand; 22 checked their result, that one did
    not, and a gate that only looked for unwrapped calls would have reported the family clean.
    The test is deliberately generous - any mention of the variable within ~1500 chars that looks like a read
    (`if (!v`, `v.ok`, `v &&`, `v ?`) counts - because a false FAIL here sends someone to re-read working code,
    while the shape it is really hunting is a variable that is written and never mentioned again.
    """
    out = []
    for start, close, cap in sites(src):
        if not cap:
            continue
        m = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+signIn", src[max(0, start - 60):close + 1])
        if not m:
            continue
        var = re.escape(m.group(1))
        after = src[close:close + 1500]
        read = re.search(r"(?:if\s*\(\s*!?\s*" + var + r"\b)|(?:!\s*" + var + r"\b)|(?:" + var
                         + r"\s*\.\s*ok)|(?:" + var + r"\s*&&)|(?:" + var + r"\s*\?)", after)
        if not read:
            out.append((src[:start].count("\n") + 1, m.group(1)))
    return out


def main() -> int:
    check = "--check" in sys.argv
    apply = "--apply" in sys.argv
    if not (check or apply):
        print(__doc__)
        return 0

    # ★A FILE IS ONLY REWRITABLE IF ITS signIn COMES FROM A MODULE THAT EXPORTS A MATCHING GUARD, and the two
    # modules do NOT share a contract: live_page_journeys.signIn resolves to {ok,...}, prover_harness.signIn to
    # a BOOLEAN. Each now exports its own assertSignedIn, so appending the name to the import statement that
    # already brings in signIn resolves to the RIGHT implementation for that family - which is why the import is
    # edited in place rather than a new one added. A file that DEFINES its own signIn, or imports it from
    # anywhere else, is reported and left alone: wrapping it would bind a guard to an unknown return shape, and
    # `node --check` cannot see a contract mismatch. (Nearly shipped as a 50-file rewrite that would have thrown
    # SIGN-IN FAILED on every SUCCESSFUL harness sign-in.)
    GUARDED_MODULES = ("./live_page_journeys.mjs", "./prover_harness.mjs")
    files, foreign = [], []
    for p in sorted(glob.glob(str(ROOT / "tools" / "*.mjs"))):
        q = Path(p)
        if q.name in SKIP_FILES:
            continue
        src0 = io.open(q, encoding="utf-8", errors="replace").read()
        if not re.search(r"[^\w.]signIn\s*\(", src0):
            continue
        im = re.search(r"import\s*\{[^}]*\bsignIn\b[^}]*\}\s*from\s*['\"]([^'\"]+)['\"]", src0)
        if not im or im.group(1) not in GUARDED_MODULES:
            if sites(src0):
                foreign.append((q, im.group(1) if im else "defines its own"))
            continue
        files.append(q)
    to_fix, captured_total, changed = [], 0, []
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        found = sites(src)
        un = [s for s in found if not s[2]]
        captured_total += len(found) - len(un)
        if un:
            to_fix.append((f, len(un)))

    print(f"  unguarded sign-ins: {sum(n for _, n in to_fix)} site(s) across {len(to_fix)} prover(s) "
          f"· {captured_total} captured site(s) left for a human read")
    blind = []
    for p in sorted(glob.glob(str(ROOT / "tools" / "*.mjs"))):
        q = Path(p)
        if q.name in SKIP_FILES:
            continue
        for ln, var in captured_unchecked(io.open(q, encoding="utf-8", errors="replace").read()):
            blind.append((q.name, ln, var))
    if blind:
        print(f"  {RED}{len(blind)} captured sign-in(s) whose result is never read{RST} - a failed sign-in is "
              f"then silent, and on a refusal/leak prover that is a FALSE PASS:")
        for n, ln, var in blind:
            print(f"      {n}:{ln}  `{var}` assigned and never checked")
    for q, mod in foreign[:8]:
        print(f"    skip  {q.name:38} signIn from {mod} - no matching guard, left alone")
    for f, n in sorted(to_fix, key=lambda t: -t[1])[:12]:
        print(f"    {n:3}  {f.relative_to(ROOT)}")

    if check:
        if to_fix or blind:
            print(f"{RED}FAIL{RST} prover-signin-guard - a prover that does not CHECK its sign-in reports a "
                  f"signed-out walk as findings"
                  + (" (run --apply for the unwrapped ones;" if to_fix else " (")
                  + (" the captured ones need a human read - assign-and-never-check)" if blind else ")"))
            return 1
        print(f"{GREEN}PASS{RST} prover-signin-guard - every sign-in in the prover family is checked; no walk "
              f"can be reported from a signed-out session")
        return 0

    for f, _ in to_fix:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        new, n, _c = rewrite(src)
        new = ensure_import(new)
        if new == src or not n:
            continue
        tmp = f.with_suffix(".mjs.tmp")
        io.open(tmp, "w", encoding="utf-8", newline="\n").write(new)
        tmp.replace(f)
        # ★EVERY EDITED FILE IS PARSED. A sweep that rewrites 60 call sites across 40 files and does not
        # re-parse them is how a prover family goes dark in one commit.
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"    {RED}SYNTAX BROKEN{RST} {f.name}: {(r.stderr or '').splitlines()[:1]}")
            return 1
        changed.append((f.name, n))
    print(f"  rewrote {sum(n for _, n in changed)} site(s) in {len(changed)} file(s); every one re-parsed clean")
    for n, c in changed[:10]:
        print(f"    {c:3}  {n}")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    raise SystemExit(main())
