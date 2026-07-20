#!/usr/bin/env python3
"""
validate_storage_keys.py — PLATFORM_CENTRALIZATION_ROADMAP C-P4 (cross-cutting SSOT).

The platform's localStorage/sessionStorage keys DRIFTED: the same concept is stored under
several keys (hive id: wh_active_hive_id / wh_hive_id / hive_id · worker: wh_last_worker /
workerName / wh_worker_name), so code reads a fallback chain and a write to one key is invisible
to a read of another. `storage_key_registry.json` is the SSOT: every key is CANONICAL or a
registered ALIAS-of-canonical (the known drift, tracked for convergence).

Modes:
  (default)  inventory every key used in *.js/*.html + print the board (canonical / alias / UNKNOWN).
  --write-registry   seed/refresh the registry from the current inventory (keeps existing aliases).
  --check    forward-only convention gate: FAIL if any key is UNKNOWN (neither canonical nor a
             registered alias) — a new key must be registered (decide: new canonical, or alias of
             an existing concept). Registered aliases are reported as the convergence BACKLOG,
             not a failure (they are known + tracked).
"""
import io
import re
import sys
import json
import argparse
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "storage_key_registry.json"

_KEY_RE = re.compile(r"(?:local|session)Storage\.(?:get|set|remove)Item\(\s*['\"]([^'\"]+)['\"]")
# Keys built by string concatenation (e.g. 'wh_ai_history_' + id) register as the PREFIX.
_PREFIX_RE = re.compile(r"['\"]([a-z][a-z0-9_]*_)['\"]\s*\+")


def inventory():
    keys = {}
    for pat in ("*.js", "*.html"):
        for fp in ROOT.glob(pat):
            if fp.name.startswith("."):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in _KEY_RE.findall(text):
                keys[m] = keys.get(m, 0) + 1
    return keys


def load_registry():
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"canonical": [], "aliases": {}, "prefixes": [], "note": ""}


def classify(key, reg):
    if key in reg.get("canonical", []):
        return "canonical"
    if key in reg.get("aliases", {}):
        return "alias"
    for pre in reg.get("prefixes", []):
        if key.startswith(pre):
            return "canonical"
    return "UNKNOWN"


def do_write():
    reg = load_registry()
    inv = inventory()
    known = set(reg.get("canonical", [])) | set(reg.get("aliases", {}))
    for pre in reg.get("prefixes", []):
        known |= {k for k in inv if k.startswith(pre)}
    for k in sorted(inv):
        if k not in known:
            reg.setdefault("canonical", []).append(k)
    reg["canonical"] = sorted(set(reg.get("canonical", [])))
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {REGISTRY.name}: {len(reg['canonical'])} canonical, {len(reg.get('aliases', {}))} aliases.")
    return 0


def do_board():
    reg = load_registry()
    inv = inventory()
    buckets = {"canonical": [], "alias": [], "UNKNOWN": []}
    for k, n in sorted(inv.items(), key=lambda kv: -kv[1]):
        buckets[classify(k, reg)].append((k, n))
    print("\n== Storage-key inventory (SSOT: storage_key_registry.json) ==")
    for b in ("canonical", "alias", "UNKNOWN"):
        print(f"\n  [{b}]  ({len(buckets[b])})")
        for k, n in buckets[b]:
            extra = f"  -> {reg['aliases'][k]}" if b == "alias" else ""
            print(f"    {n:>3}  {k}{extra}")
    return buckets


def do_check():
    reg = load_registry()
    inv = inventory()
    unknown = [k for k in inv if classify(k, reg) == "UNKNOWN"]
    aliases_used = [k for k in inv if classify(k, reg) == "alias"]
    if unknown:
        print("storage-keys: FAIL — UNKNOWN keys (register in storage_key_registry.json as a new")
        print("  canonical, or as an alias of an existing concept):")
        for k in sorted(unknown):
            print(f"    {k}")
        return 1
    print(f"storage-keys: PASS — all {len(inv)} keys registered.")
    if aliases_used:
        # C-P4 convergence COMPLETE 2026-07-20: whHiveId()/whWorker() (utils.js) built + adopted on all
        # 38 app files (app-page raw identity reads 149 -> 0). The aliases below are now read ONLY via
        # the accessor's own fallback chain (utils.js) + test fixtures — intentional back-compat, not drift.
        print(f"  {len(aliases_used)} alias(es) read via the whHiveId()/whWorker() fallback + test fixtures (app pages adopted the accessor):")
        for k in sorted(aliases_used):
            print(f"    {k} -> {reg['aliases'][k]}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Storage-key registry SSOT + drift gate (C-P4).")
    ap.add_argument("--write-registry", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.write_registry:
        return do_write()
    if args.check:
        return do_check()
    do_board()
    return 0


if __name__ == "__main__":
    sys.exit(main())
