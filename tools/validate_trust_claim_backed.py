#!/usr/bin/env python3
"""trust-claim-backed - T70: a verification badge requires the thing it verifies (2026-08-26).

The seller profile is where a buyer decides whether to trust a stranger with money.
Every pixel on it that reads as an endorsement is a claim the platform is making on
that stranger's behalf, and the recorded incident is what happens when one is not
enforced: the "Certified" chip used to render on the `cert_verified` flag ALONE across
three surfaces, and three sellers were found with cert_verified true, certifications
NULL and cert_verified_at NULL - a violet chip asserting an admin had verified trade
credentials THAT DID NOT EXIST.

CENSUSED EVERY TRUST CLAIM ON THE PROFILE 2026-08-26, and the page is in good order -
each is computed from data, not decoration:
    Top rated     ratingAvg >= 4.5 AND ratingCount >= 5
    Quick reply   avgResponseHours < 4 AND replyCount >= 5
    Tier          stated thresholds (silver 11 sales, gold 51) plus "set by WorkHive
                  from completed sales, not self-assigned"
    ID Verified   gated on kyb_verified
    Certified     routed through whCertBadgeEarned on all three surfaces
The certifications SECTION reads cert_verified on its own, and that is correct: the
whole block is already inside `if (certSection && certs.length)`, so the list is
non-empty by construction. Read before accusing - it looked like the original bug and
is not.

THE ASSERTION, guarding the fixed class rather than a present defect: no buyer-facing
surface may present a certification claim from `cert_verified` alone. It must either
call the central predicate or guard on the certifications list in the same breath.

★ADMIN SURFACES ARE EXCLUDED BY NAME, and the reason is not convenience. marketplace-
admin, founder-console and platform-actions are where verification is GRANTED - they
must show the raw flag, including the exact state "flag set but no certifications on
file" that this gate exists to keep off the buyer's screen. Blinding the moderator to
the thing they moderate would be the opposite of the goal.

Usage: python tools/validate_trust_claim_backed.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MODERATION = {"marketplace-admin.html", "founder-console.html", "platform-actions.html"}
SKIP = re.compile(r"backup|test|^index-", re.I)

# a render that ASSERTS certification to a reader
CLAIM = re.compile(r"(Certified|Cert Verified|Verified by admin|Certifications Verified)", re.I)
BACKING = re.compile(r"whCertBadgeEarned|certifications|certs\.length|certs\.length\s*[><]")

# ★THE SECOND CLASS, ADDED 2026-08-28 AFTER THE CENSUS ABOVE PROVED TOO NARROW. That census
# recorded "ID Verified — gated on kyb_verified" as a platform fact; it was a fact about the
# PROFILE PAGE, examined alone. Three other surfaces rendered the same claim from
# marketplace_listings.seller_verified — a per-listing copy that drifts from the seller's checked
# identity — so Dennis Aquino (kyb_verified FALSE, seller_verified TRUE) read as VERIFIED on the
# marketplace card, the detail sheet and asset-hub, and UNVERIFIED on his own profile. One badge,
# four predicates, and the census had generalised from the one surface that happened to be right.
#
# Now centralised in whIdVerified(), so this asserts what the Certified assertion asserts: a
# buyer-facing surface may not grant the identity badge from the drifting copy.
ID_CLAIM = re.compile(r"(ID Verified|badge-verified)", re.I)
ID_BACKING = re.compile(r"whIdVerified")
ID_DRIFTED = re.compile(r"(?<![\w.])(?:item|r|listing|row)\.seller_verified\b")


# ★THE NEGATIVE LOOKAHEAD IS LOAD-BEARING. `accept="image/*"` contains a literal /* , and a
# naive block-comment strip treated it as a comment OPENER - on logbook.html that swallowed 58,551
# characters up to the next real */, blanking an entire modal including an onclick. A census built
# on that reported a live, recently-hardened Save handler as dead code. A real comment opener is
# never immediately followed by a quote; a MIME wildcard in an attribute always is.
def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote) below: accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html")))
             if not SKIP.search(Path(f).name) and Path(f).name not in MODERATION]
    if not files:
        print("SKIP trust-claim-backed - no pages found")
        return 0

    claims, unbacked = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in CLAIM.finditer(src):
            # only claims sitting near the flag are this gate's business; prose elsewhere is not
            window = src[max(0, m.start() - 1200):m.end() + 400]
            if "cert_verified" not in window:
                continue
            claims += 1
            if not BACKING.search(window):
                line = src[:m.start()].count("\n") + 1
                unbacked.append(f"{name}:{line} presents \"{m.group(1)}\" from cert_verified alone - "
                                f"no call to whCertBadgeEarned and no certifications guard nearby")

    # ── the ID-VERIFIED class, which the census above missed by examining one surface ──────────
    id_claims, id_drifted = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in ID_CLAIM.finditer(src):
            window = src[max(0, m.start() - 900):m.end() + 300]
            # only renders that DECIDE the badge are this gate's business
            if not re.search(r"\bif\s*\(|\?\s*`|&&", window):
                continue
            id_claims += 1
            if ID_DRIFTED.search(window) and not ID_BACKING.search(window):
                line = src[:m.start()].count("\n") + 1
                id_drifted.append(f"{name}:{line} grants the identity badge from a listing's "
                                  f"seller_verified copy instead of whIdVerified()")

    print(f"  buyer-facing certification claims: {claims} | unbacked: {len(unbacked)} "
          f"| identity-badge renders: {id_claims} | from the drifting copy: {len(id_drifted)} "
          f"| moderation surfaces excluded: {len(MODERATION)}")
    if id_drifted:
        print(f"FAIL trust-claim-backed - {len(id_drifted)} identity badge(s) read the wrong column:")
        for x in id_drifted[:10]:
            print("    - " + x)
        print("    marketplace_listings.seller_verified is a per-listing COPY of the seller's checked")
        print("    identity and drifts from it. One seller once read VERIFIED on three surfaces and")
        print("    UNVERIFIED on his own profile. Call whIdVerified(seller, listing).")
        return 1
    if unbacked:
        print(f"FAIL trust-claim-backed - {len(unbacked)} claim(s) the data does not enforce:")
        for x in unbacked[:10]:
            print("    - " + x)
        print("    A verification badge requires the thing it verifies. Three sellers once carried a")
        print("    violet 'Certified' chip with certifications NULL and cert_verified_at NULL - the")
        print("    platform vouching, to a buyer about to send money, for credentials that did not")
        print("    exist. Call whCertBadgeEarned, or guard on the certifications list in the same breath.")
        return 1
    print(f"PASS trust-claim-backed - all {claims} buyer-facing certification claims are backed by the "
          f"certifications they assert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
