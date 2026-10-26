"""
AI Companion Orchestration + Integration Validator (turns #65-#74)
===================================================================
Forward-only L0 ratchet for the seventh 10-turn flywheel batch (2026-05-21).
Covers ORCHESTRATION + INTEGRATION — pdf export, pronunciation overrides,
voice-execute safety lock, persona portrait animation, cross-hive
benchmark RPC, daily digest, push notifications, multi-worker concurrency
lock, accent adaptation, streaming SSE.

  T65  PDF export request detector
  T66  Custom pronunciation library
  T67  Voice execute lock (safety gate)
  T68  Persona portrait animation state
  T69  Cross-hive benchmark RPC wiring
  T70  Daily digest mode
  T71  Push notification readiness
  T72  Multi-worker concurrency lock
  T73  Accent / voice signature adaptation
  T74  Streaming SSE response indicator

10-layer audit.
"""

from __future__ import annotations

import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
from steering_moved import gone  # BRH-AP 2026-10-27
from validator_utils import read_file, format_result


VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


def check_pdf_export(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isPdfExportRequest" not in c:
        issues.append({"check": "pdf_export",
                       "reason": "_isPdfExportRequest missing — 'save as PDF' / 'i-PDF mo ito' can't be detected."})
    if "_PDF_EXPORT_RE" not in c:
        issues.append({"check": "pdf_export",
                       "reason": "_PDF_EXPORT_RE missing — detector has no regex to match against."})
    if "PDF EXPORT REQUEST" not in c and not gone("PDF EXPORT REQUEST"):
        issues.append({"check": "pdf_export",
                       "reason": "PDF EXPORT REQUEST anchor missing — detector wired but LLM has no instruction."})
    return issues


def check_pronunciation(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_PRONUNCIATION_KEY", "_getPronunciationMap",
                "_setPronunciationOverride", "_applyPronunciation"):
        if sym not in c and not gone(sym):
            issues.append({"check": "pronunciation",
                           "reason": f"{sym} missing — custom pronunciation library doesn't persist or apply."})
    if "PRONUNCIATION RESPECT" not in c:
        issues.append({"check": "pronunciation",
                       "reason": "PRONUNCIATION RESPECT anchor missing — overrides stored but LLM still says it the STT way."})
    if "wh_pronunciation_overrides" not in c:
        issues.append({"check": "pronunciation",
                       "reason": "localStorage key wh_pronunciation_overrides missing — overrides don't survive reload."})
    return issues


def check_voice_execute_lock(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isVoiceExecuteAuth", "_setVoiceExecuteAuth"):
        if sym not in c and not gone(sym):
            issues.append({"check": "voice_execute_lock",
                           "reason": f"{sym} missing — voice-execute safety gate is dead code."})
    if "VOICE EXECUTE LOCK" not in c:
        issues.append({"check": "voice_execute_lock",
                       "reason": "VOICE EXECUTE LOCK anchor missing — write-verb intents would auto-dispatch even when device hasn't opted in."})
    if "wh_voice_execute_authorised" not in c:
        issues.append({"check": "voice_execute_lock",
                       "reason": "localStorage key wh_voice_execute_authorised missing — opt-in doesn't persist."})
    return issues


# ★THE LOCK REFUSED EVERY CONFIRM, AND THIS CHECK STAYED GREEN (LM-V companion-voice walk, 2026-10-07).
# check_voice_execute_lock asserts the lock EXISTS. It does - and once T79 wired _preflightAction into
# _confirm, it refused every intent on every page, because nothing a person could reach ever set
# wh_voice_execute_authorised and the refusal pointed at a Settings toggle that does not exist. The
# fix scopes the lock to handlers that write by themselves, which is only safe while each page's
# declared effect is TRUE - so this check asserts the three things that keep it true:
#   1. the lock in _preflightAction is conditioned on effect 'write' (a lock on everything is what
#      made Confirm unusable; a lock on nothing is what makes a writing handler unguarded);
#   2. every WHVoice.register call in a page declares an effect, and the handler of a 'read' or
#      'prefill' declaration does not itself write (db insert/upsert/update/delete, an rpc, a REST
#      call, or a form submit) - a handler that saves by itself must say 'write' and get the Save press;
#   3. neither the refusal copy nor the companion's prompt sends the person to a Settings toggle.
# Limitation, stated: (2) reads the handler's own body, not the functions it calls.
_VOICE_EFFECTS = ("read", "prefill", "write")
_HANDLER_WRITE_RX = re.compile(
    r"\.from\(\s*['\"][^'\"]+['\"]\s*\)\s*\.\s*(?:insert|upsert|update|delete)\s*\("
    r"|\.rpc\s*\(|/rest/v1/|\.(?:submit|requestSubmit)\s*\(",
    re.S,
)
_REGISTER_RX = re.compile(
    r"WHVoice\.register\(\s*['\"]([\w.]+)['\"]\s*,\s*([A-Za-z_$][\w$]*)\s*(?:,\s*\{([^}]*)\})?\s*\)")


def _function_body(src: str, name: str) -> str | None:
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(src) and depth:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return src[m.end():i - 1]


def check_voice_effect_pages(pages: dict[str, str]) -> list[dict]:
    issues: list[dict] = []
    for page, src in sorted(pages.items()):
        for m in _REGISTER_RX.finditer(src):
            kind, handler, opts = m.group(1), m.group(2), m.group(3) or ""
            em = re.search(r"effect\s*:\s*['\"](\w+)['\"]", opts)
            effect = em.group(1) if em else None
            if effect not in _VOICE_EFFECTS:
                issues.append({"check": "voice_effect_scope",
                               "reason": f"{page}: WHVoice.register('{kind}', {handler}) declares no effect "
                                         f"('read' | 'prefill' | 'write') - it falls back to 'write' and every "
                                         f"Confirm on it needs a second Save press."})
                continue
            if effect == "write":
                continue
            body = _function_body(src, handler)
            if body is None:
                issues.append({"check": "voice_effect_scope",
                               "reason": f"{page}: handler {handler} for '{kind}' not found - its declared "
                                         f"'{effect}' effect cannot be checked."})
                continue
            w = _HANDLER_WRITE_RX.search(body)
            if w:
                issues.append({"check": "voice_effect_scope",
                               "reason": f"{page}: {handler} is declared '{effect}' for '{kind}' but writes "
                                         f"({w.group(0).strip()[:40]}) - a voice Confirm would save with no "
                                         f"further press. Declare 'write', or leave the save to the person."})
    return issues


def check_voice_effect_scope(c: str, pages: dict[str, str]) -> list[dict]:
    issues: list[dict] = []
    m = re.search(r"function\s+_preflightAction\s*\(", c)
    pre = _function_body(c, "_preflightAction") if m else None
    if not pre:
        issues.append({"check": "voice_effect_scope", "reason": "_preflightAction not found."})
    else:
        lock = re.search(r"if\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*\{\s*return\s*\{\s*ok:\s*false,\s*blocker:\s*'voice_execute_lock'", pre)
        if not lock:
            issues.append({"check": "voice_effect_scope",
                           "reason": "the voice_execute_lock refusal in _preflightAction is no longer found."})
        elif not re.search(r"effect\s*===\s*'write'", lock.group(1)):
            issues.append({"check": "voice_effect_scope",
                           "reason": "the voice execute lock is not scoped to effect 'write' - it refuses read "
                                     "and pre-fill intents too, which made every companion Confirm unusable."})
        elif "savePressed" not in lock.group(1):
            issues.append({"check": "voice_effect_scope",
                           "reason": "the write lock has no person-reachable key: the Save press "
                                     "(savePressed) must open it."})
    if "function register(kind, handler, opts)" not in c or "_handlerEffects[kind]" not in c:
        issues.append({"check": "voice_effect_scope",
                       "reason": "register() no longer records the page's declared effect."})

    # copy a person reads or the companion speaks: the blocker message and the prompt anchor
    blk = re.search(r"case 'voice_execute_lock':(.*?)case '", c, re.S)
    anchor = re.search(r"const voiceExecuteLockAnchor\s*=(.*?);\s*\n", c, re.S)
    for label, mm in (("refusal message", blk), ("companion prompt anchor", anchor)):
        if mm:
            text = "\n".join(ln.split("//")[0] for ln in mm.group(1).splitlines())
            if re.search(r"\bsettings\b", text, re.I):
                issues.append({"check": "voice_effect_scope",
                               "reason": f"the voice-lock {label} names a Settings toggle - none exists, so it "
                                         f"sends the person looking for a control that is not there."})
    issues += check_voice_effect_pages(pages)
    return issues


def _read_pages() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in sorted(os.listdir(".")):
        if name.endswith(".html"):
            try:
                src = read_file(name) or ""
            except Exception:
                continue
            if "WHVoice.register" in src:
                out[name] = src
    return out


# ★"VOICE NEEDS A HIVE", SAID AFTER A SOLO OWNER HAD SPOKEN (LM-V walk, LM473, 2026-10-07). _onStopRecording
# refused every hive-less person once their recording was finished, because voice-action-router answered a call
# with no hive_id 400. Neither refusal was true: no step of voice needs a hive (transcribe primes on one only if
# present, the router can resolve a person's OWN register, the gateway grounds a hive-less answer in the verified
# caller's own records). What it needs is to know who is speaking. This check holds all of that in place:
#   1. _onStopRecording never refuses on a missing hive (the person has already spoken by then);
#   2. the one refusal left - no hive AND no session - happens in _startRecording BEFORE getUserMedia;
#   3. the transcribe call and the conversational gateway call carry the caller's token, not the bare publishable
#      key (with that key every caller is anonymous, and the gateway's solo snapshot has nobody to read for);
#   4. voice-action-router refuses a missing hive only AFTER it has looked for a verified identity, and its asset
#      lookup reads a hive-less person's own register (hive_id IS NULL + their auth_uid) - never an unscoped read.
ROUTER_TS = os.path.join("supabase", "functions", "voice-action-router", "index.ts")
_NO_HIVE_RX = re.compile(r"if\s*\(\s*!\s*(?:ctx|_ctx\(\)|ctxNow)\s*\.\s*hive_id\s*\)")


def _read_router() -> str:
    return read_file(ROUTER_TS) or ""


def _ts_function_body(src: str, name: str) -> str | None:
    """Like _function_body, for a TypeScript signature: multi-line params and a return-type annotation sit between
    the parameter list and the body, so match the parens first and take the next brace."""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(src) and depth:
        depth += {"(": 1, ")": -1}.get(src[i], 0)
        i += 1
    brace = src.find("{", i)
    if brace < 0:
        return None
    return _function_body(src[:m.start()] + "function " + name + "() " + src[brace:], name)


def check_voice_hiveless(c: str, router: str) -> list[dict]:
    issues: list[dict] = []
    stop = _function_body(c, "_onStopRecording")
    if stop is None:
        issues.append({"check": "voice_hiveless", "reason": "_onStopRecording not found."})
    else:
        code = "\n".join(ln.split("//")[0] for ln in stop.splitlines())
        if _NO_HIVE_RX.search(code) or re.search(r"needs a hive", code, re.I):
            issues.append({"check": "voice_hiveless",
                           "reason": "_onStopRecording refuses a person with no hive AFTER they have recorded - "
                                     "say any refusal before the mic opens (_startRecording), and only the true one."})
    start = _function_body(c, "_startRecording")
    if start is None:
        issues.append({"check": "voice_hiveless", "reason": "_startRecording not found."})
    else:
        mic = start.find("getUserMedia(")
        sess = start.find("_sessionState(")
        if mic < 0:
            issues.append({"check": "voice_hiveless", "reason": "_startRecording no longer opens the mic."})
        elif sess < 0 or sess > mic:
            issues.append({"check": "voice_hiveless",
                           "reason": "the who-is-speaking check (_sessionState) is not made before getUserMedia - a "
                                     "person who cannot use voice must be told before they record, not after."})
        refusal = re.search(r"(?:needs a hive|sign in)", start, re.I)
        if refusal and mic >= 0 and refusal.start() > mic:
            issues.append({"check": "voice_hiveless",
                           "reason": "a refusal sentence in _startRecording comes after the mic opens."})
    # 3. the two calls that identify the person to the server
    tr = re.search(r"/functions/v1/voice-transcribe'[^)]*?headers:\s*\{([^}]*)\}", c, re.S)
    if not tr:
        issues.append({"check": "voice_hiveless", "reason": "the voice-transcribe call was not found."})
    elif re.search(r"'Bearer '\s*\+\s*SUPABASE_KEY", tr.group(1)):
        issues.append({"check": "voice_hiveless",
                       "reason": "voice-transcribe is called with the bare publishable key - the person is anonymous "
                                 "to it, so no hive is ever proven and the limit is not keyed on them."})
    jm = re.search(r"agent:\s*'voice-journal',", c)
    gw = re.search(r"/functions/v1/ai-gateway',\s*\{(.*?)body:\s*JSON\.stringify\(gatewayBody\)", c[jm.end():], re.S) if jm else None
    if not gw:
        issues.append({"check": "voice_hiveless", "reason": "the companion's voice-journal gateway call was not found."})
    elif re.search(r"'Bearer '\s*\+\s*SUPABASE_KEY", gw.group(1)):
        issues.append({"check": "voice_hiveless",
                       "reason": "the conversational gateway call sends the bare publishable key - the gateway sees "
                                 "nobody, so a solo owner's answer is grounded in none of their own records."})
    # 4. the server step that used to refuse
    if not router:
        issues.append({"check": "voice_hiveless", "reason": f"{ROUTER_TS} not found."})
    else:
        rc = "\n".join(ln.split("//")[0] for ln in router.splitlines())
        ident = rc.find("resolveIdentity(db, req)")
        miss = rc.find("Missing required field: hive_id")
        if ident < 0:
            issues.append({"check": "voice_hiveless", "reason": "voice-action-router no longer resolves the caller."})
        elif miss >= 0 and miss < ident:
            issues.append({"check": "voice_hiveless",
                           "reason": "voice-action-router refuses a missing hive_id before it looks for a verified "
                                     "identity - a signed-in solo owner is answered 400 for being hive-less."})
        rac = _ts_function_body(rc, "resolveAssetCandidates")
        if rac is None:
            issues.append({"check": "voice_hiveless", "reason": "resolveAssetCandidates not found."})
        else:
            if not re.search(r"""\.is\(\s*["']hive_id["']\s*,\s*null\s*\)\s*\.eq\(\s*["']auth_uid["']""", rac):
                issues.append({"check": "voice_hiveless",
                               "reason": "resolveAssetCandidates has no own-register branch (hive_id IS NULL + the "
                                         "caller's auth_uid) - a solo owner's machines can never resolve."})
            if not re.search(r"if\s*\(\s*!hiveId\s*&&\s*!ownerUid\s*\)\s*return\s*\[\]", rac):
                issues.append({"check": "voice_hiveless",
                               "reason": "resolveAssetCandidates can run with neither a hive nor an owner - on the "
                                         "service-role client that is an unscoped read of every register."})
    return issues


# ★A SCREEN-READER USER WHO ASKED BY VOICE HEARD NOTHING BACK (LM-V walk, LM490, assistive-tech persona,
# 2026-10-07). The overlay's status, reply and result were plain divs inside the dialog, and the one announcer the
# file had (_announceForScreenReader) had NO caller - validate_ai_companion_accessibility certified it by name.
# This check asserts the wiring, not the presence: a live status line, both live regions INSIDE the dialog markup,
# the final reply and result actually routed to them (a failure to the role=alert one), and the thinking render
# never announced.
def check_voice_live_regions(c: str) -> list[dict]:
    issues: list[dict] = []
    m = re.search(r"const OVERLAY_HTML\s*=\s*`(.*?)`;", c, re.S)
    ov = m.group(1) if m else ""
    if not ov:
        return [{"check": "voice_live_regions", "reason": "OVERLAY_HTML not found."}]
    dlg = re.search(r'<div id="wh-voice-overlay"[^>]*>', ov)
    if not dlg or 'role="dialog"' not in dlg.group(0) or 'aria-labelledby="wh-voice-status"' not in dlg.group(0):
        issues.append({"check": "voice_live_regions",
                       "reason": "the overlay is no longer a dialog labelled by #wh-voice-status."})
    st = re.search(r'<div id="wh-voice-status"[^>]*>', ov)
    if not st or 'role="status"' not in st.group(0) or 'aria-live="polite"' not in st.group(0):
        issues.append({"check": "voice_live_regions",
                       "reason": "#wh-voice-status is not a polite live region - Listening / Transcribing / the "
                                 "failure headline change in silence for a screen-reader user."})
    lv = re.search(r'<div id="wh-voice-aria-live"[^>]*>', ov)
    if not lv or 'aria-live="polite"' not in lv.group(0):
        issues.append({"check": "voice_live_regions",
                       "reason": "the polite announcer #wh-voice-aria-live is not in the dialog markup - a region "
                                 "outside an aria-modal dialog is outside what is read while it is open."})
    if not re.search(r'<div id="wh-voice-alert"[^>]*role="alert"', ov):
        issues.append({"check": "voice_live_regions",
                       "reason": "no role=alert region in the dialog - a failure sentence waits behind the queue."})
    sr = _function_body(c, "_setResult") or ""
    if not re.search(r"isError\)\s*_announceAlert\(", sr) or "_announceForScreenReader(" not in sr:
        issues.append({"check": "voice_live_regions",
                       "reason": "_setResult does not announce: what Confirm did is never heard, and a failure "
                                 "must go to the alert region."})
    rb = _function_body(c, "_renderReplyBubble") or ""
    ann = rb.find("_announceForScreenReader(")
    els = rb.find("} else {")
    if ann < 0:
        issues.append({"check": "voice_live_regions",
                       "reason": "_renderReplyBubble never announces the reply - the answer is drawn, not said."})
    elif els < 0 or ann < els:
        issues.append({"check": "voice_live_regions",
                       "reason": "_renderReplyBubble announces in the thinking-dots render - an intermediate "
                                 "state is spoken."})
    ri = _function_body(c, "_renderIntents") or ""
    if "_announceForScreenReader(" not in ri:
        issues.append({"check": "voice_live_regions",
                       "reason": "_renderIntents never announces what Confirm would act on."})
    return issues


def check_avatar_animation(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_setAvatarAnimation" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "_setAvatarAnimation missing — persona portrait can't animate per state."})
    if "_AVATAR_ANIM_STATES" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "_AVATAR_ANIM_STATES list missing — animation states aren't allow-listed."})
    if "data-avatar-anim" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "data-avatar-anim DOM attribute never set — CSS animation hook is unreachable."})
    # Open() should set 'listening'; close() should set 'idle'.
    if "_setAvatarAnimation('listening')" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "open() doesn't set 'listening' state — avatar never reflects mic-hot."})
    if "_setAvatarAnimation('idle')" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "close() doesn't reset to 'idle' — avatar stays on prior state across opens."})
    return issues


def check_cross_hive_rpc(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_fetchCrossHiveBenchmark" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_fetchCrossHiveBenchmark missing — T54 CROSS-HIVE BENCHMARK anchor has no real RPC backing it."})
    if "_CROSS_HIVE_RPC" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_CROSS_HIVE_RPC constant missing — RPC name not bound."})
    if "fn_cross_hive_benchmark" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "RPC fn_cross_hive_benchmark not referenced — wiring incomplete."})
    if "_benchmarkCache" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_benchmarkCache missing — every turn hammers the RPC instead of caching."})
    return issues


def check_digest(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isDigestRequest" not in c:
        issues.append({"check": "digest",
                       "reason": "_isDigestRequest missing — 'morning summary' can't flip into digest mode."})
    if "_DIGEST_RE" not in c:
        issues.append({"check": "digest",
                       "reason": "_DIGEST_RE missing — detector has no regex."})
    if "DIGEST MODE" not in c and not gone("DIGEST MODE"):
        issues.append({"check": "digest",
                       "reason": "DIGEST MODE anchor missing — LLM has no 5-line briefing instruction."})
    return issues


def check_push(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_canPushNotify", "_pushNotifyState",
                "_requestPushPerm", "_isPushOptInReply", "_PUSH_OPT_IN_RE"):
        if sym not in c and not gone(sym):
            issues.append({"check": "push",
                           "reason": f"{sym} missing — push notification path is incomplete."})
    if "PUSH READINESS" not in c and not gone("PUSH READINESS"):
        issues.append({"check": "push",
                       "reason": "PUSH READINESS anchor missing — companion would promise alerts the browser may have denied."})
    return issues


def check_session_lock(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_SESSION_LOCK_TTL_MS", "_sessionLockKey",
                "_acquireSessionLock", "_isSessionLocked", "_releaseSessionLock"):
        if sym not in c and not gone(sym):
            issues.append({"check": "session_lock",
                           "reason": f"{sym} missing — multi-worker concurrency lock is incomplete."})
    if "wh_voice_session_lock_" not in c:
        issues.append({"check": "session_lock",
                       "reason": "localStorage key prefix wh_voice_session_lock_ missing — lock doesn't persist across devices."})
    if "_acquireSessionLock(ctxOpen.hive_id" not in c:
        issues.append({"check": "session_lock",
                       "reason": "open() doesn't acquire the lock — helper exists but never runs."})
    if "_releaseSessionLock(ctxClose.hive_id" not in c:
        issues.append({"check": "session_lock",
                       "reason": "close() doesn't release the lock — stale lock would block the same worker for 10 min."})
    return issues


def check_accent(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectAccentHint", "_getAccentPref",
                "_setAccentPref", "_TGL_HINT_WORDS"):
        if sym not in c and not gone(sym):
            issues.append({"check": "accent",
                           "reason": f"{sym} missing — accent / voice signature adaptation is incomplete."})
    if "ACCENT MATCH" not in c:
        issues.append({"check": "accent",
                       "reason": "ACCENT MATCH anchor missing — accent detected but LLM has no instruction to mirror."})
    if "wh_voice_accent_pref" not in c:
        issues.append({"check": "accent",
                       "reason": "localStorage key wh_voice_accent_pref missing — accent pref doesn't survive reload."})
    return issues


def check_streaming(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_setStreamingState", "_isStreaming",
                "_bindStreamingBubble", "_appendStreamingChunk", "_finalizeStream"):
        if sym not in c and not gone(sym):
            issues.append({"check": "streaming",
                           "reason": f"{sym} missing — streaming SSE incremental update is incomplete."})
    if "data-streaming" not in c:
        issues.append({"check": "streaming",
                       "reason": "data-streaming DOM attribute never set — CSS cursor indicator can't react."})
    return issues


CHECK_NAMES = [
    "pdf_export", "pronunciation", "voice_execute_lock", "voice_effect_scope",
    "voice_hiveless", "voice_live_regions",
    "avatar_animation", "cross_hive_rpc", "digest",
    "push", "session_lock", "accent", "streaming",
]

CHECK_LABELS = {
    "pdf_export":         "T65 _isPdfExportRequest + _PDF_EXPORT_RE + PDF EXPORT REQUEST anchor",
    "pronunciation":      "T66 _PRONUNCIATION_KEY + _getPronunciationMap / _setPronunciationOverride / _applyPronunciation + PRONUNCIATION RESPECT anchor",
    "voice_execute_lock": "T67 _isVoiceExecuteAuth + _setVoiceExecuteAuth + VOICE EXECUTE LOCK anchor + wh_voice_execute_authorised key",
    "voice_effect_scope": "T67b lock scoped to effect 'write' + opened by the Save press; every WHVoice.register declares an effect; no 'read'/'prefill' handler writes; no copy names a Settings toggle",
    "voice_hiveless":     "T67c (LM473) no hive refusal after recording; the only refusal (no hive AND no session) precedes getUserMedia; transcribe + answer carry the caller's token; voice-action-router serves a verified hive-less caller from their own register, never unscoped",
    "voice_live_regions": "T128b (LM490) #wh-voice-status is a polite live region; polite + role=alert regions inside the dialog; final reply, intent card and result announced once (failure to the alert), thinking render never",
    "avatar_animation":   "T68 _setAvatarAnimation + _AVATAR_ANIM_STATES + data-avatar-anim + open/close wiring",
    "cross_hive_rpc":     "T69 _fetchCrossHiveBenchmark + _CROSS_HIVE_RPC + fn_cross_hive_benchmark + _benchmarkCache",
    "digest":             "T70 _isDigestRequest + _DIGEST_RE + DIGEST MODE anchor",
    "push":               "T71 _canPushNotify + _pushNotifyState + _requestPushPerm + _isPushOptInReply + _PUSH_OPT_IN_RE + PUSH READINESS anchor",
    "session_lock":       "T72 _SESSION_LOCK_TTL_MS + _sessionLockKey + acquire/check/release + key prefix + open/close wiring",
    "accent":             "T73 _detectAccentHint + _getAccentPref + _setAccentPref + _TGL_HINT_WORDS + ACCENT MATCH anchor + wh_voice_accent_pref",
    "streaming":          "T74 _setStreamingState + _isStreaming + _bindStreamingBubble + _appendStreamingChunk + _finalizeStream + data-streaming attribute",
}


def main() -> int:
    print("\033[1m\nAI Companion Orchestration + Integration Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_pdf_export(c)
    issues += check_pronunciation(c)
    issues += check_voice_execute_lock(c)
    issues += check_voice_effect_scope(c, _read_pages())
    issues += check_voice_hiveless(c, _read_router())
    issues += check_voice_live_regions(c)
    issues += check_avatar_animation(c)
    issues += check_cross_hive_rpc(c)
    issues += check_digest(c)
    issues += check_push(c)
    issues += check_session_lock(c)
    issues += check_accent(c)
    issues += check_streaming(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


def self_test() -> int:
    """Teeth for voice_hiveless + voice_live_regions: each re-introduced defect must FAIL, the shipped files PASS."""
    import subprocess
    c, router = _read(), _read_router()

    def fails(name, fn, *args):
        return any(i["check"] == name for i in fn(*args))

    def head(path):
        try:
            return subprocess.run(["git", "show", "HEAD:" + path.replace(os.sep, "/")], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=30).stdout
        except Exception:
            return ""

    def mut(src, old, new):
        # a mutation that does not apply would make its case pass vacuously - refuse it instead
        if old not in src:
            raise SystemExit(f"self-test mutation no longer applies: {old[:60]!r}")
        return src.replace(old, new, 1)

    # read_file opens in text mode, so the CRLF file arrives here with LF line ends
    nl = "\n"
    old_refusal = ("    const ctx = _ctx();" + nl + "    if (!ctx.hive_id) {" + nl
                   + "      _setStatus('Voice needs a hive. Join or create one first.');" + nl
                   + "      return;" + nl + "    }" + nl)
    cases = [
        ("shipped files pass voice_hiveless", not fails("voice_hiveless", check_voice_hiveless, c, router)),
        ("shipped file passes voice_live_regions", not fails("voice_live_regions", check_voice_live_regions, c)),
        ("post-record hive refusal re-inserted -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            mut(c, "    const ctx = _ctx();" + nl + "    // No hive check here", old_refusal + "    // No hive check here"),
            router)),
        ("pre-mic session check removed -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            mut(c, "(await _sessionState()) === 'out'", "false"), router)),
        ("answer call back on the publishable key -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            mut(c, "'Authorization': 'Bearer ' + _gwBearer", "'Authorization': 'Bearer ' + SUPABASE_KEY"), router)),
        ("transcribe back on the publishable key -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            mut(c, "'Authorization': 'Bearer ' + _tBearer", "'Authorization': 'Bearer ' + SUPABASE_KEY"), router)),
        ("router refuses a missing hive before identity -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            c, mut(router, "    // Cap transcript per ai-engineer skill",
                   '    if (!hive_id) return new Response(JSON.stringify({ error: "Missing required field: hive_id" }));'
                   + nl + "    // Cap transcript per ai-engineer skill"))),
        ("router unscoped-read guard removed -> FAIL", fails("voice_hiveless", check_voice_hiveless,
            c, mut(router, "if (!hiveId && !ownerUid) return [];", ""))),
        ("status line not live -> FAIL", fails("voice_live_regions", check_voice_live_regions,
            mut(c, 'class="wh-voice-status" role="status" aria-live="polite"', 'class="wh-voice-status"'))),
        ("reply never announced -> FAIL", fails("voice_live_regions", check_voice_live_regions,
            mut(c, "      _announceForScreenReader(text);" + nl + "      // Wire the rating buttons",
                "      // Wire the rating buttons"))),
        ("reply announced in the thinking render -> FAIL", fails("voice_live_regions", check_voice_live_regions,
            mut(mut(c, "      _announceForScreenReader(text);" + nl + "      // Wire the rating buttons",
                    "      // Wire the rating buttons"),
                "    if (text === null) {" + nl, "    if (text === null) {" + nl + "      _announceForScreenReader(text);" + nl))),
        ("failure not sent to the alert region -> FAIL", fails("voice_live_regions", check_voice_live_regions,
            mut(c, "if (isError) _announceAlert(text);", "if (isError) _announceForScreenReader(text);"))),
        ("alert region dropped from the dialog -> FAIL", fails("voice_live_regions", check_voice_live_regions,
            mut(c, '<div id="wh-voice-alert" class="wh-voice-sr" role="alert" aria-atomic="true"></div>', ""))),
    ]
    hv, hr = head(VOICE_HANDLER_JS), head(ROUTER_TS)
    if hv and hr:
        cases.append(("pre-fix HEAD voice-handler.js + router -> voice_hiveless FAIL",
                      fails("voice_hiveless", check_voice_hiveless, hv, hr)))
        cases.append(("pre-fix HEAD router alone -> voice_hiveless FAIL",
                      fails("voice_hiveless", check_voice_hiveless, c, hr)))
        cases.append(("pre-fix HEAD voice-handler.js -> voice_live_regions FAIL",
                      fails("voice_live_regions", check_voice_live_regions, hv)))
    ok = True
    for label, passed in cases:
        print(f"  {'ok  ' if passed else 'BAD '} {label}")
        ok = ok and passed
    print("SELF-TEST " + ("PASS" if ok else "FAIL") + f" ({len(cases)} cases)")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
