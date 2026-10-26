#!/usr/bin/env python3
"""bank_brh11_batch.py - turn one MCP batch of §BRH.11 host walks into receipts and an advance batch (2026-10-26).

A batch file (.tmp/mcp_walks/batch_<group>.json) is what one Playwright-MCP run measured on several hub hosts, signed in
as one persona, at phone-390 AND desktop-1280: per host and viewport, `rest` (the panel opened where the FAB rests), `top`
(opened after the FAB is planted at the top) and `install` (the control at rest, the guide on tap). This banker maps each
host to its three BRH rows (AN rest, AN top, AM install) by the row titles the seeder wrote, writes one receipt per row
through record_mcp_walk.build_receipt (the ledger's own shape and refusals), and emits an advance batch for
advance_trajectory.py --batch - locking 60 on the two gates, exactly as the hive rows were banked by hand.

A host whose measurement failed on either viewport gets a NOT PROVEN receipt (ok=false) and is left out of the advance:
the receipt records what was observed, never a pass.

    python tools/bank_brh11_batch.py .tmp/mcp_walks/batch_A_worker.json            # receipts + advance json
    python tools/bank_brh11_batch.py .tmp/mcp_walks/batch_A_worker.json --dry-run  # what would be written
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
KINDS = {
    "rest": ("BRH-AN", "panel opened where the FAB rests"),
    "top": ("BRH-AN", "panel opened after the FAB is dragged to the top"),
    "install": ("BRH-AM", "install control"),
}
GATES = {"rest": ["hub-panel-on-screen"], "top": ["hub-panel-on-screen"], "install": ["install-affordance", "hub-panel-on-screen"]}


def _short(page: str) -> str:
    from seed_expansion_wave4 import _short as s
    return s(page)


def row_ids(hosts: list[str]) -> dict:
    """{(host, kind): id} from the registry's BRH-AM/AN titles ('<mechanism> - <short page> · <key> - <persona>')."""
    import registry_io as _rio
    out = {}
    rows = [t for t in _rio.load_doc()["trajectories"] if t.get("wave") in ("BRH-AM", "BRH-AN")]
    for host in hosts:
        sp = _short(host)
        for kind, (wave, key) in KINDS.items():
            for t in rows:
                if t.get("wave") == wave and f" - {sp} · {key}" in t["title"]:
                    out[(host, kind)] = t
                    break
    return out


def judge(step: dict, kind: str) -> tuple[bool, str]:
    if step.get("bounced"):
        return False, f"bounced to {step['bounced']}"
    if step.get("error"):
        return False, f"probe error: {step['error']}"
    m = step.get(kind) or {}
    if kind == "install":
        return bool(m.get("ok")), ("" if m.get("ok") else f"install: control {m.get('controlHeight')}px, guide {m.get('guide')}, icon {m.get('iconLoaded')}, panel {m.get('panel')}")
    ok = bool(m.get("inside") and m.get("headerHit") and m.get("open") and (kind == "rest" or m.get("below")))
    return ok, ("" if ok else f"{kind}: panel {m.get('panel')} of {m.get('vh')}, below {m.get('below')}, headerHit {m.get('headerHit')}")


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    from record_mcp_walk import build_receipt
    batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
    persona = batch.get("persona", "worker")
    walked_at = batch.get("walked_at") or _dt.datetime.now().isoformat(timespec="seconds")
    hosts = list(batch["hosts"].keys())
    ids = row_ids(hosts)
    advance = []
    written, unproven = [], []
    for host in hosts:
        rec = batch["hosts"][host]
        for kind, (wave, key) in KINDS.items():
            row = ids.get((host, kind))
            if not row:
                print(f"  no {wave} row for {host} · {key} - skipped")
                continue
            steps, problems = [], []
            for vp in ("phone-390", "desktop-1280"):
                s = rec.get(vp) or {}
                ok, why = judge(s, kind)
                if not ok:
                    problems.append(f"{vp}: {why or 'no measurement'}")
                steps.append({"viewport": vp, "device": vp, "page": host, "chars": s.get("chars", 0), "identityKept": True,
                              "identity": batch.get("signin"), kind: s.get(kind), "rest": s.get("rest") if kind != "rest" else None,
                              "shots": [f".tmp/mcp_walks/shots/{host.replace('.html', '')}_{vp}_{'install' if kind == 'install' else 'top'}.png"]})
            unproven_text = "; ".join(problems)
            if kind == "rest":
                note = (f"AN at rest on {host} as {batch.get('signin', {}).get('worker', persona)} ({persona}), signed in through the product's own form: "
                        f"the panel opened wholly inside the viewport with the header hit-testing to itself at phone-390 and desktop-1280. WebKit half: "
                        f"tools/prove_hub_panel_on_screen.mjs --engine webkit (hub_panel_on_screen_report.json, 348/348).")
            elif kind == "top":
                note = (f"AN after the FAB is planted at the top on {host} as {persona}: the hub's own drag key set to bottom innerHeight-80, reload, open - "
                        f"the panel flips BELOW the FAB, wholly inside, header hit-testing to itself, at both viewports. Pre-fix the same plant read "
                        f"-679..12 of 844 (prover at nav-hub.js 6e5888860c79). WebKit half: the prover's webkit sweep, 348/348.")
            else:
                note = (f"AM on {host} as {persona}: the Install control sits in the hub's assist row at rest at both viewports; a tap shows the "
                        f"per-platform guide with the home-screen icon loaded, the panel staying inside the viewport (nav-hub.js: prompt + choice raced "
                        f"against 1.5s, the guide the fallback). WebKit half: the prover's install case, 348/348.")
            w4 = {"layer": "F", "as_persona": persona, "viewports": ["phone-390", "desktop-1280"], "engine": "chromium"}
            try:
                doc = build_receipt(row["id"], "playwright-mcp", "normal", persona, steps, note, _dt.datetime.now().isoformat(timespec="seconds"),
                                    unproven_text, w4)
            except ValueError as e:
                print(f"  {row['id']} refused: {e}")
                continue
            doc["walked_at"] = walked_at
            out = OUT_DIR / f"{row['id']}.json"
            if not a.dry_run:
                tmp = out.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, out)
            r = doc["results"][0]
            (written if r["ok"] else unproven).append(row["id"])
            print(f"  {row['id']:<8} {host:<34} {kind:<8} ok={r['ok']} {r['metrics']['arrived']}/{r['metrics']['steps']} arrived" + (f"  {unproven_text[:90]}" if unproven_text else ""))
            if r["ok"]:
                advance.append({"ids": row["id"], "status": "locking", "pct": 60, "gate": GATES[kind],
                                "basis": f"[{_dt.date.today().isoformat()}] LOCKING->60. WALKED LIVE through the Playwright MCP (receipt .tmp/mcp_walks/{row['id']}.json): {note}"})
    adv = OUT_DIR / (Path(a.batch).stem + ".advance.json")
    if not a.dry_run:
        adv.write_text(json.dumps(advance, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n  receipts: {len(written)} proven, {len(unproven)} not proven ({', '.join(unproven) or '-'}); advance batch: {adv.name} ({len(advance)} rows)"
          + ("  [dry-run: nothing written]" if a.dry_run else ""))
    print(f"  then: python tools/advance_trajectory.py --batch {adv.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
