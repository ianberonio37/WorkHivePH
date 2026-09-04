#!/usr/bin/env python3
"""invite-code-is-unguessable - the one credential that admits a stranger to a plant (2026-08-26).

A hive's 6-character invite code is the whole of what stands between a stranger and a plant's
maintenance records: hand it over and you are in. It was generated with Math.random() - a plain
PRNG whose internal state can be recovered from a handful of observed outputs, which makes later
codes from the same page predictable. Wrong property for a credential, and there was no
compatibility excuse: createHive already REQUIRES crypto.randomUUID() (a null id aborts the
create), so the page depended on modern crypto two lines away.

★THE CENSUS IS WHY THIS GATE IS NARROW. 31 Math.random() uses across the production pages, and
exactly ONE was a credential. The rest are element ids, upload filenames, retry jitter and an
analytics session id (which already prefers crypto.randomUUID) - all cases where collision
resistance matters and unpredictability does not. A gate banning Math.random outright would have
generated 30 false findings and taught everyone to ignore it.

★IT ALSO GUARDS THE MODULO, which is the part a future editor would break silently: mapping random
bytes onto the alphabet with `b % len` is unbiased ONLY when len divides 256. The alphabet is 32
characters (O/0/I/1 omitted so the code survives being read aloud in a noisy plant), and 256 % 32
is 0, so every character gets exactly 8 of the 256 byte values. Add one character for readability
and the first 256 % len characters quietly become more likely - a real weakening that no test would
notice, so this gate computes it rather than trusting it.

Re-drive: python tools/validate_invite_code_is_unguessable.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failures = []
    page = io.open(ROOT / "hive.html", encoding="utf-8", errors="replace").read()

    m = re.search(r"function genCode\(\)\s*\{(.*?)\n\}", page, re.S)
    if not m:
        print("FAIL invite-code-is-unguessable - genCode() not found in hive.html; the invite-code "
              "generator moved and this gate no longer knows what it is guarding")
        return 1
    body = m.group(1)
    # strip comments so prose ABOUT Math.random does not read as a use of it
    code = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    code = re.sub(r"//.*", "", code)

    if re.search(r"Math\.random", code):
        failures.append("the invite code is generated with Math.random() - a plain PRNG whose state "
                        "is recoverable from a few outputs, which is the wrong property for the only "
                        "credential admitting someone to a hive")
    if not re.search(r"crypto\.getRandomValues|crypto\.randomUUID", code):
        failures.append("the invite code does not come from the CSPRNG (crypto.getRandomValues)")

    alpha = re.search(r"const chars\s*=\s*['\"]([^'\"]+)['\"]", code)
    if not alpha:
        failures.append("genCode()'s alphabet is no longer a literal this gate can measure")
    else:
        chars = alpha.group(1)
        n = len(chars)
        if len(set(chars)) != n:
            failures.append(f"the alphabet repeats characters ({n} long, {len(set(chars))} distinct), "
                            f"which skews the draw toward the repeated ones")
        if re.search(r"%\s*chars\.length|%\s*\d+", code) and 256 % n != 0:
            failures.append(f"the alphabet is {n} characters and 256 % {n} = {256 % n}, so mapping "
                            f"random bytes with a modulo now FAVOURS the first {256 % n} characters. "
                            f"Either restore a length that divides 256 or switch to rejection "
                            f"sampling - the bias is invisible to every other test")
        for bad in "O0I1":
            if bad in chars:
                failures.append(f"the alphabet contains '{bad}', which was deliberately omitted so a "
                                f"code can be read aloud in a noisy plant without being misheard")

    # the length has to stay meaningful: 32^6 is ~1.07e9, and the DB's UNIQUE(invite_code) turns a
    # collision into a clean create failure rather than a cross-tenant join
    ln = re.search(r"new Uint8Array\((\d+)\)", code)
    if ln and int(ln.group(1)) < 6:
        failures.append(f"the code is only {ln.group(1)} characters; 6 over a 32-character alphabet "
                        f"is the ~1.07e9 space this credential was sized for")

    if failures:
        print("FAIL invite-code-is-unguessable:")
        for f in failures:
            print("    - " + f)
        return 1

    n = len(alpha.group(1))
    print(f"PASS invite-code-is-unguessable - the code comes from the CSPRNG over a {n}-character "
          f"read-aloud-safe alphabet, and 256 % {n} = 0 so the byte-to-character modulo is exactly "
          f"unbiased.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
