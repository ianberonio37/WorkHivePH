#!/usr/bin/env python3
"""Gate `outage-copy-honesty` - what an OUTAGE is allowed to say to the person reading it.

Three defects found in shared chrome on one MCP walk of assistant.html (2026-10-06) with PostgREST
genuinely stopped. All three were in utils.js, all three therefore landed on every page that renders a
read (~26 of them), and each one is pinned here because each is a silent class that a green page hides.

  1. A 503 FROM THE GATEWAY FELL BETWEEN BOTH NOTICES.  utils.js splits failure handling by whether a
     RESPONSE exists: `_whNoteTransportFailure` handles a REJECTED fetch (no status) and
     `_whNoteAuthFailure` handled 401/403. A stopped service behind Kong is neither - Kong answers in
     15 ms with a real 503 - so the `.catch` never ran and the auth guard returned on its first line.
     Measured consequence at 102 s with ZERO reads in flight: `_whSettled` 0, no notice, no failure
     sentence anywhere, and the 6 s slow hint still reading "still loading" when nothing was loading
     and nothing ever would. The person sat under a permanent false statement with no action offered.

  2. A BARE `_t` IN THE SETTLE PASS WOULD HAVE DELETED THE WHOLE PASS.  `_t` is not in lexical scope in
     utils.js - it lives on `window`, and all ~17 other call sites alias it through a typeof guard. A
     bare call throws a ReferenceError directly into that pass's `empty-catch-allow`, so the failure
     sentence would have vanished ENTIRELY rather than failing loudly. Caught on the verifying walk.

  3. "RETRY WHEN YOU ARE BACK ONLINE" WAS SAID TO A CONNECTED PERSON.  navigator.onLine was true and the
     page's own connection chip read "Online" - correctly - directly beside advice to wait until they
     were back online. The one action offered was the one action that could not help; on a plant floor
     it sends somebody to re-seat a wifi dongle while the SERVICE is what is down.

Static, so it runs in --fast and needs no DB or browser: every assertion is a property of the source.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bug_repro_inventory import _strip_comments_js  # noqa: E402  (blanks comments, preserving offsets)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILS = os.path.join(ROOT, "utils.js")

# The retired sentence, in both languages. A page may never tell a reader to wait for a connection
# without first establishing that the connection is what is missing.
RETIRED = (
    "Retry when you are back online",
    "Subukan kapag nakabalik ka online",
)


def _fn_body(src, name):
    """The source of one top-level `function name(...) {...}`, by brace matching.

    Scoping each assertion to the function that owns it is what keeps this gate from passing because
    the string it wants happens to exist somewhere else in a 4,600-line file.
    """
    m = re.search(r"^function\s+" + re.escape(name) + r"\s*\(", src, re.M)
    if not m:
        return None
    i = src.index("{", m.end() - 1)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return None


def main():
    failures = []

    if not os.path.exists(UTILS):
        print("FAIL outage-copy-honesty - utils.js not found at %s" % UTILS)
        return 1
    src = io.open(UTILS, encoding="utf-8").read()

    # --- 1. every 5xx reaches the transport notice -------------------------------------------------
    auth = _fn_body(src, "_whNoteAuthFailure")
    if auth is None:
        failures.append("_whNoteAuthFailure not found - the 5xx route cannot be checked. If it was "
                        "renamed, re-point this gate at the new name rather than deleting the check.")
    else:
        if not re.search(r"res\.status\s*>=\s*500", auth):
            failures.append(
                "_whNoteAuthFailure no longer routes a 5xx anywhere. A stopped service behind the "
                "gateway answers with a real 503, which the rejected-fetch path cannot see, so "
                "without this branch an outage is NEVER named and the settle passes are never armed "
                "(measured: 102s, 0 reads in flight, _whSettled 0, slow hint still claiming 'still "
                "loading').")
        elif not re.search(r"res\.status\s*>=\s*500[^\n]*_whNoteTransportFailure", auth):
            failures.append(
                "_whNoteAuthFailure sees a 5xx but no longer hands it to _whNoteTransportFailure. "
                "That function owns the honest online/offline wording, the per-burst throttle, the "
                "settle passes AND the clear-on-next-ok; a 5xx branch that does not reach it has to "
                "rebuild all four or it silently drops one.")
        # A 4xx must NOT be routed: a 404/422 is this page's own bad request and belongs to the
        # caller's {data, error}, not to a platform-wide outage banner.
        if re.search(r"res\.status\s*>=\s*400\b", auth):
            failures.append(
                "_whNoteAuthFailure routes the whole 4xx family into the outage notice. A 404 or 422 "
                "is a request this page got wrong, not an outage; showing a platform banner for it "
                "teaches people to ignore the banner that means something.")

    # --- 2. the settle pass's translator is aliased, never bare ------------------------------------
    settle = _fn_body(src, "_whSettleStuckLoaders")
    if settle is None:
        failures.append("_whSettleStuckLoaders not found - the translator-scope check cannot run.")
    else:
        # A bare `_t(` call: not window._t, not an alias like _tP/_tRF/_tC.
        # COMMENTS ARE BLANKED FIRST, and the gate's own first run proves why: the only match it found
        # was the sentence inside this very fix explaining that a bare _t() would throw. A scanner that
        # reads prose as code manufactures its finding - so the shared stripper from
        # bug_repro_inventory is reused here rather than a second, subtly different one being written.
        bare = [m.start() for m in re.finditer(r"(?<![\w.])_t\s*\(", _strip_comments_js(settle))]
        if bare:
            failures.append(
                "%d bare _t( call(s) in _whSettleStuckLoaders. `_t` is NOT in lexical scope in "
                "utils.js - it is a window property, and every other call site aliases it through a "
                "typeof guard. A bare call throws a ReferenceError into this function's "
                "`empty-catch-allow`, which does not degrade the copy, it DELETES the whole pass: no "
                "failure sentence at all. Alias it first (var _tX = typeof window._t === 'function' "
                "? window._t : function (en) { return en; })." % len(bare))

    # --- 2b. the chip pass marks only the INNERMOST chip -------------------------------------------
    # renderSourceChip returns a complete <p class="wh-source-chip">, and a page may assign that output as
    # the innerHTML of an element that ALSO carries the class - community.html must, because the 62px
    # reserve that fixes its 0.071 layout shift lives on that class in components.css. Both elements then
    # match the pass's query, both get prefixed, and the reader sees "Read failed ·" followed by
    # "Read failed · showing the last data loaded · ...". Measured stable at exactly 2, which is what told
    # it apart from a repeated-prefix loop. Stripping the class from the container was tried first and
    # dropped the computed min-height to 0px, trading a copy stutter for a layout shift that four other
    # pages had each already patched - so the skip belongs here, where it also covers future nesting.
    if settle and not re.search(r"querySelector\(\s*['\"]\.wh-source-chip['\"]\s*\)", _strip_comments_js(settle)):
        failures.append(
            "the chip pass no longer skips a chip that CONTAINS another chip, so any page whose source-chip "
            "container also carries .wh-source-chip will read 'Read failed · Read failed ·'. Do not fix that "
            "by removing the class from the container: that class carries the 62px layout reserve.")

    # --- 3. the retired copy is gone, and both honest branches exist -------------------------------
    for phrase in RETIRED:
        if phrase in src:
            failures.append(
                "utils.js has reinstated %r. This tells a person whose connection is fine to wait for "
                "a connection: navigator.onLine was true and the page's own chip read 'Online' while "
                "this sentence was on screen. Branch on navigator.onLine and name the real cause."
                % phrase)

    if settle:
        if not re.search(r"navigator\.onLine", settle):
            failures.append(
                "the settle pass no longer asks navigator.onLine. It is the ONLY input that can tell "
                "'your connection is the problem' from 'the service did not answer', and those two "
                "cases need opposite advice (wait vs retry now).")
        # Both branches must survive, and both must be translated - a Filipino reader needs the same
        # distinction, not the English fallback.
        for want, label in ((r"you are offline", "the offline branch"),
                            (r"the service did not answer", "the online branch")):
            if not re.search(want, settle):
                failures.append("%s is gone from the settle pass (expected copy matching %r)."
                                % (label, want))
        for want, label in ((r"offline ka", "the offline branch's Filipino"),
                            (r"hindi sumagot ang serbisyo", "the online branch's Filipino")):
            if not re.search(want, settle):
                failures.append(
                    "%s is missing. An untranslated failure sentence is where the FIL reader silently "
                    "drops back to English at the exact moment the page is hardest to understand."
                    % label)

    # --- 4. whReadError, the mapper EVERY page's read-failure copy flows through ---------------
    # Same defect as (3), in the widest-reach place on the platform (2026-10-06, walked on logbook with
    # PostgREST stopped and navigator.onLine TRUE). T71 had already made this sentence answer "is it me
    # or them?" by pointing at the Status page - but it answered in the SECOND clause, after telling a
    # connected person to go and check their connection, which is the clause that gets acted on.
    rde = _fn_body(src, "whReadError")
    if rde is None:
        failures.append("whReadError not found - the platform-wide read-failure copy cannot be checked. "
                        "If it moved, re-point this gate rather than dropping the check.")
    else:
        if not re.search(r"navigator\.onLine", rde):
            failures.append(
                "whReadError no longer asks navigator.onLine. It is the mapper behind nearly every "
                "page's read-failure message, so a single un-branched sentence here tells the whole "
                "platform's readers to check a connection that may be perfectly fine.")
        if re.search(r"Couldn.t load ' \+ thing \+ '\. Check your connection", rde):
            failures.append(
                "whReadError leads again with 'Check your connection' for the generic case. On a plant "
                "floor the first clause is the one acted on: it sends somebody to re-seat a wifi dongle "
                "while the service is what is down. Lead with what is true, keep the Status pointer.")
        for want, label in ((r"WorkHive did not answer", "the online lead clause"),
                            (r"You are offline, so", "the offline lead clause"),
                            (r"hindi sumagot ang WorkHive", "the online clause's Filipino"),
                            (r"Offline ka, kaya", "the offline clause's Filipino")):
            if not re.search(want, rde):
                failures.append("whReadError is missing %s (expected copy matching %r)." % (label, want))
        # The Status-page pointer is the half that answers "is it me or them?" - it must survive on the
        # ONLINE branch, which is the only branch where that page is reachable.
        if "Status page" not in rde:
            failures.append(
                "the Status-page pointer is gone from whReadError. Without it a plant-wide outage reads "
                "exactly like bad plant wifi, which is the defect T71 fixed.")

    # --- 5. the settle pass offers the control it names --------------------------------------------
    # 2026-10-06 (engineering-design x assistive-tech): the text pass rewrote a stuck "Loading..." line as
    # "Not loaded - the service did not answer. Tap Retry." inside a div with NO button - an instruction is a
    # claim that its control exists. The pass now creates the Retry itself where there is room.
    if settle:
        code = _strip_comments_js(settle)
        if re.search(r"Tap Retry", code) and not re.search(r"createElement\(\s*['\"]button['\"]\s*\)", code):
            failures.append(
                "the settle pass says 'Tap Retry' but creates no button. On the History tab of "
                "engineering-design that pointed at nothing; either add the control or drop the pointer.")

    # --- 6. "busy" was a cause nobody measured -----------------------------------------------------
    # whAiError mapped every 5xx/408/timeout to "The AI service is busy right now" - said, on the walk that
    # found it, about a DATABASE outage. Exactly one cause in that band is load.
    if "The AI service is busy right now" in _strip_comments_js(src):
        failures.append(
            "utils.js says 'The AI service is busy right now' again. That band is every 5xx, a 408 and a "
            "timeout; 'busy' asserts load, which was not the cause on the walk that found it (PostgREST "
            "was stopped). Say what every case shares: the service could not answer.")

    # --- 7. PAGE-written connection blame can only go DOWN -----------------------------------------
    # Clauses 3-4 fix the shared mappers; pages also write their own sentences, and on 2026-10-06 the
    # assistive-tech A-row walk found the same misdirection hand-written across 15 pages ("Couldn't load X.
    # Check your connection and try again." shown while navigator.onLine was TRUE and PostgREST was down).
    # Each was fixed on its walk; some survivors are honest (an offline-guarded branch, an integration's
    # own "connection" setting, a library that genuinely failed to download). A forward-only count keeps
    # new ones out without pretending to judge every survivor statically. Lower it when you fix one.
    BASELINE = 20
    pat = re.compile(r"check (?:your|the) connection", re.I)
    total, where = 0, []
    for fn in sorted(os.listdir(ROOT)):
        if not (fn.endswith(".html") or (fn.endswith(".js") and not fn.endswith(".min.js"))):
            continue
        try:
            text = io.open(os.path.join(ROOT, fn), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        text = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), text, flags=re.S)
        try:
            text = _strip_comments_js(text)
        except Exception:  # noqa: BLE001 - a file the stripper cannot read is counted raw, never skipped
            pass
        n = len(pat.findall(text))
        if n:
            total += n
            where.append("%s:%d" % (fn, n))
    if "--teeth" in sys.argv:
        total += 1   # one more page-written blame than the ratchet allows must fail
    if total > BASELINE:
        failures.append(
            "page-written 'check your connection' copy rose to %d (ratchet %d): %s. Branch on "
            "navigator.onLine - offline: say so; online: 'WorkHive did not answer' - or route the error "
            "through whReadError/whWriteError, which already do." % (total, BASELINE, ", ".join(where)))

    if failures:
        print("FAIL outage-copy-honesty - %d problem(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1

    print("PASS outage-copy-honesty - whReadError branches on navigator.onLine and keeps its Status "
          "pointer on the online branch; every 5xx reaches the transport notice (and the 4xx family does "
          "not); the settle pass aliases its translator instead of throwing a swallowed ReferenceError; "
          "the retired 'Retry when you are back online' is absent and both honest branches "
          "(offline / the service did not answer) exist in English and Filipino.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
