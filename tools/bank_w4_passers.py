#!/usr/bin/env python3
"""bank_w4_passers.py - advance every un-banked W4 browser-shaped row (nav-hub, confusion) of one axis whose NEWEST
receipt satisfies the W4 evidence gate (live_walk_manifest._w4_missing == '' and ok) to `locking`, naming the gate
that re-earns it AT ITS AXIS. Idempotent: only rows below locking move; re-running after another walk banks the new
passers only. Registry-shaped, no browser - the one banker to run while a walk holds the browser (never run two
bankers at once: they race the registry).

  python tools/bank_w4_passers.py --axis "narrow-320 en"                    # nav-hub + confusion rows of that axis
  python tools/bank_w4_passers.py --axis "phone-390 en" --kind confusion    # one kind only
  python tools/bank_w4_passers.py --axis "phone-390 en" --dry-run           # list, do not write
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

# ★THIS BANKER'S OWN STDOUT KILLED IT MID-WRITE (2026-09-23). Run as a subprocess its stdout is a pipe, so
# Python encodes with the locale codec - cp1252 here - and a row whose subject carries U+2192 ("Generate
# Documents →") raised UnicodeEncodeError on the `print` that ANNOUNCES the bank, one line BEFORE the
# registry write. The caller saw "bank W4163 ... -> w4-actions" scroll past and a non-zero exit it was
# grepping past, and four rows that had genuinely lived clean stayed `specced` with an empty basis. The
# driver carried this exact fix in its own docstring - "every consumer, not just the one that failed
# first" - and this consumer never got it. Reconfigure before anything can print.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# ★THE GATE NAMES THE INSTRUMENT AT THE ROW'S AXIS (2026-09-14): a narrow-320 row banked under the phone-390 gate would
# be re-earned by a walk at the wrong width - the lock would be decoration. Same prover, the axis argument is the gate.
GATES = {
    ("nav-hub", "phone-390 en"): "w4-nav-hub",
    ("nav-hub", "narrow-320 en"): "w4-nav-hub-320-en",
    ("nav-hub", "phone-390 fil"): "w4-nav-hub-390-fil",
    ("confusion", "phone-390 en"): "w4-confusions",
    ("confusion", "narrow-320 en"): "w4-confusions-320-en",
    ("confusion", "phone-390 fil"): "w4-confusions-390-fil",
    ("action", "phone-390 en"): "w4-actions",
    ("action", "narrow-320 en"): "w4-actions-320-en",
    ("action", "phone-390 fil"): "w4-actions-390-fil",
    ("layer", "phone-390 en"): "w4-layer-ca",
    ("layer", "narrow-320 en"): "w4-layer-ca-320-en",
    ("layer", "phone-390 fil"): "w4-layer-ca-390-fil",
}
INSTRUMENT = {"nav-hub": "tools/prove_w4_navhub.mjs", "confusion": "tools/prove_w4_confusions.mjs", "action": "tools/prove_w4_actions.mjs",
              "layer": "tools/prove_w4_layer_ca.mjs"}   # the only browser-shaped layer still open is CA (F/CA are the person layers)


# ★THE BASIS NAMES THE INSTRUMENT THE RECEIPT CARRIES, NOT A HARD-CODED PROVER PATH (2026-09-23).
# The table above is a DEFAULT for a receipt that names nothing, and it must never override one that does.
# On 2026-09-15 Ian retracted every row banked on a Playwright-LIBRARY prover; the retraction was applied to
# the rows and NOT to the tools, so the next day `walk_navhub_axis.py` re-banked 12 rows on the retracted
# instrument - and three of them had held CORRECT `playwright-mcp` evidence that a "refresh" re-walk
# replaced with retracted evidence. Reading `res["instrument"]` is what stops that recurring here: an
# action row walked through tools/w4_action_walk.js banks as `playwright-mcp + postgres-mcp` (the string
# live_walk_manifest.MARKERS requires for a "Lived start to end:" row), and a row walked by the prover still
# says so. The instrument is part of the definition of done, so the basis must state the one actually used.
# See memory feedback_a_library_batch_is_not_an_mcp_walk.
def _instrument_of(res: dict, kind: str) -> str:
    return str(res.get("instrument") or INSTRUMENT.get(kind) or "?")


# ★AND THE RETRACTION IS ENFORCED IN THE TOOL, NOT ONLY ON THE ROWS (2026-09-23).
# On 2026-09-15 Ian retracted every row banked on a Playwright-LIBRARY prover: "I thought we are using relevant
# live MCPs?" The rows were re-opened and the TOOLS were left alone, so the next day a nav-hub driver re-banked
# 12 rows on the retracted instrument. TODAY THE SAME HOLE COST 144 ACTION ROWS: this banker advances any row
# whose NEWEST receipt passes the evidence gate, and 144 rows were still sitting on their old
# `tools/prove_w4_actions.mjs` receipts - so a single call moved all of them to `locking` on retracted evidence
# without the walk having recorded anything. A retraction that lives only in a memory file is a comment; this is
# the gate. A prover may WALK to find defects and produce receipts - it may not BANK a row reserved for an MCP
# walk, and the newest-wins receipt store means its receipt is always one banker call away from doing so.
# See memory feedback_a_library_batch_is_not_an_mcp_walk (both occurrences).
RETRACTED_INSTRUMENTS = (
    "tools/prove_w4_actions.mjs",
    "tools/prove_w4_navhub.mjs",
    "tools/prove_w4_confusions.mjs",
    "tools/prove_w4_layer_ca.mjs",
    "tools/prove_full_journeys.mjs",
)


def _is_retracted(res: dict) -> bool:
    inst = str(res.get("instrument") or "")
    return any(inst == r or inst.endswith(r) for r in RETRACTED_INSTRUMENTS)


def _axis_of(t: dict) -> str:
    ax = t.get("axis") or {}
    return f"{ax.get('device')} {ax.get('language')}"


def _overlap_phrase(res: dict) -> str:
    """★THE BASIS STATES THE OVERLAP THE RECEIPT ACTUALLY CARRIES (2026-09-23).

    Every branch below used to end with the literal words "0 overlap findings at every step" - a hard-coded
    claim, true only for as long as no walk ever found one. The control-press walker broke that the first
    time it ran: putting engineering-design.html into step 4 rendered the calculator form, and four of its
    inputs came back covered (#f-floor-area and #f-ceiling under #wh-wayfinding, #f-wall-area under the
    source chip, #f-glass-area under div.sticky) - 10 findings on a receipt whose basis would have asserted
    zero. An action row is not FAILED by an overlap (the layout is the craft lens's row, not this one), but
    its basis must not claim the opposite of its own evidence. A label is a claim.
    See feedback_metric_label_is_a_claim_add_the_missing_half, feedback_a_basis_must_describe_the_page_in_its_own_receipt.
    """
    steps = res.get("steps") or []
    total = 0
    worst = ""
    for s in steps:
        fit = s.get("fit") or {}
        n = int(fit.get("findings") or 0)
        total += n
        if n and not worst:
            occ = (fit.get("occlusion") or [""])[0]
            worst = f" (worst on {s.get('page', '?')}: {str(occ)[:90]})" if occ else f" (on {s.get('page', '?')})"
    if not total:
        return "0 overlap findings at every step"
    return f"{total} overlap finding(s) recorded, carried to this page's craft row{worst}"


def _basis(t: dict, res: dict, axis: str) -> str:
    kind = t["w4"]["kind"]
    today = time.strftime("%Y-%m-%d")
    steps = res.get("steps") or []
    pages = " -> ".join(dict.fromkeys(s.get("page", "?") for s in steps))
    cast = res.get("cast", "the row's worker")
    overlap = _overlap_phrase(res)
    if kind == "nav-hub":
        return (f"WALKED LIVE {today} via {_instrument_of(res, kind)} (serial single-host, {axis}) - {t['w4']['host']}: "
                f"{len(steps)} pages arrived as its own hive member ({cast}), identity kept, "
                f"{(res.get('w4') or {}).get('hub_controls', '?')}/11 hub controls, {overlap}, focus returned to the fab.")
    if kind == "action":
        act = t["w4"].get("action") or {}
        note = str(res.get("note", "")).replace("\n", " ")[:170]
        return (f"WALKED LIVE {today} via {_instrument_of(res, kind)} (serial, {axis}) - {act.get('kind')} {act.get('subject')} lived as {cast} "
                f"along {pages}: {note}; identity kept, {overlap}.")
    if kind == "layer":
        note = str(res.get("note", "")).replace("\n", " ")[:170]
        return (f"WALKED LIVE {today} via {_instrument_of(res, kind)} (serial, {axis}) - layer {t['w4'].get('layer')} lived as {cast} along {pages}: "
                f"{note}; identity kept, {overlap}.")
    detail = str((res.get("w4") or {}).get("predicate", "")).replace("\n", " ")[:160]
    return (f"WALKED LIVE {today} via {_instrument_of(res, kind)} (serial, {axis}) - {t['w4']['confusion']} lived again as {cast} "
            f"along {pages}: the improvement holds ({detail}), identity kept, {overlap}.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", required=True)
    ap.add_argument("--kind", default="all", choices=["all", "nav-hub", "confusion", "action", "layer"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import live_walk_manifest as m
    importlib.reload(m)
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    kinds = ("nav-hub", "confusion", "action", "layer") if a.kind == "all" else (a.kind,)
    rows = [t for t in reg["trajectories"] if (t.get("w4") or {}).get("kind") in kinds and _axis_of(t) == a.axis
            and t.get("status") not in ("locking", "locked", "descoped")]
    rec = m._w4_receipts()
    ready = [t for t in rows if (rec.get(t["id"]) or {}).get("ok") and m._w4_missing(t, rec) == ""
             and not _is_retracted(rec.get(t["id"]) or {})]
    retracted = [t for t in rows if (rec.get(t["id"]) or {}).get("ok") and m._w4_missing(t, rec) == ""
                 and _is_retracted(rec.get(t["id"]) or {})]
    if retracted:
        print(f"  REFUSED {len(retracted)} row(s) whose newest receipt names a RETRACTED library prover "
              f"({', '.join(sorted({_instrument_of(rec[t['id']], t['w4']['kind']) for t in retracted}))}) - "
              f"walk them through the MCP to bank them")
    held = [(t, m._w4_missing(t, rec) or ("receipt not ok: " + "; ".join((rec.get(t["id"]) or {}).get("problems", [])[:1])[:90]))
            for t in rows if t not in ready and rec.get(t["id"])]
    print(f"{a.axis}: {len(rows)} un-banked row(s) of kind {a.kind} · {len(ready)} pass the W4 gate · {len(held)} walked but held · "
          f"{len(rows) - len(ready) - len(held)} never walked")
    for t, why in held[:12]:
        print(f"  held  {t['id']} {t['w4'].get('confusion') or t['w4'].get('host')}: {why[:110]}")
    if not ready:
        return 0
    entries = []
    for t in ready:
        gate = GATES.get((t["w4"]["kind"], a.axis))
        if not gate:
            print(f"  skip {t['id']}: no gate registered for ({t['w4']['kind']}, {a.axis})")
            continue
        entries.append({"ids": t["id"], "status": "locking", "pct": 60, "gate": [gate], "basis": _basis(t, rec[t["id"]], a.axis)})
        label = t["w4"].get("confusion") or t["w4"].get("host") or f"{(t['w4'].get('action') or {}).get('kind')} {(t['w4'].get('action') or {}).get('subject')}"
        print(f"  bank  {t['id']} {label} -> {gate}")
    if a.dry_run or not entries:
        return 0
    bf = ROOT / ".tmp" / f"w4_bank_{a.axis.replace(' ', '-')}.json"
    bf.parent.mkdir(parents=True, exist_ok=True)
    bf.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "advance_trajectory.py"), "--batch", str(bf)],
                       capture_output=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    tail = [l for l in out.splitlines() if "advanced" in l or "FAIL" in l or "refus" in l]
    print(tail[-1] if tail else "applied (no summary line from advance_trajectory)")
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
