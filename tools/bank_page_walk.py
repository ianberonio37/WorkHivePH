#!/usr/bin/env python3
"""bank_page_walk.py -- merge a live-MCP walk's results into a PAGE bank, refusing what the walk
did not prove.

The page-bank sibling of merge_walk_results.py, and it inherits that file's whole point: the merger
runs the GATE'S OWN classify() on every row it is about to write, so it structurally cannot bank
something validate_live_mcp_bank.py would reject. A structural probe satisfying a behavioural
oracle is what produced the false 343; the asymmetry here is the mechanism that keeps it dead.

INPUT SHAPE (.tmp/page_walk_results.json, written during the live MCP session):
  [{"id": "PB-index-111-CJ-ui-layout-V1-w390_overflow",
    "ok": true,
    "checked": "verifiedWidth 390 via innerWidth; doc.scrollWidth==clientWidth; ...",
    "value_checked": "innerWidth=390 dpr=..., scrollWidth 390",   # optional; REQUIRED to bank a
    "asserts": "at a VERIFIED innerWidth of ~390 nothing overflows",  # behavioural claim
    "notes": ["..."]}]                                            # failure notes when ok=false

RULES (same as the marketplace merger, restated because this file must stand alone):
  ok=true  + gate classifies the written row green -> banked, with the session date + page URL ref
  ok=true  + gate would call it invalid            -> REFUSED, left owed, reason printed
  ok=false                                          -> stays owed; the FULL diagnosis is preserved
                                                       (title + untruncated `detail` + `observed`)
                                                       so the re-walk proves the fix instead of
                                                       re-discovering the defect. A walk writes its
                                                       narrative into `checked`, exactly as the OK
                                                       path does — `notes` is optional.
Evidence depends_on = the page + utils.js (what a page claim actually rests on), sha'd at bank
time; fn_digests stamped immediately so an unrelated later edit does not expire the row (R4b).

Usage:  python tools/bank_page_walk.py <page> [--results .tmp/page_walk_results.json] [--apply]
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--results", default=os.path.join(ROOT, ".tmp", "page_walk_results.json"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    bank_path = os.path.join(ROOT, "banks", f"{a.page}_live_mcp_bank.json")
    bank = json.load(open(bank_path, encoding="utf-8"))
    by_id = {r["id"]: r for r in bank["scenarios"]}
    gates, urls = V.gate_ids(), V.surface_urls(bank)
    today = date.today().isoformat()
    page_file = bank["url"].split("/")[-1].split("?")[0]

    # ── A CLAIM MUST BE ANCHORED TO WHAT IT ACTUALLY RESTS ON ────────────────────────────────────
    # This used to anchor EVERY row to {page, utils.js}, and the first index.html edit of the walk
    # proved why that is wrong: a one-line CSS fix in the head expired 20 of 21 banked rows, including
    # `anon_zero_rows`, `profile_identity_pinned` and two `jwt_not_body` rows — claims proven entirely
    # in psql against RLS policies, which cannot be affected by a stylesheet. It is the same defect
    # R7 already catches for the marketplace's layer/seam rows (a DB invariant anchored to whichever
    # page happened to be open), reappearing in the page banks because the merger, not the walker,
    # chose the anchor.
    #
    # Both directions cost something. Over-anchoring is noisy: it burns re-walks re-confirming claims
    # nobody doubted, which is how a discipline stops being followed. UNDER-anchoring is worse: a
    # migration could change a grant and never expire the claim that tested it — a false green with no
    # signal. So the anchor follows the EVIDENCE: a DB claim rests on the schema, a browser claim on
    # the page and the shared library, and a walk may always declare `deps` explicitly to override.
    DB_DEPS = ["supabase/migrations"]
    PAGE_DEPS = sorted({page_file, "utils.js"})

    def deps_for(res):
        if res.get("deps"):
            return sorted(res["deps"])
        blob = " ".join(str(res.get(k) or "") for k in ("checked", "asserts", "value_checked"))
        db_side = re.search(r"\bpsql\b|docker exec|set local role|RLS|rolled-back transaction|"
                           r"pg_policy|migration", blob, re.I)
        browser_side = re.search(r"live MCP browser|innerWidth|screenshot|axe|APCA|CLS|"
                                 r"live-state-runner|ufai_battery|getComputedStyle|CSSOM", blob, re.I)
        if db_side and not browser_side:
            return DB_DEPS
        if db_side and browser_side:            # a claim proven on both sides expires with either
            return sorted(set(DB_DEPS) | set(PAGE_DEPS))
        return PAGE_DEPS

    banked = refused = failed = missing = withdrawn = 0
    for res in json.load(open(a.results, encoding="utf-8")):
        row = by_id.get(res.get("id"))
        if row is None:
            missing += 1
            print(f"  {YEL}?{RST} no such row: {res.get('id')}")
            continue
        # ── WITHDRAWING A FALSE GREEN IS A FIRST-CLASS OPERATION ──────────────────────────────
        # `ok: false` records a diagnosis but deliberately does NOT touch a row that is already
        # green — so a row banked green under a measurement later found WRONG stayed green, carrying
        # evidence that no longer holds. That happened here: three component_busy rows asserted
        # "this component is static" while the corrected recorder showed all three growing. A bank
        # whose only transitions are owed->green can record a mistake but never retract one, and an
        # unretractable false green is worse than an owed row, because owed is honest.
        # `withdraw: true` flips green -> owed and keeps the REASON on the row, so the next walk
        # knows what was withdrawn and why instead of re-deriving it. Withdrawal needs no evidence:
        # it removes a claim rather than making one.
        if res.get("withdraw"):
            reason = (res.get("checked") or "withdrawn: the measurement it rested on no longer holds")
            row["findings"] = row.get("findings") or []
            f = {"date": today, "severity": "false-green-withdrawn",
                 "title": re.split(r"(?<=[.!?])\s+", reason.strip())[0][:300], "detail": reason}
            if res.get("value_checked"):
                f["observed"] = res["value_checked"]
            if not any(g.get("severity") == "false-green-withdrawn"
                       and g.get("detail") == f["detail"] for g in row["findings"]):
                row["findings"].append(f)
            was = row.get("status")
            row["status"] = "owed"
            row.pop("evidence", None)
            withdrawn += 1
            print(f"  {YEL}~{RST} withdrawn ({was} -> owed): {res.get('id')}")
            continue
        if not res.get("ok"):
            # ── AN OWED ROW'S DIAGNOSIS IS THE ONLY THING THAT MAKES THE RE-WALK CHEAPER ─────────
            # This branch used to keep `"; ".join(notes)[:300]` and DROP `checked`/`value_checked`
            # entirely — so the docstring's promise ("notes land in findings so the re-walk proves
            # the fix instead of re-discovering the defect") was false in practice: 54 of 66
            # walk-failed findings across the 22 banks sat at exactly 300 chars, cut mid-sentence,
            # and 10 read only "probe reported not-ok" because the walk wrote its diagnosis into
            # `checked` (as every OK path does) rather than into `notes`. A refusal recorded without
            # its reason costs the next session the entire probe again, which is the same waste as a
            # green with no evidence — the asymmetry the merger exists to enforce cuts both ways.
            # So: keep a readable title, and preserve the FULL narrative beside it. Nothing measured
            # is thrown away, and an identical re-run does not stack duplicate findings.
            failed += 1
            notes = [str(n) for n in (res.get("notes") or []) if str(n).strip()]
            checked, observed = res.get("checked") or "", res.get("value_checked") or ""
            title = ("; ".join(notes) if notes
                     else re.split(r"(?<=[.!?])\s+", checked.strip())[0] if checked.strip()
                     else "probe reported not-ok")
            f = {"date": today, "severity": "walk-failed", "title": title[:300]}
            if len(title) > 300 or checked:
                f["detail"] = checked or title          # untruncated: the whole diagnosis
            if observed:
                f["observed"] = observed
            existing = row.setdefault("findings", [])
            if not any(g.get("severity") == "walk-failed"
                       and g.get("detail", g.get("title")) == f.get("detail", f["title"])
                       for g in existing):
                existing.append(f)
            continue
        deps = deps_for(res)
        # A walk may declare a cell INAPPLICABLE rather than passing (rail R10). The distinction is
        # load-bearing: "0 of 0 icon-only controls lack a name" is vacuously true, and banking it as
        # a live-walk PASS is how coverage improves by deleting obligations. `declared-na` is a valid
        # evidence kind, so a vacuous cell can be recorded honestly instead of counted as proof.
        # It still requires a reason — classify() rejects empty `asserts`, and the walk must say in
        # `checked` WHY no subject exists, so the emptiness is documented rather than assumed.
        kind = res.get("kind") or "live-walk"
        if kind not in V.VALID_KINDS:
            raise SystemExit(f"{res.get('id')}: evidence kind {kind!r} not in {sorted(V.VALID_KINDS)}")
        # A gate-backed row names its PROVER, not a session. R2 then refuses the row outright if that
        # gate is ever deleted or renamed, so the claim cannot outlive the thing that proves it - and
        # unlike a walk, it is re-earned by RUNNING the gate rather than by reconstructing a session.
        # This branch did not exist, which is why 0 of 4,400 rows were gate-backed: the bank supported
        # the kind and nothing could emit the ref.
        gate_id = (res.get("gate") or "").strip()
        if kind == "gate":
            if not gate_id:
                raise SystemExit(f"{res.get('id')}: kind 'gate' needs a 'gate' field naming the registered gate id")
            if gate_id not in V.gate_ids():
                raise SystemExit(f"{res.get('id')}: gate {gate_id!r} is not registered in run_platform_checks.py")
        ev = {
            "kind": kind,
            "ref": (f"gate:{gate_id}" if kind == "gate"
                    else f"{today} declared-na {bank['url']}" if kind == "declared-na"
                    else f"{today} live MCP {bank['url']}"),
            "asserts": res.get("asserts") or row["oracle"],
            "checked": res.get("checked") or "",
            "depends_on": deps,
            "sha": V.sha_of(deps),
        }
        if res.get("value_checked"):
            ev["value_checked"] = res["value_checked"]
        # ── A16.C1 · EVIDENCE IS A RECIPE, NOT A MEMORY ───────────────────────────────────────────
        # A stale row is only expensive when nobody knows how the measurement was taken. `replay` is the
        # exact command that re-derives this verdict from scratch, so re-earning the row is running its
        # own recipe instead of reconstructing a session. Rows without one are HAND-WALKED, and that is
        # tracked rather than hidden: 48 ordering_totality rows came back in one command on 2026-08-11
        # while the layout rows stayed stale, and the only difference between them was this field.
        if res.get("replay"):
            ev["replay"] = res["replay"]
        # ── A16.P3 · THE BIRTH CHECK ──────────────────────────────────────────────────────────────
        # Evidence measured BEFORE a file it depends on was last modified is already stale when written.
        # Banking it produces a green row that the very next gate run expires - which is exactly what
        # happened on 2026-08-11: report-sender's three rows were banked and then report-sender.html was
        # edited again minutes later for the em-dash gate, expiring all three. The walk results file is
        # the measurement's own timestamp (it was written when the measurement finished), so no caller
        # has to supply one.
        measured_at = os.path.getmtime(a.results)
        # ── A16.P4 · A REPORT OLDER THAN ITS PROVER IS NOT EVIDENCE ───────────────────────────────
        # `replay` names the command that re-derives this verdict. If that command's own SOURCE has been
        # edited since the report it reads was written, the report describes an instrument that no longer
        # exists. On 2026-08-11 the idempotency report on disk was 12 minutes older than the fix to
        # prove_read_idempotency.py, still carried two pre-fix NOT-IDEMPOTENT verdicts for
        # v_ai_reports_truth, and a background re-run had exited 0 without writing anything - so the
        # stale file looked exactly like a fresh result. Two false findings were one command from being
        # banked. P3 asks "did the code move after the measurement?"; P4 asks the same question about
        # the MEASURING TOOL, which is the half that reads as trustworthy precisely because it is a tool.
        # EXTENDED 2026-08-13 to cover `.mjs`. The pattern matched `tools/*.py` ONLY, so the entire
        # BROWSER prover tier was exempt from the rail written to protect it — and that tier is the one
        # that needed it most: the five .mjs provers took twenty-plus corrections between them on the day
        # they were written (a 1.5x scale factor, a recorder armed too late, an ancestor credit that
        # cannot hold a fixed box, a PASS printed over zero measurements). Any of those edits landing
        # after a report would have left a verdict on disk that the current instrument never produced,
        # and the rail would have said nothing. A rail that silently skips a whole tier is worse than no
        # rail, because the green it lets through carries the rail's name.
        prover = re.search(r"tools[/\\]([A-Za-z0-9_]+\.(?:py|mjs))", str(res.get("replay") or ""))
        if prover:
            ppath = os.path.join(ROOT, "tools", prover.group(1))
            if os.path.exists(ppath) and os.path.getmtime(ppath) > measured_at + 1:
                refused += 1
                print(f"  {YEL}REFUSED{RST} {row['id']}\n          {DIM}A16.P4 report older than its "
                      f"prover: tools/{prover.group(1)} was modified AFTER this measurement. Re-run the "
                      f"replay command and bank its output, rather than a verdict the current "
                      f"instrument never produced.{RST}")
                continue
        newer = [d for d in deps
                 if os.path.exists(os.path.join(ROOT, d))
                 and os.path.getmtime(os.path.join(ROOT, d)) > measured_at + 1]
        if newer:
            refused += 1
            print(f"  {YEL}REFUSED{RST} {row['id']}\n          {DIM}A16.P3 stale at birth: "
                  f"{', '.join(sorted(newer))} changed AFTER this measurement was taken. Re-measure "
                  f"against the current file rather than banking evidence the next gate run will "
                  f"expire.{RST}")
            continue
        candidate = dict(row)
        candidate["status"] = "green"
        candidate["evidence"] = ev
        state, why = V.classify(candidate, gates, urls)
        if state != "green":
            refused += 1
            print(f"  {YEL}REFUSED{RST} {row['id']}\n          {DIM}{why or state}{RST}")
            continue
        ev["fn_digests"] = V.fn_digests(deps)          # stamp NOW, while provably fresh (R4b)
        row["status"] = "green"
        row["evidence"] = ev
        banked += 1

    print(f"\n  banked {GREEN}{banked}{RST} · refused {refused} · walk-failed {failed} "
          f"· unknown-id {missing}  ({'APPLIED' if a.apply else 'dry run'})")
    if a.apply:
        tmp = bank_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(bank, f, indent=1, ensure_ascii=False)
        os.replace(tmp, bank_path)
        print(f"  wrote {os.path.relpath(bank_path, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
