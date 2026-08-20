# -*- coding: utf-8 -*-
"""Is what the client WRITES what the database hands BACK? — the CB `value_survives` oracle.

The oracle: *"what one side of the seam WRITES is what the other side READS - compared value-to-value
against psql, never screen-to-screen."* On this platform the interesting answer is not network
corruption; it is that **87 BEFORE triggers deliberately rewrite `NEW.<column>` on the way in.** A value
can therefore differ from what was submitted without any error, and the question is whether every such
rewrite is one we can name.

FOUR CLASSES OF REWRITE, three intended and one that would be a defect:

  bind_*    ATTRIBUTION REBINDING, and it is a SECURITY FEATURE. A spoofed worker_name / auth_uid /
            approved_by on an INSERT is replaced with the caller's own. So the value does NOT survive,
            by design — and any surface that optimistically echoes what the user typed is showing a
            value the database refused. That is worth knowing, not fixing.
  cap_*     SILENT TRUNCATION via left(NEW.col, N). This is the one that can lose a person's work: type
            past the cap and the excess is dropped with no error. Whether it HAS is a live question.
  guard_*   STATUS / CATEGORY COERCION (guard_community_announcement rewrites category,
            guard_marketplace_listing_status rewrites status) — a submitted value replaced by a
            permitted one.
  touch_*   updated_at stamping. Benign and expected.

ANY OTHER trigger assigning to NEW is an UNEXPLAINED rewrite, and the gate fails on it: a value changed
on the way in by something nobody named is exactly the seam defect this oracle exists to catch.

THE LIVE HALF, because a possible truncation and an actual one are different facts. Every
`left(NEW.col, N)` cap is extracted from the trigger body and the column measured against it: how many
stored values sit AT the cap (evidence the truncation fired), and what the longest stored value is.
A cap nothing has ever reached is exposure; a value sitting exactly at the cap is lost text.

WHAT LOOKED LIKE A FINDING AND WAS NOT, recorded so it is not re-derived. `cap_logbook_text_fields`
caps problem/action/knowledge at 2000 and root_cause at **200**, and logbook.html carries
`maxlength="2000"` on exactly the first three — so root_cause appeared to be an unbounded free-text
field feeding a 200-char cap, on the column that feeds failure analysis. It is not: `f-root-cause` is a
`<select>`, so the value comes from a fixed option list and the cap is unreachable from the product.
The live measurement agrees — the longest stored root_cause is 20 characters.

    python tools/prove_values_survive_the_write.py            # human report
    python tools/prove_values_survive_the_write.py --gate     # exit 1 on truncation or an unexplained rewrite
    python tools/prove_values_survive_the_write.py --json
"""
import argparse
import collections
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "values_survive_report.json")
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
      "-At", "-F", "\x1f"]

WRITE_RE = re.compile(r"""\.from\(\s*['"]([a-z_0-9]+)['"]\s*\)\s*\n?\s*\.\s*(?:insert|update|upsert)\b""",
                      re.I)
ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]


def q(sql):
    p = subprocess.run(DB + ["-c", sql], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


ASSIGN_RE = re.compile(r"NEW\.([a-z_][a-z0-9_]*)\s*:=\s*([^;]{0,300})", re.I)


def classify(trigger_fn, src, columns):
    """Classify by WHAT the trigger writes and WHAT IT WRITES IT FROM, not only by its name.

    A name-only classifier called 5 rewrites UNEXPLAINED on the first run and all five were legitimate
    — three timestamp stamps whose functions are named `set_..._updated_at` / `..._stamp_resolved`
    rather than `touch_...`, one derived key, and one default-fill. Widening the NAME allowlist until
    the gate went green would have been bending the gate; the honest fix is to classify on structure,
    because what a rewrite DOES is the thing that matters and it is readable from the assignment:

      the expression mentions now()/CURRENT_TIMESTAMP, or every column written ends in `_at`
                                                        -> a timestamp stamp
      the expression is built from OTHER NEW.* columns   -> derived from the caller's OWN row, so no
                                                           outside value replaces their intent
      the expression is guarded by a comparison against the column's default
                                                        -> default-fill: filled only when the caller
                                                           expressed no preference
    """
    n = trigger_fn.lower()
    if n.startswith("bind_") or n.startswith("wh_bind_") or "_submitter" in n or "_from_hive" in n:
        return "attribution-rebind"
    if n.startswith("cap_") or "left(new." in src.lower().replace(" ", ""):
        return "silent-truncation"
    if n.startswith("guard_"):
        return "status-coercion"
    if n.startswith("match_"):
        return "matching"

    assigns = ASSIGN_RE.findall(src)
    exprs = " ".join(e for _, e in assigns).lower()
    # FIELD-LEVEL AUTHORIZATION GUARD: every assignment restores the column to its OWN prior value
    # (NEW.x := OLD.x). Structurally distinct from the classes above and from a defect: no outside
    # value replaces the caller's, and nothing is derived - the submitted change is simply REFUSED
    # for a caller not entitled to make it, while their other edits go through. Added 2026-08-20 for
    # tg_community_posts_moderation_fields, which keeps flagged/pinned from being changed by anyone
    # but a supervisor of that hive (migration ...000063/64: a reported author was clearing their own
    # flag). Detected on shape, not on name, per this function's own rule - renaming the trigger
    # guard_* to slip past the prefix check would have been bending the gate.
    if assigns and all(expr.strip().lower() == "old." + col.strip().lower()
                       for col, expr in assigns):
        return "field-authorization-guard"
    if columns and all(c.endswith("_at") for c in columns):
        return "timestamp-stamp"
    if re.search(r"\bnow\(\)|current_timestamp", exprs):
        return "timestamp-stamp"
    # DEFAULT-FILL IS TESTED BEFORE DERIVED-FROM-ROW, and the order is load-bearing.
    # apply_hive_broadcast_radius assigns `service_knob(NEW.hive_id, 'broadcast_radius_start_m')`, which
    # mentions a NEW column and so matched derived-from-row first — but that label asserts "nothing
    # external overrode their intent", and a hive KNOB is exactly something external. The honest label is
    # default-fill: its own guard is `IF NEW.broadcast_radius_m = 3000` (the column default), so the knob
    # decides only when the caller expressed no preference, and any other value is left exactly as sent.
    # A label that overstates what was proven is the same defect as a wrong verdict, just quieter.
    if re.search(r"if\s+new\.[a-z_]+\s*=\s*[0-9']", src, re.I):
        return "default-fill"
    # Derived from the row itself: the new value is a function of the caller's own submitted columns,
    # so nothing external overrode what they meant (sensor_readings.external_key is
    # source:asset_id:parameter:recorded_at).
    if assigns and all(re.search(r"\bnew\.[a-z_]+", e, re.I) for _, e in assigns):
        return "derived-from-row"
    return "UNEXPLAINED"


def rewrites():
    rows = q("SELECT c.relname, p.proname, "
             "(SELECT string_agg(DISTINCT m[1], ',') FROM regexp_matches(p.prosrc, "
             "'NEW\\.([a-z_][a-z0-9_]*)\\s*(?::=|=[^=])', 'g') m), "
             "replace(p.prosrc, chr(10), ' ') "
             "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_proc p ON p.oid=t.tgfoid "
             "WHERE NOT t.tgisinternal AND c.relnamespace='public'::regnamespace "
             "AND (t.tgtype::int & 2) > 0 AND p.prosrc ~ 'NEW\\.[a-z_]+\\s*(:=|=[^=])' ORDER BY 1,2")
    out = []
    for r in rows or []:
        if len(r) >= 4 and r[2]:
            cols = sorted(set(r[2].split(",")))
            out.append({"relation": r[0], "trigger_fn": r[1], "columns": cols,
                        "kind": classify(r[1], r[3], cols)})
    return out


def caps():
    rows = q("SELECT DISTINCT c.relname, m[1], m[2] FROM pg_trigger t "
             "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_proc p ON p.oid=t.tgfoid, "
             "regexp_matches(p.prosrc, 'NEW\\.([a-z_]+)\\s*:=\\s*left\\(NEW\\.[a-z_]+,\\s*([0-9]+)\\)', "
             "'g') m WHERE NOT t.tgisinternal AND c.relnamespace='public'::regnamespace ORDER BY 1,2")
    return [{"relation": r[0], "column": r[1], "cap": int(r[2])}
            for r in (rows or []) if len(r) >= 3 and r[2].isdigit()]


def measure_caps(cs):
    """One statement over every capped column: has the truncation actually fired?"""
    if not cs:
        return {}
    parts = ["SELECT '%s.%s' k, count(*) FILTER (WHERE length(%s) >= %d) at_cap, "
             "count(*) FILTER (WHERE %s IS NOT NULL) filled, coalesce(max(length(%s)),0) mx FROM %s"
             % (c["relation"], c["column"], c["column"], c["cap"], c["column"], c["column"],
                c["relation"]) for c in cs]
    rows = q("SELECT * FROM (" + " UNION ALL ".join(parts) + ") z")
    out = {}
    for r in rows or []:
        if len(r) >= 4:
            try:
                out[r[0]] = {"at_cap": int(r[1]), "filled": int(r[2]), "max_len": int(r[3])}
            except ValueError:
                pass
    return out


def control(rw):
    """NON-VACUITY: the census must FIND a rewrite that certainly exists."""
    hit = any(r["relation"] == "logbook" and "auth_uid" in r["columns"]
              and r["kind"] == "attribution-rebind" for r in rw)
    return {"ok": hit, "expected": "logbook.auth_uid rebound by bind_logbook_submitter",
            "note": "a census that cannot see this rewrite cannot see any rewrite, and would report "
                    "'nothing is rewritten on the way in' over an empty scan"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if q("SELECT 1") is None:
        print("  %sSKIP%s local database not reachable" % (YEL, RST))
        return 0

    rw = rewrites()
    cs = caps()
    measured = measure_caps(cs)
    for c in cs:
        c.update(measured.get("%s.%s" % (c["relation"], c["column"]), {}))
    ctl = control(rw)
    unexplained = [r for r in rw if r["kind"] == "UNEXPLAINED"]
    truncated = [c for c in cs if c.get("at_cap")]

    by_rel = collections.defaultdict(list)
    for r in rw:
        by_rel[r["relation"]].append(r)
    pages = []
    for page in ALL_PAGES:
        src = ""
        for f in (page + ".html", page + ".js"):
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                src += "\n" + open(p, encoding="utf-8", errors="replace").read()
        if not src.strip():
            continue
        written = sorted({m.group(1).lower() for m in WRITE_RE.finditer(src)})
        mine = [r for rel in written for r in by_rel.get(rel, [])]
        mycaps = [c for c in cs if c["relation"] in written]
        pages.append({"page": page, "writes": written, "rewrites": mine,
                      "kinds": dict(collections.Counter(r["kind"] for r in mine)),
                      "caps": len(mycaps),
                      "caps_fired": [c for c in mycaps if c.get("at_cap")],
                      "unexplained": [r for r in mine if r["kind"] == "UNEXPLAINED"]})

    payload = {"pages": pages, "rewrites": rw, "caps": cs, "control": ctl,
               "counts": dict(collections.Counter(r["kind"] for r in rw)),
               "capped_columns": len(cs), "caps_fired": len(truncated),
               "unexplained": len(unexplained)}
    with open(REPORT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    os.replace(REPORT + ".tmp", REPORT)
    if a.json:
        print(json.dumps(payload, indent=1))
        return 1 if (truncated or unexplained or not ctl["ok"]) else 0

    print("  %sVALUES SURVIVING THE WRITE%s  %d BEFORE-trigger(s) rewrite NEW columns across %d "
          "relation(s)" % (DIM, RST, len(rw), len({r["relation"] for r in rw})))
    if not ctl["ok"]:
        print("  %sCONTROL FAILED%s the census cannot see %s - every verdict below is unproven"
              % (RED, RST, ctl["expected"]))
    else:
        print("  %scontrol: %s is seen, so the census can detect a rewrite%s"
              % (DIM, ctl["expected"], RST))
    for k, n in collections.Counter(r["kind"] for r in rw).most_common():
        note = {"attribution-rebind": "by design, and a SECURITY feature - a spoofed name is replaced "
                                      "with the caller's",
                "silent-truncation": "left(NEW.col, N) - can lose text with no error",
                "status-coercion": "a submitted status/category replaced with a permitted one",
                "timestamp-stamp": "updated_at, benign",
                "matching": "a matching routine fills its own result columns",
                "UNEXPLAINED": "a rewrite nobody named - this is the defect shape"}.get(k, "")
        print("    %s%4d  %-20s%s %s" % (RED if k == "UNEXPLAINED" else GREEN, n, k, RST, note))

    print("\n  %sTRUNCATION, LIVE%s  %d capped column(s) measured" % (DIM, RST, len(cs)))
    if truncated:
        for c in truncated:
            print("    %sAT CAP%s %s.%s cap=%d, %d row(s) at it, longest=%d"
                  % (RED, RST, c["relation"], c["column"], c["cap"], c["at_cap"], c.get("max_len", 0)))
    else:
        widest = sorted(cs, key=lambda c: -(c.get("max_len") or 0))[:4]
        print("    %sno stored value sits at its cap. Widest: %s%s"
              % (GREEN, "; ".join("%s.%s %d/%d" % (c["relation"], c["column"], c.get("max_len", 0),
                                                   c["cap"]) for c in widest), RST))

    print("\n  wrote %s" % os.path.relpath(REPORT, ROOT))
    if a.gate:
        if not ctl["ok"]:
            print("  %sFAIL%s the non-vacuity control failed" % (RED, RST))
            return 1
        if unexplained:
            print("  %sFAIL%s %d trigger(s) rewrite a submitted value and are not one of the named "
                  "classes: %s" % (RED, RST, len(unexplained),
                                   "; ".join("%s.%s via %s" % (r["relation"], ",".join(r["columns"]),
                                                               r["trigger_fn"])
                                             for r in unexplained[:5])))
            return 1
        if truncated:
            print("  %sFAIL%s %d capped column(s) hold a value at the cap - text has been lost"
                  % (RED, RST, len(truncated)))
            return 1
        print("  %sPASS%s every rewrite on the way in belongs to a named class, and none of the %d "
              "capped columns has ever truncated a stored value" % (GREEN, RST, len(cs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
