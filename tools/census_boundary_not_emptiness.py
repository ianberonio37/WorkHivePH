#!/usr/bin/env python3
"""census_boundary_not_emptiness.py - which surfaces can tell a REFUSAL from an ABSENCE?

Not a gate (yet). A census, written to put a number on the 34 identical `boundary_not_emptiness` bank
rows: "a permission boundary reads as 'not visible with this session', never as 'nothing here'."

WHY THE PROPERTY IS HARD, stated because it explains the expected answer: RLS refuses by FILTERING, not
by raising. A `USING` clause hands back zero rows and no error, so a foreign-hive read and a genuinely
empty hive are byte-identical at the client. A page can only tell them apart if it makes a SEPARATE
membership/role check and has somewhere to say so. Most do not.

WHAT IS COUNTED, and the limits of it:
  * ABSENCE states - elements whose id/class marks an empty or no-results state. These are easy to find
    and pages have many.
  * REFUSAL states - text that names a permission boundary to a person. Counted only when it is REAL
    user-facing copy: matches inside HTML comments, JS `//` and `/* */` comments are stripped first,
    because the first pass at this counted four "refusal states" in inventory.html that were, every one,
    a source comment or the unrelated toast "Part removed from inventory."
  * MEMBERSHIP DISCRIMINATOR - evidence the page can even ASK the question (a membership/role/status
    read). Without one, a refusal state is unreachable by construction, so a page with refusal copy but
    no discriminator is reported separately rather than credited.
This is a NECESSARY-CONDITION census: a page with zero refusal states provably cannot distinguish. A page
with them still has to be walked to show it uses them on the right branch - the runtime half belongs to
the walk lane, and this file does not pretend otherwise.
"""
import glob, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

SKIP_DIRS = ("_fixtures", "node_modules", "learn", "tools", ".git", "substrate")

ABSENCE = re.compile(r"""id="([a-z0-9_-]*(?:empty|no-results)[a-z0-9_-]*)\"""", re.I)
# copy that names a permission boundary TO A PERSON
# ★WIDENED 2026-08-31, after the live walk exposed the first vocabulary as too narrow. shift-brain
# answers a hiveless session with "Shift Brain needs a hive ... Join or create a hive to see briefings
# for your team. Go to Hive" - it names the boundary AND offers the remedy, and the first regex scored
# it as having NO refusal copy. A census whose vocabulary is narrower than the product's is measuring
# its own wording rather than the product's, and it does so in the pessimistic direction: it invents a
# backlog out of surfaces that were already handling the case.
# Refusal vocabulary, kept IDENTICAL to the walk harness so the static and live instruments
# cannot disagree about what a refusal sounds like. Widened four times in one session, each
# time because the product said it a way the regex did not know ('needs a hive'; 'Create or
# join a Hive' vs 'join or create'; 'does not have access' vs 'do not'). Every widening moved
# the count DOWN - the instrument was inventing backlog, never hiding it.
REFUSAL = re.compile(r"""(not visible with this session|no longer a member|not a member of|belongs to a hive|was deleted, or|removed from|(does|do|did) ?n.t have access|don't have access|do not have access|does not have access|no access to|cannot see|not authorised|not authorized|access denied|not permitted|ask (a|your) supervisor|only supervisors|supervisors only|switch hive|choose a hive|select a hive|needs a hive|no hive selected|not in (a|this) hive|hive-by-hive|(join|create)[^.]{0,30}hive|hive[^.]{0,30}(to (start|see|join))|a workhive first|team tool)""", re.I)
# Can the page even ASK whether this was a refusal? Two legitimate ways, and the first version of this
# census only knew one - it scored marketplace.html "NO" while marketplace is the single surface on the
# platform that DOES discriminate. An instrument that marks the reference implementation as the worst
# case is measuring the wrong thing.
#   (a) a membership/role read - the only way to catch the SILENT refusal, where RLS filters a row out
#       and the response is a perfectly ordinary 200 with zero rows;
#   (b) an HTTP status branch - catches the LOUD refusal (403/401) that the server announces, which is
#       what marketplace does.
# Both are recorded, and they are NOT equivalent: (b) alone cannot see a filtered row, so the census
# prints which kind each surface has rather than collapsing them into one yes/no.
# ★SPLIT AGAIN, because "has a discriminator" was overstating and it overstated in the direction that
# matters - fix COST. The first pattern lumped a real membership QUERY together with mere role
# VOCABULARY, so alert-hub and community were credited with a discriminator while neither file contains
# a single hive_members read: they carry HIVE_ROLE strings, which tell you what a member may do, not
# whether this person still IS one. Those are different jobs and different amounts of work:
#   query      - the page already asks the server and can simply say the answer (pm-scheduler, inventory)
#   role-vocab - the page knows a role but never re-checks membership; the check must be ADDED
# ★A PER-FILE CENSUS CANNOT SEE CENTRALLY-PROVIDED COPY, and that was the biggest single error in this
# instrument. analytics.html was listed as having NO refusal copy while the WALK watched it render
# "your account does not have access to it. Your session is fine. Ask a supervisor if you need it." -
# because that sentence lives in utils.js:937/:2354, the shared error taxonomy, and appears ZERO times
# in analytics.html. A page that routes its failures through the central helpers is not silent; it is
# doing the RIGHT thing, and grading it on literal strings in its own file punishes exactly the
# centralisation this platform spent effort building.
CENTRAL_REFUSAL = re.compile(r"""(whReadError|whListError|whWriteError|whIsAccessDenied
                                |whAuthRequiredToast|whAiError)""", re.I | re.X)

DISCRIM_QUERY = re.compile(r"""(hive_members|user_hive_ids|recoverHiveMembership
                              |validateHiveMembership|hive_status)""", re.I | re.X)
DISCRIM_ROLEVOCAB = re.compile(r"""(wh_hive_role|HIVE_ROLE|is_supervisor|\.role\s*===)""", re.I | re.X)
DISCRIM_STATUS = re.compile(r"""(_accessDenied|accessDenied|status\s*===\s*403|status\s*===\s*401
                               |=== *'?403|\b403\b[^0-9]{0,24}(refus|denied|forbidden)
                               |PGRST301|42501)""", re.I | re.X)


def strip_comments(src: str) -> str:
    """HTML comments and JS line/block comments. The census is about what a PERSON reads."""
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)
    return src


BASELINE = os.path.join(ROOT, "boundary_refusal_baseline.json")


def main(argv):
    check = "--check" in argv
    rebaseline = "--rebaseline" in argv
    pages = []
    for p in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        base = os.path.basename(p)
        # ★MATCH THE RELATIVE PATH, NOT THE ABSOLUTE ONE. The first version tested the full path and
        # skipped every single file: this repo lives under ".../Self-learning Road-Map/...", and
        # "Self-LEARNing" contains "learn". A substring test against an absolute path silently inherits
        # every word in someone's directory names - the census reported "0 surfaces" and looked calm.
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        if any(rel.startswith(s + "/") or rel == s for s in SKIP_DIRS):
            continue
        pages.append((base, p))

    rows, no_refusal = [], []
    for base, path in pages:
        raw = io.open(path, encoding="utf-8", errors="replace").read()
        clean = strip_comments(raw)
        absence = sorted(set(ABSENCE.findall(raw)))
        refusal = sorted({m.group(0).lower() for m in REFUSAL.finditer(clean)})
        central = sorted({m.group(0) for m in CENTRAL_REFUSAL.finditer(clean)})
        # delegating to the shared taxonomy IS refusal capability - credit it as such
        if central and not refusal:
            refusal = ['via ' + central[0] + '()']
        d_q = bool(DISCRIM_QUERY.search(clean))
        d_r = bool(DISCRIM_ROLEVOCAB.search(clean))
        d_s = bool(DISCRIM_STATUS.search(clean))
        # ordered by how close the page already is to being able to SAY it
        discrim = ('membership-query' if d_q else
                   'http-status' if d_s else
                   'role-vocab-only' if d_r else '')
        rows.append((base, len(absence), len(refusal), discrim, refusal[:2]))
        if absence and not refusal:
            no_refusal.append(base)

    rows.sort(key=lambda r: (r[2], -r[1]))
    print(f"  {'surface':32} {'absence':>8} {'refusal':>8}  discriminator")
    for base, na, nr, disc, sample in rows:
        colour = RED if (na and not nr) else (GREEN if nr else DIM)
        print(f"  {colour}{base:32}{RST} {na:>8} {nr:>8}  {disc or 'NO':<12}"
              + (f"   {DIM}{sample[0][:40]}{RST}" if sample else ""))

    with_absence = [r for r in rows if r[1] > 0]
    print(f"\n  {len(pages)} surfaces · {len(with_absence)} own an absence state · "
          f"{RED}{len(no_refusal)}{RST} of those have NO refusal copy at all")
    print(f"  {DIM}A page with zero refusal states cannot distinguish a refusal from an absence -"
          f" that is provable from here. The converse is not: refusal copy still has to be WALKED to"
          f" show it fires on the right branch.{RST}")

    # ★A FORWARD-ONLY RATCHET, NOT A FAIL. 25 of 26 surfaces cannot distinguish a refusal from an
    # absence today, so a gate demanding zero would be red on the day it was written - and a gate that
    # is red by default is one people learn to scroll past. The ordering this repo already uses is fix
    # first, then enforce (the retry_path family did exactly this). So this holds the LINE: the count
    # may fall, never rise. A new surface shipping an empty state with no way to say "you cannot see
    # this" fails here on the next run, which is the regression that matters while the backlog is worked
    # down.
    current = sorted(no_refusal)

    if rebaseline:
        json.dump({"_doc": "Surfaces owning an absence state but NO refusal copy. Forward-only:"
                           " this list may SHRINK, never grow. Re-baseline only when it shrinks.",
                   "count": len(current), "surfaces": current},
                  io.open(BASELINE, "w", encoding="utf-8"), indent=1)
        print("  " + YEL + "re-baselined" + RST + " at " + str(len(current)) + " surface(s)")
        return 0

    if check:
        try:
            base = json.load(io.open(BASELINE, encoding="utf-8"))
        except Exception:
            print(RED + "FAIL" + RST + " boundary-refusal-ratchet: no baseline. Run --rebaseline once.")
            return 1
        known = set(base.get("surfaces") or [])
        regressed = sorted(set(current) - known)
        if regressed:
            print("")
            print(RED + "FAIL" + RST + " boundary-refusal-ratchet: " + str(len(regressed))
                  + " NEW surface(s) own an empty state with no way to say a refusal happened: "
                  + ", ".join(regressed))
            return 1
        fixed = sorted(known - set(current))
        print("")
        if fixed:
            print(GREEN + "PASS" + RST + " boundary-refusal-ratchet: improved - " + str(len(fixed))
                  + " surface(s) gained refusal copy (" + ", ".join(fixed)
                  + "). Re-baseline to lock the gain in.")
        else:
            print(GREEN + "PASS" + RST + " boundary-refusal-ratchet: held at " + str(len(current))
                  + " (baseline " + str(base.get("count")) + "); no new silent surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
