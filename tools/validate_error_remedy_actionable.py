#!/usr/bin/env python3
"""
validate_error_remedy_actionable.py — MK11: an error must not propose a remedy that cannot work.

BORN FROM THE WALK, not from a reading list. The 2026-07-24 marketplace deepwalk hit the SAME shape
four independent times, on four different surfaces:

  * the buyer's inquiry step   — an anon filled name + phone + message and got
                                 "Failed to send inquiry. Try again." from a 42501
  * platform-actions           — "Action failed. Try again." for an expired admin session
  * founder-console            — the same, on the sibling moderation surface
  * the saved-search save      — "Could not save. Try again."

In every case the write failed because the SESSION was gone, so retrying reproduces the failure
exactly. "Try again" is not merely unhelpful there: it is a remedy the system knows cannot succeed,
and the user pays for it by re-typing and re-tapping before giving up. On the inquiry step the user had
already typed a phone number.

HARVESTED STANDARD (retrieve-first, substrate/external/external-error-message-quality-guidelines.md,
nngroup.com/articles/error-message-guidelines): an error should "concisely and precisely describe the
issue, providing context and potential remedies" and "include instructions on how to resolve" it. A
remedy that cannot resolve the error fails that on its own terms.

THE RULE: a catch around a client WRITE (insert/upsert/update/delete/rpc/functions.invoke) that offers
a RETRY must first branch on the auth/permission case and say something different there. The branch is
cheap — check the error's 42501 / 401 / RLS / JWT signature — and it is what turns a dead end into a
next step ("sign in again and re-save it").

Static + offline, so it runs in --fast. Forward-only: the count may not rise.
Self-test: `--selftest`.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "error_remedy_baseline.json"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

SKIP_SUFFIXES = ("-test.html", ".backup.html", ".backup2.html")
SKIP_DIRS = {".emoji_bak", ".hexvar_bak", ".leftover_bak", ".tmp", "radbak", "radbak2", "learn", "node_modules"}

CATCH_RE  = re.compile(r"catch\s*\(([^)]*)\)\s*\{")
# A remedy that tells the user to repeat the same action — and only where it is ADDRESSED to the user
# as an error message. Two shapes look identical to a naive match but are correct code:
#   * a BUTTON CAPTION being reset (`lbl.textContent = 'Try again'`) is a control's label, not a claim
#     about why the write failed;
#   * a SYSTEM retry ("will retry automatically", the offline queue draining on reconnect) is a promise
#     the app keeps itself, and it does work — the opposite of the dead end this class is about.
# Both were live findings on analytics.html and dayplanner.html; treating them as defects would have
# meant "fixing" correct behaviour, which is how a gate starts costing more than it catches.
RETRY_RE  = re.compile(r"\b(try again|retry|please try)\b", re.I)
LABEL_RETRY_RE = re.compile(r"(textContent|innerHTML|innerText|\.label|value)\s*=\s*['\"`][^'\"`]*\btry again\b",
                            re.I)
SYSTEM_RETRY_RE = re.compile(r"retry\s+automatically|will\s+retry|saved\s+offline|queued\s+offline|auto[- ]?retry",
                             re.I)
# The write verbs whose failure is plausibly an auth/RLS rejection.
WRITE_RE  = re.compile(r"\.(insert|upsert|update|delete)\s*\(|\.rpc\s*\(|functions\s*\.\s*invoke\s*\(")
# The branch that makes the remedy honest — either the inline signature test, or (preferred) the
# central helpers in utils.js. Adopting whWriteError/whIsAuthFailure MOVES those signatures out of the
# call site, so a detector that only looked for them inline would go red on exactly the sites that had
# just been fixed properly. Centralization must not read as a regression.
AUTHBR_RE = re.compile(
    r"whWriteError\s*\(|whIsAuthFailure\s*\("
    r"|42501|\b401\b|row-level security|permission denied|not authenticated|JWT|session expired",
    re.I)


def _catch_body(src: str, brace_idx: int) -> str:
    """Balanced-brace slice of the catch block."""
    depth, i, n = 0, brace_idx, len(src)
    while i < n:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[brace_idx:i + 1]
        i += 1
    return src[brace_idx:brace_idx + 900]


def scan_source(src: str) -> list[str]:
    """Pure over source text so the self-test needs no files."""
    out = []
    for m in CATCH_RE.finditer(src):
        body = _catch_body(src, m.end() - 1)
        if not RETRY_RE.search(body):
            continue                                   # offers no retry -> nothing to be wrong about
        if SYSTEM_RETRY_RE.search(body):
            continue                                   # the APP retries, and it works (offline queue)
        # If the only "try again" is a control's caption, the user was never told to retry a failed write.
        stripped = LABEL_RETRY_RE.sub("", body)
        if not RETRY_RE.search(stripped):
            continue
        if AUTHBR_RE.search(body):
            continue                                   # already branches on the auth case
        # Only a WRITE can fail this way; a parse/render catch is out of scope.
        before = src[max(0, m.start() - 900):m.start()]
        if not WRITE_RE.search(before + body):
            continue
        out.append(re.sub(r"\s+", " ", body[:80]))
    return out


def scan_all() -> dict:
    per = {}
    for p in sorted(ROOT.glob("*.html")):
        if p.name.endswith(SKIP_SUFFIXES) or any(x in p.parts for x in SKIP_DIRS):
            continue
        hits = scan_source(p.read_text(encoding="utf-8", errors="replace"))
        if hits:
            per[p.name] = hits
    return per


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    bad = "try { await db.from('t').insert(r); } catch (e) { showToast('Failed. Try again.'); }"
    chk("flags a retry on a failed write", len(scan_source(bad)), 1)

    good = ("try { await db.from('t').insert(r); } catch (e) { "
            "const a = String(e.code)==='42501'; showToast(a ? 'Session expired, sign in again.' : 'Failed. Try again.'); }")
    chk("accepts a retry that branches on auth", len(scan_source(good)), 0)

    central = "try { await db.from('t').insert(r); } catch (e) { showToast(whWriteError(e, 'Save failed. Try again.')); }"
    chk("accepts the CENTRAL helper as the branch", len(scan_source(central)), 0)

    no_retry = "try { await db.rpc('x'); } catch (e) { showToast('Could not load the list.'); }"
    chk("ignores a catch offering no retry", len(scan_source(no_retry)), 0)

    non_write = "try { JSON.parse(s); } catch (e) { showToast('Bad file. Try again.'); }"
    chk("ignores a non-write catch", len(scan_source(non_write)), 0)

    invoke = "try { await db.functions.invoke('f'); } catch (e) { showToast('Failed, please try again'); }"
    chk("covers functions.invoke", len(scan_source(invoke)), 1)

    # The two live false positives that shaped this detector.
    caption = ("try { await db.rpc('recompute'); } catch (e) { "
               "lbl.textContent = 'Try again'; showToast('Recompute failed, check console'); }")
    chk("ignores a retry used as a BUTTON CAPTION", len(scan_source(caption)), 0)

    offline = ("try { await db.from('t').upsert(r); } catch (e) { "
               "await q.enqueue(r); showToast('Network issue: saved offline, will retry automatically.'); }")
    chk("ignores a SYSTEM retry that actually works", len(scan_source(offline)), 0)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    per = scan_all()
    total = sum(len(v) for v in per.values())
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", total) if BASELINE.exists() else total
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")

    print(f"{BOLD}MK11 error-remedy actionability — a retry must be able to succeed{RESET}")
    print(f"  pages scanned for write-catches offering a retry: {len(per)} with findings")
    for name, hits in per.items():
        print(f"  {RED}HIT {RESET} {name}: {len(hits)} retry-on-write catch(es) with no auth branch")
        for h in hits[:2]:
            print(f"        {h}")
    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> {total}")
        return 0
    if total > base:
        print(f"  {RED}FAIL{RESET}  rose {base} -> {total}: a new error offers a remedy that cannot work")
        return 1
    print(f"  {GREEN}PASS{RESET}  {total} (baseline {base})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
