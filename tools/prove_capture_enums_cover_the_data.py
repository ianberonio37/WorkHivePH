"""
prove_capture_enums_cover_the_data.py — a contract enum is a CLAIM about the data. Check it.
=============================================================================================
`wh-capture-validate.js` validates a capture payload against
`canonical_capture_contracts.contract_schema` BEFORE the write leaves the browser. So an enum in
that table is not documentation: on a surface that calls the validator it is a gate on the save
path, and a value the enum omits cannot be saved at all.

THIS HAS BLOCKED REAL SAVES TWICE, AND BOTH TIMES ON schedule_item_v1:

  2026-06-09  schedule_item_v1.category    declared ["planning","execution","review","admin"] while
                                           the form emitted PM/CM/Inspection/... - "every real user
                                           Schedule Item save with a category hit
                                           [capture-violation] and was blocked" (migration
                                           20260609000004's own header).
  2026-09-16  schedule_item_v1.item_status declared [pending,in_progress,done,blocked,skipped,null]
                                           while 139 of 231 live rows hold `planned`. Latent for
                                           months because dayplanner.html silently rewrote the value;
                                           the moment a fix made the page HONEST and re-sent
                                           `planned` untouched, 60% of the table became unsaveable.

Both were found by a person operating the product and watching a row fail to appear. Nothing
compared the enum to the column, which is a question a database can answer in one query.

THE CHECK. For every contract whose `target_table` is a real table, and every property whose schema
carries an `enum`, assert:

    SELECT DISTINCT <column> FROM <target_table>   is a SUBSET of   the contract's enum

TWO THINGS DECIDE WHAT A MISMATCH MEANS, AND THE FIRST VERSION OF THIS GATE GOT BOTH WRONG.
Run live on 2026-09-16 it found five mismatches and told the same story about all five: "each of
these rows exists and CANNOT be re-saved". Two questions separate a real outage from a note.

  1. IS ANYTHING ENFORCING IT?  `validates_at` is a COLUMN IN THE TABLE, not a mechanism. Three
     contracts declare `edge`, and NO edge function reads canonical_capture_contracts at all (zero
     matches for capture_id / contract_schema under supabase/functions). What actually bites is a
     CALL SITE - `whValidateCapture(db, '<capture_id>', payload)` in a served page. Four exist.

  2. CAN AN EXISTING ROW EVER REACH IT?  A contract governs ONE surface's writes, but this check
     compares the enum against the WHOLE column, including rows other writers put there. That only
     matters if the validated page re-sends values it LOADED. Read at all four call sites:

       schedule_item_v1       LOADED ROWS.  dayplanner.html validates every save, including edits,
                              on toDBRow(item) where item came from fromDBRow(row) - so a value
                              another writer put in the table is handed straight back to the
                              contract. This is the ONLY one of the four, and it is the only one
                              that has ever caused an outage. Twice.
       logbook_add_entry_v1   NEW WRITES ONLY.  addEntry validates a payload built from the form;
                              the two update paths (:2141, :4790) never call the validator.
       inventory_add_part_v1  NEW WRITES ONLY.  validated only in the `else` branch that builds a
                              brand-new item; the edit branch does not call it.
       hive_invite_v1         NEW WRITES ONLY.  validated only when `!existingRow`, on a literal
                              {worker_name, role} payload.

So a mismatch is reported in one of three classes, and only the first fails the gate. Calling the
other two an outage is how a gate pressures someone into widening an enum to go green, which is the
drift these contracts exist to stop.

FAILS CLOSED ON AN UNREACHABLE DATABASE. It reports SKIPPED and exits non-zero rather than PASS,
because "I could not check" must never read as "I checked and it was fine" - the exact confusion this
gate exists to prevent. Use --allow-offline in a context where the stack is legitimately down.

Usage:  python tools/prove_capture_enums_cover_the_data.py
            [--check] [--allow-offline] [--strict] [--self-test]
        --strict also fails on the two reported-but-not-blocking classes (use when wiring a new
        validator call site, or when teaching a page to re-save rows it loaded).
"""
from __future__ import annotations
import glob as _glob
import io
import json
import os
import re
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# `whValidateCapture(db, 'schedule_item_v1', row)` - the id is the only thing that matters, and the
# call is written across two lines on one page, so the pattern must not anchor to the whole call.
_CALL_RE = re.compile(r"whValidateCapture\s*\(\s*[A-Za-z_$][\w$]*\s*,\s*['\"]([a-z0-9_]+)['\"]")

# WHAT THE VALIDATED PAYLOAD IS BUILT FROM. Determined by reading each call site (2026-09-16); there
# is no honest way to infer it, so it is written down with its evidence and the self-test refuses to
# let a new call site go un-annotated. "loaded" means the page hands back values it read from the
# table, so an existing off-enum row reaches the contract; "new" means the payload is built fresh
# from a form or a literal, so it cannot.
PAYLOAD_SOURCE = {
    "schedule_item_v1": ("loaded",
        "dayplanner.html syncItemToSupabase validates EVERY save on toDBRow(item), and item came "
        "from fromDBRow(row) - an existing row's own category/item_status are re-sent verbatim"),
    "logbook_add_entry_v1": ("new",
        "logbook.html addEntry validates a payload built from the form; the two update paths "
        "(:2141, :4790) never call the validator, so a stored row is never re-validated"),
    "inventory_add_part_v1": ("new",
        "inventory.html validates only in the `else` branch that builds a brand-new item "
        "({id: Date.now(), ...payload}); the edit branch does not call it"),
    "hive_invite_v1": ("new",
        "hive.html validates only when !existingRow, on the literal {worker_name, role:'worker'}"),
}


def client_enforced_ids(root=None):
    """The capture_ids a served page actually validates. An id absent here cannot refuse a save.

    Scans the served surfaces (root-level .html/.js), NOT the whole tree: the validator itself and
    the docs that quote it mention ids they do not enforce, and counting those would recreate the
    error this function exists to correct.
    """
    root = root or REPO
    found = set()
    for pat in ("*.html", "*.js"):
        for path in _glob.glob(os.path.join(root, pat)):
            if os.path.basename(path) == "wh-capture-validate.js":
                continue          # the validator's own docstring names an id it does not call
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    found.update(_CALL_RE.findall(fh.read()))
            except OSError:
                continue
    return found


def classify(capture_id, enforced):
    """-> 'blocking' | 'new-writes-only' | 'latent' | 'unannotated'."""
    if capture_id not in enforced:
        return "latent"
    kind = PAYLOAD_SOURCE.get(capture_id, (None, ""))[0]
    if kind == "loaded":
        return "blocking"
    if kind == "new":
        return "new-writes-only"
    return "unannotated"


def _enums_from_schema(schema):
    """-> {column: set(allowed)} for every property that declares an enum."""
    out = {}
    props = (schema or {}).get("properties") or {}
    for col, spec in props.items():
        if isinstance(spec, dict) and isinstance(spec.get("enum"), list):
            out[col] = set(spec["enum"])
    return out


def _sortable(v):
    """NULL is a legitimate member of these enums and of these columns, and `None < 'str'` raises.
    Caught by this file's own self-test on its first run."""
    return (v is None, "" if v is None else str(v))


def compare(allowed, present):
    """The finding, as data: values that exist in the column and are absent from the enum."""
    missing = sorted((v for v in present if v not in allowed), key=_sortable)
    unused = sorted((v for v in allowed if v not in present), key=_sortable)
    return missing, unused


def _counts(cur, table, col, missing):
    """Row counts for the offending values. NULL is counted with IS NULL, never with `= ANY(...)`,
    which matches nothing and silently reported a finding with no blast radius at all."""
    out = []
    non_null = [m for m in missing if m is not None]
    if non_null:
        cur.execute(
            'SELECT "%s"::text, count(*) FROM public."%s" WHERE "%s"::text = ANY(%%s) GROUP BY 1 ORDER BY 2 DESC'
            % (col, table, col), (non_null,))
        out.extend(cur.fetchall())
    if any(m is None for m in missing):
        cur.execute('SELECT count(*) FROM public."%s" WHERE "%s" IS NULL' % (table, col))
        out.append(("NULL", cur.fetchone()[0]))
    return out


def _show(title, findings):
    print("")
    print(title)
    for cid, tbl, col, missing, counts in findings:
        print("       %s.%s (%s): absent from the enum -> %s" % (cid, col, tbl, missing))
        for val, n in counts:
            print("          %-18s %s row(s)" % (val, n))


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    allow_offline = "--allow-offline" in sys.argv
    strict = "--strict" in sys.argv

    try:
        import psycopg2
    except Exception as e:
        print("SKIPPED capture-enums-cover-the-data: psycopg2 is not importable (%s)." % e)
        return 0 if allow_offline else 1

    try:
        conn = psycopg2.connect(DB_DSN, connect_timeout=5)
    except Exception as e:
        print("SKIPPED capture-enums-cover-the-data: the local database is unreachable (%s)."
              % str(e).strip().splitlines()[0][:110])
        print("        Reported as SKIPPED and NOT as a pass: 'I could not check' must never read as")
        print("        'I checked and it was fine', which is the confusion this gate exists to prevent.")
        print("        Pass --allow-offline where the stack is legitimately down.")
        return 0 if allow_offline else 1

    enforced = client_enforced_ids()
    buckets = {"blocking": [], "new-writes-only": [], "latent": [], "unannotated": []}
    checked, empty_enum_values = 0, []

    with conn, conn.cursor() as cur:
        cur.execute("SELECT capture_id, target_table, contract_schema FROM public.canonical_capture_contracts")
        rows = cur.fetchall()
        for capture_id, target_table, schema in rows:
            if not target_table:
                continue
            if isinstance(schema, str):
                try:
                    schema = json.loads(schema)
                except Exception:
                    continue
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", ("public." + target_table,))
            if not cur.fetchone()[0]:
                continue
            for col, allowed in _enums_from_schema(schema).items():
                cur.execute("""SELECT 1 FROM information_schema.columns
                               WHERE table_schema='public' AND table_name=%s AND column_name=%s""",
                            (target_table, col))
                if not cur.fetchone():
                    continue
                cur.execute('SELECT DISTINCT "%s" FROM public."%s"' % (col, target_table))
                present = {r[0] for r in cur.fetchall()}
                checked += 1
                missing, unused = compare(allowed, present)
                if missing:
                    buckets[classify(capture_id, enforced)].append(
                        (capture_id, target_table, col, missing, _counts(cur, target_table, col, missing)))
                if unused:
                    empty_enum_values.append((capture_id, col, unused))

    print("capture enums: checked %d enum column(s) across %d contract(s)." % (checked, len(rows)))
    print("               validated by a served page: %s" % (", ".join(sorted(enforced)) or "none"))
    for cid, col, unused in empty_enum_values[:6]:
        print("   note: %s.%s declares %s with no rows yet (fine)" % (cid, col, unused))

    if buckets["latent"]:
        _show("LATENT (%d): NO page calls the validator for this capture_id, so nothing refuses a save\n"
              "             today. These become outages the moment a call site is added - fix the\n"
              "             contract or the data BEFORE wiring one, not after. Both of today's two are\n"
              "             corrected by migration 20260916000003, which also records why\n"
              "             asset_wizard_v1 was UNSATISFIABLE rather than merely stale: its Title-case\n"
              "             enum contradicts asset_nodes_criticality_check, so EVERY possible value\n"
              "             failed one gate or the other."
              % len(buckets["latent"]), buckets["latent"])

    if buckets["new-writes-only"]:
        _show("NOT REACHED BY EXISTING ROWS (%d): the page validates only payloads it builds FRESH\n"
              "             (a form, a literal), never values it loaded, so these stored rows are\n"
              "             never handed to the contract. What it does mean is that the column holds\n"
              "             values the form can no longer produce - a history/vocabulary drift worth\n"
              "             knowing about, and a trap for any change that starts re-saving loaded rows."
              % len(buckets["new-writes-only"]), buckets["new-writes-only"])

    if buckets["unannotated"]:
        _show("UNANNOTATED (%d): a page validates this capture but PAYLOAD_SOURCE does not say whether\n"
              "             it re-sends loaded rows. Read the call site and record it, with evidence."
              % len(buckets["unannotated"]), buckets["unannotated"])

    if buckets["blocking"]:
        _show("FAIL capture-enums-cover-the-data: %d column(s) on a capture that RE-SENDS LOADED ROWS\n"
              "     hold values the contract forbids. wh-capture-validate.js runs CLIENT-SIDE, so each\n"
              "     of these rows exists and cannot be re-saved from its page - the write is refused\n"
              "     before it reaches the network, and retrying is the one action that cannot work."
              % len(buckets["blocking"]), buckets["blocking"])
        print("     Two fixes, and WHO WRITES THE VALUE decides which: a value a shipping path emits")
        print("     means the CONTRACT is wrong (widen it, as 20260916000001 does for `planned`, which")
        print("     land_accepted_job_on_dayplan() writes); a value nothing writes means the DATA is")
        print("     wrong (normalise it, as 20260916000002 does for ten orphaned lowercase categories).")
        return 1

    if buckets["unannotated"]:
        print("")
        print("FAIL: an enforced capture is unannotated - its severity cannot be judged.")
        return 1

    reported = len(buckets["latent"]) + len(buckets["new-writes-only"])
    if reported and strict:
        print("")
        print("FAIL (--strict): %d reported-but-not-blocking mismatch(es) treated as failures." % reported)
        return 1

    print("PASS capture-enums-cover-the-data: no capture that re-sends loaded rows holds a value its")
    print("     contract forbids.")
    return 0


def self_test() -> int:
    ok = True
    allowed = {"pending", "done", None}

    missing, unused = compare(allowed, {"pending", "done", "planned"})
    if missing != ["planned"]:
        print("FAIL: a value present in the column and absent from the enum must be reported -> %s" % missing)
        ok = False

    missing, unused = compare(allowed, {"pending"})
    if missing:
        print("FAIL: a subset must not be reported as a problem -> %s" % missing)
        ok = False
    if unused != ["done"] and unused != [None, "done"] and sorted(map(str, unused)) != ["None", "done"]:
        print("FAIL: an enum value with no rows should be reported as unused, not failed -> %s" % unused)
        ok = False

    missing, _ = compare(allowed, {None})
    if missing:
        print("FAIL: NULL is in this enum and must not be flagged -> %s" % missing)
        ok = False

    got = _enums_from_schema({"properties": {"a": {"enum": ["x", "y"]}, "b": {"type": "string"}}})
    if got != {"a": {"x", "y"}}:
        print("FAIL: only properties declaring an enum should be extracted -> %s" % got)
        ok = False

    # The severity split is the correction this gate needed; test it against the real repo.
    ids = client_enforced_ids()
    if "schedule_item_v1" not in ids:
        print("FAIL: dayplanner.html calls the validator for schedule_item_v1 - it must be enforced -> %s"
              % sorted(ids))
        ok = False
    if "asset_wizard_v1" in ids:
        print("FAIL: no page calls the validator for asset_wizard_v1; calling it enforced is the bug "
              "this split fixes -> %s" % sorted(ids))
        ok = False

    # EVERY enforced capture must be annotated, or its severity is a guess. This is the check that
    # forces whoever adds the next whValidateCapture call to read their own payload and say where it
    # comes from, instead of inheriting a default that happens to be wrong.
    unannotated = sorted(i for i in ids if i not in PAYLOAD_SOURCE)
    if unannotated:
        print("FAIL: enforced but unannotated in PAYLOAD_SOURCE -> %s" % unannotated)
        ok = False

    if classify("schedule_item_v1", ids) != "blocking":
        print("FAIL: schedule_item_v1 re-sends loaded rows and must classify as blocking.")
        ok = False
    if classify("logbook_add_entry_v1", ids) != "new-writes-only":
        print("FAIL: logbook_add_entry_v1 validates only form-built payloads - existing rows never "
              "reach the contract, so it must not be reported as an outage.")
        ok = False
    if classify("asset_wizard_v1", ids) != "latent":
        print("FAIL: asset_wizard_v1 has no call site and must classify as latent.")
        ok = False
    if classify("brand_new_v1", ids | {"brand_new_v1"}) != "unannotated":
        print("FAIL: an enforced capture with no PAYLOAD_SOURCE entry must classify as unannotated, "
              "not silently pass.")
        ok = False

    # A call written across two lines (logbook.html) must still be seen, and the validator's own
    # docstring must NOT count as a call site.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "page.html"), "w", encoding="utf-8") as fh:
            fh.write("  const vr = await window.whValidateCapture(db, 'multi_line_v1',\n      payload);\n")
        with open(os.path.join(td, "wh-capture-validate.js"), "w", encoding="utf-8") as fh:
            fh.write("// const r = await whValidateCapture(db, 'never_called_v1', payload);\n")
        got_ids = client_enforced_ids(td)
    if got_ids != {"multi_line_v1"}:
        print("FAIL: a wrapped call must be found and the validator's own docstring must not count -> %s"
              % sorted(got_ids))
        ok = False

    print("self-test: %s" % ("PASS - catches a value the enum omits, ignores a subset, tolerates NULL, "
                             "extracts only enum properties, and sorts a mismatch into blocking / "
                             "not-reached / latent / unannotated" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
