#!/usr/bin/env python3
"""build_test_bank.py - materialise the marketplace test bank from the DERIVED matrix.

The bank is not hand-typed. `transition_matrix.json` (derived from the guard functions) says what the
bank OWES; `gate_coverage_map.json` says what a registered gate ALREADY locks; this tool merges them
into `marketplace_test_bank.json`, where every cell carries one of three honest states:

  covered   a registered gate already asserts this exact obligation -> do NOT rebuild it (the cell
            still counts toward the board, with the owning gate named, so coverage is not understated)
  owed      nothing asserts it yet -> the bank must author it
  banked    the bank itself asserts it (a runner executes it)

Re-running is safe and idempotent: `banked` cells and any hand-added fields survive; only the derived
skeleton is refreshed. That is what keeps the bank honest when a migration changes a guard - the
denominator moves by itself and new obligations appear as `owed` instead of quietly not existing
([[feedback_short_denominator_is_a_false_100]]).

Usage:  python tools/build_test_bank.py [--selftest]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX = os.path.join(ROOT, "transition_matrix.json")
COVERAGE = os.path.join(ROOT, "gate_coverage_map.json")
BANK = os.path.join(ROOT, "marketplace_test_bank.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The DEFAULT axes, used only when there is no prior bank to carry forward. `viewport` and `lang` were
# RETIRED from this list after the board proved they were decoration — declared on the axes but used by 0 of
# 247 cells, with the real measurement owned by tools/validate_service_ufai_deep.py (390/1280 tap targets and
# overflow) and validate_i18n. `metamorphic` was added when the MR lane landed. Both edits are here as well
# as in the bank because a rebuild from scratch must not resurrect a retired axis.
AXES = {
    "authority": ["anon", "member", "owner", "counterparty", "admin", "cross-tenant"],
    "state": ["empty", "populated", "filtered0", "error", "edge"],
    "path": ["happy", "error", "degraded"],
    "layer": ["S1-ui", "S2-pwa", "S3-data", "S4-db", "S5-edge",
              "S6-realtime", "S7-ai", "S8-gates", "S9-knowledge"],
    "oracle": ["db-truth", "continuity", "rubric", "refusal", "eval", "metamorphic"],
    "lane": ["sql", "journey"],
}

# Top-level keys this builder OWNS and regenerates. Everything else in the prior bank is curated by hand and
# is carried forward untouched — see the reconstruction at the end of build().
OWNED_KEYS = {"_doc", "_states", "axes", "derived_from", "tests"}


def load(path, what):
    if not os.path.exists(path):
        print(f"  {RED}missing{RST} {what}: {os.path.basename(path)} — run its producer first")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def covered_index(cov):
    """cell-id (or a wildcard pattern) -> (gate-id, evidence). Wildcards let a gate claim a family."""
    idx = {}
    for gate_id, g in (cov.get("gates") or {}).items():
        for c in g.get("covers", []):
            idx[c["cell"]] = (gate_id, c.get("evidence", ""), c.get("kind", ""))
    return idx


def match_cover(cell_id, kind, idx):
    """Resolve a cell to the gate that already locks it.

    Three claim shapes, in order of precision. A broad claim is allowed because one gate check often
    does cover a whole family (hive-isolation's 26 invariants really do cover cross-tenant everywhere)
    — but the map states it as broad IN WRITING, so the breadth is auditable instead of hidden.

      exact    "TB-service_requests-requested__broadcasting-owner"
      prefix   "TB-...-admin-or-system--neg-"   -> every authority-negative on that transition
      suffix   "--neg-cross-tenant"             -> that partition across every transition
    """
    if cell_id in idx:
        return idx[cell_id]
    for pat, val in idx.items():
        if pat.startswith("--") and cell_id.endswith(pat):          # suffix / partition-wide
            return val
        if pat.endswith("*") and cell_id.startswith(pat[:-1]):      # explicit wildcard
            return val
        if pat.endswith("-") and cell_id.startswith(pat):           # prefix / family
            return val
    return None


def build():
    matrix = load(MATRIX, "derived matrix")
    cov = load(COVERAGE, "gate coverage map")
    if matrix is None or cov is None:
        return None
    idx = covered_index(cov)

    prior, prior_bank = {}, {}
    if os.path.exists(BANK):
        with open(BANK, encoding="utf-8") as f:
            prior_bank = json.load(f)
        for t in (prior_bank.get("tests") or []):
            prior[t["id"]] = t

    tests = []
    for mc in matrix.get("machines", []):
        for c in mc.get("cells", []):
            # ── the POSITIVE obligation: the authorised actor CAN do it ──────────────────
            pid = c["id"]
            hit = match_cover(pid, "positive", idx)
            cell = prior.get(pid) or {}
            cell.update({
                "id": pid,
                "kind": "positive",
                "transition": {"table": c["table"], "from": c["from"], "to": c["to"]},
                "authority": c["authority"],
                "expect": "allowed",
                # A transition legality check is a DB fact: proven in rolled-back SQL, never through a
                # browser. That is the cheapest honest altitude, and the one that cannot flake.
                "lane": cell.get("lane", "sql"),
                "oracle": cell.get("oracle", "db-truth"),
                "layers": cell.get("layers", ["S4-db"]),
                "evidence_src": c.get("evidence", ""),
            })
            cell["status"] = ("covered" if hit else cell.get("status", "owed"))
            if hit:
                cell["covered_by"], cell["covered_evidence"] = hit[0], hit[1]
            tests.append(cell)

            # ── AUTHORITY negatives: every other actor must be refused ───────────────────
            for neg in c.get("negatives", []):
                nid = f"{pid}--neg-{neg['authority']}"
                nhit = match_cover(nid, "authority-negative", idx)
                ncell = prior.get(nid) or {}
                ncell.update({
                    "id": nid, "kind": "authority-negative",
                    "transition": {"table": c["table"], "from": c["from"], "to": c["to"]},
                    "authority": neg["authority"], "expect": "refused",
                    "lane": ncell.get("lane", "sql"),
                    "oracle": ncell.get("oracle", "refusal"),
                    "layers": ncell.get("layers", ["S4-db"]),
                })
                ncell["status"] = ("covered" if nhit else ncell.get("status", "owed"))
                if nhit:
                    ncell["covered_by"], ncell["covered_evidence"] = nhit[0], nhit[1]
                tests.append(ncell)

            # ── SNEAK PATHS: the temporal negatives, each already a real incident here ───
            for sp in c.get("sneak_paths", []):
                sid = f"{pid}--sneak-{sp}"
                shit = match_cover(sid, f"sneak-path:{sp}", idx)
                scell = prior.get(sid) or {}
                scell.update({
                    "id": sid, "kind": f"sneak-path:{sp}",
                    "transition": {"table": c["table"], "from": c["from"], "to": c["to"]},
                    "authority": c["authority"], "expect": "refused-or-idempotent",
                    "lane": scell.get("lane", "sql"),
                    "oracle": scell.get("oracle", "refusal"),
                    "layers": scell.get("layers", ["S4-db"]),
                })
                scell["status"] = ("covered" if shit else scell.get("status", "owed"))
                if shit:
                    scell["covered_by"], scell["covered_evidence"] = shit[0], shit[1]
                tests.append(scell)

        # ── BIRTH obligations: what state may a row be BORN in? ─────────────────────────────
        # These are INSERTs, not UPDATEs, and they are the reason this section exists at all: every
        # derived cell above is an `UPDATE ... SET status`, so each guard's TG_OP='INSERT' branch had
        # ZERO cells across 247 obligations. The guard mutation score found it mechanically — deleting
        # the birth rules one at a time and watching no cell object. Deriving them means a status added
        # to a CHECK constraint tomorrow arrives as an obligation instead of silently not existing.
        for b in mc.get("births", []):
            bid = b["id"]
            bhit = match_cover(bid, "birth", idx)
            bcell = prior.get(bid) or {}
            bcell.update({
                "id": bid,
                "kind": "birth",
                # `from: "(insert)"` is what the runner dispatches on. It is deliberately NOT a status:
                # a birth has no origin state, and giving it a fake one would let a transition-shaped
                # cell claim to cover it — the exact conflation that hid these obligations.
                "transition": {"table": b["table"], "from": "(insert)", "to": b["to"]},
                "authority": b["authority"],
                "expect": b["expect"],
                "lane": bcell.get("lane", "sql"),
                "oracle": bcell.get("oracle", "db-truth" if b["expect"] == "allowed" else "refusal"),
                "layers": bcell.get("layers", ["S4-db"]),
                "evidence_src": b.get("evidence", ""),
            })
            bcell["status"] = ("covered" if bhit else bcell.get("status", "owed"))
            if bhit:
                bcell["covered_by"], bcell["covered_evidence"] = bhit[0], bhit[1]
            tests.append(bcell)

    # AUTHORED cells survive a rebuild. Not every obligation is derivable from a guard: a journey
    # cell like "the buyer contacts the seller and the inquiry lands with attribution intact" spans
    # pages and asserts PII staging, which no state machine describes. Dropping them on refresh would
    # silently delete the very work the journey lane exists to produce.
    derived_ids = {t["id"] for t in tests}
    # PRESERVE EVERY NON-DERIVED CELL, not only the ones that happen to carry source:"authored".
    # The rule above states the intent correctly and the predicate did not honour it: 139 of the 154
    # journey cells have NO `source` field at all, so each rebuild silently deleted them — 492
    # obligations collapsed to 308, the journey lane from 154 to 15, and `owed` fell to 0 because the
    # owed cells were the ones destroyed. A coverage number that improves by losing the obligations is
    # the most dangerous shape a green can take. If this builder did not derive a cell, it does not own
    # it, and it must not drop it.
    authored = [t for tid, t in prior.items() if tid not in derived_ids]
    for t in authored:
        t.setdefault("source", "authored")   # backfill so the intent is explicit from here on

    # AN AUTHORED CELL IS BANKED THE MOMENT A REAL SPEC EXECUTES IT — learned from the runner, never
    # from a human remembering to edit this file. 67 journey cells sat `owed` with the reason "needs a
    # live browser (Playwright MCP)" long after every one of them had a Playwright spec: the reason had
    # simply stopped being true and nothing re-read it. A bank that cannot learn from its own runner
    # reports debt it no longer has, which is the same dishonesty as reporting coverage it never earned
    # — just in the flattering direction instead of the alarming one.
    try:
        from run_marketplace_sim import BROWSER_COVERED, DB_CHECKS   # the runner is the source of truth
        executes = set(BROWSER_COVERED) | set(DB_CHECKS)
    except Exception:
        executes = set()
    promoted = 0
    for cell in authored:
        if cell.get("status") == "owed" and cell["id"] in executes:
            cell["status"] = "banked"
            cell["runner"] = "tools/run_marketplace_sim.py (tests/marketplace-sim-*.spec.ts)"
            cell.pop("reason", None)
            cell.pop("owed_reason", None)
            promoted += 1
    if promoted:
        print(f"  promoted {promoted} authored cell(s) owed -> banked (a real spec now executes them)")

    tests.extend(authored)

    bank = {
        "_doc": "Marketplace test bank. GENERATED from transition_matrix.json + gate_coverage_map.json "
                "by tools/build_test_bank.py, then enriched by hand. Re-running preserves banked cells, "
                "hand-added fields, and every cell marked source:authored (journey cells, which no "
                "guard describes); it only refreshes the derived skeleton.",
        "_states": {"covered": "a registered gate already locks it - do not rebuild",
                    "owed": "nothing asserts it yet - the bank must author it",
                    "banked": "the bank asserts it; a runner executes it"},
        # The CURATED axes win over the default. This block is edited by hand when an axis is retired with
        # its owning instrument named, and regenerating from the constant would have silently RESURRECTED
        # `viewport` and `lang` and dropped the `metamorphic` oracle.
        "axes": prior_bank.get("axes") or AXES,
        "derived_from": matrix.get("machines") and [m["guard"] for m in matrix["machines"]],
        "tests": tests,
    }

    # CARRY FORWARD every hand-curated top-level block this builder does not own. Reconstructing the bank
    # from a fixed key set silently DELETED five of them — `_ufai_note`, `_ufai_ownership`, `_retired_axes`,
    # `_covers_tables_doc`, `_layer_owners` — which are read by the scoreboard to name axis owners and
    # disclose retirements. A rebuild is supposed to refresh the derived skeleton, not quietly revert the
    # curation layered on top of it; the whole file already says so in its own `_doc`, and the code did not
    # honour it. Caught by diffing the prior bank's keys against the rebuilt ones BEFORE overwriting.
    for k, v in prior_bank.items():
        if k not in OWNED_KEYS:
            bank[k] = v
    return bank


def summarise(bank):
    tests = bank["tests"]
    by_status, by_lane, by_kind = {}, {}, {}
    for t in tests:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_lane[t["lane"]] = by_lane.get(t["lane"], 0) + 1
        k = t["kind"].split(":")[0]
        by_kind[k] = by_kind.get(k, 0) + 1
    print("=" * 78)
    print(f"  {BOLD}Marketplace test bank — materialised{RST}")
    print("=" * 78)
    print(f"  obligations : {BOLD}{len(tests)}{RST}")
    print(f"  by kind     : " + " · ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
    print(f"  by lane     : " + " · ".join(f"{k} {v}" for k, v in sorted(by_lane.items())))
    cov = by_status.get("covered", 0)
    owed = by_status.get("owed", 0)
    banked = by_status.get("banked", 0)
    pct = round(100.0 * (cov + banked) / len(tests), 1) if tests else 0.0
    print(f"  {GREEN}covered{RST} {cov}  ·  {GREEN}banked{RST} {banked}  ·  {YEL}owed{RST} {owed}")
    print(f"  {BOLD}coverage    : {pct}%{RST}  {DIM}(covered+banked ÷ obligations){RST}")
    gates = sorted({t["covered_by"] for t in tests if t.get("covered_by")})
    if gates:
        print(f"  {DIM}already locked by: {', '.join(gates)}{RST}")
    print(f"\n  {DIM}The owed cells are the honest work list; the covered ones are NOT rebuilt.{RST}")
    return pct


def selftest():
    ok = True
    idx = {"TB-x-a__b-owner": ("g1", "ev", "positive"),
           "TB-x-c__d-*": ("g2", "ev2", "sneak-path:replay")}
    if match_cover("TB-x-a__b-owner", "positive", idx) is None:
        print(f"  {RED}FAIL{RST} exact cell match broken"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} exact cell id matches its gate")
    if match_cover("TB-x-c__d-anything", "sneak-path:replay", idx) is None:
        print(f"  {RED}FAIL{RST} wildcard family match broken"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} a gate can claim a `*` family (one check, many cells)")
    if match_cover("TB-y-zzz", "positive", idx) is not None:
        print(f"  {RED}FAIL{RST} an UNRELATED cell was claimed as covered — over-claim risk"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} an unrelated cell is NOT claimed (no silent coverage inflation)")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


DOC = os.path.join(ROOT, "MARKETPLACE_TEST_BANK.md")


def write_doc(bank):
    """A human-readable index of the bank. The JSON is the machine's copy; this is the one a person
    reads to answer 'what does this platform actually assert about the marketplace, and what does it
    still only hope?' — so the OWED cells get as much room as the banked ones."""
    tests = bank["tests"]
    authored = [t for t in tests if t.get("source") == "authored"]
    owed = [t for t in authored if t.get("status") == "owed"]
    L = ["# Marketplace Test Bank", "",
         "_Generated by `tools/build_test_bank.py --doc`. The derived skeleton comes from the four "
         "guard functions; the authored cells are the scenarios no generator describes._", "",
         f"**{len(tests)} obligations** · "
         f"{len([t for t in tests if t['status'] == 'covered'])} already locked by an existing gate · "
         f"{len([t for t in tests if t['status'] == 'banked'])} asserted by the bank · "
         f"{len([t for t in tests if t['status'] == 'owed'])} owed", "",
         "## Authored cells — the scenarios", "",
         "| Cell | Lane | Layers | Runner / gate | Status |", "|---|---|---|---|---|"]
    for t in sorted(authored, key=lambda x: x["id"]):
        who = t.get("gate") or t.get("runner") or t.get("probe", {}).get("file", "") or "—"
        L.append(f"| `{t['id']}` | {t.get('lane','')} | {' · '.join(t.get('layers') or [])} | "
                 f"{who} | {t['status']} |")
    L += ["", "### What each one proves", ""]
    for t in sorted(authored, key=lambda x: x["id"]):
        L.append(f"**`{t['id']}`**" + (f" — {' × '.join(t['role_pair'])}" if t.get("role_pair") else ""))
        for a in (t.get("asserts") or []):
            L.append(f"- {a}")
        if t.get("provenance"):
            L.append(f"\n_Why:_ {t['provenance']}")
        if t.get("note"):
            L.append(f"\n_Note:_ {t['note']}")
        L.append("")
    if owed:
        L += ["## Still owed — stated, not hidden", ""]
        for t in sorted(owed, key=lambda x: x["id"]):
            L.append(f"- **`{t['id']}`** — {t.get('why_owed') or t.get('blocked_reason') or 'not yet built'}")
            if t.get("requires"):
                L.append(f"  - _needs:_ {t['requires']}")
        L.append("")
    with open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {os.path.basename(DOC)} ({len(authored)} authored, {len(owed)} owed)")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--doc" in sys.argv:
        with open(BANK, encoding="utf-8") as f:
            write_doc(json.load(f))
        return 0
    bank = build()
    if bank is None:
        return 1
    # ATOMIC. `open(..., "w")` truncates before it writes, so an interrupted run leaves a 275-cell bank as an
    # empty file - and this platform has already lost a 55KB document to exactly that
    # ([[feedback_open_w_truncates_before_write_use_atomic]]). Write beside it, then replace.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(BANK) or ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)
    os.replace(tmp, BANK)
    summarise(bank)
    print(f"  wrote {os.path.basename(BANK)}")
    # The human-facing doc used to regenerate ONLY behind `--doc`, so every ordinary rebuild left it drifting
    # from the JSON it describes: it still showed 253 cells and no BIRTH lane after the bank had 275. A
    # generated artifact that regenerates on a flag nobody passes is a stale artifact by default - the same
    # doc-drift the substrate freshness gate exists to catch, one level up.
    write_doc(bank)
    return 0


if __name__ == "__main__":
    sys.exit(main())
