#!/usr/bin/env python3
"""validate_breakdown_cause_listed.py - BRH.10 AI (2026-10-26): every breakdown cause is one the analytics can group.

The logbook form offers 12 causes. The voice entry, the CSV import and the CMMS sync stored the cause as said, and
every reader grouped by the exact text: a reworded cause hid a real repeat failure, one cause said three ways raised a
false multi-symptom alert, and "Unknown" twice read as an ineffective repair.

THE FIX: root_cause always holds one of the 12; the words it was given are kept beside it in root_cause_note
(trg_logbook_listed_cause, migration 20261026000002). The voice entry asks the model for a listed cause plus the words;
the page keeps the words through new entry, edit, draft and every fill path; repeat-failure and multi-symptom leave an
unrecorded cause out.

STATIC  (a revert of any one reddens this gate without a database)
  - the migration defines the trigger and wh_listed_root_cause
  - the form's select, the database function and the voice prompt name the SAME 12 causes
  - voice-logbook-entry returns root_cause_note
  - logbook.html carries root_cause_note in the new entry, the insert payload and the edit update, and fills the
    select through lbFillCause (a select set to text it has no option for goes blank while "filled" is claimed)
  - failure-signature-scan and descriptive.py leave "Unknown" out of a repeat
LIVE    (the local database; a stopped stack prints SKIP for this half only)
  - the trigger is installed, and no stored root_cause sits outside the 12

    python tools/validate_breakdown_cause_listed.py
    python tools/validate_breakdown_cause_listed.py --self-test
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "migration": "supabase/migrations/20261026000002_a_breakdown_cause_from_the_list.sql",
    "voice": "supabase/functions/voice-logbook-entry/index.ts",
    "page": "logbook.html",
    "scan": "supabase/functions/failure-signature-scan/index.ts",
    "descriptive": "python-api/analytics/descriptive.py",
    "repeat_rpc": "supabase/migrations/20261026000003_repeat_failures_leave_unknown_out.sql",
    "integrations": "integrations.html",
}

STATIC = {
    "the migration installs the trigger": ("migration", r"CREATE TRIGGER trg_logbook_listed_cause\s+BEFORE INSERT OR UPDATE OF root_cause ON public\.logbook"),
    "the migration maps other words onto the list": ("migration", r"CREATE OR REPLACE FUNCTION public\.wh_listed_root_cause\("),
    "the voice entry returns the words beside the cause": ("voice", r"root_cause_note:\s*parsed\.root_cause_note"),
    "a new entry carries the words": ("page", r"root_cause_note:\s*\(document\.getElementById\('f-root-cause-note'\)"),
    "the insert payload carries the words": ("page", r"root_cause_note:\s*entry\.root_cause_note"),
    "the voice fill goes through lbFillCause": ("page", r"lbFillCause\(e\.root_cause,\s*e\.root_cause_note\)"),
    "repeat-failure leaves an unrecorded cause out": ("scan", r"k === \"unknown\" \? \"\" : k"),
    "the Python repeat analysis leaves Unknown out": ("descriptive", r"str\.lower\(\) != \"unknown\""),
    # the analytics page reads get_repeat_failures (the precompute); the Python function is only its fallback
    "get_repeat_failures leaves Unknown out": ("repeat_rpc", r"lower\(btrim\(root_cause\)\) <> 'unknown'"),
    # 2026-10-27: no built-in CMMS mapping names a cause column and the connector form never wrote field_map, so every
    # work order a page-made connector synced arrived with no cause. The form now names it (walked: 25/25 causes synced).
    "a connector can name its cause column": ("integrations", r"fieldMap\.root_cause = causeCol"),
}
NO_RAW_FILL = re.compile(r"getElementById\('f-root-cause'\);\s*if \(el\) \{ el\.value = e\.root_cause")


def listed_from_form(page: str) -> set[str]:
    m = re.search(r'<select id="f-root-cause"[\s\S]*?</select>', page)
    return set(re.findall(r'value="([^"]+)"', m.group(0))) if m else set()


def listed_from_sql(mig: str) -> set[str]:
    m = re.search(r"listed\(cause\) AS \(VALUES([\s\S]*?)\)\s*\n", mig)
    return set(re.findall(r"\('([^']+)'\)", m.group(1))) if m else set()


def listed_from_prompt(voice: str) -> set[str]:
    m = re.search(r'"root_cause":\s*<[^>]*?EXACTLY one of:([^>]*?)—', voice)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


def static_findings(src: dict[str, str]) -> list[str]:
    out = [name for name, (f, rx) in STATIC.items() if not re.search(rx, src.get(f, ""))]
    if NO_RAW_FILL.search(src.get("page", "")):
        out.append("a fill path still sets the select to raw text")
    form, sql, prompt = listed_from_form(src.get("page", "")), listed_from_sql(src.get("migration", "")), listed_from_prompt(src.get("voice", ""))
    if len(form) != 12 or form != sql or form != prompt:
        out.append(f"the 12 causes disagree: form {len(form)}, database {len(sql)}, voice prompt {len(prompt)}"
                   + (f" (form-only {sorted(form - sql - prompt)}, missing from form {sorted((sql | prompt) - form)})" if form else ""))
    return out


def live_findings() -> tuple[list[str], str]:
    def q(sql: str) -> str:
        r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-c", sql],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "").strip()[:200])
        return r.stdout.strip()
    try:
        trig = q("select count(*) from pg_trigger where tgname = 'trg_logbook_listed_cause' and tgrelid = 'public.logbook'::regclass")
        off = q("select count(*) from public.logbook where coalesce(btrim(root_cause), '') <> '' "
                "and root_cause is distinct from public.wh_listed_root_cause(root_cause)")
        rpc = q("select (pg_get_functiondef('public.get_repeat_failures(uuid,text,integer)'::regprocedure) "
                "ilike '%<> ''unknown''%')::int")
    except Exception as e:  # noqa: BLE001
        return [], f"SKIP live half: the local database could not be read ({e})"
    out = []
    if trig != "1":
        out.append("trg_logbook_listed_cause is not installed on the local logbook (apply 20261026000002)")
    if off != "0":
        out.append(f"{off} stored root_cause value(s) sit outside the 12 causes")
    if rpc != "1":
        out.append("the installed get_repeat_failures still counts Unknown (apply 20261026000003)")
    return out, f"live: trigger installed {trig == '1'}, stored causes off the list {off}, repeat RPC leaves Unknown out {rpc == '1'}"


def self_test() -> int:
    src = {k: (ROOT / p).read_text(encoding="utf-8", errors="replace") for k, p in FILES.items()}
    ok = not static_findings(src)
    reverts = {
        "page": [("lbFillCause(e.root_cause, e.root_cause_note)", "x"),
                 ("root_cause_note: entry.root_cause_note", "x: 1")],
        "scan": [('k === "unknown" ? "" : k', "k")],
        "voice": [("root_cause_note:  parsed.root_cause_note", "x: 1"), ('"Design Issue" | ', "")],
        "migration": [("CREATE TRIGGER trg_logbook_listed_cause", "-- ")],
        "descriptive": [('str.lower() != "unknown"', "str.lower() != 'x'")],
        "repeat_rpc": [("AND lower(btrim(root_cause)) <> 'unknown'", "")],
    }
    for f, pairs in reverts.items():
        for a, b in pairs:
            if a not in src[f]:
                print(f"  FAIL teeth: '{a}' not found in {f}")
                ok = False
                continue
            red = static_findings({**src, f: src[f].replace(a, b)})
            print(f"  {'PASS' if red else 'FAIL'} reverting '{a[:40]}' in {f} reddens: {red[:1]}")
            ok = ok and bool(red)
    raw = src["page"].replace("if (lbFillCause(e.root_cause, e.root_cause_note)) {",
                              "const el = document.getElementById('f-root-cause'); if (el) { el.value = e.root_cause; } if (lbFillCause(e.root_cause, e.root_cause_note)) {")
    ok = ok and "a fill path still sets the select to raw text" in static_findings({**src, "page": raw})
    print(("PASS" if ok else "FAIL") + " breakdown-cause-listed self-test")
    return 0 if ok else 1


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    src = {k: (ROOT / p).read_text(encoding="utf-8", errors="replace") if (ROOT / p).exists() else "" for k, p in FILES.items()}
    st = static_findings(src)
    lv, line = live_findings()
    print("breakdown-cause-listed (§BRH.10 AI): every breakdown cause is one the analytics can group")
    print(f"  static: {len(STATIC) + 2 - len(st)}/{len(STATIC) + 2} facts hold")
    print(f"  {line}")
    for f in st + lv:
        print(f"  - {f}")
    bad = st + lv
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
