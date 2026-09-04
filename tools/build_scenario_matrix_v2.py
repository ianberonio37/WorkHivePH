#!/usr/bin/env python3
"""build_scenario_matrix_v2.py — the diversity guarantee for the T201-T500 expansion.

v1 (scenario_matrix.json) is device x auth x entry x intent for HUMAN acquisition/task journeys,
and validate_scenario_matrix.py holds it to an EXACT cartesian product. Adding the expansion's new
values (kiosk/print viewports, adversary/assistive/oversight/machine actors, api/webhook channels,
attack/audit/comply intents) to that matrix would explode it combinatorially and every new
combination would have to be reasoned - so the expansion gets its OWN matrix, v2, validated by the
same four rules (structure / no-silent-axis / NA-reasoned / covered-evidenced).

This file is the ONLY writer of scenario_matrix_v2.json. The cells are the exact cartesian product
of four axes; status + NA reason are derived from a small set of SEMANTIC rules (an actor's intent,
a channel's actor) so the reasons genuinely follow from the axis meanings rather than being typed
per cell. Every axis value is claimed by >=1 non-NA cell naming a real expansion trajectory, so the
gate's rule 2 passes.

  (default)  write substrate/reference/scenario_matrix_v2.json
  --check    exit 1 if the written file differs from a fresh build (used by the gate)
  --stdout   print the JSON only
"""
from __future__ import annotations

import io
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "substrate" / "reference" / "scenario_matrix_v2.json"

# The four expansion axes (product 3x4x3x4 = 144, generated). Every value has at least one real,
# SEMANTICALLY HONEST trajectory home in waves T-AE — no value survives only on a strained cell.
AXES = {
    # the new viewports the human waves introduced (X a11y small screens, AD kiosk/print surfaces);
    # fixed-kiosk-print also stands in for a machine client's headless, non-visual surface
    "viewport": ["narrow-320", "wide-1920", "fixed-kiosk-print"],
    # the four NEW actor classes the bespoke families model
    "actor": ["adversary", "assistive-tech", "oversight", "machine-client"],
    # how the actor reaches the system — browser-ui is the rendered human path (v1's implicit
    # channel), api-direct/webhook-inbound are the machine paths v1 never modelled
    "channel": ["browser-ui", "api-direct", "webhook-inbound"],
    # the new intents beyond v1's convert/do-a-task/browse-read
    "intent": ["attack", "audit", "comply", "operate"],
}

# Which expansion wave/trajectory owns each actor class — used to stamp a claiming trajectory on the
# covered/planned cells so rule 2 (every axis value claimed by >=1 non-NA cell) holds honestly.
ACTOR_WAVE = {
    "adversary": ("W", "T361"),        # security & adversarial personas
    "assistive-tech": ("X", "T385"),   # accessibility spectrum
    "oversight": ("Y", "T403"),        # regulator/auditor/procurement personas
    "machine-client": ("V", "T314"),   # edge-function layer (api/webhook clients)
}


def classify(cell: dict) -> tuple[str, str, list[str]]:
    """Return (status, na_reason, trajectories) for one cartesian cell from semantic rules.

    A cell is declared_na when the actor and the intent/channel are semantically incompatible - a
    real modelling judgement, not a skipped partition. Otherwise it is planned (an expansion arc
    that will walk it) or covered (an arc that already has a receipt)."""
    actor, intent, channel, vp = cell["actor"], cell["intent"], cell["channel"], cell["viewport"]
    wave, tid = ACTOR_WAVE[actor]

    # --- each actor has ONE coherent intent set; everything else is a reasoned NA ---
    ALLOWED_INTENT = {
        "adversary": {"attack"},              # the adversary's whole premise is defeating controls
        "assistive-tech": {"operate"},        # an assistive-tech user is here to DO a task with AT
        "oversight": {"audit", "comply"},     # a regulator/auditor reviews and attests, doesn't operate
        "machine-client": {"operate", "audit", "comply"},  # an integration client runs + reports
    }
    if intent not in ALLOWED_INTENT[actor]:
        return "declared_na", (f"a {actor} actor's intent is {sorted(ALLOWED_INTENT[actor])}, not "
                               f"'{intent}' — that intent belongs to a different actor's story"), []

    # --- each actor reaches the system over a coherent channel set ---
    ALLOWED_CHANNEL = {
        "adversary": {"browser-ui", "api-direct", "webhook-inbound"},  # attacks every surface
        "assistive-tech": {"browser-ui"},     # a human on AT drives a rendered UI, never a raw API
        "oversight": {"browser-ui", "api-direct"},  # dashboards + bulk export; not inbound webhooks
        "machine-client": {"api-direct", "webhook-inbound"},  # headless; no rendered UI
    }
    if channel not in ALLOWED_CHANNEL[actor]:
        return "declared_na", (f"a {actor} actor does not arrive over {channel} — its channels are "
                               f"{sorted(ALLOWED_CHANNEL[actor])}"), []

    # --- viewport coherence ---
    if actor == "machine-client" and vp in ("narrow-320", "wide-1920"):
        return "declared_na", ("a machine client has no viewport; the fixed-kiosk-print cell stands "
                               "in for its non-visual, headless surface"), []
    if actor == "adversary" and vp == "fixed-kiosk-print":
        return "declared_na", ("the adversary attacks over the wire, not from a kiosk/print display; "
                               "its viewport cells are the responsive ones"), []

    # otherwise it is a real expansion story: planned, owned by the actor's wave
    return "planned", "", [tid]


def build() -> dict:
    cells = []
    for vp, actor, channel, intent in itertools.product(*AXES.values()):
        cell = {"id": f"{vp}|{actor}|{channel}|{intent}",
                "viewport": vp, "actor": actor, "channel": channel, "intent": intent}
        status, reason, trajs = classify(cell)
        cell["status"] = status
        if status == "declared_na":
            cell["na_reason"] = reason
        else:
            cell["trajectories"] = trajs
            cell["evidence"] = f"wave {ACTOR_WAVE[actor][0]} expansion catalog (specced 2026-08-31)"
        cells.append(cell)
    return {
        "_meta": {
            "name": "scenario_matrix_v2",
            "version": "2.0.0",
            "created": "2026-08-31",
            "description": ("T201-T500 expansion diversity guarantee: viewport x actor x channel x "
                            "intent. Kept separate from v1 (which stays human-acquisition and "
                            "cartesian-strict). A cell is planned when an expansion arc will walk it, "
                            "declared_na when the actor and the intent/channel/viewport are "
                            "semantically incompatible (a modelling judgement, reasoned), covered "
                            "when a receipt exists. Built by tools/build_scenario_matrix_v2.py; "
                            "validate_scenario_matrix.py enforces structure/no-silent-axis/NA-"
                            "reasoned/covered-evidenced on it exactly as on v1."),
            "axes": AXES,
            "cell_count": len(cells),
        },
        "cells": cells,
    }


def main() -> int:
    doc = build()
    blob = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if "--stdout" in sys.argv:
        print(blob)
        return 0
    if "--check" in sys.argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != blob:
            print("scenario_matrix_v2 DRIFT — run: python tools/build_scenario_matrix_v2.py")
            return 1
        print("scenario_matrix_v2 current.")
        return 0
    OUT.write_text(blob, encoding="utf-8")
    from collections import Counter
    c = Counter(x["status"] for x in doc["cells"])
    print(f"scenario_matrix_v2 written: {len(doc['cells'])} cells · "
          + " · ".join(f"{k} {v}" for k, v in sorted(c.items())))
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
