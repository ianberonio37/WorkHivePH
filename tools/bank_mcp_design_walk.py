#!/usr/bin/env python3
"""bank_mcp_design_walk.py - bank ONE design-lens row from the walk just made through the Playwright MCP (2026-09-15).

The walk is `browser_run_code_unsafe { filename: 'tools/w4_design_walk.js' }` with its parameters in `.tmp/w4_args.json`
(id, page, lens, cast). It arrives on the page as the person, records the overlap/occlusion record and the lens's
live measurements at phone-390 AND desktop-1280 (one batched round), and POSTs the per-step ledger to the seeder,
which writes `.tmp/w4_steps/<id>.json`. The lens's JUDGEMENT (the playbook applied, the findings, the fixes) happens
in the conversation between the walk and this call; this tool then:

  1. runs the mechanical detector on the page (`impeccable detect --json`) -> .tmp/w4_design/<id>.detect.json,
     and REFUSES to bank while it reports a primary finding (the row closes only clean);
  2. writes the receipt through tools/record_mcp_walk.py (instrument playwright-mcp, or playwright-mcp + figma-mcp
     for the figma lens; --lens, --viewports, --detector, --scores, --languages, --figma);
  3. banks the row through tools/bank_journey_walk.py at locking/60 under the gate `w4-design`.

  python tools/bank_mcp_design_walk.py --id W45842 --lens slop --page achievements.html --cast "Christine Dizon"
  python tools/bank_mcp_design_walk.py --id W45844 --lens audit --page achievements.html --cast "Christine Dizon" \
      --scores '{"before":{"a11y":2,"performance":3,"theming":2,"responsive":3,"integrity":3},"after":{"a11y":3,...}}'
  python tools/bank_mcp_design_walk.py --id W45847 --lens figma --page index.html --cast "Christine Dizon" \
      --figma "<fileKey> <node@390> <node@1280>"

A receipt is written only from the walk it names: the steps file must carry the id's page at both viewports with a
`fit` dict on every step, and no problems.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ★THE BANK SUCCEEDED AND THE TOOL REPORTED A CRASH (2026-09-15, W45868). The detector's descriptions carry an
# em-dash and the walk's control names carry emoji, so echoing the child's tail through a cp1252 stdout raised
# UnicodeEncodeError AFTER the row was already recorded and banked - a caller reading the exit code would have
# re-run a bank that had landed, or believed a green row had failed. A tool that writes state must not be able to
# fail on the way to saying so.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
# ONE definition, three consumers. See prove_design_detector_ratchet.is_measurement_artifact.
from prove_design_detector_ratchet import is_measurement_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = Path(os.environ.get("IMPECCABLE_HOME", str(Path.home() / ".claude" / "skills" / "impeccable"))) / "scripts" / (
    "impeccable.cmd" if os.name == "nt" else "impeccable")
GATE = "w4-design"
VIEWPORTS = ("phone-390", "desktop-1280")


def run_detector(page: str, out: Path) -> list[dict]:
    r = subprocess.run([str(DETECTOR), "detect", "--json", "--no-advisory", page], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (r.stdout or "").strip() or "[]"
    findings = json.loads(text)
    out.parent.mkdir(parents=True, exist_ok=True)
    # The FILE keeps every finding the detector reported, artifacts included: it is the receipt's
    # evidence, and trimming stored evidence so a gate goes green is the opposite of the job.
    out.write_text(json.dumps(findings, indent=1, ensure_ascii=False), encoding="utf-8")
    # The VERDICT excludes what is measured on paper. Without this, a page whose only findings are
    # `@media print { body * { color:#111 } }` against the screen background looks like 92 unfixed
    # defects - which is exactly why logbook.html's receipts had to pin 92 as "disproven", and why
    # that pin then broke when one <option> moved it to 93 (2026-09-16).
    return [f for f in findings
            if f.get("severity") != "advisory" and not is_measurement_artifact(f)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--lens", required=True, choices=["slop", "craft", "audit", "copy", "motion", "figma", "critique"])
    ap.add_argument("--page", required=True)
    ap.add_argument("--cast", required=True)
    ap.add_argument("--scores", default="", help="JSON {before:{...}, after:{...}} (audit / critique)")
    ap.add_argument("--languages", default="", help="'en,fil' for the copy lens (defaults to en)")
    ap.add_argument("--figma", default="", help="'<fileKey> <node@390> <node@1280>' for the figma lens")
    ap.add_argument("--note", default="")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    ap.add_argument("--detector-disproven", default="",
                    help="JSON {antipattern: {count, why}} for findings a LIVE measurement disproves; the count must "
                         "match the detector exactly, anything unclaimed still refuses, and the claims enter the receipt")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = ROOT / ".tmp" / "w4_steps" / f"{a.id}.json"
    if not src.exists():
        print(f"REFUSED: no steps file at {src} - the MCP walk writes it via the seeder's POST /api/w4/steps")
        return 2
    steps = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(steps, dict):
        steps = steps.get("steps") or []
    problems = list((steps[0].get("problems") if steps else None) or [])
    if problems:
        print(f"REFUSED: the walk reported {len(problems)} problem(s):")
        for p in problems:
            print("   -", str(p)[:160])
        return 2
    seen_vps = {s.get("viewport") for s in steps if s.get("page") == a.page}
    if not set(VIEWPORTS) <= seen_vps:
        print(f"REFUSED: {a.page} walked at {sorted(v for v in seen_vps if v)} - both {VIEWPORTS} are needed")
        return 2
    thin = [f"{s.get('page')}@{s.get('viewport') or '-'}" for s in steps if not isinstance(s.get("fit"), dict)]
    if thin:
        print(f"REFUSED: no overlap/occlusion record on {thin}")
        return 2
    if a.lens == "figma" and not a.figma:
        print("REFUSED: the figma lens needs --figma '<fileKey> <node@390> <node@1280>'")
        return 2
    langs = a.languages or ("en,fil" if a.lens == "copy" else "en")
    if a.lens == "copy" and not {"en", "fil"} <= set(langs.split(",")):
        print("REFUSED: the copy lens is walked in both en and fil")
        return 2
    if a.lens in ("audit", "critique") and not a.scores:
        print(f"REFUSED: the {a.lens} lens banks with --scores '{{\"before\":{{...}},\"after\":{{...}}}}'")
        return 2

    # ★A PAGE WHOSE INLINE SCRIPT DOES NOT PARSE IS NOT A PAGE (2026-09-15). Every <script> without src
    # must parse; typed blocks are checked under the grammar their type names. The rule and the four
    # repairs it has taken (typed scripts, empty JSON placeholders, a <script> token inside an HTML
    # comment) live in tools/check_inline_scripts.js, which walks the file the way a tokenizer does
    # rather than running one regex over it.
    if a.page.endswith(".html"):
        chk = subprocess.run(["node", str(ROOT / "tools" / "check_inline_scripts.js"), a.page],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if chk.returncode != 0:
            print(f"REFUSED: {a.page} has an inline script that does not parse: {(chk.stdout or chk.stderr).strip()[:200]}")
            return 2
    det_path = ROOT / ".tmp" / "w4_design" / f"{a.id}.detect.json"
    primary = run_detector(a.page, det_path)
    # ★A DISPROVEN FINDING IS STILL A FINDING UNTIL ITS COUNT IS PINNED (2026-09-15). impeccable's own critique
    # playbook says to "keep deterministic findings separate from visual judgment and call out false positives",
    # and analytics-report.html is the case that forces it: ONE file holds a dark app shell and a white printed
    # document, so the detector pairs the shell's white text with the document's white ground and reports nine
    # low-contrast findings - while a live sampler over the GENERATED report measured 0 of 609 text nodes below
    # threshold. The exception is bounded so it cannot become a door: every claimed antipattern must state its
    # EXACT current count and a reason, the counts must match what the detector reports right now, and anything
    # NOT claimed still refuses the bank. A new finding of an already-claimed kind changes the count, so it
    # refuses too. The claims land in the receipt, and prove_w4_design_receipts re-checks them on every run.
    claimed: dict[str, dict] = {}
    if a.detector_disproven:
        claimed = json.loads(Path(a.detector_disproven).read_text(encoding="utf-8"))
        for k, v in claimed.items():
            if not isinstance(v, dict) or "count" not in v or not str(v.get("why", "")).strip():
                print(f"REFUSED: the disproven map's '{k}' needs a count and a why"); return 2
    from collections import Counter
    seen = Counter(f.get("antipattern") for f in primary)
    unclaimed = [f for f in primary if f.get("antipattern") not in claimed]
    miscounted = {k: (v["count"], seen.get(k, 0)) for k, v in claimed.items() if seen.get(k, 0) != v["count"]}
    if unclaimed or miscounted:
        print(f"REFUSED: impeccable detect reports {len(primary)} primary finding(s) on {a.page} "
              f"(saved to {det_path.relative_to(ROOT)}); the {a.lens} lens closes only clean:")
        for f in unclaimed[:12]:
            print(f"   - {f.get('antipattern')}: {str(f.get('snippet') or f.get('name'))[:110]}")
        for k, (want, got) in miscounted.items():
            print(f"   - '{k}' was claimed disproven at {want}, the detector now reports {got}")
        return 2
    if claimed:
        print(f"   {len(primary)} primary finding(s) accepted as DISPROVEN, each pinned to its count:")
        for k, v in claimed.items():
            print(f"     - {k} x{v['count']}: {str(v['why'])[:120]}")

    compact = []
    for s in steps:
        f = s.get("fit") or {}
        compact.append({"page": s.get("page"), "viewport": s.get("viewport"), "chars": s.get("chars"),
                        "identityKept": s.get("identityKept", True), "loadError": s.get("loadError") or None,
                        "lang": s.get("lang"), "measures": s.get("measures"),
                        "fit": {"findings": f.get("findings") or 0, "occlusion": (f.get("occlusion") or [])[:4],
                                "overflowEl": (f.get("overflowEl") or [])[:2], "wrapped": (f.get("wrapped") or [])[:2]}})
    findings = sum(int(c["fit"]["findings"]) for c in compact)
    out = ROOT / ".tmp" / "w4_steps" / f"{a.id}.steps.json"
    out.write_text(json.dumps(compact, ensure_ascii=False, indent=1), encoding="utf-8")
    instrument = ("playwright-mcp + figma-mcp" if a.lens == "figma"
                  else "playwright-mcp + chrome-devtools-mcp" if a.lens == "audit"
                  else "playwright-mcp")
    note = (f"Design lens {a.lens} on {a.page}, walked through the Playwright MCP as {a.cast} at "
            f"{' and '.join(VIEWPORTS)} in one batched round ({' -> '.join(dict.fromkeys(c['page'] for c in compact))}); "
            f"{findings} overlap finding(s); impeccable detect --json clean on the page ({det_path.relative_to(ROOT)}). "
            + a.note).strip()
    rec = [sys.executable, "tools/record_mcp_walk.py", "--id", a.id, "--instrument", instrument, "--cast", a.cast,
           "--axis", "phone-390 en", "--lens", a.lens, "--viewports", ",".join(VIEWPORTS),
           "--detector", str(det_path.relative_to(ROOT)).replace("\\", "/"), "--languages", langs,
           *(["--detector-disproven", json.dumps(claimed, ensure_ascii=False)] if claimed else []),
           "--note", note, "--steps", str(out)]
    if a.scores:
        rec += ["--scores", a.scores]
    if a.figma:
        rec += ["--figma", a.figma]
    bank = [sys.executable, "tools/bank_journey_walk.py", str(ROOT / ".tmp" / "mcp_walks" / f"{a.id}.json"),
            "--status", a.status, "--pct", a.pct, "--gate", GATE]
    print(f"{a.id} {a.lens} @ {a.page}: {len(compact)} steps, findings {findings}, detector clean, problems 0")
    if a.dry_run:
        print("  would run:", " ".join(rec[:8]), "...\n  then:", " ".join(bank[1:]))
        return 0
    for cmd in (rec, bank):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout or "").strip().splitlines()[-2:] + (r.stderr or "").strip().splitlines()[-2:]
        print("  " + " | ".join(t.strip()[:160] for t in tail if t.strip()))
        if r.returncode != 0:
            print(f"  FAILED ({r.returncode}): {Path(cmd[1]).name}")
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
