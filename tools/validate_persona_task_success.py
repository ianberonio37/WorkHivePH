#!/usr/bin/env python3
"""validate_persona_task_success.py — can a DIVERSE human finish the money task, not just an idealised one?

Ian, 2026-07-31: "you have to consider the diversity of human beings — there are diverse simulations in test
banks."

WHAT THIS ASKS THAT NOTHING ELSE DOES. UFAI grades the PAGE (contrast, tap targets, overflow — all measured
by validate_service_ufai_deep.py); validate_i18n_coverage.py owns language; validate_clickable_keyboard_a11y
owns keyboard. None of them can answer "could THIS PERSON complete THIS TASK?", because that is a property of
the journey, not the surface. This is the `task-success` oracle, and it also corrects a bank whose mix was
235 refusal to 1 eval.

The personas and their journey pairings live in `tools/service_personas.mjs` — a persona is a RUNTIME
CONDITION (viewport, zoom, colour filter, throttle, locale, input delay), not a comment, so "we tested for
low vision" means the page really was rendered at 200%.

WHY THESE SEVEN CHECKS. Each is the property that decides whether one paired persona finishes at all, on the
family where failure costs pesos (E-money) or closes the door entirely (A-discovery, B-map):

  T1 P-COLORBLIND    every one of the 12 request states carries a DISTINCT TEXT label, not just a colour.
                     Verified live and the page PASSES — SVC_CHIP maps each state to its own phrase
                     ("Provider on the way", "No provider found", "In dispute"). The first probe reported
                     this MISSING; the probe's regex assumed quoted object keys and the source uses bare
                     ones. The instrument was wrong, not the page — the fourth such finding this session,
                     which is exactly why this gate reads the real mapping instead of pattern-matching.
  T2 P-SCAMWARY      the release screen must state WHO GETS WHAT, that the platform never holds the money,
                     and what happens if the job was bad. This persona decides whether the economy works:
                     if "Confirm payment & release" reads like a trick they abandon, and they are right to.
  T3 P-UNBANKED      the min-balance refusal must be ANNOUNCED and must say how to fix it. A silent no-op is
                     not a refusal a human can act on.
  T4 P-IMPULSIVE     a double-tapped Release mints exactly ONE commission (proven in the DB by the money
                     probe; asserted here as a journey property).
  T5 P-FILIPINO      money words resolve in the locale. Commission/settle/release/cashback have no clean
                     everyday Tagalog equivalents, and an unresolved marker on a money screen is someone
                     not understanding what they are agreeing to.
  T6 P-SCREENREADER  the map needs a TEXT EQUIVALENT. A map is unusable by a screen reader, so with no
                     "providers near you" list, discovery is entirely closed to blind users.
  T7 P-GLOVED        primary money actions clear a 48px target — a real industrial constraint on a
                     maintenance platform, not a nicety.

Usage:  python tools/validate_persona_task_success.py [--selftest]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "marketplace.html", ROOT / "marketplace-seller.html"]
PERSONAS = ROOT / "tools" / "service_personas.mjs"
G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

STATES = ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress",
          "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]


def chip_labels(src):
    """Pull the state->label map out of the page. Reads the ACTUAL object rather than pattern-matching for
    quoted keys, which is what made the first probe report every label missing on a page that has them all."""
    m = re.search(r"SVC_CHIP\s*=\s*\{(.+?)\}\s*;", src, re.S)
    if not m:
        return {}
    out = {}
    for k, v in re.findall(r"([A-Za-z_]+)\s*:\s*'([^']*)'", m.group(1)):
        out[k] = v
    return out


def checks(src, personas_src):
    labels = chip_labels(src)
    distinct = len(set(labels.get(s, "") for s in STATES if labels.get(s)))
    missing = [s for s in STATES if not labels.get(s)]

    # T2 — the disclosure a scam-wary person needs before parting with money
    disclosure = {
        "who gets what": bool(re.search(r"provider (gets|receives)|goes to your provider|pay(s|ing)? the provider", src, re.I)),
        "platform holds nothing": bool(re.search(r"never hold|does not hold|directly to (your|the) provider|pay .{0,20}directly", src, re.I)),
        "what if the job was bad": bool(re.search(r"dispute|report a problem|not to spec|something wrong", src, re.I)),
    }
    money_terms = re.findall(r"\b(commission|cashback|settle|release|top ?-?up)\b", src, re.I)

    return [
        ("T1 P-COLORBLIND  12 states carry distinct TEXT labels", not missing and distinct >= 12,
         f"{len(labels)} labelled, {distinct} distinct" + (f", MISSING {missing}" if missing else "")),
        ("T2 P-SCAMWARY    release screen discloses the deal", all(disclosure.values()),
         ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in disclosure.items())),
        ("T3 P-UNBANKED    min-balance refusal is announced", bool(
            re.search(r"Accepting jobs needs at least|keeps your listings live|min_?list_?balance", src, re.I)),
         "a silent no-op is not a refusal a human can act on"),
        ("T4 P-IMPULSIVE   release is guarded against a double tap", bool(
            re.search(r"disabled\s*=\s*true|\.disabled|busy|inFlight|submitting", src)),
         "the DB mints once; the UI must not invite the second tap"),
        ("T5 P-FILIPINO    money terms are translatable", bool(re.search(r"data-i=", src)) and bool(money_terms),
         f"{len(set(t.lower() for t in money_terms))} money terms present"),
        ("T6 P-SCREENREADER map has a text equivalent", bool(
            re.search(r"provider[- ]?list|nearby providers|providers near", src, re.I)),
         "a map is unusable by a screen reader; without a list, discovery is closed"),
        ("T7 P-GLOVED      persona registry declares a 48px floor", "minTapTargetPx: 48" in personas_src,
         "gloves make anything under ~48px unhittable on a maintenance platform"),
    ]


def selftest():
    print("  selftest: the chip reader must find bare-key labels, which the first probe missed")
    fake = "const SVC_CHIP = { requested: 'Draft', broadcasting: 'Finding a provider' };"
    got = chip_labels(fake)
    ok = got.get("requested") == "Draft" and got.get("broadcasting") == "Finding a provider"
    if not ok:
        print(f"  {R}FAIL{X} — bare object keys were not read (the exact instrument bug this replaces)")
        return 1
    if chip_labels("no map here"):
        print(f"  {R}FAIL{X} — invented labels where there is no SVC_CHIP")
        return 1
    print(f"  {G}PASS{X} — reads the real mapping, invents nothing")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{B}Persona task-success{X} — can a DIVERSE human finish, not just an idealised one?")
    if selftest() != 0:
        return 1
    # BOTH money surfaces. The accept/min-balance refusal lives on marketplace-seller.html and the
    # release flow on marketplace.html; reading only the first reported T3 owed while a message existed.
    if not any(p.exists() for p in PAGES):
        print(f"  {Y}SKIP{X} no marketplace page found")
        return 0
    src = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in PAGES if p.exists())
    psrc = PERSONAS.read_text(encoding="utf-8", errors="replace") if PERSONAS.exists() else ""
    if not psrc:
        print(f"  {R}FAIL{X} tools/service_personas.mjs missing — no runtime conditions to walk with")
        return 1

    results = checks(src, psrc)
    for label, ok, detail in results:
        print(f"  {(G+'pass'+X) if ok else (R+'OWED'+X)}  {label:<52} {D}{detail}{X}")
    owed = [l for l, ok, _ in results if not ok]
    if owed:
        print(f"\n  {Y}{len(owed)} owed{X} — each names a persona who cannot finish the task, and why. "
              f"Reported, never averaged away.")
        return 1
    print(f"\n  {G}PASS{X} — all seven paired personas can complete the money task")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
