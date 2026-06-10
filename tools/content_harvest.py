#!/usr/bin/env python3
"""
content_harvest.py — Content Grounding Gate, Layer G3 (the self-improving loop).
================================================================================
Closes the loop the same shape as companion_harvest.py: drift detected by the G0
gate becomes a regeneration CANDIDATE, a human disposes each one, and `regenerate`
drives catalog-grounded generators to PROPOSE the fix — written to a staging dir,
NEVER applied to a live file. Forward-only, human-on-judgment.

Anti-drift contract (mirrors companion_harvest.py):
  * A candidate is a PROPOSAL. The human disposes each (accept / reject). The
    tool never edits a live surface itself.
  * `regenerate` writes corrected artifacts to .tmp/content_regen/ ONLY. The
    human reviews + applies. Nothing auto-publishes.
  * Re-harvesting MERGES: existing dispositions are preserved, only genuinely-new
    drift is added as `pending`.

The generators are catalog-grounded — every proposal is derived from
platform_catalog.json, so the regenerated content cannot itself drift from the
platform. The two failure modes the gate must catch (content born wrong /
content rotted later) both heal here: the loop re-derives from the catalog.

Subcommands:
  python tools/content_harvest.py harvest           # current drift -> candidates (merge)
  python tools/content_harvest.py report            # the triage queue
  python tools/content_harvest.py dispose --id ID --accept|--reject
  python tools/content_harvest.py regenerate [--all|--check NAME]   # proposals -> .tmp/content_regen/
  python tools/content_harvest.py --self-test       # prove the contract (no live mutation)
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

import platform_catalog as pc            # noqa: E402
import content_grounding_gate as cg      # noqa: E402

CANDIDATES_PATH = ROOT / "content_harvest_candidates.json"
REGEN_DIR = ROOT / ".tmp" / "content_regen"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

DISPOSITIONS = ("pending", "accepted", "rejected")

# Per drift check: a human-readable action + which generator regenerate uses.
# "deterministic" generators emit a catalog-grounded artifact; "manual" ones emit
# a TODO note (the fix needs human authoring, but we hand them the specifics).
CHECK_PLANS = {
    "feature_drift":      ("Reword/remove content that names a renamed/removed/deprecated feature", "manual"),
    "count_drift":        ("Update the homepage count claim to the live article count", "index_count"),
    "link_drift":         ("Fix or remove the dead internal link", "manual"),
    "learn_hub_unlisted": ("Add the unlisted article(s) to the learn hub from the catalog", "learn_hub"),
    "sitemap_drift":      ("Add the missing article(s) to sitemap.xml", "sitemap"),
    "schema_featurelist": ("Align JSON-LD featureList to the catalog", "jsonld_featurelist"),
    "undated_articles":   ("Add a dateModified to the article(s)", "manual"),
    "capability_drift":   ("Reword/remove the WorkHive capability claim the page does not support", "manual"),
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _load(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cand_id(check: str, payload: str) -> str:
    return "CG-" + hashlib.sha1(f"{check}:{payload}".encode("utf-8")).hexdigest()[:10]


# ── harvest ───────────────────────────────────────────────────────────────────

def harvest() -> dict:
    checks = cg.run_checks()
    existing = _load(CANDIDATES_PATH) or {"candidates": []}
    by_id = {c["id"]: c for c in existing.get("candidates", [])}

    added = 0
    for check, data in checks.items():
        action, generator = CHECK_PLANS.get(check, (f"Resolve {check}", "manual"))
        for iss in data["issues"]:
            payload = iss.get("slug") or iss.get("href") or iss.get("claim") or iss.get("entry") or iss.get("reason", "")
            cid = _cand_id(check, str(payload))
            if cid in by_id:
                continue  # preserve any existing human disposition
            by_id[cid] = {
                "id":         cid,
                "check":      check,
                "payload":    payload,
                "reason":     iss.get("reason", ""),
                "action":     action,
                "generator":  generator,
                "status":     "pending",
                "harvested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            added += 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidates":   sorted(by_id.values(), key=lambda c: (c["check"], c["id"])),
    }
    CANDIDATES_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Harvested drift -> {len(out['candidates'])} candidate(s) ({added} new). "
          f"Triage with `report`, then `dispose`.")
    return out


# ── report / dispose ──────────────────────────────────────────────────────────

def report() -> int:
    data = _load(CANDIDATES_PATH)
    if not data or not data.get("candidates"):
        print("No candidates. Run `harvest` first (or there is no drift to harvest).")
        return 0
    cands = data["candidates"]
    by_status = {s: [c for c in cands if c["status"] == s] for s in DISPOSITIONS}
    print(f"\nContent regeneration queue — {len(cands)} candidate(s)")
    print("=" * 64)
    for s in DISPOSITIONS:
        if by_status[s]:
            print(f"\n  {s.upper()} ({len(by_status[s])}):")
            for c in by_status[s][:30]:
                print(f"    {c['id']}  [{c['check']}]  {c['action']}")
                print(f"        ↳ {c['reason'][:96]}")
    print(f"\n  Accept: python tools/content_harvest.py dispose --id <ID> --accept")
    print(f"  Then:   python tools/content_harvest.py regenerate --all\n")
    return 0


def dispose(cid: str, accept: bool) -> int:
    data = _load(CANDIDATES_PATH)
    if not data:
        print("No candidate file. Run `harvest` first.")
        return 1
    hit = next((c for c in data["candidates"] if c["id"] == cid), None)
    if not hit:
        print(f"No candidate {cid!r}.")
        return 1
    hit["status"] = "accepted" if accept else "rejected"
    hit["disposed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    CANDIDATES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{cid} -> {hit['status']}")
    return 0


# ── regenerate (catalog-grounded; writes to staging ONLY) ─────────────────────

def _gen_index_count(cat: dict, cands: list) -> list[str]:
    live = len(cat["articles"])
    claims = cat["public_surface"]["index"].get("count_claims", {})
    notes = [f"# index.html count-claim fix (catalog-derived)",
             f"# live article count = {live}", ""]
    for noun in ("guide", "article"):
        for val in sorted(set(claims.get(noun, []))):
            if val != live:
                notes.append(f"REPLACE  '{val} {noun}s'  ->  '{live} {noun}s'   (every occurrence in index.html)")
    path = REGEN_DIR / "index_count_fix.txt"
    path.write_text("\n".join(notes) + "\n", encoding="utf-8")
    return [str(path)]


def _gen_learn_hub(cat: dict, cands: list) -> list[str]:
    slugs = [c["payload"] for c in cands if c["check"] == "learn_hub_unlisted"]
    by_slug = {a["slug"]: a for a in cat["articles"]}
    e = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rows = ["<!-- Catalog-derived learn-hub cards for articles missing from the hub.",
            "     Review + paste into learn/index.html's article grid, matching the existing card markup. -->"]
    for slug in slugs:
        a = by_slug.get(slug, {"slug": slug, "title": slug, "url": f"/learn/{slug}/"})
        rows.append(f'<a class="learn-card" href="{e(a["url"])}">{e(a.get("title") or slug)}</a>')
    path = REGEN_DIR / "learn_hub_additions.html"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return [str(path)]


def _gen_sitemap(cat: dict, cands: list) -> list[str]:
    slugs = [c["payload"] for c in cands if c["check"] == "sitemap_drift"]
    rows = ["<!-- Catalog-derived sitemap entries for articles missing from sitemap.xml -->"]
    for slug in slugs:
        rows.append(f"  <url>\n    <loc>https://workhiveph.com/learn/{slug}/</loc>\n"
                    f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    path = REGEN_DIR / "sitemap_additions.xml"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return [str(path)]


def _gen_jsonld_featurelist(cat: dict, cands: list) -> list[str]:
    # Regenerate a correct featureList from the catalog (subset by construction).
    names = [f["name"] for f in cat["features"]
             if f["status"] == "active" and f["route"] and not f["nav_hidden"]]
    payload = {"featureList": sorted(set(names))}
    path = REGEN_DIR / "jsonld_featurelist.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return [str(path)]


def _gen_manual(cat: dict, cands: list) -> list[str]:
    lines = ["# Manual regeneration TODOs (need human authoring — specifics provided)"]
    for c in cands:
        lines.append(f"- [{c['check']}] {c['action']}: {c['reason']}")
    path = REGEN_DIR / "manual_todos.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(path)]


_GENERATORS = {
    "index_count":        _gen_index_count,
    "learn_hub":          _gen_learn_hub,
    "sitemap":            _gen_sitemap,
    "jsonld_featurelist": _gen_jsonld_featurelist,
    "manual":             _gen_manual,
}


def regenerate(only_check: str | None, do_all: bool) -> int:
    data = _load(CANDIDATES_PATH)
    if not data or not data.get("candidates"):
        print("No candidates. Run `harvest` first.")
        return 0
    cands = data["candidates"]
    # Eligible = accepted; or, with --all, every pending+accepted (still staging-only).
    eligible = [c for c in cands if c["status"] == "accepted"
                or (do_all and c["status"] != "rejected")]
    if only_check:
        eligible = [c for c in eligible if c["check"] == only_check]
    if not eligible:
        print("Nothing to regenerate (accept candidates first, or pass --all).")
        return 0

    REGEN_DIR.mkdir(parents=True, exist_ok=True)
    cat = pc.build_catalog()
    written: list[str] = []
    by_gen: dict[str, list] = {}
    for c in eligible:
        by_gen.setdefault(c["generator"], []).append(c)
    for gen, group in by_gen.items():
        fn = _GENERATORS.get(gen, _gen_manual)
        written += fn(cat, group)

    print(f"\nRegenerated {len(written)} catalog-grounded proposal(s) into {REGEN_DIR.relative_to(ROOT)}/ "
          f"(staging only — nothing applied to live):")
    for p in written:
        print(f"  → {Path(p).name}")
    print("\nReview each, then apply by hand. Re-run the gate after applying to ratchet the baseline down.\n")
    return 0


# ── self-test (no live mutation) ──────────────────────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  {GREEN}PASS{RESET}  {label}")
    def bad(label): print(f"  {RED}FAIL{RESET}  {label}")
    print(f"\n{BOLD}content_harvest.py --self-test{RESET}")
    print("=" * 55)
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    # Snapshot live surfaces to prove regenerate never mutates them.
    live_hub = (pc.LEARN_DIR / "index.html")
    before = live_hub.read_text(encoding="utf-8") if live_hub.exists() else None

    out = harvest()
    cands = out["candidates"]
    check(len(cands) >= 1, f"harvest produced candidates from real drift ({len(cands)})")
    check(all(c["status"] in DISPOSITIONS for c in cands), "every candidate has a valid disposition")
    check(any(c["check"] == "learn_hub_unlisted" for c in cands),
          "learn_hub_unlisted drift became a candidate")

    # Merge preserves a human disposition across a re-harvest.
    target = next(c for c in cands if c["check"] == "learn_hub_unlisted")
    dispose(target["id"], accept=True)
    harvest()  # re-harvest
    again = next(c for c in (_load(CANDIDATES_PATH)["candidates"]) if c["id"] == target["id"])
    check(again["status"] == "accepted", "re-harvest MERGES — human disposition preserved, not clobbered")

    # Regenerate writes catalog-grounded proposals to staging, mutates NOTHING live.
    regenerate(only_check=None, do_all=True)
    hub_add = REGEN_DIR / "learn_hub_additions.html"
    check(hub_add.exists() and hub_add.read_text(encoding="utf-8").count("href=") >= 1,
          "regenerate emitted catalog-grounded learn-hub additions to staging")
    after = live_hub.read_text(encoding="utf-8") if live_hub.exists() else None
    check(before == after, "FORWARD-ONLY: live learn hub was NOT mutated by regenerate")

    # The regenerated featureList is a subset of the catalog (cannot itself drift).
    regenerate(only_check=None, do_all=True)
    fl = _load(REGEN_DIR / "jsonld_featurelist.json")
    if fl:
        feats = pc.build_catalog()["features"]
        unresolved = [n for n in fl["featureList"] if pc._resolve_label_to_feature(n, feats) is None]
        check(not unresolved, "regenerated JSON-LD featureList ⊆ catalog (grounded by construction)")

    print("=" * 55)
    if fails == 0:
        print(f"{GREEN}{BOLD}  self-test PASS{RESET}\n")
    else:
        print(f"{RED}{BOLD}  self-test FAIL — {fails} check(s){RESET}\n")
    return 1 if fails else 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Content Grounding Gate — self-improving loop (G3).")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("harvest")
    sub.add_parser("report")
    pd = sub.add_parser("dispose"); pd.add_argument("--id", required=True)
    g = pd.add_mutually_exclusive_group(required=True)
    g.add_argument("--accept", action="store_true"); g.add_argument("--reject", action="store_true")
    pr = sub.add_parser("regenerate")
    pr.add_argument("--all", action="store_true"); pr.add_argument("--check", default=None)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.cmd == "harvest":
        harvest(); return 0
    if args.cmd == "report":
        return report()
    if args.cmd == "dispose":
        return dispose(args.id, accept=args.accept)
    if args.cmd == "regenerate":
        return regenerate(only_check=args.check, do_all=args.all)
    return report()


if __name__ == "__main__":
    sys.exit(main())
