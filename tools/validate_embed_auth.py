#!/usr/bin/env python3
"""
validate_embed_auth.py  --  LOCK for the client-drops-JWT / tenancy-gated-edge-fn-401 class.

Bug class (found live 2026-07-07, deep-walk dim-4 "write-CRUD + DB/FK verify"):
a browser page POSTs to a tenancy-gated edge function with `hive_id` in the body but
WITHOUT forwarding the user's session JWT as `Authorization: Bearer <access_token>`.
`embed-entry` runs `verify_jwt=false` on a service-role client and, on the manual (browser)
path, runs a Pillar I tenancy check (`resolveIdentity`+`resolveTenancy`) whenever `hive_id`
is set. With no `Authorization` header the identity resolves to null and the call 401s
("Sign-in required." / code=auth_required) -- so the embedding is SILENTLY dropped and the
skill / fault / PM entry never reaches the RAG (semantic-search) index. The write itself
succeeds; only the embedding signal is lost, so this is invisible to a self-test that only
checks the DB row.

Found on skillmatrix.html (embedSkillEntry), logbook.html (embedFaultEntry),
pm-scheduler.html (embedPMEntry). Fixed by forwarding
`(await db.auth.getSession()).data.session.access_token` as the bearer (apikey stays the anon
publishable key for the functions gateway) -- the exact fix analytics-orchestrator got 2026-06-07.

Contract enforced: every client `fetch`/`fetchWithTimeout` to one of TARGET_FNS must carry an
`Authorization` header within the fetch's options block. FAIL = a call whose header block omits
`Authorization` (the JWT is not forwarded -> the tenancy check 401s).

Usage:  python tools/validate_embed_auth.py [--json] [--selftest]
Exit 0 = clean, 1 = violations (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Tenancy-gated edge fns that require the caller to forward the user session JWT when the
# browser passes hive_id. Grow this list as new caller-auth checks ship (see the ai-engineer
# skill "anon-key-as-bearer is a platform-wide legacy convention -- audit whenever you add a
# caller-auth check").
TARGET_FNS = ["embed-entry", "semantic-search"]

# A client call to the fn: the URL appears as `.../functions/v1/<fn>` inside a fetch(...) arg.
URL_RE = {fn: re.compile(r"/functions/v1/" + re.escape(fn) + r"\b") for fn in TARGET_FNS}
AUTH_RE = re.compile(r"Authorization")
# The headers object always precedes the body in these calls; bound the window at `body:`.
BODY_RE = re.compile(r"\bbody\s*:")
# Only a REAL call counts: the URL must sit on a line that invokes fetch/fetchWithTimeout
# (inside a template literal). This excludes doc-comment / TODO prose that merely names the
# endpoint (e.g. voice-handler.js "Wire this to a real /functions/v1/embed-entry call ...").
FETCH_LINE_RE = re.compile(r"\bfetch(?:WithTimeout)?\s*\(")
COMMENT_LINE_RE = re.compile(r"^\s*(//|\*|/\*)")


def scanned_files():
    for p in sorted(ROOT.glob("*.html")):
        yield p
    for p in sorted(ROOT.glob("*.js")):
        yield p
    fb = ROOT / "feedback" / "index.html"
    if fb.exists():
        yield fb


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def analyze(text, fname):
    """Return list of violation dicts for one file's text."""
    viols = []
    lines = text.splitlines()
    for fn, rx in URL_RE.items():
        for m in rx.finditer(text):
            ln = line_of(text, m.start())  # 1-based
            url_line = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
            # Skip doc-comment / TODO mentions: only a line that actually invokes fetch(...) is a call.
            if COMMENT_LINE_RE.match(url_line) or not FETCH_LINE_RE.search(url_line):
                continue
            # Window: from the URL line forward to the fetch's `body:` (headers precede it),
            # capped at 14 lines so a stray later body: can't widen it unboundedly.
            lo = ln - 1
            hi = min(len(lines), ln + 14)
            window_lines = lines[lo:hi]
            # trim at the first body: so we only inspect the headers portion of THIS call
            trimmed = []
            for wl in window_lines:
                trimmed.append(wl)
                if BODY_RE.search(wl):
                    break
            window = "\n".join(trimmed)
            if not AUTH_RE.search(window):
                viols.append({"file": fname, "line": ln, "fn": fn})
    return viols


def scan(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return analyze(text, path.name)


def selftest():
    """Synthetic regression shapes: the real bug must FAIL, the fix must PASS."""
    bug = (
        "await fetchWithTimeout(`${SUPABASE_URL}/functions/v1/embed-entry`, {\n"
        "  method: 'POST',\n"
        "  headers: { 'Content-Type': 'application/json' },\n"
        "  body: JSON.stringify({ type: 'skill', hive_id: HIVE_ID || null })\n"
        "}, 8000);"
    )
    fix = (
        "const { data: { session: _s } } = await db.auth.getSession();\n"
        "const _tok = _s?.access_token || SUPABASE_KEY;\n"
        "await fetchWithTimeout(`${SUPABASE_URL}/functions/v1/embed-entry`, {\n"
        "  method: 'POST',\n"
        "  headers: { 'Content-Type': 'application/json', 'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + _tok },\n"
        "  body: JSON.stringify({ type: 'skill', hive_id: HIVE_ID || null })\n"
        "}, 8000);"
    )
    unrelated = (
        "await fetch(`${SUPABASE_URL}/functions/v1/some-public-fn`, {\n"
        "  headers: { 'Content-Type': 'application/json' }, body: '{}' });"
    )
    comment_mention = (
        "  // Wire this to a real /functions/v1/embed-entry call when that path is\n"
        "  // exposed without requiring an auth.uid. TODO closes when that work lands.\n"
        "  async function _embedQuery(_t) { return null; }"
    )
    cases = [
        ("no-Authorization embed-entry call (the bug)", bug, True),
        ("JWT-forwarding embed-entry call (the fix)", fix, False),
        ("call to a non-target fn (out of scope)", unrelated, False),
        ("doc-comment mention only (not a real call)", comment_mention, False),
    ]
    ok = True
    for name, text, expect in cases:
        got = bool(analyze(text, "synthetic.html"))
        status = "PASS" if got == expect else "FAIL"
        if got != expect:
            ok = False
        print(f"  selftest {status}: {name}  (expected violation={expect}, got={got})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("embed-auth selftest:", "OK" if rc == 0 else "FAILED")
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
        print("embed-auth (client fetch to a tenancy-gated edge fn forwards the user JWT)")
        if not all_viols:
            print(f"  PASS: every embed-entry client call forwards Authorization ({n} files scanned)")
        else:
            print(f"  FAIL: {len(all_viols)} embed-entry call(s) omit the Authorization header:")
            for v in all_viols:
                print(f"    {v['file']}:{v['line']}  POST /functions/v1/{v['fn']} without Authorization "
                      f"(forward (await db.auth.getSession()).data.session.access_token as Bearer)")
    return 1 if all_viols else 0


if __name__ == "__main__":
    sys.exit(main())
