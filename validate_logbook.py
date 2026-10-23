"""
Logbook Validator — WorkHive Platform
======================================
Four-layer validation of logbook.html + pm-scheduler.html:

  Layer 1 — Data integrity rules
    1.  closed_at consistency         — every write with status='Closed' sets closed_at
    2.  Parts deduction guard         — saveEdit skips _existing parts (no double-deduct)
    3.  closed_at preservation        — re-editing a closed entry keeps original timestamp
    4.  Valid status values           — only 'Open' and 'Closed' used
    5.  Valid category values         — categories match the dropdown
    6.  PM category alignment         — PM_CAT_TO_LOG_CAT maps to valid logbook categories

  Layer 2 — Tenant isolation
    7.  hive_id in txn insert         — inventory_transactions.insert includes hive_id
    8.  delete scoped by worker       — deleteEntry uses .eq('worker_name', WORKER_NAME)
    9.  update scoped by worker       — saveEdit update uses .eq('worker_name', WORKER_NAME)

  Layer 3 — Logic correctness
    10. Auth gate present             — WORKER_NAME redirect before any DB access
    11. maintenance_type values       — types used match VALID_MAINTENANCE_TYPES
    12. qty_after floor               — inventory deduction uses Math.max(0, ...) guard

  Layer 4 — XSS / JS correctness
    13. highlight() calls escHtml     — search highlight function escapes before rendering
    14. No await in non-async cb      — await in regular function() crashes ALL JS on page load

Usage:  python validate_logbook.py
Output: logbook_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LOGBOOK_PAGE = "logbook.html"
PM_PAGE      = "pm-scheduler.html"

VALID_LOGBOOK_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Vehicle", "Other",
]
VALID_STATUSES = ["Open", "Closed"]
VALID_MAINTENANCE_TYPES = [
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
]


def function_body(content, pattern):
    """
    Return the REAL body of the function whose declaration matches `pattern`, by matching braces
    from its opening `{`. Returns None when the function isn't found.

    Why this exists (2026-07-28): checks anchored to a fixed character window (`content[start:start+3000]`)
    silently measure the wrong thing the moment the function grows. The LB7/LB17 fixes added explanatory
    comments to loadEntries(), which pushed `_allEntries =` past the 3000-char window and turned
    check_new_fields_in_load_entries red against code that was correct and had MORE safety than before.
    Teaching the gate to read the actual body is the fix; deleting the comments to fit an arbitrary
    window would be bending the code to a broken ruler ([[feedback_teach_the_gate_not_bend_the_code]]).
    """
    m = re.search(pattern, content)
    if not m:
        return None
    i = content.find("{", m.start())
    if i == -1:
        return None
    depth, j = 0, i
    while j < len(content):
        c = content[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return content[i:j + 1]
        j += 1
    return content[i:]


def strip_template_literals(text):
    return re.sub(r'\$\{[^}]*\}', '__INTERP__', text)


# ── Layer 1: Data integrity ───────────────────────────────────────────────────

def check_closed_at_consistency(content, page):
    issues = []
    clean = strip_template_literals(content)
    for op in ("insert", "update"):
        pattern = rf"from\(['\"]logbook['\"]\)\.{op}\((\{{[^}}]{{0,1500}}\}})"
        for m in re.finditer(pattern, clean, re.DOTALL):
            block = m.group(1)
            if re.search(r"status\s*:\s*['\"]Closed['\"]", block) and \
               not re.search(r"closed_at\s*:", block):
                line_no = content[:m.start()].count('\n') + 1
                issues.append({"check": "closed_at_consistency", "page": page,
                               "operation": op, "line": line_no,
                               "reason": f"logbook.{op}() sets status='Closed' but missing closed_at field"})
    return issues


def check_parts_deduction_guard(content, page):
    # 2026-07-28: retargeted from saveEdit() to saveEditFromForm(). saveEdit was the edit-MODAL
    # path and it was dead -- nothing called it, and the `e-` inputs it read do not exist -- so
    # these three checks had been passing against unreachable code. saveEditFromForm is the path a
    # worker actually takes. Body read by brace-matching rather than a fixed window, per function_body.
    body = function_body(content, r"async function saveEditFromForm\s*\(")
    if body is None:
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEditFromForm() function not found — cannot verify parts deduction guard"}]
    edit_block = body
    if not re.search(r"if\s*\(!p\.partId\s*\|\|\s*p\._existing\)\s*continue", edit_block):
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEditFromForm() deducts parts without _existing guard — will double-deduct inventory on re-save"}]
    return []


def check_closed_at_preservation(content, page):
    patterns = [
        r"existing\?\.closed_at\s*\|\|",
        r"existing\.closed_at\s*\|\|",
        r"original.*closed_at",
        r"preserve.*close",
    ]
    if not any(re.search(p, content) for p in patterns):
        return [{"check": "closed_at_preservation", "page": page,
                 "reason": "No closed_at preservation pattern found — re-saving a closed entry may overwrite the original close timestamp"}]
    return []


def check_status_values(content, page):
    logbook_only = {s for s in re.findall(r"status\s*:\s*['\"]([^'\"]+)['\"]", content)
                    if s in ("Open", "Closed", "open", "closed")}
    bad = [s for s in logbook_only if s not in VALID_STATUSES]
    if bad:
        return [{"check": "status_values", "page": page, "bad_values": bad,
                 "reason": f"Non-standard status values found: {bad} — only {VALID_STATUSES} allowed"}]
    return []


def check_category_values(content, page):
    array_matches = re.findall(
        r"\[([^\]]+)\]\s*\.map\s*\(\s*\w+\s*=>\s*`<option[^`]{0,200}?entry\.category",
        content, re.DOTALL
    )
    cats = set()
    for arr in array_matches:
        cats.update(re.findall(r"['\"]([^'\"]+)['\"]", arr))
    unknown = [c for c in cats if c not in VALID_LOGBOOK_CATEGORIES]
    if unknown:
        return [{"check": "category_values", "page": page, "unknown": unknown,
                 "reason": f"Category values {unknown} not in VALID_LOGBOOK_CATEGORIES — update the constant in this validator"}]
    return []


def check_pm_category_alignment(pm_content):
    if not pm_content:
        return [{"check": "pm_category_alignment", "page": PM_PAGE,
                 "reason": f"{PM_PAGE} not found"}]
    m = re.search(r"PM_CAT_TO_LOG_CAT\s*=\s*\{([^}]+)\}", pm_content, re.DOTALL)
    if not m:
        return [{"check": "pm_category_alignment", "page": PM_PAGE,
                 "reason": "PM_CAT_TO_LOG_CAT not found in pm-scheduler.html"}]
    issues = []
    for pm_cat, log_cat in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
        if log_cat not in VALID_LOGBOOK_CATEGORIES:
            issues.append({"check": "pm_category_alignment", "page": PM_PAGE,
                           "pm_category": pm_cat, "maps_to": log_cat,
                           "reason": f"PM category '{pm_cat}' maps to '{log_cat}' which is not in logbook's category dropdown — PM entries will have unrecognized category"})
    return issues


# ── Layer 2: Tenant isolation ─────────────────────────────────────────────────

def check_txn_id_present(content, page):
    """
    inventory_transactions.id is TEXT NOT NULL with no DEFAULT.
    Every insert must supply an id explicitly — omitting it causes a not-null
    constraint violation. The insert still returns no error to the caller (PostgREST
    wraps it as txnErr), so the inventory qty IS decremented but the transaction
    record is never written, and the user sees 'Parts log failed' even though the
    logbook entry saved correctly.
    """
    issues = []
    for m in re.finditer(r"from\(['\"]inventory_transactions['\"]\)\.insert\((\{[^}]{0,600}\})", content, re.DOTALL):
        block = m.group(1)
        if not re.search(r"\bid\s*:", block):
            line = content[:m.start()].count('\n') + 1
            issues.append({"check": "txn_id_present", "page": page, "line": line,
                           "reason": (f"inventory_transactions.insert() at line {line} missing 'id' field — "
                                      f"inventory is decremented but transaction record fails to write; "
                                      f"user sees 'Parts log failed' toast even when logbook save succeeded")})
    return issues


def check_hive_id_in_txn_insert(content, page):
    """
    Both saveEntry and saveEdit insert to inventory_transactions when parts are used.
    Each insert must include hive_id: HIVE_ID so transactions are tenant-scoped.
    """
    issues = []
    for m in re.finditer(r"from\(['\"]inventory_transactions['\"]\)\.insert\((\{[^}]{0,600}\})", content, re.DOTALL):
        block = m.group(1)
        if "hive_id" not in block:
            line = content[:m.start()].count('\n') + 1
            issues.append({"check": "hive_id_in_txn_insert", "page": page, "line": line,
                           "reason": f"inventory_transactions.insert() at line {line} missing hive_id — transactions not tenant-scoped in hive mode"})
    return issues


def check_delete_scoped_by_worker(content, page):
    m = re.search(r"async function deleteEntry\s*\(", content)
    if not m:
        return [{"check": "delete_scoped_by_worker", "page": page,
                 "reason": "deleteEntry() function not found"}]
    # 2026-08-26: read the WHOLE function by brace-matching, the idiom its sibling
    # check_update_scoped_by_worker adopted 2026-07-28 for exactly this failure - a fixed
    # 400-char window went red when a comment + longer confirm copy (T17's reversal-on-glass
    # wording) pushed the .eq past the window while the scoping itself never moved.
    body = function_body(content, r"async function deleteEntry\s*\(")
    # 2026-10-04: auth_uid is the PREFERRED form, and worker_name stays accepted as legacy. The property
    # this check exists for is "the delete is scoped to the OWNER" - it was written when the only
    # available key was the display name, and then pinned to that spelling. A display name is a weaker
    # key in both directions: two people can share one, and a renamed person stops matching rows that are
    # theirs (which is how 27,420 logbook entries became un-deletable by their authors, and how the asset
    # picker came up empty for Ian on 2026-10-04). auth_uid is what RLS logbook_delete itself enforces.
    # Same shape as this file's own ocUpdate allowance below: a STRONGER mechanism satisfies the check.
    # 2026-10-16 (SL D3): the delete is now RECOVERABLE - whTrash(db, 'logbook', id) calls wh_trash, which runs as
    # the caller (SECURITY INVOKER, held by deletes-are-recoverable L2) and stamps deleted_at under logbook_update's
    # `auth_uid = auth.uid()` - the same owner rule logbook_delete enforced, applied by the database rather than by a
    # client filter. That is the stronger mechanism again, so it satisfies the check; a bare client .delete() still
    # needs the explicit owner filter.
    if re.search(r"whTrash\s*\(\s*db\s*,\s*['\"]logbook['\"]", body) and not re.search(r"\.delete\s*\(", body):
        return []
    if not re.search(r"\.eq\s*\(['\"](?:auth_uid|worker_name)['\"],\s*(?:_authUid|WORKER_NAME)\s*\)", body):
        return [{"check": "delete_scoped_by_worker", "page": page,
                 "reason": "deleteEntry() does not scope the delete to the owner (expected .eq('auth_uid', "
                           "_authUid), or the legacy .eq('worker_name', WORKER_NAME)) — users could "
                           "delete other workers' entries"}]
    return []


def check_update_scoped_by_worker(content, page):
    m = re.search(r"async function saveEditFromForm\s*\(", content)
    if not m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEditFromForm() function not found"}]
    # 2026-07-28: retargeted to the LIVE saveEditFromForm and read by brace-matching, so the check
    # no longer depends on a fixed window OR on the dead edit-modal path it used to inspect.
    body = function_body(content, r"async function saveEditFromForm\s*\(")
    # Two acceptable patterns:
    #   (a) Legacy: .from('logbook').update(...).eq('worker_name', WORKER_NAME)
    #   (b) Phase Tier2.1: ocUpdate(db, 'logbook', id, updates, oldStamp)
    #       -- OC guard is stronger isolation than worker_name (the stamp
    #       moves on every UPDATE and is unique per writer).
    if re.search(r"ocUpdate\s*\(\s*db\s*,\s*['\"]logbook['\"]", body):
        return []
    # Allow the chain to be broken across lines. The live saveEditFromForm writes
    #   db.from('logbook')\n    .update({...})\n    .eq('id', id)\n    .eq('worker_name', WORKER_NAME)
    # which the old adjacent-only pattern could not span -- it only ever matched the single-line
    # form in the dead edit-modal path, which is why this check went red the moment that was deleted.
    update_m = re.search(r"from\(['\"]logbook['\"]\)\s*\.update\(", body)
    if not update_m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEditFromForm() logbook.update() / ocUpdate call not found"}]
    # 2026-10-04: 400 -> 900 chars, because the auth_uid fix carries an explanatory comment between the
    # .update( and the .eq(, and a fixed window is a broken ruler - this file has been bitten by exactly
    # that before (a correct comment pushed the scoping out of a 3,000-char window and turned a green
    # check red). The property, not the spelling: auth_uid preferred, worker_name accepted as legacy,
    # ocUpdate above accepted as stronger still.
    after = body[update_m.start():update_m.start() + 900]
    if not re.search(r"\.eq\s*\(['\"](?:auth_uid|worker_name)['\"],\s*(?:_authUid|WORKER_NAME)\s*\)", after):
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEditFromForm() logbook.update() is not scoped to the owner (expected "
                           ".eq('auth_uid', _authUid), the legacy .eq('worker_name', WORKER_NAME), or "
                           "ocUpdate) — users could overwrite other workers' entries"}]
    return []


# ── Layer 3: Logic correctness ────────────────────────────────────────────────

def check_auth_gate(content, page):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access the logbook"}]
    return []


def check_maintenance_type_values(content, page):
    """
    Find maintenance_type values written to the DB in insert/update payloads.
    They should match VALID_MAINTENANCE_TYPES exactly.
    """
    found = set(re.findall(r"maintenance_type\s*:\s*['\"]([^'\"]+)['\"]", content))
    # Exclude field selector references (short strings or UI labels). 'Maintenance Type' is the
    # FIELD'S OWN LABEL (T38's FIELD_LABELS key->label map, not a DB payload value) — the exact
    # UI-label class this comment always intended to exclude.
    UI_LABELS = {"Maintenance Type"}
    # 2026-10-07: a value that is an element id on this page (`maintenance_type: 'f-maint-type'` in the
    # LB_AI_FIELD_EL column->field map) names the FIELD, not a value written to the column - same class as
    # the UI label above. Matched against a real id="..." on the page, so a typo'd type still fails.
    page_ids = set(re.findall(r"\bid=['\"]([^'\"]+)['\"]", content))
    bad = [v for v in found if len(v) > 3 and v not in VALID_MAINTENANCE_TYPES and v not in UI_LABELS
           and v not in page_ids]
    if bad:
        return [{"check": "maintenance_type_values", "page": page, "bad_values": bad,
                 "reason": f"maintenance_type values {bad} not in VALID_MAINTENANCE_TYPES — entries may have unrecognized types"}]
    return []


def check_qty_after_floor(content, page):
    """
    Every inventory deduction in logbook must use Math.max(0, ...) to prevent
    qty_after going negative.
    """
    for m in re.finditer(r"from\(['\"]inventory_transactions['\"]\)\.insert\(", content):
        # Check within 500 chars before the insert for Math.max
        context = content[max(0, m.start() - 500):m.start()]
        if "Math.max(0," not in context and "Math.max( 0," not in context:
            line = content[:m.start()].count('\n') + 1
            return [{"check": "qty_after_floor", "page": page, "line": line,
                     "reason": f"inventory_transactions.insert() near line {line}: no Math.max(0,...) guard found — qty_after may go negative"}]
    return []


# ── Layer 3 (cont): New field sync ───────────────────────────────────────────

NEW_LOGBOOK_FIELDS = ["failure_consequence", "readings_json", "production_output"]

def check_new_fields_in_add_entry(content, page):
    """
    addEntry() must include all new fields in its Supabase insert.
    Missing = new entries saved without the data.
    """
    m = re.search(r"async function addEntry\s*\(", content)
    if not m:
        return [{"check": "new_fields_in_add_entry", "page": page,
                 "reason": "addEntry() not found"}]
    body = content[m.start():m.start() + 1500]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_add_entry", "page": page, "field": field,
                           "reason": f"addEntry() missing '{field}' in Supabase insert — new entries lose this data"})
    return issues


def check_new_fields_in_save_edit(content, page):
    """
    saveEditFromForm()'s updates object must include or preserve the new fields.
    Missing = editing an entry silently wipes failure_consequence, readings, production data.

    2026-07-28: retargeted from the dead edit-modal saveEdit() and read by brace-matching.
    """
    body = function_body(content, r"async function saveEditFromForm\s*\(")
    if body is None:
        return [{"check": "new_fields_in_save_edit", "page": page,
                 "reason": "saveEditFromForm() not found"}]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_save_edit", "page": page, "field": field,
                           "reason": f"saveEditFromForm() updates object missing '{field}' — editing an entry wipes this field to null"})
    return issues


def check_new_fields_in_load_entries(content, page):
    """
    loadEntries() cache shape must include the new fields.
    Anchors to the loadEntries function body so the offline-queue spread
    pattern `_allEntries = [...pending.map(...), ...(data||[]).map(` is
    accepted alongside the legacy `_allEntries = data.map(` form.
    Missing = fields are dropped from the local cache, openEditModal reads null.
    """
    body = function_body(content, r"async function loadEntries\s*\(")
    if body is None:
        return [{"check": "new_fields_in_load_entries", "page": page,
                 "reason": "loadEntries() function not found"}]
    m = re.search(r"_allEntries\s*=", body)
    if not m:
        return [{"check": "new_fields_in_load_entries", "page": page,
                 "reason": "_allEntries = ... not found inside loadEntries()"}]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_load_entries", "page": page, "field": field,
                           "reason": f"loadEntries() cache missing '{field}' — field dropped from local state, saveEdit reads null instead of DB value"})
    return issues


# ── L3 (2026-10-07): the two write paths and the edit snapshot, read as STRUCTURE ─────────────────
#
# Two defects found from source on 2026-10-07, both invisible to every check above because those
# checks ask "does the word appear in the function" and both words did appear:
#
#   1. addEntry()'s insert payload never copied wo_state / wo_assigned_to. The form submit put them
#      on `entry`, saveEditFromForm() saved them, and the INSERT dropped them - 0 of 31,257 local rows
#      carried a work-order state. The words were in the file; they were not in the payload.
#   2. loadEntries() SELECTED updated_at and then dropped it from the cached row, so openEditModal
#      snapshotted null and saveEditFromForm()'s `if (_editingUpdatedAt) .eq('updated_at', ...)`
#      skipped the optimistic lock for every entry opened from "Mine". searchTeam() did the same.
#
# So these checks parse the object literals (top-level keys only, comments and strings skipped) and
# compare SETS, instead of searching for spellings.

def _js_skip_string(text, i):
    """i points at a quote; return the index just past the closing quote (escape-aware)."""
    q, j, n = text[i], i + 1, len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == q:
            return j + 1
        j += 1
    return n


def _js_strip_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            j = _js_skip_string(text, i)
            out.append(text[i:j])
            i = j
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _js_brace_literal(text, open_idx):
    """text[open_idx] == '{'. Return the balanced literal, or None. Strings AND comments are skipped:
    a trailing `// the loader's (see ...) note` holds an apostrophe and a paren, and reading either as
    code ended the literal mid-way (the first version of this reader did exactly that)."""
    depth, i, n = 0, open_idx, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            i = _js_skip_string(text, i)
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:
                return text[open_idx:i + 1]
        i += 1
    return None


def _js_top_level_keys(literal):
    """Top-level property names of an object literal: `a: x`, shorthand `a`, quoted `'a': x`.
    Spreads (`...x`) are not keys. Nested objects / arrow bodies are skipped by depth."""
    body = _js_strip_comments(literal)
    body = body[body.find("{") + 1: body.rfind("}")]
    segs, depth, cur, i, n = [], 0, [], 0, len(body)
    while i < n:
        c = body[i]
        if c in "'\"`":
            j = _js_skip_string(body, i)
            cur.append(body[i:j])
            i = j
            continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if c == "," and depth == 0:
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    keys = []
    for s in segs:
        s = s.strip()
        if not s or s.startswith("..."):
            continue
        m = re.match(r"""(?:['"]([\w$]+)['"]|([A-Za-z_$][\w$]*))\s*(?::|$)""", s)
        if m:
            keys.append(m.group(1) or m.group(2))
    return keys


def _object_after(body, decl_regex):
    m = re.search(decl_regex, body)
    if not m:
        return None
    return _js_brace_literal(body, body.find("{", m.start()))


# Columns the EDIT path writes that a NEW entry legitimately does not. Empty today: every one of the
# 25 is something a person can set on the wizard, so a new entry must be able to carry it too.
EDIT_ONLY_KEYS = set()


def check_insert_carries_edit_fields(content, page):
    """
    Every column saveEditFromForm() saves must also be carried by addEntry()'s insert payload, and
    must already be on the payload when it is handed to the offline queue (queueEntryOffline), so a
    queued new entry drains with the same fields. An offline edit of a still-queued insert must keep
    the queued payload as its base, or put() replaces it with only the fields the edit form sent.
    """
    chk = "insert_carries_edit_fields"
    add = function_body(content, r"async function addEntry\s*\(")
    edit = function_body(content, r"async function saveEditFromForm\s*\(")
    if add is None or edit is None:
        return [{"check": chk, "page": page, "reason": "addEntry() or saveEditFromForm() not found"}]
    payload_lit = _object_after(add, r"const\s+payload\s*=\s*\{")
    updates_lit = _object_after(edit, r"const\s+updates\s*=\s*\{")
    if not payload_lit or not updates_lit:
        return [{"check": chk, "page": page,
                 "reason": "could not read `const payload = {...}` in addEntry() or `const updates = {...}` in saveEditFromForm()"}]
    q = add.find("queueEntryOffline(payload)")
    if q == -1:
        return [{"check": chk, "page": page,
                 "reason": "addEntry() no longer hands `payload` to queueEntryOffline() - the offline half of this check has nothing to read"}]
    pre_queue = _js_strip_comments(add[:q])
    insert_keys = set(_js_top_level_keys(payload_lit)) | set(
        re.findall(r"\bpayload\.([A-Za-z_]\w*)\s*=(?!=)", pre_queue))
    edit_keys = set(_js_top_level_keys(updates_lit)) | set(
        re.findall(r"\bupdates\.([A-Za-z_]\w*)\s*=(?!=)", _js_strip_comments(edit)))
    # The photo's two names are DERIVED at write time (BRH 9 AB): the payload carries the picture as `photo` and
    # whPhotoSettle(db, uid, payload) uploads it and writes photo_path / photo_thumb_path onto that payload - in
    # addEntry when online, in the queue drain when offline. Read as missing, they failed this check (2026-10-23).
    if "photo" in insert_keys and re.search(r"whPhotoSettle\(\s*db\s*,\s*\w+\s*,\s*payload\s*\)", add) \
            and re.search(r"whPhotoSettle\(\s*db\s*,\s*\w+\s*,\s*_photoOf\s*\)", content):
        insert_keys |= {"photo_path", "photo_thumb_path"}
    # Denominator guard: a parser that read nothing must not pass by having nothing to compare.
    if len(edit_keys) < 10 or len(insert_keys) < 10:
        return [{"check": chk, "page": page,
                 "reason": f"parsed only {len(edit_keys)} edit keys / {len(insert_keys)} insert keys - the literal reader is broken, not the page"}]
    issues = []
    missing = sorted(edit_keys - insert_keys - EDIT_ONLY_KEYS)
    if missing:
        issues.append({"check": chk, "page": page, "fields": missing,
                       "reason": f"saveEditFromForm() saves {missing} but addEntry()'s insert payload does not carry them "
                                 f"(before queueEntryOffline) - what the person picks on a NEW entry is silently not saved"})
    m = re.search(r"insertPayload\s*=\s*\{([^}]*)\}", _js_strip_comments(edit))
    if not m:
        issues.append({"check": chk, "page": page,
                       "reason": "saveEditFromForm()'s offline edit of a queued insert (insertPayload = {...}) not found"})
    elif not re.match(r"\s*\.\.\.(?!updates\b)[\w$]+\s*,\s*\.\.\.updates\b", m.group(1)):
        issues.append({"check": chk, "page": page,
                       "reason": "an offline edit of a still-queued new entry rebuilds insertPayload from `updates` alone - put() "
                                 "replaces the queued record, so every column the edit form did not send (wo_state, "
                                 "wo_assigned_to, ...) is dropped. Spread the queued entry first: { ...queued, ...updates, id, date }"})
    return issues


def check_edit_cache_keeps_snapshot(content, page):
    """
    openEditModal() edits the CACHED row and snapshots its updated_at for the optimistic lock. Every
    loader that fills a cache it reads from must SELECT updated_at and KEEP it in the mapped row, must
    keep every other column it selects (the form is filled from that row and saved back), and every
    r.<col> a mapping reads must be one its select asked for (a dead read renders undefined).
    """
    chk = "edit_cache_keeps_snapshot"
    opener = function_body(content, r"async function openEditModal\s*\(")
    if opener is None:
        return [{"check": chk, "page": page, "reason": "openEditModal() not found"}]
    m = re.search(r"let\s+entry\s*=\s*\(([^;]*?)\)\s*\.find\(", opener)
    caches = sorted(set(re.findall(r"\b(_\w+Entries)\b", m.group(1)))) if m else []
    if not caches:
        return [{"check": chk, "page": page,
                 "reason": "could not read which cache arrays openEditModal() edits from - nothing to check against"}]
    issues = []
    for cache in caches:
        loaders = []
        for fm in re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(", content):
            body = function_body(content[fm.start():], r"function\s+\w+\s*\(")
            if not body or not re.search(rf"\b{re.escape(cache)}\s*=(?!=)", body):
                continue
            sel = re.search(r"\.from\(\s*['\"]logbook['\"]\s*\)\s*\.select\(\s*['\"]([^'\"]+)['\"]", body)
            if sel:
                loaders.append((fm.group(1), body, sel.group(1)))
        if not loaders:
            issues.append({"check": chk, "page": page,
                           "reason": f"no logbook loader found that fills {cache} - the snapshot check would be vacuous"})
            continue
        for name, body, select in loaders:
            cols = {c.strip() for c in select.split(",")}
            if "*" not in cols and "updated_at" not in cols:
                issues.append({"check": chk, "page": page,
                               "reason": f"{name}() fills {cache} without selecting updated_at - an edit opened from it cannot arm the optimistic lock"})
            mm = re.search(r"\{\s*id\s*:\s*r\.id\b", body)
            if not mm:
                continue   # rows cached as returned keep every selected column
            lit = _js_brace_literal(body, mm.start())
            if not lit:
                continue
            kept = set(_js_top_level_keys(lit))
            if "updated_at" not in kept:
                issues.append({"check": chk, "page": page,
                               "reason": f"{name}() selects updated_at but its row mapping into {cache} drops it - openEditModal "
                                         f"snapshots null and saveEditFromForm skips the optimistic lock (silent overwrite)"})
            # The same shape for every other column: openEditModal fills the form FROM this cached row, so a column
            # selected and then dropped reads as empty there and is written back empty (searchTeam dropped
            # loto_applied / permit_reference, so an edit from the team view erased the LOTO record).
            dropped = sorted(cols - kept - {"*", "updated_at"})
            if dropped:
                issues.append({"check": chk, "page": page,
                               "reason": f"{name}() selects {dropped} but its row mapping into {cache} drops them - an edit opened "
                                         f"from it shows them empty and saves them back empty"})
            if "*" not in cols:
                dead = sorted(set(re.findall(r"\br\.([A-Za-z_]\w*)", _js_strip_comments(lit))) - cols)
                if dead:
                    issues.append({"check": chk, "page": page,
                                   "reason": f"{name}() maps r.{dead} into {cache} but never selects them - they are always undefined"})
    return issues


def check_oc_snapshot_required(content, page):
    """
    saveEditFromForm()'s online UPDATE applies .eq('updated_at', snapshot) only when a snapshot exists.
    A server row without one must be REFUSED before that UPDATE, never written unguarded.
    """
    chk = "oc_snapshot_required"
    body = function_body(content, r"async function saveEditFromForm\s*\(")
    if body is None:
        return [{"check": chk, "page": page, "reason": "saveEditFromForm() not found"}]
    code = _js_strip_comments(body)
    up = re.search(r"\.from\(\s*['\"]logbook['\"]\s*\)\s*\.update\(\s*\{\s*\.\.\.updates", code)
    if not up:
        return [{"check": chk, "page": page, "reason": "the online logbook .update({ ...updates }) was not found"}]
    for g in re.finditer(r"if\s*\(\s*!\s*_editingUpdatedAt\b", code[:up.start()]):
        blk = _js_brace_literal(code, code.find("{", g.end()))
        if blk and re.search(r"\breturn\b", blk):
            return []
    return [{"check": chk, "page": page,
             "reason": "saveEditFromForm() runs the online UPDATE when _editingUpdatedAt is missing - the optimistic lock is "
                       "skipped and a stale form overwrites a newer edit silently. Refuse (if (!_editingUpdatedAt ...) { ...; return; }) "
                       "before the update."}]


# ── 2026-10-07 (second pass): the OFFLINE queue meets the online rules ─────────────────────────────────────────────
# The four checks below read the queue's DRAIN as structure. Each was red on the file as it stood on 2026-10-07
# (teeth: `python validate_logbook.py --page <pre-fix copy>`): a queued edit replayed with no updated_at guard, an
# edit never refilled the work-order state, an offline-created entry never notified its assignee, and a refused
# queued write was resent on every reconnect forever.

def _functions(content):
    """(name, body) for every `function name(` AND anonymous `function (` in the file, brace-matched. Anonymous
    bodies get name '' - a delegated listener (`addEventListener('click', async function (ev) {...})`) is where a
    page often keeps exactly the handler a check is looking for."""
    out = []
    for fm in re.finditer(r"(?:async\s+)?function\b\s*(\w*)\s*\(", content):
        body = function_body(content[fm.start():], r"function\b\s*\w*\s*\(")
        if body:
            out.append((fm.group(1), body))
    return out


def _drain(content):
    """The function that replays the logbook offline queue: it INSERTs queued rows, branches on _queueOp and removes
    drained items. saveEditFromForm also removes a queue item now, so it is excluded by name."""
    for name, body in _functions(content):
        if name == "saveEditFromForm":
            continue
        code = _js_strip_comments(body)
        if ("_queueOp" in code and "removeFromQueue" in code
                and re.search(r"\.from\(\s*['\"]logbook['\"]\s*\)\s*\.insert\(", code)):
            return name, code
    return None, None


def check_offline_edit_replays_oc(content, page):
    """
    A queued offline EDIT must replay under the same optimistic lock as the online save: saveEditFromForm stores the
    updated_at it was opened with ON the queued item, and the drain's UPDATE carries .eq('updated_at', <that key>) -
    with a missing snapshot refused BEFORE the update (parked), never written unguarded.
    """
    chk = "offline_edit_replays_oc"
    edit = function_body(content, r"async function saveEditFromForm\s*\(")
    if edit is None:
        return [{"check": chk, "page": page, "reason": "saveEditFromForm() not found"}]
    ecode = _js_strip_comments(edit)
    snap_key = None
    for qm in re.finditer(r"queueEntryOffline\(\s*\{", ecode):
        lit = _js_brace_literal(ecode, ecode.find("{", qm.start()))
        if not lit or not re.search(r"_queueOp\s*:\s*['\"]update['\"]", lit):
            continue
        for km in re.finditer(r"(?:^|[{,])\s*([A-Za-z_$][\w$]*)\s*:\s*([^,}]*)", lit[1:-1]):
            if "_editingUpdatedAt" in km.group(2):
                snap_key = km.group(1)
    if not snap_key:
        return [{"check": chk, "page": page,
                 "reason": "saveEditFromForm() queues an offline edit ({ _queueOp: 'update', ... }) WITHOUT the updated_at it was "
                           "opened with - the drain has nothing to compare, so a dead-zone edit overwrites whatever was saved "
                           "since. Store it on the item (e.g. _snapshot: _editingUpdatedAt)."}]
    name, code = _drain(content)
    if not code:
        return [{"check": chk, "page": page, "reason": "the offline-queue drain (inserts queued rows, branches on _queueOp) was not found"}]
    k = re.escape(snap_key)
    up = re.search(r"\.from\(\s*['\"]logbook['\"]\s*\)\s*\.update\(", code)
    if not up:
        return [{"check": chk, "page": page, "reason": f"{name}() has no logbook .update( for queued edits"}]
    chain_end = code.find(".select(", up.end())
    chain = code[up.end(): chain_end if chain_end != -1 else up.end() + 1500]
    if not re.search(rf"\.eq\(\s*['\"]updated_at['\"]\s*,\s*(?:\w+\.)?{k}\s*\)", chain):
        return [{"check": chk, "page": page,
                 "reason": f"{name}() replays a queued edit without .eq('updated_at', {snap_key}) - the online save's optimistic "
                           f"lock is skipped offline, so the replay overwrites a newer edit made elsewhere, silently"}]
    if not re.search(rf"!\s*(?:\w+\.)?{k}\b", code[:up.start()]):
        return [{"check": chk, "page": page,
                 "reason": f"{name}() never refuses a queued edit whose {snap_key} is missing before its UPDATE - a .eq() on "
                           f"undefined is not a guard. Park it (the same rule as oc_snapshot_required online)."}]
    return []


def _guard_privileged_states():
    """sup_states from the LATEST migration that defines wh_guard_supervisor_approval (tg_guard_approval): the
    wo_state values a non-supervisor may not move an entry INTO (42501)."""
    mig_dir = os.path.join("supabase", "migrations")
    try:
        files = sorted(f for f in os.listdir(mig_dir) if f.endswith(".sql"))
    except OSError:
        return None
    states = None
    for f in files:
        try:
            sql = open(os.path.join(mig_dir, f), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "wh_guard_supervisor_approval" not in sql:
            continue
        m = re.search(r"sup_states\s+text\[\]\s*:=\s*ARRAY\[([^\]]*)\]", sql)
        if m:
            states = set(re.findall(r"'([a-z_]+)'", m.group(1)))
    return states


def check_edit_refills_wo_state(content, page):
    """
    Opening an edit must refill the work-order state and assignee from the row, the menu of states must be measured
    from the ROW's state (not from the last pick), no move offered to a worker may be one tg_guard_approval refuses
    (into a supervisor-only state), and the assignee nudge must fire only when the assignee CHANGED (a refilled
    assignee is resent on every edit).
    """
    chk = "edit_refills_wo_state"
    issues = []
    opener = function_body(content, r"async function openEditModal\s*\(")
    ui = function_body(content, r"function applyWoStateUI\s*\(")
    edit = function_body(content, r"async function saveEditFromForm\s*\(")
    if opener is None or ui is None or edit is None:
        return [{"check": chk, "page": page, "reason": "openEditModal(), applyWoStateUI() or saveEditFromForm() not found"}]
    ocode, ucode, ecode = _js_strip_comments(opener), _js_strip_comments(ui), _js_strip_comments(edit)
    for col, el in (("wo_state", "f-wo-state"), ("wo_assigned_to", "f-wo-assigned-to")):
        if el not in ocode or not re.search(rf"\.value\s*=\s*\(?\s*entry\.{col}\b", ocode):
            issues.append({"check": chk, "page": page,
                           "reason": f"openEditModal() never fills #{el} from entry.{col} - clearForm() resets it, so an edit "
                                     f"shows no work-order state and a worker cannot move an assigned job forward"})
    im = re.search(r"WO_TRANSITIONS\s*\[\s*\w+\s*\]\s*\[\s*([A-Za-z_$][\w$]*)\s*\]", ucode)
    if not im:
        issues.append({"check": chk, "page": page, "reason": "applyWoStateUI() no longer indexes WO_TRANSITIONS[role][<state>]"})
    else:
        var = im.group(1)
        dm = re.search(rf"(?:const|let|var)\s+{re.escape(var)}\s*=\s*([^;]+);", ucode[:im.start()])
        src = dm.group(1) if dm else ""
        # The pre-fix shape: `const current = sel.value || '';` - the menu indexed by whatever is selected right now.
        if not dm or (re.search(r"\.value\b", src) and "dataset" not in src):
            issues.append({"check": chk, "page": page,
                           "reason": f"applyWoStateUI() computes the allowed moves from `{var}` = {src.strip() or '?'} - the CURRENT "
                                     f"selection, so each pick re-bases the menu. Measure from the row's state (a base the "
                                     f"edit opener sets)"})
        else:
            bm = re.search(r"dataset\.(\w+)", src)
            if bm and not re.search(rf"dataset\.{bm.group(1)}\s*=\s*\(?\s*entry\.wo_state\b", ocode):
                issues.append({"check": chk, "page": page,
                               "reason": f"applyWoStateUI() measures moves from dataset.{bm.group(1)}, but openEditModal() never "
                                         f"sets it from entry.wo_state - every edit is measured from None"})
    priv = _guard_privileged_states()
    tm = re.search(r"const\s+WO_TRANSITIONS\s*=\s*\{", content)
    wlit = None
    if tm:
        whole = _js_brace_literal(content, content.find("{", tm.start()))
        wm = re.search(r"\bworker\s*:\s*\{", whole or "")
        if wm:
            wlit = _js_brace_literal(whole, whole.find("{", wm.start()))
    if not priv or not wlit:
        issues.append({"check": chk, "page": page,
                       "reason": "could not read the guard's supervisor-only wo_states (migrations) or WO_TRANSITIONS.worker - "
                                 "the mirror check has nothing to compare"})
    else:
        bad = []
        for fm in re.finditer(r"['\"]([a-z_]*)['\"]\s*:\s*\[([^\]]*)\]", wlit):
            frm, tos = fm.group(1), re.findall(r"['\"]([a-z_]*)['\"]", fm.group(2))
            bad += [f"{frm or 'None'}->{t}" for t in tos if t in priv and t != frm]
        if bad:
            issues.append({"check": chk, "page": page,
                           "reason": f"WO_TRANSITIONS.worker offers {bad}, which tg_guard_approval refuses a non-supervisor (42501)"})
    nm = re.search(r"\.rpc\(\s*['\"]notify_wo_assigned['\"]", ecode)
    if nm:
        cond = None
        for im2 in re.finditer(r"\bif\s*\(", ecode[:nm.start()]):
            cond = _js_brace_literal(ecode, ecode.find("(", im2.start()))
        # The innermost `if (...)` before the RPC is its gate; it must compare against the opened value.
        if not cond or not re.search(r"!==?", cond):
            issues.append({"check": chk, "page": page,
                           "reason": "saveEditFromForm() sends notify_wo_assigned whenever an assignee is present - with the "
                                     "assignee refilled on open, every edit of an assigned job re-pushes 'assigned to you'. "
                                     "Gate it on the assignee having CHANGED (!== the opened value)."})
    return issues


def check_offline_insert_notifies_assignee(content, page):
    """
    A queued NEW entry that names an assignee must, once its insert lands in the drain, call notify_wo_assigned -
    the online insert (addEntry) does, and an entry created in a dead zone is the same assignment.
    """
    chk = "offline_insert_notifies_assignee"
    name, code = _drain(content)
    if not code:
        return [{"check": chk, "page": page, "reason": "the offline-queue drain was not found"}]
    ins = re.search(r"\.from\(\s*['\"]logbook['\"]\s*\)\s*\.insert\(", code)
    after = code[ins.end():]
    nm = re.search(r"\.rpc\(\s*['\"]notify_wo_assigned['\"]", after)
    if not nm:
        return [{"check": chk, "page": page,
                 "reason": f"{name}() inserts a queued entry and never calls notify_wo_assigned - an entry created offline "
                           f"with an assignee syncs and the assignee is never told (addEntry's online insert tells them)"}]
    between = after[:nm.start()]
    if not re.search(r"if\s*\(\s*!\s*error\b", between) or "wo_assigned_to" not in between:
        return [{"check": chk, "page": page,
                 "reason": f"{name}() calls notify_wo_assigned after the insert but not gated on the insert having landed "
                           f"(if (!error ...)) AND on the entry carrying wo_assigned_to"}]
    return []


def check_offline_refusal_parked(content, page):
    """
    A queued write the server REFUSES (42501, 23xxx ...) must be parked - kept on the device, marked _stalled, with the
    server's own sentence (whWriteError) - not resent on every reconnect; transient failures keep retrying. The parked
    item must be shown with its reason and be discardable and fixable, and a parked NEW entry must be fixable ONLINE
    (saveEditFromForm must not route it into an UPDATE of a row that does not exist).
    """
    chk = "offline_refusal_parked"
    issues = []
    name, code = _drain(content)
    if not code:
        return [{"check": chk, "page": page, "reason": "the offline-queue drain was not found"}]
    fn = None
    # `else if (await isRefusal(error)) { ...park... }` - a classifier applied to the write's error, whose own body
    # names the refusal codes (42501 and the 23xxx integrity class).
    for cm in re.finditer(r"(?:await\s+)?([A-Za-z_$][\w$]*)\(\s*error\s*\)\s*\)", code):
        cand = function_body(content, rf"function\s+{re.escape(cm.group(1))}\s*\(")
        if cand and "42501" in cand and re.search(r"2\[23\]|23\\d|23\d{3}", cand):
            fn = (cm.group(1), cm.end(), cand)
            break
    if not fn:
        issues.append({"check": chk, "page": page,
                       "reason": f"{name}() never classifies a failed queued write - a server refusal (42501 / 23xxx) is left "
                                 f"queued and resent on every reconnect, forever, with nothing said"})
    else:
        cname, pos, cbody = fn
        branch_start = code.find("{", pos)
        branch = _js_brace_literal(code, branch_start) if branch_start != -1 else None
        if not branch or not re.search(r"_stalled\s*:\s*true", branch) or "whWriteError(" not in branch:
            issues.append({"check": chk, "page": page,
                           "reason": f"{name}()'s {cname}() branch does not park the item (_stalled: true) with the server's "
                                     f"sentence (whWriteError)"})
        if not re.search(r"whIsAuthFailure|status\s*>=\s*500|\b429\b|PGRST00", cbody):
            issues.append({"check": chk, "page": page,
                           "reason": f"{cname}() does not keep transient failures (dead session, 429, 5xx, no answer) queued - "
                                     f"they would be parked as if refused"})
    funcs = [(n, _js_strip_comments(b)) for n, b in _functions(content)]
    # Shown: a NAMED renderer puts _stallReason on screen escaped, AND something calls it - a renderer nothing calls
    # is the built-but-never-called shape, and passes every check that only looks for the function.
    # HTML comments go too: the panel's markup comment names the renderer, and must not count as a call.
    code_all = _js_strip_comments(re.sub(r"<!--[\s\S]*?-->", "", content))
    renderers = [n for n, b in funcs if n and "_stallReason" in b and "escHtml" in b and "innerHTML" in b]
    shown = any(len(re.findall(rf"\b{re.escape(n)}\s*\(", code_all)) >= 2 for n in renderers)
    # Discard: some handler other than the drain finds a PARKED item and removes it.
    discard = any(n not in (name, "saveEditFromForm") and "_stalled" in b and "removeFromQueue(" in b
                  and not re.search(r"\.from\(\s*['\"]logbook['\"]", b) for n, b in funcs)
    # Fix, for both kinds: a parked NEW entry opens as a still-queued entry (_offline: true - it is not in the list
    # caches and has no server row), and a parked EDIT opens with a FRESH updated_at (so its save is checked against
    # the version it would replace).
    fix = any("_queueOp" in b
              and re.search(r"openEditModal\(\s*[^,)]+,\s*\{[^;]*_offline\s*:\s*true", b)
              and re.search(r"openEditModal\(\s*[^,)]+,\s*\{[^;]*\bupdated_at\s*:", b) for _, b in funcs)
    if not shown:
        issues.append({"check": chk, "page": page,
                       "reason": "no renderer shows a parked item's _stallReason (escaped) - a refused save is kept with its "
                                 "reason and nothing on screen says so"})
    if not discard:
        issues.append({"check": chk, "page": page, "reason": "a parked item cannot be discarded (no path removes a _stalled item)"})
    if not fix:
        issues.append({"check": chk, "page": page,
                       "reason": "a parked item cannot be opened to fix it (no path opens a queued item in the edit form)"})
    edit = function_body(content, r"async function saveEditFromForm\s*\(")
    if edit:
        ecode = _js_strip_comments(edit)
        om = re.search(r"if\s*\(\s*!\s*navigator\.onLine\s*\)\s*\{", ecode)
        if om:
            offline_blk = _js_brace_literal(ecode, ecode.find("{", om.start())) or ""
            if re.search(r"existing\s*\?\.\s*_offline", offline_blk):
                issues.append({"check": chk, "page": page,
                               "reason": "saveEditFromForm() handles a still-queued NEW entry only inside `if (!navigator.onLine)` - "
                                         "online (a parked entry being fixed) it falls through to an UPDATE of a row that does not "
                                         "exist and says the entry was deleted"})
    return issues


# ── Layer 4: XSS / security ───────────────────────────────────────────────────

def check_await_in_non_async(content, page):
    """
    An `await` inside a regular function() callback (not async function) is a
    SyntaxError that crashes the entire JS engine on page load — ALL entries
    disappear because no code after the crash runs.

    Bug history (2026-04-28): TWO separate listeners had this bug in logbook.html.
    The first was caught at line 2076 (f-category). A second was missed at line 2138
    (f-maint-type) because the validator lookback window was only 5 lines and the
    function() was 7 lines above the await. Fixed: lookback extended to 20 lines.
    """
    issues = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "await " not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Look back up to 20 lines — function() can be many lines above the await
        # (e.g. a long variable declaration block between the function header and the await)
        window_back = "\n".join(lines[max(0, i - 20):i])
        has_plain_fn = bool(re.search(r"\bfunction\s*\(", window_back))
        has_async_fn = bool(re.search(r"\basync\s+function\s*\(", window_back))
        if has_plain_fn and not has_async_fn:
            issues.append({"check": "await_in_non_async", "page": page, "line": i + 1,
                           "reason": (f"{page}:{i+1} — `await` inside a non-async function() callback. "
                                      f"SyntaxError crashes ALL JS — entries never load. "
                                      f"Fix: add `async` to the function keyword.")})
    return issues


def check_highlight_escapes(content, page):
    m = re.search(r"function highlight\s*\(", content)
    if not m:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() function not found — logbook entries may render unsanitized HTML"}]
    body = content[m.start():m.start() + 300]
    if "escHtml" not in body:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() function does not call escHtml — search results render raw DB content as HTML"}]
    return []


def check_offline_queue(content, page):
    """
    logbook.html must implement the IndexedDB offline entry queue so field workers
    in low-signal areas can log jobs without losing data.
    Missing any piece = entries silently fail with no recovery when offline.
    """
    required = {
        "openOfflineDB":               "openOfflineDB() function missing",
        "queueEntryOffline":           "queueEntryOffline() function missing",
        "syncOfflineQueue":            "syncOfflineQueue() function missing",
        "navigator.onLine":            "navigator.onLine check missing in addEntry",
        "window.addEventListener('online'": "online event listener missing — queue never drains on reconnect",
        "offline-banner":              "#offline-banner element missing — worker has no visual feedback when offline",
    }
    issues = []
    for token, reason in required.items():
        if token not in content:
            issues.append({"check": "offline_queue", "page": page, "reason": reason})
    return issues


def check_team_query_first(content, page):
    """
    The team feed must use query-first UX: show an empty prompt until the user
    explicitly searches. Auto-loading all team entries is an unbounded fetch that
    causes visible lag on large hives.
    """
    required = {
        "async function searchTeam":  "searchTeam() function missing",
        "loadTeamMembers":            "loadTeamMembers() function missing",
        "team-filter-row":            "#team-filter-row element missing",
        "team-prompt":                "#team-prompt empty state missing",
        "TEAM_PAGE":                  "TEAM_PAGE constant missing — no server-side page size limit",
        "_teamSearched":              "_teamSearched flag missing — team view will auto-load on switch",
    }
    issues = []
    for token, reason in required.items():
        if token not in content:
            issues.append({"check": "team_query_first", "page": page, "reason": reason})
    return issues


def check_realtime_live_badge(content, page):
    """
    D3.2 (INTERACTIVE_LINEAGE_ROADMAP): the team feed surfaces a teammate's new
    logbook entry via a live realtime badge. It MUST:
      - subscribe to a hive-scoped `logbook-feed:` channel (INSERT on logbook),
      - guard the silent-freeze with rtConn() and clean up on beforeunload,
      - render a tap-to-refresh badge (NOT auto-prepend — that breaks the
        query-first team-feed contract, see team_query_first),
      - skip the user's OWN inserts (already rendered optimistically).
    """
    required = {
        "subscribeLogbookRealtime":       "subscribeLogbookRealtime() missing — no live team-activity feed",
        "'logbook-feed:'":                "logbook-feed channel name missing (hive-scoped realtime channel)",
        "refreshFromLiveBadge":           "refreshFromLiveBadge() missing — badge has no tap-to-refresh action",
        "logbook-live-badge":             "#logbook-live-badge element missing",
        "rtConn":                         "rtConn() guard missing — subscription can silently freeze",
        "_logbookRtChannel":              "_logbookRtChannel handle missing — channel can't be cleaned up",
    }
    issues = []
    for token, reason in required.items():
        if token not in content:
            issues.append({"check": "realtime_live_badge", "page": page, "reason": reason})
    # Must skip own inserts (no self-badging) — look for the own-row guard inside the subscription handler.
    # 2026-10-19: the identity form `_isMine(payload.new)` (account first, the display name only for a row with no
    # account) is the stronger guard the BRP wave moved this handler to; the old name compare is still accepted.
    _rt_body = function_body(content, r"function\s+subscribeLogbookRealtime\s*\(") or content   # brace-matched, not a window
    if "subscribeLogbookRealtime" in content and not re.search(
            r"worker_name\s*===\s*WORKER_NAME|_isMine\(\s*payload\??\.new\s*\)", _rt_body):
        issues.append({"check": "realtime_live_badge", "page": page,
                       "reason": ("Realtime handler does not skip the user's own inserts "
                                  "(payload.new.worker_name === WORKER_NAME guard missing) — "
                                  "the user would be badged for their own optimistic entry.")})
    # Must NOT auto-prepend a teammate INSERT into the live list (query-first
    # contract). A direct unshift/splice of payload.new into _teamEntries inside
    # the realtime handler would break it.
    m = re.search(r"subscribeLogbookRealtime[\s\S]{0,800}?\.subscribe", content)
    if m and re.search(r"_teamEntries\.(unshift|splice|push)", m.group(0)):
        issues.append({"check": "realtime_live_badge", "page": page,
                       "reason": ("Realtime handler mutates _teamEntries directly (auto-prepend) — "
                                  "breaks the query-first team-feed contract. Use the tap-to-refresh "
                                  "badge instead.")})
    return issues


def check_optimistic_lock_on_edit(content, page):
    """
    Layer 2 concurrent runner (2026-05-17): saveEditFromForm() must include
    an updated_at equality filter before the .update() call so concurrent
    edits are detected and the user is warned rather than silently overwritten.
    """
    if "saveEditFromForm" not in content:
        return []
    # OC guard requires: module-level variable AND usage inside the save function.
    # The function can be 100+ lines so search the whole file, not a window.
    has_oc_var  = "_editingUpdatedAt" in content
    has_oc_use  = re.search(r"eq\(['\"]updated_at['\"].*_editingUpdatedAt", content) is not None
    if not (has_oc_var and has_oc_use):
        return [{"check": "optimistic_lock_on_edit", "page": page,
                 "reason": (
                     "saveEditFromForm() online update path has no optimistic lock. "
                     "Concurrent edit by another user will silently overwrite. "
                     "Fix: add .eq('updated_at', _editingUpdatedAt) to the update query."
                 )}]
    return []


def check_machine_validation_toast(content, page):
    """
    Layer 2 → Layer 1 feedback (2026-05-16): the machine-empty guard in the
    submit handler must call showToast() so the user sees a clear message.
    A border-highlight alone is too subtle — consistent with category and
    problem guards that both show a toast.
    """
    # Find the submit handler's machine guard
    m = re.search(r"if\s*\(!machine\)", content)
    if not m:
        return []  # No guard at all — caught by other checks
    window = content[m.start():m.start() + 400]
    if "showToast" not in window:
        return [{"check": "machine_validation_toast", "page": page,
                 "reason": ("Submit handler machine-empty guard does not call showToast(). "
                            "User only sees border highlight (too subtle). "
                            "Fix: add showToast('Please select an asset before saving.') inside the if(!machine) block.")}]
    return []


def check_required_field_signposting(content, page):
    """
    Arc V (EFFORTLESS) — Layer 2 persona-walk feedback (2026-06-25, P1 Marielle).
    The "Log a Repair" wizard validated Discipline/Category + Symptom + (Breakdown)
    Impact only at the final Save click, drip-fed one toast at a time — and neither
    Category nor Symptom was marked 'required', while the Impact 'required for
    Breakdown' badge was dead code (never .remove('hidden')). An impatient field tech
    completed the whole wizard, then got bounced back two steps. RATCHET the fix:
      (1) Discipline/Category label signposts 'required'
      (2) Symptom label signposts 'required'
      (3) the consequence-required-badge is actually SHOWN on Breakdown (.remove('hidden'))
      (4) stepGo validates the step-2 required fields at the step-2 -> step-3 boundary,
          so the error surfaces on the step the field lives on (no bounce-back).
    """
    issues = []

    def label_has_required(label_for):
        m = re.search(r'<label[^>]*for="' + re.escape(label_for) + r'"[^>]*>(.*?)</label>', content, re.S)
        return bool(m) and "required" in m.group(1).lower()

    if not label_has_required("f-category"):
        issues.append({"check": "required_field_signposting", "page": page,
                       "reason": "Discipline/Category (f-category) is required at Save but its <label> does not signpost 'required'. Add the required badge (parity with Machine)."})
    if not label_has_required("f-problem"):
        issues.append({"check": "required_field_signposting", "page": page,
                       "reason": "Symptom (f-problem) is required at Save but its <label> does not signpost 'required'."})

    # (3) the impact badge must be SHOWN on Breakdown, not only ever hidden.
    if "consequence-required-badge').classList.remove('hidden')" not in content \
       and 'consequence-required-badge").classList.remove("hidden")' not in content:
        issues.append({"check": "required_field_signposting", "page": page,
                       "reason": "consequence-required-badge ('required for Breakdown') is never shown (.remove('hidden') missing in the Breakdown branch) — the requirement is invisible until the Save-time toast."})

    # (4) stepGo must validate step-2 required fields at the 2->3 boundary.
    # T42 (2026-08-25): stepGo grew a second param (fromPop, the wizard history-state walk) —
    # accept any parameter list starting with n.
    m = re.search(r"function stepGo\(n(?:,[^)]*)?\)\s*\{(.*?)\n\}", content, re.S)
    body = m.group(1) if m else ""
    if "_currentStep === 2" not in body or "f-category" not in body:
        issues.append({"check": "required_field_signposting", "page": page,
                       "reason": "stepGo() does not validate the step-2 required fields (f-category) at the step-2 -> step-3 boundary; a missing required field is drip-fed as a surprise toast two steps later at Save instead of being caught on its own step."})

    return issues


def check_edit_in_place(content, page):
    """
    Edit must reuse the main add form (edit-in-place) not a parallel mc.innerHTML modal.
    A parallel modal drifts from the add form over time — edited entries can have
    different field options, missing sections, or silently dropped fields.
    """
    required = {
        "_editingId":            "_editingId state variable missing",
        "cancelEditMode":        "cancelEditMode() function missing",
        "saveEditFromForm":      "saveEditFromForm() function missing",
        "edit-mode-banner":      "#edit-mode-banner element missing",
        "log-form.editing":      "CSS .editing class missing — step wizard not collapsed in edit mode",
    }
    issues = []
    for token, reason in required.items():
        if token not in content:
            issues.append({"check": "edit_in_place", "page": page, "reason": reason})
    return issues


def check_entry_kind_readings_shaping(content, page):
    """
    LOGBOOK arc (2026-07-12) — entry-KIND field-shaping must route READINGS to every
    condition-monitoring kind (Inspection / Preventive / Corrective), NOT breakdown-only.
    The prior code gated readings on `isBreakdown` alone, so an Inspection could never
    capture a reading — 0/645 seeded Inspection entries had readings, the data mirroring
    the broken UI. Readings (temp/vibration/pressure) are the DEFINING field of an
    inspection and a normal part of a PM. Failure consequence stays corrective-only;
    production output is decoupled from breakdown (any Closed run can record OEE output).
    RATCHET so a regression to isBreakdown-only cannot silently return:
      (1) a kindTakesReadings() helper exists and covers Inspection + Preventive;
      (2) the old `if (isBreakdown) ... renderReadingsFields` gate is GONE (readings are
          driven by kindTakesReadings);
      (3) updateProductionVisibility() no longer gates on isBreakdown.
    """
    issues = []

    # (1) helper exists and covers the two kinds the old code missed
    m = re.search(r"function\s+kindTakesReadings\s*\([^)]*\)\s*\{([^}]*)\}", content)
    if not m:
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "kindTakesReadings() helper missing — readings must be gated by a kind-set that includes Inspection + Preventive, not isBreakdown alone (an Inspection is definitionally reading-taking)."})
    else:
        low = m.group(1).lower()
        if "inspection" not in low or "preventive" not in low:
            issues.append({"check": "entry_kind_readings_shaping", "page": page,
                           "reason": "kindTakesReadings() does not include both Inspection and Preventive — both must render readings (an inspection IS reading-taking; a PM records condition)."})

    # (2) the old breakdown-only readings gate must not return
    if re.search(r"if\s*\(\s*isBreakdown\s*\)\s*(await\s+)?renderReadingsFields", content):
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "readings are gated on `if (isBreakdown) renderReadingsFields` — this hides readings from Inspection/Preventive. Drive readings off kindTakesReadings() instead."})
    if "kindTakesReadings" not in content or "renderReadingsFields" not in content:
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "readings rendering is not driven by kindTakesReadings() — regression risk to breakdown-only shaping."})

    # (4) 2026-07-28, walked live: the DISPLAY gate is not enough. Hiding #readings-section does not
    # clear its inputs (unlike the consequence branch, which zeroes f-consequence when it hides), so
    # entering readings as an Inspection and switching to Project Work left the values in the DOM and
    # collectReadings() still returned them — {temperature_c:40, vibration_mms:41, pressure_bar:42}
    # collected onto a Project Work entry. Readings on a kind that does not take them pollute the
    # trend/threshold analytics that read readings_json by maintenance_type. The COLLECTOR must apply
    # the same predicate as the reveal, because nothing reaches the database except through it.
    body = function_body(content, r"function collectReadings\s*\(")
    if body is None:
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "collectReadings() not found — cannot verify readings are collected only for kinds that take them."})
    elif "kindTakesReadings" not in body:
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "collectReadings() does not gate on kindTakesReadings() — a hidden readings field is still collected, so switching kind after typing saves readings onto an entry kind that does not take them."})

    # (3) production must not be re-coupled to isBreakdown (strip // comments first — the
    #     rationale comment legitimately names the retired `isBreakdown && isClosed` gate)
    m2 = re.search(r"function\s+updateProductionVisibility\s*\(\)\s*\{(.*?)\n\}", content, re.S)
    prod = re.sub(r"//[^\n]*", "", m2.group(1)) if m2 else ""
    if re.search(r"isBreakdown|includes\(['\"]Breakdown", prod):
        issues.append({"check": "entry_kind_readings_shaping", "page": page,
                       "reason": "updateProductionVisibility() gates production on isBreakdown — production output (OEE Quality/Performance) is orthogonal to breakdown and belongs to any Closed run (Preventive/Inspection are where OEE output originates). Gate on isClosed."})

    return issues


def check_audit_trail_wiring(content, page):
    """
    LOGBOOK arc Extension 3 (2026-07-12) — the logbook IS the DOLE/ISO audit trail: every
    create + amendment of an entry must leave an actor-attributed, hive-scoped `hive_audit_log`
    record (who did what, when), and an edit must capture the status transition (prev->new) so
    a closed/signed-off entry's amendments are tamper-evident. This LOCKS the wiring so a refactor
    can't silently drop the audit call (a dropped audit = a silent compliance-trail hole — the same
    silent-failure class as the cron/checkProactive dead-path bugs).
    RATCHET:
      (1) writeAuditLog() sets actor + hive_id;
      (2) the create path logs `create_logbook_entry` on target_type 'logbook';
      (3) the edit path logs `edit_logbook_entry` AND records prev_status/new_status (the amendment).
    """
    issues = []
    # (1) the audit helper attributes an actor + is hive-scoped
    m = re.search(r"function\s+writeAuditLog\s*\([^)]*\)\s*\{(.*?)\n\}", content, re.S)
    body = m.group(1) if m else ""
    if not m or "actor:" not in body or "hive_id:" not in body:
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "writeAuditLog() missing or does not set actor + hive_id — the DOLE/ISO audit trail must attribute who did what, hive-scoped."})
    # (2) create is audited
    if not re.search(r"writeAuditLog\(\s*['\"]create_logbook_entry['\"]", content):
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "the create path does not writeAuditLog('create_logbook_entry', ...) — new entries leave no audit-trail record."})
    # (3) edit is audited AND records the status transition (tamper-evident amendment)
    me = re.search(r"writeAuditLog\(\s*['\"]edit_logbook_entry['\"][^;]*?\{(.*?)\}\s*\)", content, re.S)
    if not me:
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "the edit path does not writeAuditLog('edit_logbook_entry', ...) — amendments to a (possibly closed) entry leave no audit record."})
    elif not re.search(r"prev_status", me.group(1)) or not re.search(r"new_status", me.group(1)):
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "the edit audit does not record prev_status + new_status — a closed/signed-off entry's status amendment must be tamper-evident (capture the before->after transition)."})
    # (4) the CSV export must be audit-GRADE — carry WHO (Worker) + WHEN-signed-off (Closed At),
    #     or it is a field-dump, not a DOLE/ISO trail. Guard the export column set + row projection.
    mc = re.search(r"const\s+cols\s*=\s*\[([^\]]*)\]", content)
    cols = mc.group(1) if mc else ""
    if "Worker" not in cols or "Closed At" not in cols:
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "the logbook CSV export omits Worker (WHO) and/or Signed Off (Closed At) columns — an audit trail must record who did the work and when it was signed off. Include worker_name + closed_at."})
    if not re.search(r"e\.worker_name", content) or not re.search(r"e\.closed_at", content):
        issues.append({"check": "audit_trail_wiring", "page": page,
                       "reason": "the CSV export row projection does not emit e.worker_name / e.closed_at — the audit columns are headers without data."})
    return issues


def check_loto_first_class(content, page):
    """
    LOGBOOK arc Extension 3 (2026-07-12) — LOTO / Permit-to-Work is a FIRST-CLASS field, not
    regex-inferred free text. Safety- + compliance-critical (RA 11058 / DOLE DO 198-18 PTW; ISO
    45001). RATCHET the full capture->persist->export chain so it can't silently drop:
      (1) the create payload persists loto_applied + permit_reference;
      (2) the form reads f-loto (checkbox) + f-permit-ref;
      (3) the loadEntries cache carries loto_applied (else edit rehydration loses it);
      (4) the audit CSV export includes the LOTO column (compliance record).
    """
    issues = []
    # (1) persisted in the insert payload
    if not re.search(r"loto_applied:\s*entry\.loto_applied", content) or \
       not re.search(r"permit_reference:\s*entry\.permit_reference", content):
        issues.append({"check": "loto_first_class", "page": page,
                       "reason": "the addEntry payload does not persist loto_applied + permit_reference — LOTO/permit-to-work must be a stored field, not regex-inferred."})
    # (2) read from the form
    if "'f-loto'" not in content and '"f-loto"' not in content:
        issues.append({"check": "loto_first_class", "page": page,
                       "reason": "the capture form has no #f-loto control — LOTO must be a deliberate first-class input."})
    if "f-permit-ref" not in content:
        issues.append({"check": "loto_first_class", "page": page,
                       "reason": "no #f-permit-ref permit-reference input — the permit-to-work authorization is part of the compliance record."})
    # (3) cache shape carries it (edit rehydration)
    if not re.search(r"loto_applied:\s*r\.loto_applied", content):
        issues.append({"check": "loto_first_class", "page": page,
                       "reason": "the loadEntries cache shape omits loto_applied — editing from cache would silently drop the safety-isolation flag."})
    # (4) audit export includes LOTO
    if "LOTO Applied" not in content or not re.search(r"e\.loto_applied", content):
        issues.append({"check": "loto_first_class", "page": page,
                       "reason": "the CSV audit export omits the LOTO column — the DOLE/ISO trail must record whether the asset was locked/tagged out."})
    # (5) the fetch .select() column lists must include loto_applied — an explicit column list that
    #     omits it means the field is NEVER fetched, so the cache/export/edit silently show it as
    #     false even when the DB row is true (the exact trap this arc hit + fixed). Every explicit
    #     logbook column-select must carry it.
    for m in re.finditer(r"\.select\(\s*'(id, date, machine[^']*)'\s*\)", content):
        cols = m.group(1)
        # only the FULL-entry selects (they carry failure_consequence + feed the cache/export) must
        # include loto; narrow selects (e.g. the asset fault-history panel) legitimately omit it.
        if "failure_consequence" not in cols:
            continue
        if "loto_applied" not in cols:
            issues.append({"check": "loto_first_class", "page": page,
                           "reason": "a logbook .select() column list omits loto_applied — the LOTO flag will not be fetched, so it renders false everywhere regardless of the stored value. Add loto_applied + permit_reference to every explicit entry select."})
            break
    return issues


def check_pm_mirror_asset_lineage(pm_content):
    """
    LOGBOOK arc reuse Extension 2 (2026-07-12) — when a PM completion mirrors into the
    logbook (the default-ON "Also save to Logbook" path in pm-scheduler.html), the
    mirrored entry must be ASSET-LINEAGED and machine-consistent, or it is orphaned from
    the asset's equipment history (v_asset_truth counts on asset_node_id) and inconsistent
    with every other logbook row (machine is the TAG platform-wide).
    RATCHET:
      (1) the mirror must NOT hard-code `asset_node_id: null` — it must resolve the FK;
      (2) machine must come from the tag (currentAsset.tag_id), not the display asset_name.
    """
    issues = []
    if not pm_content:
        return issues
    # locate the PM->logbook mirror payload block
    m = re.search(r"pm_completion_id:\s*compData\.id", pm_content)
    if not m:
        return issues  # mirror path absent/renamed — other checks own that
    window = pm_content[max(0, m.start() - 900): m.end() + 200]
    if re.search(r"asset_node_id:\s*null", window):
        issues.append({"check": "pm_mirror_asset_lineage", "page": PM_PAGE,
                       "reason": "PM->logbook mirror sets `asset_node_id: null` — the mirrored entry is orphaned from v_asset_truth equipment history. Resolve the asset_nodes.id via pm_asset_id."})
    if re.search(r"machine:\s*currentAsset\.asset_name\b", window):
        issues.append({"check": "pm_mirror_asset_lineage", "page": PM_PAGE,
                       "reason": "PM->logbook mirror sets machine from currentAsset.asset_name (the display name); machine is the TAG platform-wide. Use currentAsset.tag_id (fall back to asset_name)."})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1 — data integrity
    "closed_at_consistency", "parts_deduction_guard", "closed_at_preservation",
    "status_values", "category_values", "pm_category_alignment",
    # L2 — tenant isolation
    "txn_id_present", "hive_id_in_txn_insert", "delete_scoped_by_worker", "update_scoped_by_worker",
    # L3 — logic + new field sync
    "auth_gate", "maintenance_type_values", "qty_after_floor",
    "new_fields_in_add_entry", "new_fields_in_save_edit", "new_fields_in_load_entries",
    # L3 — 2026-10-07: write-path parity + the edit snapshot, read as structure
    "insert_carries_edit_fields", "edit_cache_keeps_snapshot", "oc_snapshot_required",
    # L3 — 2026-10-07 (second pass): the offline queue meets the online rules
    "offline_edit_replays_oc", "edit_refills_wo_state", "offline_insert_notifies_assignee", "offline_refusal_parked",
    # L4 — XSS / JS correctness
    "highlight_escapes", "await_in_non_async",
    # L4 — feature completeness
    "offline_queue", "team_query_first", "edit_in_place",
    # L4 — D3.2 interactive-lineage realtime
    "realtime_live_badge",
    # L3 — Layer 2 E2E feedback
    "machine_validation_toast",
    # L3 — Layer 2 concurrent runner
    "optimistic_lock_on_edit",
    # L3 — Arc V persona-walk (EFFORTLESS)
    "required_field_signposting",
    # L1 — LOGBOOK arc entry-KIND field-shaping (2026-07-12)
    "entry_kind_readings_shaping",
    # L2 — LOGBOOK arc reuse Extension 2: PM->logbook mirror lineage (2026-07-12)
    "pm_mirror_asset_lineage",
    # L2 — LOGBOOK arc Extension 3: DOLE/ISO audit-trail wiring (2026-07-12)
    "audit_trail_wiring",
    # L1 — LOGBOOK arc Extension 3: LOTO / Permit-to-Work first-class (2026-07-12)
    "loto_first_class",
]

CHECK_LABELS = {
    # L1
    "closed_at_consistency":        "L1  closed_at set when status='Closed'",
    "parts_deduction_guard":        "L1  saveEdit: _existing guard (no double-deduct)",
    "closed_at_preservation":       "L1  closed_at preserved on re-edit",
    "status_values":                "L1  Only Open/Closed used as status values",
    "category_values":              "L1  Category values match dropdown",
    "pm_category_alignment":        "L1  PM_CAT_TO_LOG_CAT maps to valid categories",
    # L2
    "txn_id_present":               "L2  inventory_transactions.insert() includes id field",
    "hive_id_in_txn_insert":        "L2  hive_id in inventory_transactions insert",
    "delete_scoped_by_worker":      "L2  deleteEntry scoped to the OWNER (auth_uid preferred; worker_name legacy)",
    "update_scoped_by_worker":      "L2  saveEdit update scoped to the OWNER (auth_uid preferred; ocUpdate or worker_name accepted)",
    # L3
    "auth_gate":                    "L3  WORKER_NAME auth gate present",
    "maintenance_type_values":      "L3  maintenance_type values match valid list",
    "qty_after_floor":              "L3  Math.max(0,...) guard on qty_after",
    # L3 (new field sync)
    "new_fields_in_add_entry":      "L3  New fields in addEntry insert (consequence/readings/production)",
    "new_fields_in_save_edit":      "L3  New fields preserved in saveEdit update",
    "new_fields_in_load_entries":   "L3  New fields included in loadEntries cache shape",
    "insert_carries_edit_fields":   "L3  addEntry insert (incl. offline queue) carries every column saveEditFromForm saves",
    "edit_cache_keeps_snapshot":    "L3  Every loader feeding openEditModal selects AND keeps updated_at; no dead r.<col> reads",
    "oc_snapshot_required":         "L3  Edit save refuses (never writes unguarded) when the updated_at snapshot is missing",
    "offline_edit_replays_oc":      "L3  A queued offline edit carries its updated_at snapshot; the drain replays it under .eq(updated_at) and parks a missing one",
    "edit_refills_wo_state":        "L3  Edit refills wo_state/assignee; moves measured from the row's state, none the approval guard refuses; notify only on change",
    "offline_insert_notifies_assignee": "L3  A queued new entry with an assignee calls notify_wo_assigned once its insert lands",
    "offline_refusal_parked":       "L3  A refused queued write is parked with the server's sentence (shown, discardable, fixable online); transient ones retry",
    # L4
    "highlight_escapes":            "L4  highlight() calls escHtml before rendering",
    "await_in_non_async":           "L4  No await inside non-async callback (JS crash guard)",
    # L4 — feature completeness
    "offline_queue":                "L4  Offline queue present (IndexedDB + online drain + banner)",
    "team_query_first":             "L4  Team feed uses query-first UX (not auto-load)",
    "edit_in_place":                "L4  Edit uses main form in-place (not parallel mc.innerHTML)",
    # L4 — D3.2 interactive-lineage realtime (2026-06-29)
    "realtime_live_badge":          "L4  Live team-activity badge (logbook-feed realtime, tap-to-refresh, skips own, query-first)",
    # L3 — Layer 2 E2E feedback (2026-05-16)
    "machine_validation_toast":     "L3  Machine-empty guard shows showToast() not just border highlight",
    # L3 — Layer 2 concurrent runner (2026-05-17)
    "optimistic_lock_on_edit":      "L3  saveEditFromForm has updated_at OC guard (no silent last-write-wins)",
    # L3 — Arc V persona-walk EFFORTLESS (2026-06-25)
    "required_field_signposting":   "L3  Required fields signposted + validated at their own step (no Save-time drip-bounce)",
    # L1 — LOGBOOK arc entry-KIND field-shaping (2026-07-12)
    "entry_kind_readings_shaping":  "L1  Readings shape to Inspection/Preventive/Corrective (not breakdown-only); production decoupled from breakdown",
    # L2 — LOGBOOK arc reuse Extension 2 (2026-07-12)
    "pm_mirror_asset_lineage":      "L2  PM->logbook mirror is asset-lineaged (resolves asset_node_id, machine=tag not name)",
    # L2 — LOGBOOK arc Extension 3 (2026-07-12)
    "audit_trail_wiring":           "L2  Audit trail wired (create+edit -> hive_audit_log, actor-attributed, edit records prev->new status)",
    # L1 — LOGBOOK arc Extension 3 (2026-07-12)
    "loto_first_class":             "L1  LOTO/Permit-to-Work is first-class (persisted loto_applied+permit_reference, form input, cached, in audit export)",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nLogbook Validator (4-layer)"))
    print("=" * 55)

    # --page PATH: validate another copy of logbook.html (a teeth run against a pre-fix file); the
    # report is then NOT written, so a deliberate red run never overwrites the gate's real verdict.
    page_override = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else None
    logbook = read_file(page_override or LOGBOOK_PAGE)
    pm      = read_file(PM_PAGE)

    if not logbook:
        print(f"  ERROR: {LOGBOOK_PAGE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_closed_at_consistency(logbook, LOGBOOK_PAGE)
    all_issues += check_parts_deduction_guard(logbook, LOGBOOK_PAGE)
    all_issues += check_closed_at_preservation(logbook, LOGBOOK_PAGE)
    all_issues += check_status_values(logbook, LOGBOOK_PAGE)
    all_issues += check_category_values(logbook, LOGBOOK_PAGE)
    all_issues += check_pm_category_alignment(pm)

    # L2
    all_issues += check_txn_id_present(logbook, LOGBOOK_PAGE)
    all_issues += check_hive_id_in_txn_insert(logbook, LOGBOOK_PAGE)
    all_issues += check_delete_scoped_by_worker(logbook, LOGBOOK_PAGE)
    all_issues += check_update_scoped_by_worker(logbook, LOGBOOK_PAGE)

    # L3
    all_issues += check_auth_gate(logbook, LOGBOOK_PAGE)
    all_issues += check_maintenance_type_values(logbook, LOGBOOK_PAGE)
    all_issues += check_qty_after_floor(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_add_entry(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_save_edit(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_load_entries(logbook, LOGBOOK_PAGE)
    all_issues += check_insert_carries_edit_fields(logbook, LOGBOOK_PAGE)
    all_issues += check_edit_cache_keeps_snapshot(logbook, LOGBOOK_PAGE)
    all_issues += check_oc_snapshot_required(logbook, LOGBOOK_PAGE)
    all_issues += check_offline_edit_replays_oc(logbook, LOGBOOK_PAGE)
    all_issues += check_edit_refills_wo_state(logbook, LOGBOOK_PAGE)
    all_issues += check_offline_insert_notifies_assignee(logbook, LOGBOOK_PAGE)
    all_issues += check_offline_refusal_parked(logbook, LOGBOOK_PAGE)

    # L4
    all_issues += check_highlight_escapes(logbook, LOGBOOK_PAGE)
    all_issues += check_await_in_non_async(logbook, LOGBOOK_PAGE)

    # L4 — feature completeness
    all_issues += check_offline_queue(logbook, LOGBOOK_PAGE)
    all_issues += check_team_query_first(logbook, LOGBOOK_PAGE)
    all_issues += check_edit_in_place(logbook, LOGBOOK_PAGE)
    all_issues += check_realtime_live_badge(logbook, LOGBOOK_PAGE)

    # L3 — Layer 2 E2E + concurrent runner feedback
    all_issues += check_machine_validation_toast(logbook, LOGBOOK_PAGE)
    all_issues += check_optimistic_lock_on_edit(logbook, LOGBOOK_PAGE)

    # L3 — Arc V persona-walk (EFFORTLESS)
    all_issues += check_required_field_signposting(logbook, LOGBOOK_PAGE)

    # L1 — LOGBOOK arc entry-KIND field-shaping (2026-07-12)
    all_issues += check_entry_kind_readings_shaping(logbook, LOGBOOK_PAGE)

    # L2 — LOGBOOK arc reuse Extension 2: PM->logbook mirror lineage (2026-07-12)
    all_issues += check_pm_mirror_asset_lineage(pm)

    # L2 — LOGBOOK arc Extension 3: DOLE/ISO audit-trail wiring (2026-07-12)
    all_issues += check_audit_trail_wiring(logbook, LOGBOOK_PAGE)

    # L1 — LOGBOOK arc Extension 3: LOTO / Permit-to-Work first-class (2026-07-12)
    all_issues += check_loto_first_class(logbook, LOGBOOK_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "logbook",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    if not page_override:
        with open("logbook_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
