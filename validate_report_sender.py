"""
Report Sender Validator — WorkHive Platform
============================================
Comprehensive validation of the Report Sender PWA feature across 4 layers:

  Layer 1 — Page structure
    1.  report-sender.html exists
    2.  Supabase CDN script present in <head>
    3.  viewport-fit=cover in viewport meta
    4.  Auth gate present (WORKER_NAME + redirect)
    5.  escHtml defined
    6.  Toast has role="alert" aria-live="polite"
    7.  nav-hub.js loaded at bottom

  Layer 2 — UI components
    8.  All 6 report chips defined in REPORTS array
    9.  4 active chips (no phase3 flag) match scheduled-agents runners
    10. Supabase client initialized (supabase.createClient)
    11. Install button present (#install-icon-btn)
    12. Mic circle present (#mic-btn)
    13. Voice context card present (#voice-ctx)
    14. Bottom sheet present (#sheet-overlay)
    15. Contacts list present (#contacts-list)
    16. Report history section present (#history-section)
    17. Processing state has per-report list (#proc-list)
    18. Email status indicator present (#email-status)

  Layer 3 — Logic & safety
    19. Promise.allSettled used for parallel report generation
    20. loadContacts function present
    21. loadHistory function present
    22. resendReport function present
    23. report_contacts table queried
    24. hive_id scoping on contacts query
    25. Voice transcript capped (slice(0, 500) or similar)

  Layer 4 — Edge functions & PWA
    26. send-report-email/index.ts exists
    27. RESEND_API_KEY referenced in send-report-email
    28. voice-report-intent/index.ts exists
    29. voice-report-intent imports callAI from ai-chain
    30. scheduled-agents accepts voice_context in request body
    31. report-sender-manifest.json exists with start_url
    32. sw.js exists with fetch handler
    33. Bottom sheet HTML is before the <script> block (DOM ordering)
    34. voice-transcribe edge function exists
    35. audio-chain.ts exists with Whisper fallback chain
    36. MediaRecorder path present in report-sender.html (iOS support)

Usage:  python validate_report_sender.py
Output: report_sender_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

PAGE            = "report-sender.html"
MANIFEST        = "report-sender-manifest.json"
SW              = "sw.js"
SEND_EMAIL_FN   = "supabase/functions/send-report-email/index.ts"
VOICE_INTENT_FN    = "supabase/functions/voice-report-intent/index.ts"
VOICE_TRANSCRIBE_FN = "supabase/functions/voice-transcribe/index.ts"
AUDIO_CHAIN_FN      = "supabase/functions/_shared/audio-chain.ts"
SCHEDULED_FN    = "supabase/functions/scheduled-agents/index.ts"

ACTIVE_REPORT_TYPES = ["pm_overdue", "failure_digest", "shift_handover", "predictive"]

CHECK_NAMES = [
    "page_exists", "supabase_cdn", "viewport_fit", "auth_gate", "esc_html",
    "toast_aria", "nav_hub",
    "reports_array", "active_types_match", "db_client", "install_btn",
    "mic_circle", "voice_ctx_card", "bottom_sheet", "contacts_list",
    "history_section", "proc_list", "email_status",
    "promise_all_settled", "load_contacts", "load_history", "resend_report",
    "contacts_table", "hive_id_scoping", "transcript_cap",
    "send_email_exists", "resend_key", "voice_intent_exists",
    "voice_intent_chain", "scheduled_voice_ctx", "manifest_start_url", "sw_fetch",
    "dom_ordering",
    "voice_transcribe_exists", "audio_chain_exists", "media_recorder_path",
]

CHECK_LABELS = {
    "page_exists":          "report-sender.html exists",
    "supabase_cdn":         "Supabase CDN script in <head>",
    "viewport_fit":         "viewport-fit=cover in viewport meta",
    "auth_gate":            "Auth gate — WORKER_NAME check + redirect",
    "esc_html":             "escHtml defined",
    "toast_aria":           "Toast has role='alert' aria-live='polite'",
    "nav_hub":              "nav-hub.js loaded",
    "reports_array":        "All 6 report chips in REPORTS array",
    "active_types_match":   "4 active types match scheduled-agents runners",
    "db_client":            "Supabase client initialized",
    "install_btn":          "Install button (#install-icon-btn) present",
    "mic_circle":           "Mic circle (#mic-btn) present",
    "voice_ctx_card":       "Voice context card (#voice-ctx) present",
    "bottom_sheet":         "Contact bottom sheet (#sheet-overlay) present",
    "contacts_list":        "Contacts list (#contacts-list) present",
    "history_section":      "Report history section (#history-section) present",
    "proc_list":            "Processing per-report list (#proc-list) present",
    "email_status":         "Email status indicator (#email-status) present",
    "promise_all_settled":  "Promise.allSettled used for parallel generation",
    "load_contacts":        "loadContacts function present",
    "load_history":         "loadHistory function present",
    "resend_report":        "resendReport function present",
    "contacts_table":       "report_contacts table queried",
    "hive_id_scoping":      "hive_id scoping on contacts query",
    "transcript_cap":       "Voice transcript length capped",
    "send_email_exists":    "send-report-email/index.ts exists",
    "resend_key":           "RESEND_API_KEY referenced in send-report-email",
    "voice_intent_exists":  "voice-report-intent/index.ts exists",
    "voice_intent_chain":   "voice-report-intent imports callAI from ai-chain",
    "scheduled_voice_ctx":  "scheduled-agents accepts voice_context",
    "manifest_start_url":   "report-sender-manifest.json has correct start_url",
    "sw_fetch":             "sw.js has fetch event handler",
    "dom_ordering":             "Bottom sheet HTML is before the <script> block",
    "voice_transcribe_exists":  "voice-transcribe/index.ts exists (iOS audio upload)",
    "audio_chain_exists":       "audio-chain.ts exists with Whisper fallback chain",
    "media_recorder_path":      "MediaRecorder path present in report-sender.html",
}


def run():
    issues = []
    page     = read_file(PAGE)
    manifest = read_file(MANIFEST)
    sw       = read_file(SW)
    send_fn  = read_file(SEND_EMAIL_FN)
    voice_fn = read_file(VOICE_INTENT_FN)
    sched_fn = read_file(SCHEDULED_FN)

    # ── Layer 1: Page structure ───────────────────────────────────────────────

    # 1. page exists
    if not page:
        issues.append({"check": "page_exists", "reason": f"{PAGE} not found"})
        return format_result(CHECK_NAMES, CHECK_LABELS, issues)

    # 2. Supabase CDN
    if not re.search(r'<script[^>]+supabase-js', page):
        issues.append({"check": "supabase_cdn",
                       "reason": "Supabase CDN <script> missing from <head> — supabase.createClient will throw ReferenceError and crash all JS"})

    # 3. viewport-fit=cover
    if "viewport-fit=cover" not in page:
        issues.append({"check": "viewport_fit",
                       "reason": "viewport-fit=cover missing — env(safe-area-inset-*) returns 0 on iPhone"})

    # 4. auth gate
    if not re.search(r'WORKER_NAME.*\|\|.*\|\|.*\|\|.*[\'"]', page, re.DOTALL) or \
       "index.html?signin=1" not in page:
        issues.append({"check": "auth_gate",
                       "reason": "Auth gate pattern missing — unauthenticated users can access the page"})

    # 5. escHtml
    if "function escHtml" not in page and "const escHtml" not in page:
        issues.append({"check": "esc_html",
                       "reason": "escHtml not defined — contact names/summaries rendered without XSS protection"})

    # 6. toast aria
    if 'role="alert"' not in page or 'aria-live' not in page:
        issues.append({"check": "toast_aria",
                       "reason": "Toast missing role='alert' or aria-live — screen readers on mobile won't announce notifications"})

    # 7. nav-hub
    if "nav-hub.js" not in page:
        issues.append({"check": "nav_hub",
                       "reason": "nav-hub.js not loaded — Report Sender missing from tool switcher"})

    # ── Layer 2: UI components ────────────────────────────────────────────────

    # 8. All 6 report chips
    all_report_types = ["pm_overdue", "failure_digest", "shift_handover",
                        "predictive", "oee", "descriptive"]
    missing_types = [t for t in all_report_types if f"'{t}'" not in page and f'"{t}"' not in page]
    if missing_types:
        issues.append({"check": "reports_array",
                       "reason": f"Missing report types in REPORTS array: {missing_types}"})

    # 9. Active types match scheduled-agents
    if sched_fn:
        for rt in ACTIVE_REPORT_TYPES:
            if f'"{rt}"' not in sched_fn and f"'{rt}'" not in sched_fn:
                issues.append({"check": "active_types_match",
                               "reason": f"'{rt}' missing from scheduled-agents runners — chip exists but no handler"})

    # 10. Supabase client
    if "supabase.createClient" not in page:
        issues.append({"check": "db_client",
                       "reason": "supabase.createClient not found — contacts and history cannot be saved/loaded"})

    # 11-18. Required DOM elements
    dom_checks = {
        "install_btn":   ("install-icon-btn", "Install button"),
        "mic_circle":    ("mic-btn",          "Mic circle button"),
        "voice_ctx_card":("voice-ctx",        "Voice context card"),
        "bottom_sheet":  ("sheet-overlay",    "Contact bottom sheet"),
        "contacts_list": ("contacts-list",    "Contacts list container"),
        "history_section":("history-section", "Report history section"),
        "proc_list":     ("proc-list",        "Processing per-report list"),
        "email_status":  ("email-status",     "Email status indicator"),
    }
    for check, (el_id, label) in dom_checks.items():
        if f'id="{el_id}"' not in page and f"id='{el_id}'" not in page:
            issues.append({"check": check,
                           "reason": f"#{el_id} element missing — {label} not rendered"})

    # ── Layer 3: Logic & safety ───────────────────────────────────────────────

    # 19. Promise.allSettled
    if page.count("Promise.allSettled") < 1:
        issues.append({"check": "promise_all_settled",
                       "reason": "Promise.allSettled not found — one failing report will block all others"})

    # 20-22. Required functions
    fn_checks = {
        "load_contacts": ("loadContacts",  "Contacts won't load on page open"),
        "load_history":  ("loadHistory",   "Report history won't display"),
        "resend_report": ("resendReport",  "Resend button has no handler"),
    }
    for check, (fn_name, reason) in fn_checks.items():
        if f"function {fn_name}" not in page and f"async function {fn_name}" not in page:
            issues.append({"check": check, "reason": f"{fn_name} function missing — {reason}"})

    # 23. report_contacts table
    if "report_contacts" not in page:
        issues.append({"check": "contacts_table",
                       "reason": "report_contacts not queried — contacts feature non-functional"})

    # 24. hive_id scoping on contacts
    if "report_contacts" in page:
        contacts_block = page[page.find("report_contacts"):][:500]
        if "hive_id" not in contacts_block:
            issues.append({"check": "hive_id_scoping",
                           "reason": "hive_id not scoped on report_contacts query — contacts leak across hives"})

    # 25. Transcript cap
    if "transcript" in page and ".slice(0," not in page:
        issues.append({"check": "transcript_cap",
                       "reason": "Voice transcript not length-capped — long transcripts could bloat edge function payload"})

    # ── Layer 4: Edge functions & PWA ─────────────────────────────────────────

    # 26. send-report-email exists
    if not send_fn:
        issues.append({"check": "send_email_exists",
                       "reason": f"{SEND_EMAIL_FN} not found — email delivery non-functional"})

    # 27. RESEND_API_KEY
    if send_fn and "RESEND_API_KEY" not in send_fn:
        issues.append({"check": "resend_key",
                       "reason": "RESEND_API_KEY not referenced in send-report-email — emails will never send"})

    # 28. voice-report-intent exists
    if not voice_fn:
        issues.append({"check": "voice_intent_exists",
                       "reason": f"{VOICE_INTENT_FN} not found — voice parsing non-functional"})

    # 29. voice-report-intent imports callAI
    if voice_fn and "callAI" not in voice_fn:
        issues.append({"check": "voice_intent_chain",
                       "reason": "voice-report-intent does not use callAI — bypasses multi-provider fallback chain"})

    # 30. scheduled-agents accepts voice_context
    if sched_fn and "voice_context" not in sched_fn:
        issues.append({"check": "scheduled_voice_ctx",
                       "reason": "scheduled-agents does not accept voice_context — voice enrichment silently ignored"})

    # 31. manifest start_url
    if not manifest:
        issues.append({"check": "manifest_start_url",
                       "reason": f"{MANIFEST} not found — PWA installs to wrong start page"})
    elif "report-sender.html" not in manifest:
        issues.append({"check": "manifest_start_url",
                       "reason": "start_url in manifest does not point to report-sender.html"})

    # 32. sw.js fetch handler
    if not sw:
        issues.append({"check": "sw_fetch",
                       "reason": f"{SW} not found — PWA not installable (Chrome requires service worker)"})
    elif "fetch" not in sw:
        issues.append({"check": "sw_fetch",
                       "reason": "sw.js has no fetch handler — Chrome will not recognise page as installable PWA"})

    # 34-36. iOS voice support (voice-transcribe + audio-chain + MediaRecorder)
    voice_t = read_file(VOICE_TRANSCRIBE_FN)
    audio_c = read_file(AUDIO_CHAIN_FN)

    if not voice_t:
        issues.append({"check": "voice_transcribe_exists",
                       "reason": f"{VOICE_TRANSCRIBE_FN} not found — iOS voice transcription non-functional"})
    if not audio_c:
        issues.append({"check": "audio_chain_exists",
                       "reason": f"{AUDIO_CHAIN_FN} not found — Groq Whisper fallback chain missing"})
    elif "WHISPER_CHAIN" not in audio_c:
        issues.append({"check": "audio_chain_exists",
                       "reason": "audio-chain.ts exists but WHISPER_CHAIN not defined — no fallback models"})
    if page and "MediaRecorder" not in page:
        issues.append({"check": "media_recorder_path",
                       "reason": "MediaRecorder not referenced in report-sender.html — iOS voice will not work"})

    # 33. Bottom sheet HTML before <script> block (DOM ordering)
    # Root cause of April 2026 bug: chips disappeared because #cancel-contact-btn
    # was declared after the script, returned null, crashed entire script on load.
    script_match = re.search(r'<script>\s*\n', page or '')
    if script_match and page:
        script_pos  = script_match.start()
        html_before = page[:script_pos]
        for el_id in ["cancel-contact-btn", "save-contact-btn", "sheet-overlay"]:
            if f'id="{el_id}"' not in html_before and f"id=\'{el_id}\'" not in html_before:
                issues.append({"check": "dom_ordering",
                               "reason": f"#{el_id} declared AFTER the <script> block — getElementById returns null, TypeError crashes entire script (unrelated sections break too)"})
                break

    return format_result(CHECK_NAMES, CHECK_LABELS, issues)


if __name__ == "__main__":
    n_pass, n_skip, n_fail = run()
    total = len(CHECK_NAMES)
    with open("report_sender_report.json", "w") as f:
        json.dump({"pass": n_pass, "skip": n_skip, "fail": n_fail, "total": total}, f, indent=2)

    print(f"\nReport Sender Validator: {n_pass}/{total} PASS", end="")
    if n_fail:
        print(f"  — {n_fail} FAIL")
        sys.exit(1)
    else:
        print(" — all checks passed")
        sys.exit(0)
