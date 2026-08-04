#!/usr/bin/env python3
"""validate_live_mcp_bank.py — a green scenario must carry TYPED evidence, and that evidence EXPIRES.

BORN FROM A FALSE 343 (2026-08-04). The live-MCP bank reported 343 green / 0 owed. Ian: "I don't believe
what you have accomplished all the flywheel walks owed." He was right, and the mechanism was precise:

    LM-A-discovery-market-anon-populated was green on the oracle "the surface renders real rows and every
    visible number matches its source of truth". Walking it live showed the credits-back chip had
    DISAPPEARED from every priced listing — service_knob('reward_max_per_listing') returns NULL meaning
    "no cap" (the function says so in its own comment), the client read it through Number(null) -> 0, and
    Math.min(raw, 0) zeroed every chip. The one place a buyer meets the 10% reward was gone, and the page
    still rendered perfectly.

So the count was never the problem. The problems were:
  1. a green cell carried NO TYPED EVIDENCE — nobody could ask "green because of what?"
  2. a green cell NEVER EXPIRED — the code underneath could change and the row stayed green forever
  3. a STRUCTURAL probe was allowed to satisfy a BEHAVIOURAL oracle ("renders fine" vs "the number is right")

This gate fixes all three, mechanically. The anti-drift doctrine was already written down in
DEEPWALK_JOURNEY_BUGHUNT_ROADMAP.md §0 and CORRECTNESS_SCOREBOARD.md §6.0 — "COVERED requires EVIDENCE, a
cited gate name OR a live-walk ledger ref" — and nothing enforced it on the registry. Prose does not hold.

THE RULES (each with a self-test that proves it fires):
  R1  a non-owed row carries evidence{kind, ref, asserts} with a non-empty `asserts`
  R2  kind=gate  -> the ref names a gate id that exists in run_platform_checks.py
  R3  kind=live-walk -> the ref carries a date and a URL that exists in the SURFACES table
  R4  evidence.sha still matches a fresh hash of evidence.depends_on -> else the row is STALE
  R5  forward-only ratchet on green, with STALE excluded from the denominator so drift is visible
  R6  a behavioural `asserts` may not rest on purely structural evidence (the exact false-343 defect)

STALE is a first-class state and deliberately not "owed": it WAS true, the ground moved, re-walk it.
This is the same source_sha idea validate_substrate_freshness.py already uses for substrate chunks — a
proven pattern here, applied to the claim instead of the chunk.

Usage:  python tools/validate_live_mcp_bank.py [--selftest] [--report] [--accept]
"""
import hashlib
import json
import os
import re
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
BASELINE = os.path.join(ROOT, "live_mcp_bank_baseline.json")
CHECKS = os.path.join(ROOT, "run_platform_checks.py")

VALID_KINDS = {"live-walk", "gate", "psql", "declared-na"}

# A claim about a VALUE or a BEHAVIOUR cannot be settled by "the page rendered". These verbs are the tell.
BEHAVIOURAL_RE = re.compile(
    r"\bmatch(es|ing)?\b|\bequals?\b|\bcorrect\b|\bsame as\b|\bagrees?\b|\breturns?\b|\bwrites?\b|"
    r"\brefus(e|es|al)\b|\bblocks?\b|\bprevents?\b|\bconserv|\bbalance|\bexactly\b", re.I)
# What a purely structural probe can actually establish.
STRUCTURAL_ONLY_RE = re.compile(
    r"renders?|no overflow|unclipped|chars of visible text|no error chrome|no unrendered junk|"
    r"structural half", re.I)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def rows_of(reg):
    return reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg


def sha_of(paths):
    """Hash the files a claim depends on. Missing file => its own marker, so a DELETED dependency
    invalidates the claim rather than silently hashing to nothing."""
    h = hashlib.sha256()
    for p in sorted(paths or []):
        fp = os.path.join(ROOT, p)
        h.update(p.encode("utf-8"))
        if os.path.exists(fp):
            with open(fp, "rb") as f:
                h.update(f.read())
        else:
            h.update(b"<<MISSING>>")
    return h.hexdigest()[:16]


# ── R4b · A WHOLE-FILE HASH IS TOO BLUNT FOR A SHARED LIBRARY ────────────────────────────────────
# The file hash above is right for a page: edit marketplace.html and every claim about marketplace.html
# should be re-walked. It is WRONG for utils.js, which nearly every row depends on. Adding one new
# helper to it -- `whReadError`, appended, touching nothing -- expired 402 of 435 green rows in one
# commit (2026-08-04). None of those claims could possibly have been affected: "the seller edit form
# refuses a blank title" does not become doubtful because a function it never calls now exists.
#
# An instrument that cannot tell "the code this claim rests on changed" from "unrelated code was added
# beside it" is not measuring freshness, it is measuring file mtime with extra steps -- and the cost is
# paid in re-walks that re-confirm what nobody doubted, which is exactly how a discipline stops being
# followed.
#
# So a row may ALSO carry `fn_digests`: a map of {"utils.js::whWriteError": "<digest>", ...} plus the
# file's TOP-LEVEL code (everything outside any function body) under "::toplevel". A row stays fresh if
# every entry it recorded is still byte-identical. A NEW function is absent from the map, so it expires
# nothing; a CHANGED or DELETED one expires the row, which is the case that matters. Top-level code is
# included because that is where a wrapper, a monkey-patch or an assignment could change behaviour
# without touching any function body.
#
# This is a WIDENING of what counts as fresh, so it must not become a way to launder a real change:
# the map is written at BANK time from the code as it then was, never recomputed from the current file,
# and a row with no map falls back to the whole-file hash. The self-test proves both directions.
_FN_RE = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)


def fn_digests(paths):
    """{"<file>::<fn>": digest} for every top-level `function name(...)`, plus "<file>::toplevel"
    for everything outside those bodies. Brace-matched rather than regex-sliced, because a regex that
    stops at the first `}` reports a two-line function for a fifty-line one and would call a real
    change unchanged."""
    out = {}
    for p in sorted(paths or []):
        fp = os.path.join(ROOT, p)
        if not os.path.exists(fp) or not p.endswith(".js"):
            continue
        src = open(fp, "r", encoding="utf-8", errors="replace").read()
        spans = []
        for m in _FN_RE.finditer(src):
            i = src.find("{", m.end() - 1)
            if i < 0:
                continue
            depth, j, n = 0, i, len(src)
            while j < n:
                c = src[j]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                continue                      # unbalanced: skip rather than guess
            body = src[m.start():j + 1]
            out["%s::%s" % (p, m.group(1))] = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
            spans.append((m.start(), j + 1))
        top, last = [], 0
        for a, b in sorted(spans):
            top.append(src[last:a])
            last = b
        top.append(src[last:])
        # Normalised, because appending a function leaves an extra blank line in the top-level slice
        # and a raw hash would read that as a behaviour change -- expiring every row for a whitespace
        # gap, which is the exact over-sensitivity this whole mechanism exists to remove. Whitespace
        # BETWEEN top-level declarations cannot change what the file does; whitespace INSIDE a function
        # is inside that function's own digest, untouched by this.
        norm = "\n".join(ln.strip() for chunk in top for ln in chunk.splitlines() if ln.strip())
        out["%s::toplevel" % p] = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return out


def fn_digests_still_hold(recorded):
    """True when every function/top-level digest a row RECORDED is still byte-identical. Names absent
    from `recorded` are new code and are deliberately ignored."""
    if not recorded:
        return False
    files = sorted({k.split("::", 1)[0] for k in recorded})
    current = fn_digests(files)
    for k, v in recorded.items():
        if current.get(k) != v:
            return False
    return True


def gate_ids():
    src = ""
    try:
        with open(CHECKS, encoding="utf-8") as f:
            src = f.read()
    except Exception:
        return set()
    # The character class used to be [a-z0-9_], which cannot match a HYPHEN -- and the gate registry
    # names gates like "edge-status-body", "admin-gates", "abort-timeout". Measured 2026-08-04: the
    # old pattern saw 186 of the 732 registered ids, so 546 gates (75% of the registry) were invisible
    # and rule R2 rejected any evidence citing them. The bank could only ever cite the underscore
    # quarter of its own gate suite, which silently pushed walks toward weaker live-walk evidence when
    # a whole-layer gate was the stronger proof available.
    return set(re.findall(r'"id"\s*:\s*"([a-z0-9_-]+)"', src))


def surface_urls(reg):
    urls = {r.get("url") for r in rows_of(reg) if r.get("url")}
    return {u for u in urls if u}


def classify(row, gates, urls):
    """-> (state, reason). state in {green, stale, owed, invalid}."""
    status = row.get("status")
    if status == "owed":
        return "owed", ""
    if status == "lane-reassigned":
        return "owed", ""
    ev = row.get("evidence")
    if not isinstance(ev, dict):
        return "invalid", "R1 no evidence block on a non-owed row"
    kind, ref, asserts = ev.get("kind"), (ev.get("ref") or ""), (ev.get("asserts") or "").strip()
    if kind not in VALID_KINDS:
        return "invalid", f"R1 evidence.kind {kind!r} is not one of {sorted(VALID_KINDS)}"
    if not asserts:
        return "invalid", "R1 evidence.asserts is empty — 'green because of what?' has no answer"
    if kind == "gate":
        gid = ref.split("gate:")[-1].strip()
        if gid not in gates:
            return "invalid", f"R2 evidence names gate {gid!r}, which is not registered"
    if kind == "live-walk":
        if not re.search(r"\d{4}-\d{2}-\d{2}", ref):
            return "invalid", "R3 a live-walk ref must carry the session date"
        if not any(u in ref for u in urls):
            return "invalid", "R3 a live-walk ref must name a surface URL from the bank"
    if BEHAVIOURAL_RE.search(asserts) and STRUCTURAL_ONLY_RE.search(str(ev.get("checked") or "")) \
            and not ev.get("value_checked"):
        return "invalid", ("R6 a behavioural claim resting on structural evidence — this is the exact "
                           "shape that produced the false 343")
    dep = ev.get("depends_on") or []
    if dep:
        if sha_of(dep) != ev.get("sha"):
            # R4b: before calling it stale, ask the finer question. If the row recorded which FUNCTIONS
            # it rested on and every one of them is byte-identical, the file changed around the claim
            # rather than under it. Only rows that took the trouble to record that get the benefit.
            if not fn_digests_still_hold(ev.get("fn_digests")):
                return "stale", "R4 a file this claim depends on has changed since the walk"
    return "green", ""


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Live-MCP bank — typed evidence, and evidence that expires{RST}")
    if selftest() != 0:
        return 1

    reg = load(REGISTRY)
    if reg is None:
        print(f"  {RED}FAIL{RST} — live_mcp_registry.json is unreadable")
        return 1
    rows = rows_of(reg)
    gates, urls = gate_ids(), surface_urls(reg)

    buckets = {"green": [], "stale": [], "owed": [], "invalid": []}
    for r in rows:
        st, why = classify(r, gates, urls)
        buckets[st].append((r.get("id"), why))

    live = len(buckets["green"]) + len(buckets["stale"]) + len(buckets["owed"])
    denom = len(buckets["green"]) + len(buckets["owed"])          # stale excluded, deliberately
    pct = (100.0 * len(buckets["green"]) / denom) if denom else 0.0
    print(f"  {DIM}scenarios: {len(rows)} · green {len(buckets['green'])} · stale {len(buckets['stale'])} "
          f"· owed {len(buckets['owed'])} · invalid {len(buckets['invalid'])}{RST}")
    print(f"  {DIM}green% over non-stale: {pct:.1f}%  (stale is excluded so drift shows up rather than "
          f"being absorbed){RST}")

    if "--report" in argv:
        import collections
        cats = collections.Counter(r.get("category") for r in rows)
        print(f"\n  {BOLD}distribution{RST}")
        for c, n in sorted(cats.items()):
            print(f"    {n:4d}  {c}")

    if buckets["invalid"]:
        print(f"\n  {RED}FAIL{RST} — {len(buckets['invalid'])} row(s) claim a status they cannot support:")
        for rid, why in buckets["invalid"][:15]:
            print(f"    · {rid}\n        {DIM}{why}{RST}")
        if len(buckets["invalid"]) > 15:
            print(f"    {DIM}… and {len(buckets['invalid']) - 15} more{RST}")
        print(f"\n  {DIM}A row is green because of something. Say what, in evidence.asserts, and cite it "
              f"in evidence.ref.{RST}")
        return 1

    if buckets["stale"]:
        print(f"\n  {YEL}STALE{RST} — {len(buckets['stale'])} row(s) were true and the ground moved:")
        for rid, _ in buckets["stale"][:10]:
            print(f"    · {rid}")
        if len(buckets["stale"]) > 10:
            print(f"    {DIM}… and {len(buckets['stale']) - 10} more{RST}")
        print(f"  {DIM}Re-walk them on the live MCP browser. Stale is not a failure; a stale row treated "
              f"as green is.{RST}")

    base = load(BASELINE, {}) or {}
    prev = int(base.get("green", 0))
    if "--accept" in argv:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"green": len(buckets["green"]), "note":
                       "forward-only ratchet on GREEN. stale is excluded from the denominator."}, f, indent=1)
        print(f"\n  {GREEN}ACCEPTED{RST} — baseline set to {len(buckets['green'])} green")
        return 0
    # WITHDRAWING A FALSE GREEN IS NOT A REGRESSION. The ratchet exists so a walk cannot be quietly
    # un-done, and it was right to fire the first time it saw this drop. But it could not tell a lost
    # walk from an honest retraction, and on 2026-08-04 it blocked exactly the correction the bank
    # exists to make possible: a contrast_wcag row banked green on "axe: 0 violations" when axe had
    # actually ABSTAINED on 185 nodes it could not measure. Correcting a false claim must never be
    # harder than making one, or the ratchet quietly rewards leaving it green.
    #
    # The exception is narrow and auditable: a decrease is allowed ONLY when every missing green is
    # accounted for by a row that is now owed AND carries a `false-green-withdrawn` finding saying
    # why. Anything else -- an expired sha, a deleted row, a silently flipped status -- still FAILs.
    #
    # A RATCHET THAT TURNS BOTH WAYS IS NOT A RATCHET (found 2026-08-04). This compared a CUMULATIVE
    # pool of withdrawn rows against an INCREMENTAL drop, so every past withdrawal stayed in the pool
    # and kept authorising future drops. It fired for real: an edit to marketplace.html expired rows
    # into `stale`, the drop was covered by withdrawals audited in EARLIER runs, and the baseline
    # lowered itself 317 -> 312 while printing "not by absorbing drift" -- which is precisely what it
    # had done. Nothing had been withdrawn that run.
    # A withdrawal may only pay for a drop ONCE. The ids that bought a decrease are recorded in the
    # baseline and are not counted again.
    spent = set(base.get("withdrawn_ids") or [])
    withdrawn = [s for s in rows
                 if s.get("status") == "owed"
                 and s.get("id") not in spent
                 # findings are dicts in the newer rows and bare strings in the older ones
                 and any(isinstance(f, dict) and f.get("severity") == "false-green-withdrawn"
                         for f in (s.get("findings") or []))]
    drop = prev - len(buckets["green"])
    if drop > 0 and len(withdrawn) >= drop:
        print(f"\n  {YEL}WITHDRAWN{RST} — green {prev} -> {len(buckets['green'])} ({drop}), and "
              f"{len(withdrawn)} row(s) carry a false-green-withdrawn finding. A retraction is not a "
              f"regression; the baseline follows it DOWN so the correction sticks:")
        for s in withdrawn[:5]:
            title = next((f.get("title") for f in (s.get("findings") or [])
                          if isinstance(f, dict) and f.get("severity") == "false-green-withdrawn"), "")
            print(f"    · {s['id']}\n        {title}")
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"green": len(buckets["green"]),
                       "note": "lowered by an audited false-green withdrawal, not by absorbing drift",
                       # the ids that bought this decrease; they cannot buy another one
                       "withdrawn_ids": sorted(spent | {s["id"] for s in withdrawn})},
                      f, indent=1)
        return 0
    if len(buckets["green"]) < prev:
        print(f"\n  {RED}FAIL{RST} — green went backwards: {prev} -> {len(buckets['green'])}. Either a walk "
              f"was undone or evidence expired; re-walk, do not re-baseline.")
        return 1

    print(f"\n  {GREEN}PASS{RST} — every non-owed row carries typed, unexpired evidence "
          f"(baseline {prev} green)")
    return 0


def selftest():
    print("  selftest: each rule must FIRE on a rigged row")
    ok = True
    gates, urls = {"validate_public_read_surface"}, {"/workhive/marketplace.html"}
    # THIS file, because it is certainly present and certainly inside ROOT. The first version used
    # CLAUDE.md, which lives one directory UP — so the fixture hashed an empty list while classify()
    # hashed the missing-file marker, and the self-test failed its own well-formed case. A fixture that
    # does not exist is the oldest way to fail a test that is actually passing.
    DEP = "tools/validate_live_mcp_bank.py"
    good_sha = sha_of([DEP])

    cases = [
        # (row, expected_state, label)
        ({"status": "green"}, "invalid", "R1 green with no evidence block"),
        ({"status": "green", "evidence": {"kind": "vibes", "ref": "x", "asserts": "a"}},
         "invalid", "R1 unknown kind"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:x", "asserts": ""}},
         "invalid", "R1 empty asserts"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:no_such_gate", "asserts": "a"}},
         "invalid", "R2 gate that is not registered"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "/workhive/marketplace.html",
                                          "asserts": "a"}},
         "invalid", "R3 live-walk with no date"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "2026-08-04 /workhive/nope.html",
                                          "asserts": "a"}},
         "invalid", "R3 live-walk naming a surface not in the bank"),
        ({"status": "green", "evidence": {"kind": "live-walk", "ref": "2026-08-04 /workhive/marketplace.html",
                                          "asserts": "the chip matches service_knob_pct",
                                          "checked": "renders content; no overflow"}},
         "invalid", "R6 behavioural claim on structural evidence"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface",
                                          "asserts": "a", "depends_on": [DEP], "sha": "deadbeef"}},
         "stale", "R4 dependency changed since the walk"),
        ({"status": "green", "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface",
                                          "asserts": "a", "depends_on": [DEP], "sha": good_sha}},
         "green", "a well-formed, unexpired row"),
        ({"status": "owed"}, "owed", "an owed row needs no evidence"),
    ]
    for row, want, label in cases:
        got, _ = classify(row, gates, urls)
        if got != want:
            print(f"  {RED}FAIL{RST} — {label}: expected {want}, got {got}")
            ok = False

    # ── R4b, both directions, against a REAL temporary .js rather than a mocked digest ────────────
    # The widening must survive the question "does it still catch a change?", so it is tested by
    # actually editing a file: appending a function must NOT expire the row, and editing a recorded
    # one MUST. A one-directional test here would let R4b quietly become "never stale".
    tmp = os.path.join(ROOT, "_r4b_selftest.js")
    try:
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'a'; }\n}\nvar top = 1;\n")
        rec = fn_digests(["_r4b_selftest.js"])
        row = {"status": "green",
               "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                            "depends_on": ["_r4b_selftest.js"], "sha": "stale-on-purpose",
                            "fn_digests": rec}}
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b: an unchanged function should read green even with a stale file sha")
            ok = False
        # append a NEW function: nothing the row recorded moved, so the row must survive
        open(tmp, "a", encoding="utf-8").write("function beta() {\n  return 'b';\n}\n")
        if classify(row, gates, urls)[0] != "green":
            print(f"  {RED}FAIL{RST} — R4b: appending an unrelated function must not expire a row")
            ok = False
        # now EDIT the recorded function: this must expire it
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'CHANGED'; }\n}\nvar top = 1;\n")
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: editing a recorded function MUST expire the row")
            ok = False
        # and a change to TOP-LEVEL code must expire it too -- that is where a wrapper would hide
        open(tmp, "w", encoding="utf-8").write(
            "function alpha() {\n  if (1) { return 'a'; }\n}\nvar top = 2;\n")
        if classify(row, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: a top-level change MUST expire the row")
            ok = False
        # a row that recorded nothing gets no benefit: it falls back to the whole-file hash
        bare = {"status": "green",
                "evidence": {"kind": "gate", "ref": "gate:validate_public_read_surface", "asserts": "a",
                             "depends_on": ["_r4b_selftest.js"], "sha": "stale-on-purpose"}}
        if classify(bare, gates, urls)[0] != "stale":
            print(f"  {RED}FAIL{RST} — R4b: a row with no fn_digests must still fall back to the file hash")
            ok = False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    if ok:
        print(f"  {GREEN}PASS{RST} — R1/R2/R3/R4/R4b/R6 all fire; a well-formed row passes; owed is exempt")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
