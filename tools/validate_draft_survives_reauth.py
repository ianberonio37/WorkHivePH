#!/usr/bin/env python3
"""draft-survives-reauth - T38: typed work must outlive a session expiry.

A worker half-fills a logbook entry, the token dies, they sign in again. Whether their typing is
still there depends on a three-link chain that no single file makes visible, and every link is
somewhere else:

  1. whAutoSaveDraft persists the text to localStorage under its own key;
  2. session-timeout's clearIdentityHard wipes the IDENTITY keys and must not touch draft keys;
  3. the draft is restored only to the worker who typed it - an OWNER CHECK that reads
     `wh_last_worker`, the very key step 2 just deleted.

★SO THE DRAFT SURVIVES ONLY BECAUSE RE-AUTH PUTS THAT KEY BACK. Sign-in rewrites wh_last_worker, so
by the time the worker returns the owner check matches again and the text reappears. If the owner
check were ever re-keyed to something re-auth does NOT restore, every draft on the platform would be
silently discarded after an expiry - the form would come back empty and nothing would explain it.
That is the assertion here: the key the owner check reads must be one the sign-in path writes.

★THE OWNER CHECK ITSELF IS NOT THE BUG, it is the shared-tablet protection: worker A's draft must
not appear in worker B's form. Removing it would "fix" the expiry case by leaking someone's typing
to the next person on the device, which is worse.

Re-drive: python tools/validate_draft_survives_reauth.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DRAFTY = re.compile(r"draft|autosave|_wip|compose", re.I)


def main() -> int:
    failures = []
    utils = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    st = io.open(ROOT / "session-timeout.js", encoding="utf-8", errors="replace").read()
    idx = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()

    m = re.search(r"whAutoSaveDraft\s*=\s*function[^{]*\{(.*?)\n  \};", utils, re.S) or \
        re.search(r"function whAutoSaveDraft\([^)]*\)\s*\{(.*?)\n\}", utils, re.S)
    if not m:
        print("FAIL draft-survives-reauth - whAutoSaveDraft not found in utils.js; every draft on the "
              "platform depends on it")
        return 1
    body = m.group(1)

    owner_keys = set(re.findall(r"localStorage\.getItem\(\s*'([A-Za-z0-9_]+)'", body))
    identity_keys = {k for k in owner_keys if not DRAFTY.search(k)}
    if not identity_keys:
        failures.append("the draft owner check no longer reads an identity key, so a draft either "
                        "restores for anybody or for nobody - on a shared tablet the first is a leak")

    # ★AT LEAST ONE key in the chain must be rewritten by sign-in, not every one. The owner check is
    #   a FALLBACK CHAIN (wh_last_worker || wh_worker_name), and utils.js records that the alias
    #   reads are dead - "never written anywhere in the codebase (get-without-set)". Demanding that
    #   every link be restored flagged that dead alias and called a working chain broken; what
    #   matters is that the chain RESOLVES after re-auth, which one live link achieves.
    restored = [k for k in sorted(identity_keys)
                if re.search(rf"setItem\(\s*'{re.escape(k)}'", idx)]
    if not restored:
        failures.append(f"the draft owner check reads {sorted(identity_keys)}, and the sign-in path "
                        f"rewrites NONE of them - after an expiry wipes them the check can never "
                        f"match again and every saved draft is silently discarded")

    # and the expiry path must not wipe the DRAFT keys themselves
    wipe = re.search(r"function clearIdentityHard\([^)]*\)\s*\{(.*?)\n  \}", st, re.S)
    if wipe:
        wiped = re.findall(r"'([A-Za-z0-9_]+)'", wipe.group(1))
        drafty = [k for k in wiped if DRAFTY.search(k)]
        if drafty:
            failures.append(f"session expiry wipes {drafty}, which look like DRAFT storage - the text "
                            f"is gone before the worker ever gets the chance to sign back in")
    else:
        failures.append("could not read clearIdentityHard() to check what an expiry wipes")

    if failures:
        print("FAIL draft-survives-reauth:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"  owner check chain: {', '.join(sorted(identity_keys))} · restored by sign-in: "
          f"{', '.join(restored)} · expiry wipes no draft key")
    print("PASS draft-survives-reauth - a half-typed entry is still there after the session dies and "
          "the worker signs back in, and still belongs only to whoever typed it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
