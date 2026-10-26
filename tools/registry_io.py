#!/usr/bin/env python3
"""registry_io.py - ONE loader for the trajectory registry and the critic bank, with the cube in a shard of its own.

WHY A SHARD (2026-10-26). trajectory_registry.json and critic_registry.json are tracked and pushed: 66.9 MB and 71.2 MB
in HEAD at indent=2. GitHub warns at 50 MB and REFUSES a file over 100 MB. Wave CX (the cube: U/F/I x layer x admitted
persona, A x layer, the UX face) is 19,250 measured rows - at indent=2 that is +40 MB on the registry and the file would
be refused on Ian's next push; even lean rows leave no room for the walk receipts that follow. So the cube lives in
trajectory_registry_cx.json / critic_registry_cx.json, written COMPACT (no indentation), and every core tool reads the
UNION through load_doc() / load_critic() and writes back through save_doc() / save_critic(), which route each row to its
shard by id prefix (CX... -> the cube shard; everything else -> the main file, in the main file's own format).

The union is what every reader sees: the gate derives ids over it, the ledger closes over it, the header counts it, the
critic bank seeds against it, the stop guard counts buildable rows in it, a walk receipt lands in whichever shard owns
the id. A tool that still reads trajectory_registry.json directly sees the main program only - true, and smaller than
the whole; the readers that must see the whole are the ones this module was fitted to.

    from registry_io import load_doc, save_doc, load_critic, save_critic
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "trajectory_registry.json"
SHARDS = {"CX": ROOT / "trajectory_registry_cx.json"}            # id prefix -> file (the cube)
CRITIC_MAIN = ROOT / "critic_registry.json"
CRITIC_SHARDS = {"CX": ROOT / "critic_registry_cx.json"}


def _read(path: Path) -> dict | None:
    if not path.exists():
        return None
    with io.open(path, encoding="utf-8") as f:
        return json.loads(f.read())


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _shard_of(row_id: str, shards: dict) -> str | None:
    rid = str(row_id)
    for pfx in shards:
        if rid.startswith(pfx) and rid[len(pfx):].isdigit():
            return pfx
    return None


def load_doc() -> dict:
    """The registry as one document: the main file's rows followed by each shard's, count = the union."""
    main = _read(MAIN) or {"trajectories": []}
    rows = list(main.get("trajectories") or [])
    for pfx, path in SHARDS.items():
        shard = _read(path)
        if shard:
            rows.extend(shard.get("trajectories") or [])
    doc = {k: v for k, v in main.items() if k != "trajectories"}
    doc["trajectories"] = rows
    doc["count"] = len(rows)
    return doc


def save_doc(doc: dict, indent: int | None = 2) -> dict:
    """Write the union back: shard rows to their shard (compact), the rest to the main file. Returns {file: rows}."""
    buckets: dict[str, list] = {"": []}
    for pfx in SHARDS:
        buckets[pfx] = []
    for r in doc.get("trajectories") or []:
        buckets[_shard_of(r.get("id", ""), SHARDS) or ""].append(r)
    main = {k: v for k, v in doc.items() if k not in ("trajectories", "count")}
    main["trajectories"] = buckets[""]
    main["count"] = len(buckets[""])
    _atomic_write(MAIN, json.dumps(main, indent=indent, ensure_ascii=False) + "\n")
    written = {MAIN.name: len(buckets[""])}
    for pfx, path in SHARDS.items():
        shard = {"_doc": f"trajectory registry shard: ids {pfx}1.. (tools/registry_io.py); written compact because GitHub refuses a "
                         f"file over 100 MB and the main registry is already past 60 MB - read the UNION through registry_io.load_doc()",
                 "updated": doc.get("updated"), "count": len(buckets[pfx]), "trajectories": buckets[pfx]}
        if buckets[pfx] or path.exists():
            _atomic_write(path, json.dumps(shard, separators=(",", ":"), ensure_ascii=False) + "\n")
            written[path.name] = len(buckets[pfx])
    return written


def load_critic() -> dict:
    main = _read(CRITIC_MAIN) or {"rows": []}
    rows = list(main.get("rows") or [])
    for pfx, path in CRITIC_SHARDS.items():
        shard = _read(path)
        if shard:
            rows.extend(shard.get("rows") or [])
    doc = {k: v for k, v in main.items() if k != "rows"}
    doc["rows"] = rows
    doc["count"] = len(rows)
    return doc


def save_critic(critic: dict, indent: int | None = 2) -> dict:
    buckets: dict[str, list] = {"": []}
    for pfx in CRITIC_SHARDS:
        buckets[pfx] = []
    for r in critic.get("rows") or []:
        buckets[_shard_of(r.get("id", ""), CRITIC_SHARDS) or ""].append(r)
    main = {k: v for k, v in critic.items() if k not in ("rows", "count")}
    main["rows"] = buckets[""]
    main["count"] = len(buckets[""])
    _atomic_write(CRITIC_MAIN, json.dumps(main, indent=indent, ensure_ascii=False) + "\n")
    written = {CRITIC_MAIN.name: len(buckets[""])}
    for pfx, path in CRITIC_SHARDS.items():
        shard = {"_doc": f"critic registry shard: ids {pfx}1.. (tools/registry_io.py); compact - read the UNION through registry_io.load_critic()",
                 "updated": critic.get("updated"), "rubric_sha": critic.get("rubric_sha"), "count": len(buckets[pfx]), "rows": buckets[pfx]}
        if buckets[pfx] or path.exists():
            _atomic_write(path, json.dumps(shard, separators=(",", ":"), ensure_ascii=False) + "\n")
            written[path.name] = len(buckets[pfx])
    return written


def self_test() -> int:
    ok = _shard_of("CX12", SHARDS) == "CX" and _shard_of("CXU1", SHARDS) is None and _shard_of("T1", SHARDS) is None \
        and _shard_of("KA3", SHARDS) is None
    d = load_doc()
    ok = ok and isinstance(d.get("trajectories"), list) and d["count"] == len(d["trajectories"])
    print(("PASS" if ok else "FAIL") + f" registry-io self-test - union {d['count']} rows, shards present: "
          + ", ".join(p.name for p in SHARDS.values() if p.exists()) or "none")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
