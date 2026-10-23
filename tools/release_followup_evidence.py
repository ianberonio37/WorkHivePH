#!/usr/bin/env python3
"""release_followup_evidence.py - what the 2026-10-24 release left open, measured (BRH-AF .. BRH-AL).

Ian, 2026-10-24, on the release report's open items: "can we be proactive on this below, you have to understand these
first, and make a necessary and appropriate number of trajectories to add". The number is derived, never typed (the
BRP rule): each class below is read from the source, the local database or production, and one site is one row.

  AF  a post-deploy check that cannot reach the signed-in product: the smoke's app tier seeds a LOCAL hive, worker and
      role into storage instead of asking the server, and production has no smoke identity to sign in with
  AG  a page never seen signed in on production after a deploy: one site per page in the smoke's app roster
  AH  a critical path never walked on production after a deploy: one site per Tier-0 flow in the deploy runbook
  AI  a breakdown cause the analytics cannot group: writers that store the cause as said, and readers that group
      root_cause by its exact text, against the logbook form's list
  AJ  an adoption census that credits a lookalike class: the census's \\b treats "-" as a word edge, so heat-tile
      counts as .tile and pulse-card as .card - one site per primitive with a lookalike credit
  AK  free credit the solvency check does not hold to its policy, and a cover figure that does not say why it is low
  AL  a release that shipped ahead of its data move: pages that read only a photo's stored path while production's
      rows still hold the picture inline

    python tools/release_followup_evidence.py --prod .tmp/release_followup_prod.json

The production file is read through the claude.ai Supabase connector (SELECT only); no credential leaves it.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "release_followup_evidence.json"
sys.path.insert(0, str(ROOT / "tools"))


def _read(p: str) -> str:
    return (ROOT / p).read_text(encoding="utf-8", errors="replace")


def _line(src: str, pat: str) -> int:
    m = re.search(pat, src, re.M)
    return src.count("\n", 0, m.start()) + 1 if m else 0


def smoke() -> dict:
    src = _read("tools/post_deploy_smoke.mjs")
    roster = re.search(r"const APP_PAGES = \[([\s\S]*?)\];", src)
    pages = re.findall(r"'([a-z0-9-]+)'", roster.group(1)) if roster else []
    seeds = re.findall(r"localStorage\.setItem\('([a-zA-Z_]+)'", src)
    env = (ROOT / ".env").read_text(encoding="utf-8", errors="replace") if (ROOT / ".env").exists() else ""
    rep = {}
    if (ROOT / "post_deploy_smoke_report.json").exists():
        r = json.loads(_read("post_deploy_smoke_report.json"))
        rep = {"base": r.get("base"), "at": r.get("at"), "tier2_pages": len(r.get("tier2") or [])}
    return {
        "app_pages": pages,
        "hive_line": _line(src, r"^const HIVE = \{"),
        "seeded_keys": seeds,
        "has_identity": bool(re.search(r"^WH_SMOKE_EMAIL\s*=\s*\S", env, re.M)),   # presence only, never the value
        "last_report": rep,
    }


def tier0() -> list[dict]:
    rb = _read("PRODUCTION_DEPLOY_RUNBOOK.md")
    m = re.search(r"\*\*Tier 0[^\n]*\n([\s\S]*?)\n\n", rb)
    text = (m.group(0) if m else "").replace("\n", " ")
    flows = re.findall(r"(\d)\)\s*([^;]+?)(?=;\s*\d\)|\.\s*Any fail|$)", text)
    return [{"n": int(n), "flow": re.sub(r"\s+", " ", f).strip()} for n, f in flows]


def root_causes(prod: dict) -> dict:
    lb = _read("logbook.html")
    sel = re.search(r'<select id="f-root-cause"[\s\S]*?</select>', lb)
    vocab = [v for v in re.findall(r'value="([^"]*)"', sel.group(0))] if sel else []
    vocab = [v for v in vocab if v]
    writers, readers = [], []
    for page, f, pat, how in [
        ("logbook.html", "supabase/functions/voice-logbook-entry/index.ts", r'"root_cause":\s*<string', "the voice entry asks the model for the cause as said"),
        ("integrations.html", "integrations.html", r"root_cause:\s*get\(_mapping\.root_cause\)", "a CSV import maps its own cause column straight in"),
        ("integrations.html", "supabase/functions/cmms-sync/index.ts", r"root_cause:\s*get\(fieldMap\.root_cause\)", "a CMMS sync copies the external system's cause text"),
    ]:
        ln = _line(_read(f), pat)
        if ln:
            writers.append({"page": page, "file": f, "line": ln, "how": how})
    for page, f, pat, how in [
        ("analytics.html", "python-api/analytics/descriptive.py", r'groupby\(\["machine", "root_cause"\]\)', "repeat failures group by the exact cause text"),
        ("analytics.html", "python-api/analytics/diagnostic.py", r'groupby\("root_cause"\)|groupby\(\["root_cause"', "the Pareto groups by the exact cause text"),
        ("alert-hub.html", "supabase/functions/failure-signature-scan/index.ts", r"const key = \(r\.root_cause", "repeat_failure keys on the lower-cased text"),
        ("alert-hub.html", "supabase/functions/failure-signature-scan/index.ts", r"const roots\s*=\s*new Set", "multi_symptom counts distinct cause texts"),
    ]:
        ln = _line(_read(f), pat)
        if ln:
            readers.append({"page": page, "file": f, "line": ln, "how": how})
    local = None
    try:
        q = ("select count(*) from logbook where root_cause is not null and btrim(root_cause) <> '' and root_cause <> all(array["
             + ",".join("'" + v.replace("'", "''") + "'" for v in vocab) + "])")
        r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-c", q],
                           capture_output=True, text=True, timeout=60)
        local = int((r.stdout or "").strip() or 0) if r.returncode == 0 else None
    except Exception:
        local = None
    return {"vocabulary": vocab, "writers": writers, "readers": readers, "local_free_text": local,
            "prod": prod.get("root_cause") or {}}


def lookalikes() -> list[dict]:
    from component_adoption_census import REGISTRY, FAMILY, strip_comments
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fam = json.loads(FAMILY.read_text(encoding="utf-8"))
    pages = [p for p in (fam["pages"] if isinstance(fam["pages"], list) else list(fam["pages"])) if (ROOT / p).exists()]
    srcs = {p: strip_comments((ROOT / p).read_text(encoding="utf-8", errors="ignore")) for p in pages}
    out = []
    for comp in reg["components"]:
        for d in comp["detect"]:
            if d.get("kind") != "css-class":
                continue
            cls = d["class"]
            loose = re.compile(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"')
            exact = re.compile(r'class="(?:[^"]*\s)?' + re.escape(cls) + r'(?=[\s"])[^"]*"')
            false = sorted(p for p, s in srcs.items() if loose.search(s) and not exact.search(s))
            if false:
                out.append({"component": comp["id"], "class": cls, "pages": false})
    return out


def credits(prod: dict) -> dict:
    gate = _read("tools/validate_credit_solvency.py")
    ops = _read("operator-actions.js")
    cover = ops[ops.find("Liability cover"):][:600] if "Liability cover" in ops else ""
    return {
        # the gate must ASK the grant records (a query naming them), not mention the policy in a printed line
        "gate_holds_grant_policy": bool(re.search(r"from\s+public\.credit_starter_grants|kyb_verified\s*=", gate)),
        "console_names_backing": "starter" in cover.lower(),
        "prod": prod.get("credits") or {},
    }


def photos(prod: dict) -> list[dict]:
    utils = _read("utils.js")
    cols = re.search(r"var WH_ROW_COLS = \{([\s\S]*?)\};", utils)
    reads_path_only = bool(cols) and "photo_path" in cols.group(1) and not re.search(r"[,']photo[,']", cols.group(1))
    out = []
    for table, page in (("logbook", "logbook.html"), ("inventory_items", "inventory.html")):
        p = (prod.get("inline_photos") or {}).get(table) or {}
        if p.get("inline") and not p.get("stored") and reads_path_only:
            out.append({"table": table, "page": page, "inline": p["inline"], "stored": p.get("stored", 0)})
    return out


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod", help="production reads (JSON, from the Supabase connector)")
    a = ap.parse_args()
    prod = json.loads(Path(a.prod).read_text(encoding="utf-8")) if a.prod else {}
    ev = {"_doc": "release follow-up evidence (BRH-AF..AL), tools/release_followup_evidence.py",
          "prod_read": {k: prod.get(k) for k in ("read_at", "via")},
          "smoke": smoke(), "tier0": tier0(), "root_causes": root_causes(prod), "lookalikes": lookalikes(),
          "credits": credits(prod), "photos": photos(prod)}
    OUT.write_text(json.dumps(ev, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    s = ev["smoke"]
    print(f"AF smoke: hive seeded at line {s['hive_line']} ({', '.join(s['seeded_keys'])}); identity in .env: {s['has_identity']}")
    print(f"AG app pages: {len(s['app_pages'])}; last report's signed-in pages: {s['last_report'].get('tier2_pages')}")
    print(f"AH tier-0 flows: {len(ev['tier0'])}")
    rc = ev["root_causes"]
    print(f"AI causes: {len(rc['vocabulary'])} on the list; {len(rc['writers'])} free-text writers, {len(rc['readers'])} "
          f"exact-text readers; local free text {rc['local_free_text']}, production {rc['prod'].get('free_text')}")
    print(f"AJ lookalike credits: {[(x['class'], len(x['pages'])) for x in ev['lookalikes']]}")
    print(f"AK grant policy in the gate: {ev['credits']['gate_holds_grant_policy']}; console names backing: "
          f"{ev['credits']['console_names_backing']}")
    print(f"AL photos hidden by the move not yet run: {[(x['table'], x['inline']) for x in ev['photos']]}")
    print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
