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
    "Instrumentation", "Lubrication", "Other",
]
VALID_STATUSES = ["Open", "Closed"]
VALID_MAINTENANCE_TYPES = [
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
]


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
    m = re.search(r"async function saveEdit\b", content)
    if not m:
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEdit() function not found — cannot verify parts deduction guard"}]
    # Phase Tier2.1 (2026-05-12): saveEdit gained ~600 chars of optimistic-
    # concurrency wrapping, so the parts-deduction loop now lives further
    # down. Widen the window from 3000 to 6000 chars (saveEdit is ~120 lines
    # in total, well within that bound).
    edit_block = content[m.start():m.start() + 6000]
    if not re.search(r"if\s*\(!p\.partId\s*\|\|\s*p\._existing\)\s*continue", edit_block):
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEdit() deducts parts without _existing guard — will double-deduct inventory on re-save"}]
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
    body = content[m.start():m.start() + 400]
    if not re.search(r"\.eq\s*\(['\"]worker_name['\"],\s*WORKER_NAME\s*\)", body):
        return [{"check": "delete_scoped_by_worker", "page": page,
                 "reason": "deleteEntry() does not scope delete by worker_name — users could delete other workers' entries"}]
    return []


def check_update_scoped_by_worker(content, page):
    m = re.search(r"async function saveEdit\s*\(", content)
    if not m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() function not found"}]
    # Phase Tier2.1 (2026-05-12): saveEdit grew with the optimistic-
    # concurrency wrapper. Window widened to 6000 chars to span the OC
    # branch + the fallback .update() path that still exists for rows
    # without updated_at.
    body = content[m.start():m.start() + 6000]
    # Two acceptable patterns:
    #   (a) Legacy: .from('logbook').update(...).eq('worker_name', WORKER_NAME)
    #   (b) Phase Tier2.1: ocUpdate(db, 'logbook', id, updates, oldStamp)
    #       -- OC guard is stronger isolation than worker_name (the stamp
    #       moves on every UPDATE and is unique per writer).
    if re.search(r"ocUpdate\s*\(\s*db\s*,\s*['\"]logbook['\"]", body):
        return []
    update_m = re.search(r"from\(['\"]logbook['\"]\)\.update\(", body)
    if not update_m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() logbook.update() / ocUpdate call not found"}]
    after = body[update_m.start():update_m.start() + 200]
    if not re.search(r"\.eq\s*\(['\"]worker_name['\"],\s*WORKER_NAME\s*\)", after):
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() logbook.update() not scoped by worker_name or ocUpdate — users could overwrite other workers' entries"}]
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
    # Exclude field selector references (short strings or UI labels)
    bad = [v for v in found if len(v) > 3 and v not in VALID_MAINTENANCE_TYPES]
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
    saveEdit() updates object must include or preserve the new fields.
    Missing = editing an entry silently wipes failure_consequence, readings, production data.
    """
    m = re.search(r"async function saveEdit\s*\(", content)
    if not m:
        return [{"check": "new_fields_in_save_edit", "page": page,
                 "reason": "saveEdit() not found"}]
    body = content[m.start():m.start() + 3000]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_save_edit", "page": page, "field": field,
                           "reason": f"saveEdit() updates object missing '{field}' — editing an entry wipes this field to null"})
    return issues


def check_new_fields_in_load_entries(content, page):
    """
    loadEntries() cache shape must include the new fields.
    Anchors to the loadEntries function body so the offline-queue spread
    pattern `_allEntries = [...pending.map(...), ...(data||[]).map(` is
    accepted alongside the legacy `_allEntries = data.map(` form.
    Missing = fields are dropped from the local cache, openEditModal reads null.
    """
    fn = re.search(r"async function loadEntries\s*\(", content)
    if not fn:
        return [{"check": "new_fields_in_load_entries", "page": page,
                 "reason": "loadEntries() function not found"}]
    body = content[fn.start():fn.start() + 3000]
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
    # Must skip own inserts (no self-badging) — look for the WORKER_NAME guard
    # inside the subscription handler.
    if "subscribeLogbookRealtime" in content and not re.search(
            r"worker_name\s*===\s*WORKER_NAME", content):
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
    m = re.search(r"function stepGo\(n\)\s*\{(.*?)\n\}", content, re.S)
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
    "delete_scoped_by_worker":      "L2  deleteEntry scoped by worker_name",
    "update_scoped_by_worker":      "L2  saveEdit update scoped by worker_name",
    # L3
    "auth_gate":                    "L3  WORKER_NAME auth gate present",
    "maintenance_type_values":      "L3  maintenance_type values match valid list",
    "qty_after_floor":              "L3  Math.max(0,...) guard on qty_after",
    # L3 (new field sync)
    "new_fields_in_add_entry":      "L3  New fields in addEntry insert (consequence/readings/production)",
    "new_fields_in_save_edit":      "L3  New fields preserved in saveEdit update",
    "new_fields_in_load_entries":   "L3  New fields included in loadEntries cache shape",
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
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nLogbook Validator (4-layer)"))
    print("=" * 55)

    logbook = read_file(LOGBOOK_PAGE)
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
    with open("logbook_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
