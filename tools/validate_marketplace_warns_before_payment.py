#!/usr/bin/env python3
"""marketplace-warns-before-payment - T101: 100% of the money risk sits at one step.

This is a CONTACT-ONLY marketplace. There is no escrow, no held funds, no reversal - the buyer
contacts a stranger and pays them off-platform, and every peso of risk lives at that single moment.
RA 11967, the PH Internet Transactions Act, requires consumer education on the red flags in internet
transactions, so this is a legal floor as well as a decent one.

★STATING A FACT IS NOT WARNING. "Payment is off-platform" is true and tells a buyer nothing about
what to do; the page carries an actual warning at the decision point - inspect the item, meet at the
seller's business address or a public place, avoid paying in full up front to a new seller, and the
sentence that matters most: WorkHive never holds your payment, so we cannot reverse it.

★AND IT MUST NOT IMPLY PROTECTION IT DOES NOT PROVIDE. The opposite failure is worse than silence: a
buyer who believes there is escrow behaves as if losses are recoverable. So the gate also refuses
escrow / buyer-protection / money-back / guaranteed-refund language anywhere on the marketplace
surfaces, and holds the related credits sentence, since "credits back" reads as cash returning when
credits are spend-only and cannot be withdrawn.

★THE TRUST BAR IS THE SUBTLE CASE. "ID-Verified Sellers" as a bare heading reads as a property of
the RESULTS - that the sellers below are verified - when 3 of 9 listings had a verified seller. The
page says "ID-Verified badge per seller" instead: where to look, not a guarantee about what is
found.

Re-drive: python tools/validate_marketplace_warns_before_payment.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SURFACES = ["marketplace.html", "marketplace-seller.html"]
# language that promises the platform stands behind the transaction
PROMISES = re.compile(
    r"escrow|buyer protection|purchase protection|money[- ]back|guaranteed refund|"
    r"we (?:hold|guarantee) your (?:payment|money)|protected by workhive", re.I)


def visible_text(src: str) -> str:
    """Strip comments so prose ABOUT a promise is not read as the promise itself."""
    s = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    return s


def main() -> int:
    failures = []
    mk = io.open(ROOT / "marketplace.html", encoding="utf-8", errors="replace").read()

    # 1. the warning exists, and warns rather than merely stating
    if not re.search(r"Before you pay", mk, re.I):
        failures.append("no 'Before you pay' warning on the marketplace - this is a contact-only "
                        "marketplace with no escrow, so ALL of the money risk sits at the moment a "
                        "buyer takes a stranger off-platform, and RA 11967 requires the education")
    for clause, why in [
        (r"inspect the item", "inspect the item first"),
        (r"public place|business address", "meet somewhere safe"),
        (r"in full up front", "do not prepay a new seller in full"),
    ]:
        if not re.search(clause, mk, re.I):
            failures.append(f"the pre-payment warning no longer tells the buyer to {why} - stating "
                            f"that payment is off-platform is a FACT, not a warning")
    if not re.search(r"never holds your payment|cannot reverse it", mk, re.I):
        failures.append("the page no longer says WorkHive does not hold the payment and cannot "
                        "reverse it - the single sentence that sets a buyer's expectations correctly")

    # 2. and no surface implies protection that does not exist
    for name in SURFACES:
        p = ROOT / name
        if not p.exists():
            continue
        txt = visible_text(io.open(p, encoding="utf-8", errors="replace").read())
        for m in PROMISES.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            failures.append(f"{name}:~{line}: promises '{m.group(0)}' - there is no escrow and no "
                            f"reversal, and a buyer who believes otherwise behaves as though a loss "
                            f"is recoverable")

    # 3. credits must not read as money coming back
    if re.search(r"credits back", mk, re.I) and not re.search(
            r"not withdraw|cannot be withdrawn|spend-only|spent on WorkHive", mk, re.I):
        failures.append("the page shows 'credits back' without saying credits are spend-only and "
                        "cannot be withdrawn - the bare words read like money returning")

    # 4. the trust bar points at a badge, it does not vouch for the results
    if re.search(r"ID-Verified Sellers\s*<", mk):
        failures.append("the trust bar says 'ID-Verified Sellers' as a bare heading, which reads as a "
                        "property of the RESULTS rather than a per-card badge - the same false claim "
                        "the source chip carried when 3 of 9 listings had a verified seller")

    if failures:
        print("FAIL marketplace-warns-before-payment:")
        for f in failures:
            print("    - " + f)
        return 1

    print("  pre-payment warning present (inspect / meet safely / no full prepay / no reversal) · "
          "no escrow or protection promised · credits stated spend-only")
    print("PASS marketplace-warns-before-payment - the buyer is warned at the step where all the "
          "money risk is, and nothing promises a protection this platform does not provide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
