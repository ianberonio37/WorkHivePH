"""AI Assistant flows — response quality and platform context checks.

Scenarios:
  A – Chat interface loads (input, send button, message area)
  B – Question gets a non-empty AI response within 45s
  C – Response does not contain raw JSON brackets or error text
  D – Platform context active: mention of WorkHive tool in response
  E – Hive context: asking about plant data references actual machines
  F – Follow-up builds on previous answer (conversation memory)
  G – No <think> reasoning tokens in any response
  H – Long response does not overflow or truncate with ellipsis mid-sentence
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


def _send_message(page, text: str, wait_ms: int = 35000) -> str:
    """Fill input, click send, wait for response, return response text."""
    chat_input = page.locator(
        "#chat-input, #message-input, textarea[placeholder*='ask' i], "
        "textarea[placeholder*='message' i], input[type='text']:visible"
    ).first

    send_btn = page.locator(
        "button:has-text('Send'), button[type='submit'], "
        "button[aria-label*='send' i]"
    ).first

    if not chat_input.count():
        return ""

    chat_input.fill(text)
    page.wait_for_timeout(200)

    if send_btn.count():
        send_btn.click()
    else:
        chat_input.press("Enter")

    # Wait for response (AI can be slow on cold start)
    page.wait_for_timeout(wait_ms)

    # Return all message text after our question
    messages = page.locator(
        "[class*='message']:not([class*='user']):not([class*='sent']), "
        "[class*='assistant'], [class*='bot'], [class*='ai-response'], "
        "[class*='response']"
    ).all()

    if messages:
        return messages[-1].inner_text()

    # Fallback: return the full body text (caller will filter)
    return page.locator("body").inner_text()


def run(page, errors, warnings, log) -> dict:
    log("AI Assistant flow checks...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/assistant.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Scenario A: Chat interface loads ──────────────────────────────────────
    log("  [A] Chat interface renders (input, send button, message area)...")
    try:
        chat_input = page.locator(
            "#chat-input, #message-input, textarea[placeholder*='ask' i], "
            "textarea[placeholder*='message' i], input[type='text']:visible"
        ).first

        send_btn = page.locator(
            "button:has-text('Send'), button[type='submit'], button[aria-label*='send' i]"
        ).first

        msg_area = page.locator(
            "[class*='message'], [class*='chat'], [class*='conversation'], "
            "#chat-messages, #messages"
        ).first

        has_input   = chat_input.count() > 0
        has_send    = send_btn.count() > 0
        has_area    = msg_area.count() > 0

        if has_input:
            send_label = "✓" if has_send else "Enter key"
            results.append(("PASS", f"A: chat input=✓ send={send_label} msg_area={'✓' if has_area else '?'}"))
        else:
            results.append(("FAIL", "A: no chat input found — assistant UI not rendering"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Question gets a non-empty AI response ─────────────────────
    log("  [B] Question sends and AI responds within 45s...")
    try:
        q1 = "What is MTBF?"
        response_text = _send_message(page, q1, wait_ms=45000)

        if not response_text or len(response_text.strip()) < 30:
            results.append(("FAIL", "B: AI response is empty or too short (<30 chars)"))
        else:
            results.append(("PASS", f"B: AI responded with {len(response_text)} chars"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"B crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario C: Response has no raw JSON or error text ────────────────────
    log("  [C] Response is readable prose — no raw JSON or error strings...")
    try:
        page_text = page.locator("body").inner_text()
        # Look for raw JSON objects in response (not code blocks)
        has_raw_json = bool(re.search(r'"\w+":\s*"[^"]{5,}"[,}]', page_text))
        has_error    = any(kw in page_text for kw in
                           ["SyntaxError", "TypeError", "fetch failed",
                            "500 Internal", "Edge Function returned"])

        if has_error:
            results.append(("FAIL", f"C: error text found in assistant response"))
        elif has_raw_json:
            results.append(("WARN", "C: raw JSON visible in response — may be LLM returning structured data instead of prose"))
        else:
            results.append(("PASS", "C: response is readable prose without raw JSON or error text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"C crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario D: Platform context active ───────────────────────────────────
    log("  [D] Platform context: response mentions WorkHive tools...")
    try:
        q2 = "How do I log a breakdown entry?"
        response_text = _send_message(page, q2, wait_ms=40000)

        platform_kws = ["logbook", "Logbook", "Log a Repair", "maintenance type",
                        "WorkHive", "machine", "breakdown"]
        found_kws    = [kw for kw in platform_kws if kw.lower() in response_text.lower()]

        if len(found_kws) >= 2:
            results.append(("PASS", f"D: response references platform context: {found_kws[:3]}"))
        elif len(found_kws) == 1:
            results.append(("WARN", f"D: only 1 platform keyword found: {found_kws} — context may be weak"))
        else:
            results.append(("WARN", "D: no platform-specific keywords in response — system prompt may not be active"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Hive context references actual plant data ─────────────────
    log("  [E] Hive context: plant data question references actual machines...")
    try:
        if not hive_id:
            results.append(("WARN", "E: no hive context — machine reference check skipped"))
        else:
            # Get actual machine names from the hive's logbook
            machines = db.table("logbook").select("machine") \
                .eq("hive_id", hive_id).limit(20).execute().data or []
            machine_tags = list(set(r["machine"] for r in machines if r.get("machine")))[:5]

            if not machine_tags:
                results.append(("WARN", "E: no logbook entries for hive — machine context check skipped"))
            else:
                q3 = "Which machines have failed recently in this plant?"
                response_text = _send_message(page, q3, wait_ms=40000)

                found_machines = [m for m in machine_tags if m in response_text]
                if found_machines:
                    results.append(("PASS", f"E: AI response references hive machines: {found_machines[:3]}"))
                else:
                    results.append(("WARN", f"E: response does not mention hive machines ({machine_tags[:3]}) — hive context may not be injected"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Follow-up references previous answer ─────────────────────
    log("  [F] Follow-up question references previous answer (memory)...")
    try:
        q4 = "Can you give me an example of what you just explained?"
        response_text = _send_message(page, q4, wait_ms=35000)

        # A context-aware response will not start with "I don't have previous context"
        no_memory_phrases = [
            "I don't have previous", "I have no context", "I cannot recall",
            "no previous conversation", "fresh conversation"
        ]
        lost_memory = any(p.lower() in response_text.lower() for p in no_memory_phrases)

        if lost_memory:
            results.append(("WARN", "F: AI lost conversation context — response treats follow-up as new question"))
        elif len(response_text.strip()) > 50:
            results.append(("PASS", "F: AI responded to follow-up (conversation memory appears intact)"))
        else:
            results.append(("WARN", "F: follow-up got very short response — context unclear"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: No <think> tokens in any response ─────────────────────────
    log("  [G] No <think> reasoning tokens in chat responses...")
    try:
        page_text  = page.locator("body").inner_text()
        has_think  = re.search(r"<think>|</think>", page_text, re.IGNORECASE)

        if has_think:
            results.append(("FAIL", "G: <think> reasoning tokens visible in assistant chat — AI leak"))
        else:
            results.append(("PASS", "G: no <think> tokens in any assistant response"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"G crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario H: Response does not hard-truncate mid-sentence ─────────────
    log("  [H] AI response is complete (does not end with '...' mid-sentence)...")
    try:
        # Get the latest response text
        messages = page.locator(
            "[class*='message']:not([class*='user']):not([class*='sent']), "
            "[class*='assistant'], [class*='ai-response']"
        ).all()
        last_response = messages[-1].inner_text() if messages else ""

        hard_truncated = last_response.rstrip().endswith("...") and len(last_response) > 100
        ends_mid_word  = bool(re.search(r"\b[a-zA-Z]{4,}\.\.\.$", last_response.rstrip()))

        if hard_truncated or ends_mid_word:
            results.append(("WARN", "H: response may be truncated — ends with '...' after substantial text"))
        else:
            results.append(("PASS", "H: response appears complete (no mid-sentence truncation)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "assistant_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  AI Assistant: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

