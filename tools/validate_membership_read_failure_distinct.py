#!/usr/bin/env python3
"""Gate `membership-read-failure-distinct` - a membership read that FAILED is not a membership that is ABSENT.

Found 2026-10-06 by walking LXP199 (analytics-report) with PostgREST genuinely stopped. Four edge-function
membership gates were written as:

    const { data: _mem } = await db.from("v_worker_truth")...maybeSingle();
    if (!_mem) return 403 "Caller is not an active member of this hive";

The read's `error` was destructured away and discarded, so a read that NEVER RAN produced `!_mem` and the
function announced a fact about the person's standing in the hive on the strength of no evidence at all.

MEASURED CONSEQUENCE: Bryan Garcia - an active member of Baguio Textile Mills whose full 8,117-character
report had generated two minutes earlier - pressed Generate Report during the outage and was told "You are
not an active member of this hive, so its data cannot be read. Switch or rejoin a hive, then retry." The
advice cannot work (nothing is wrong with his membership), it is alarming (it says his access was revoked),
and the one true cause was never mentioned. The client-side mapper was innocent: it was handed the literal
sentence "Caller is not an active member of this hive" and mapped it faithfully.

THE SHAPE OF THE RULE: a read has THREE outcomes, not two - a row, no row, and no answer. The third is the
refused/failed read, and collapsing it into "no row" turns an outage into an accusation. So every membership
gate must capture `error` and answer 503 ("could not be CHECKED") before it is allowed to conclude 403
("is not a MEMBER").

Static, so it runs in --fast with no DB, no runtime and no browser.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bug_repro_inventory import _strip_comments_js  # noqa: E402  (blanks comments, preserving offsets)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCS = os.path.join(ROOT, "supabase", "functions")

# The canonical hive-scoped identity view. A read of it filtered to an ACTIVE membership is, by
# construction, a membership gate: presence means verified member, so absence is about to be treated
# as a refusal - which is exactly the decision this gate audits.
VIEW = "v_worker_truth"

READ = re.compile(
    r"const\s*\{\s*data:\s*(?P<data>[A-Za-z_$][\w$]*)\s*"
    r"(?:,\s*error:\s*(?P<err>[A-Za-z_$][\w$]*)\s*)?\}\s*=\s*await\s+\w+\s*\n?\s*"
    r"\.?from\(\s*[\"']" + re.escape(VIEW) + r"[\"']\s*\)",
    re.S)


def _fn_body_js(src, name):
    """The source of one top-level `async function name(...) {...}` in a JS file, by brace matching."""
    m = re.search(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src, re.M)
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
    if not os.path.isdir(FUNCS):
        print("FAIL membership-read-failure-distinct - %s not found" % FUNCS)
        return 1

    checked, failures = 0, []
    for dirpath, _dirs, files in os.walk(FUNCS):
        for fn in sorted(files):
            if not fn.endswith(".ts"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            src = io.open(path, encoding="utf-8").read()

            for m in READ.finditer(src):
                data, err = m.group("data"), m.group("err")
                # The window from the read to its decision. 1,400 chars comfortably spans the longest
                # of these gates (the shared tenant-context one) without reaching the next read.
                tail = src[m.end():m.end() + 1400]
                # Only a read filtered to an ACTIVE membership is a membership GATE. A read that
                # selects a worker_name for display is not making an access decision.
                if not re.search(r"hive_status[\"']?\s*,\s*[\"']active", tail):
                    continue
                neg = re.search(r"if\s*\(\s*!\s*" + re.escape(data) + r"\s*\)", tail)
                if not neg:
                    continue  # the row is used, not tested for absence - not a refusal gate
                checked += 1
                line = src[:m.start()].count("\n") + 1

                if not err:
                    failures.append(
                        "%s:%d - the membership read discards its `error`. A read that never ran is "
                        "indistinguishable from an absent membership here, so an outage will be "
                        "reported as revoked access. Destructure `error:` and answer 503 first."
                        % (rel, line))
                    continue

                before_neg = tail[:neg.start()]
                errbranch = re.search(r"if\s*\(\s*" + re.escape(err) + r"\s*\)", before_neg)
                if not errbranch:
                    failures.append(
                        "%s:%d - `%s` is captured but never checked BEFORE `if (!%s)`. Capturing the "
                        "error changes nothing if the negative conclusion is still reached first: the "
                        "person is still told their membership is gone when the truth is the service "
                        "did not answer." % (rel, line, err, data))
                    continue

                # The honest answer is a 5xx. A 403 for a failed read is the original defect with
                # extra steps; a 200 would silently grant access on an unverified read, which is worse.
                guarded = before_neg[errbranch.start():]
                if not re.search(r"\b503\b", guarded):
                    failures.append(
                        "%s:%d - the `%s` branch does not answer 503. 'Could not be CHECKED' is a "
                        "server-state answer the reader waits out; sending 403 keeps accusing them, "
                        "and a 2xx would grant access on a read that never happened."
                        % (rel, line, err))

    # -- the SAME class on the client: the identity resolver ------------------------------------
    # Third instance found on one day (2026-10-06, walking LXP204 with PostgREST stopped), and the one
    # with the worst consequence: restoreIdentityFromSession destructured getSession()'s error away and
    # read "no session" as a SIGN-OUT, so it deleted the cached worker name and returned '' - every page
    # gating on identity then sent a signed-in person to the sign-in wall. Measured on audit-log.html:
    # redirected to index.html?signin=1 while `sb-127-auth-token` was still in localStorage and
    # wh_last_worker had been wiped, so the damage OUTLIVED the outage that caused it.
    utils = os.path.join(ROOT, "utils.js")
    if not os.path.exists(utils):
        failures.append("utils.js not found - the client half of this class cannot be checked.")
    else:
        usrc = io.open(utils, encoding="utf-8").read()
        body = _fn_body_js(usrc, "restoreIdentityFromSession")
        # 2026-10-29: the resolver became a wrapper that shares one in-flight lookup per load (a page asked the
        # membership up to four times); the logic it guards lives in the function the wrapper calls. Follow the
        # delegation by name - a wrapper that stopped delegating is checked as itself, and fails.
        if body and "_restoreIdentityFromSessionOnce(" in _strip_comments_js(body):
            body = _fn_body_js(usrc, "_restoreIdentityFromSessionOnce")
        if not body:
            failures.append(
                "restoreIdentityFromSession not found in utils.js. It is the one function every gated "
                "page's identity depends on; if it moved, re-point this check rather than dropping it.")
        else:
            checked += 1
            if not re.search(r"error:\s*\w*[Ss]essErr", body):
                failures.append(
                    "restoreIdentityFromSession discards getSession()'s error again. getSession refreshes "
                    "an expired token, so an unreachable service yields no session - read as a sign-out, "
                    "it ejects a signed-in person AND deletes their cached identity.")
            # COMMENTS BLANKED FIRST: the teeth test disabled the discriminator in CODE and this check
            # still passed, because the words "auth-token" survived in the comment that explains it.
            # Twice in one session a gate of mine read its own prose as evidence.
            code = _strip_comments_js(body)
            if not re.search(r"/\^sb-\.\*-auth-token\$/", code):
                failures.append(
                    "the stored-token discriminator is gone from restoreIdentityFromSession. Without it "
                    "there is no way to tell 'signed out' from 'could not verify': supabase-js removes "
                    "the sb-*-auth-token key on an explicit signOut, so its presence beside a null "
                    "session means the answer was unavailable, not negative.")
            # The clear-the-cache branch must sit AFTER the could-not-tell return, or the wipe still runs.
            giveup = re.search(r"return cached;", code)
            wipe = re.search(r"removeItem\(\s*['\"]wh_last_worker", code)
            if giveup and wipe and wipe.start() < giveup.start():
                failures.append(
                    "the cache wipe in restoreIdentityFromSession now runs BEFORE the could-not-verify "
                    "return, so an outage still deletes a signed-in person's identity - the half of this "
                    "defect that outlived the outage.")

    if checked == 0:
        print("FAIL membership-read-failure-distinct - found 0 membership gates on %s. Either the view "
              "was renamed or the gating moved; re-point this check rather than leaving it vacuous."
              % VIEW)
        return 1

    if failures:
        print("FAIL membership-read-failure-distinct - %d of %d membership gate(s) can report an "
              "outage as revoked access:" % (len(failures), checked))
        for f in failures:
            print("  - %s" % f)
        return 1

    print("PASS membership-read-failure-distinct - all %d membership gate(s) on %s capture the read's "
          "error and answer 503 ('your membership could not be CHECKED') before they are allowed to "
          "conclude 403 ('you are not a MEMBER'). A refused read is the third outcome, not a refusal."
          % (checked, VIEW))
    return 0


if __name__ == "__main__":
    sys.exit(main())
