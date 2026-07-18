#!/usr/bin/env python3
"""
validate_voice_journal_single_write.py  --  LOCK for the voice-journal DOUBLE-WRITE class.

Bug (found live 2026-07-07, deep-walk dim-4 "write-CRUD + DB/FK verify"):
the companion voice path (voice-handler.js `_converseInline`) routes a spoken turn through
`ai-gateway` with `agent: 'voice-journal'`. Because 'voice-journal' is a SEMANTIC_RECALL_AGENT,
ai-gateway ALREADY persists that (transcript, answer) turn to `voice_journal_entries` SERVER-SIDE
via persistJournalEntry() -- with an embedding + server-resolved attribution. The client success
path (and the low-confidence clarify path) then ALSO called `_saveJournalTurn(...)`, inserting a
SECOND row for the identical turn: an embedding-less duplicate (meta.source='voice-handler',
lang='en'). Net effect: every companion voice turn was journaled TWICE -- the history UI showed
each turn twice and the recall index carried a dead (un-embedded) copy.

Proven live: one gateway turn -> 2 rows (a server row w/ embedding + a client row w/o). Fixed by
DELETING the client `_saveJournalTurn` on the two post-successful-gateway paths (success + clarify);
the server-side persist is the single source of truth there. `_saveJournalTurn` legitimately REMAINS
on paths the gateway never reached: the local conversational shortcuts (greet / goodbye / thanks /
switch / recommend / negative / unhandled), the agentic-rag-loop short-circuit, and the offline
fallback INSIDE the gateway `catch` (gateway threw -> server did NOT persist -> client save is the
only writer).

Contract enforced: inside any `agent: 'voice-journal'` gateway block (a gatewayBody whose fetch
targets /functions/v1/ai-gateway), NO uncommented client journal write -- neither `_saveJournalTurn(`
nor a direct `.from('voice_journal_entries').insert` -- may appear between the block start and the
try's `} catch` (the success + clarify portion). A write there re-introduces the double-write.

Usage:  python tools/validate_voice_journal_single_write.py [--json] [--selftest]
Exit 0 = clean, 1 = violations (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The companion conversational gateway call: agent:'voice-journal' whose block also fetches the
# ai-gateway front door. (The `agent:'voice-journal'` FIELD on an ai_reply_feedback insert is NOT
# a gateway call -- it has no ai-gateway fetch nearby -- so it is correctly ignored.)
AGENT_RE       = re.compile(r"agent\s*:\s*['\"]voice-journal['\"]")
GATEWAY_URL_RE = re.compile(r"/functions/v1/ai-gateway\b")
CATCH_RE       = re.compile(r"^\s*\}\s*catch\b")
# A client journal WRITE (either the helper or a direct insert).
CLIENT_WRITE_RE = re.compile(
    r"_saveJournalTurn\s*\(|\.from\(\s*['\"]voice_journal_entries['\"]\s*\)\s*\.insert"
)
COMMENT_LINE_RE = re.compile(r"^\s*(//|\*|/\*)")

# How far after the agent: line to look for the ai-gateway fetch (gatewayBody -> fetch gap).
FETCH_LOOKAHEAD = 40
# Safety cap on the try-body scan (start -> catch).
CATCH_LOOKAHEAD = 220


def scanned_files():
    for p in sorted(ROOT.glob("*.html")):
        yield p
    for p in sorted(ROOT.glob("*.js")):
        yield p
    fb = ROOT / "feedback" / "index.html"
    if fb.exists():
        yield fb


def analyze(text, fname):
    """Return list of violation dicts for one file's text."""
    viols = []
    lines = text.splitlines()
    n = len(lines)
    for m in AGENT_RE.finditer(text):
        start = text.count("\n", 0, m.start())  # 0-based line index of the agent: line
        # Confirm this is a GATEWAY call: an ai-gateway fetch within FETCH_LOOKAHEAD lines.
        win = "\n".join(lines[start:min(n, start + FETCH_LOOKAHEAD)])
        if not GATEWAY_URL_RE.search(win):
            continue  # not a gateway call (e.g. an ai_reply_feedback label field)
        # Find this try's `} catch` -- the boundary between the success/clarify portion
        # (must be write-free) and the offline fallback (client save is legit there).
        catch_idx = None
        for i in range(start, min(n, start + CATCH_LOOKAHEAD)):
            if CATCH_RE.match(lines[i]):
                catch_idx = i
                break
        hi = catch_idx if catch_idx is not None else min(n, start + CATCH_LOOKAHEAD)
        # Any uncommented client journal write in [start, catch) is a double-write.
        for i in range(start, hi):
            ln = lines[i]
            if COMMENT_LINE_RE.match(ln):
                continue
            if CLIENT_WRITE_RE.search(ln):
                viols.append({"file": fname, "line": i + 1, "code": ln.strip()[:90]})
    return viols


def scan(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return analyze(text, path.name)


def selftest():
    """Synthetic shapes: the double-write must FAIL; the fix (+ legit fallback-in-catch) must PASS."""
    bug = (
        "const gatewayBody = { agent: 'voice-journal', message: transcript, context: {} };\n"
        "const resp = await fetcher(SUPABASE_URL + '/functions/v1/ai-gateway', { body: JSON.stringify(gatewayBody) });\n"
        "const answer = String((data && data.answer) || '').trim();\n"
        "_appendSessionTurn(transcript, answer);\n"
        "_saveJournalTurn(db, ctx, transcript, answer, persona);\n"
        "_storeTurn(db, ctx.hive_id, ctx.worker_name, transcript, answer, k, c, 0);\n"
        "} catch (err) {\n"
        "  _saveJournalTurn(db, ctx, transcript, fallbackReply, persona);\n"
        "}\n"
    )
    fix = (
        "const gatewayBody = { agent: 'voice-journal', message: transcript, context: {} };\n"
        "const resp = await fetcher(SUPABASE_URL + '/functions/v1/ai-gateway', { body: JSON.stringify(gatewayBody) });\n"
        "const answer = String((data && data.answer) || '').trim();\n"
        "_appendSessionTurn(transcript, answer);\n"
        "// server already persisted this turn -- no client insert. [journal-single-write]\n"
        "_storeTurn(db, ctx.hive_id, ctx.worker_name, transcript, answer, k, c, 0);\n"
        "} catch (err) {\n"
        "  // offline: gateway threw so the server did NOT persist -> client save is the only writer\n"
        "  _saveJournalTurn(db, ctx, transcript, fallbackReply, persona);\n"
        "}\n"
    )
    direct_insert_bug = (
        "const gatewayBody = { agent: 'voice-journal', message: transcript };\n"
        "const resp = await fetch(SUPABASE_URL + '/functions/v1/ai-gateway', { body: JSON.stringify(gatewayBody) });\n"
        "const answer = String(data.answer || '').trim();\n"
        "await db.from('voice_journal_entries').insert({ auth_uid, transcript, reply: answer });\n"
        "} catch (err) { console.warn(err); }\n"
    )
    feedback_field = (   # agent:'voice-journal' as a FIELD, not a gateway call -> out of scope
        "await db.from('ai_reply_feedback').insert({\n"
        "  agent: 'voice-journal', source: 'voice', question, answer, rating: r,\n"
        "});\n"
    )
    shortcut_only = (    # local greeting shortcut, no gateway call -> _saveJournalTurn is legit
        "const greetReply = _composeGreeting(persona);\n"
        "_renderReplyBubble(greetReply, persona);\n"
        "_saveJournalTurn(db, ctx, transcript, greetReply, persona);\n"
        "return;\n"
    )
    cases = [
        ("double-write on gateway success path (the bug)", bug, True),
        ("server-only + fallback-in-catch (the fix)", fix, False),
        ("direct insert on gateway success path (the bug, inlined)", direct_insert_bug, True),
        ("agent:'voice-journal' feedback field (not a gateway call)", feedback_field, False),
        ("local shortcut _saveJournalTurn, no gateway (legit)", shortcut_only, False),
    ]
    ok = True
    for name, text, expect in cases:
        got = bool(analyze(text, "synthetic.js"))
        status = "PASS" if got == expect else "FAIL"
        if got != expect:
            ok = False
        print(f"  selftest {status}: {name}  (expected violation={expect}, got={got})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("voice-journal single-write selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    all_viols = []
    n = 0
    for p in scanned_files():
        n += 1
        all_viols.extend(scan(p))
    if as_json:
        print(json.dumps({"violations": all_viols, "count": len(all_viols)}, indent=2))
    else:
        print("voice-journal single-write (companion gateway path relies on server persist; no client duplicate)")
        if not all_viols:
            print(f"  PASS: no client journal write on any agent:'voice-journal' gateway success path ({n} files scanned)")
        else:
            print(f"  FAIL: {len(all_viols)} client journal write(s) inside a gateway 'voice-journal' success path (double-write):")
            for v in all_viols:
                print(f"    {v['file']}:{v['line']}  {v['code']}")
                print("      -> the ai-gateway 'voice-journal' call already persisted this turn server-side "
                      "(with an embedding); remove the client insert (it is a double-write). "
                      "Client saves belong ONLY on non-gateway paths (shortcuts / RAG short-circuit / offline catch).")
    return 1 if all_viols else 0


if __name__ == "__main__":
    sys.exit(main())
