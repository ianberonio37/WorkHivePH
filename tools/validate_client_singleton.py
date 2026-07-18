#!/usr/bin/env python3
"""
validate_client_singleton.py  --  LOCK for the raw-createClient / idle-session-bypass class.

Bug class (found live 2026-07-06, deep-walk dim-14 "idle / expired-session"):
a shared client module or page builds its OWN Supabase client via `supabase.createClient(...)`
instead of routing through the shared `window.getDb()` singleton in utils.js. Consequences:
  1. It skips getDb()'s Finding-#6 auth config (autoRefreshToken + persistSession) and the
     visibilitychange getSession() refresh -> the module 401s on its first read after the tab
     idles (the "broken signed-in dashboard" bug).
  2. It skips the fail-fast timeout fetch wrapper (a dead backend hangs the tab).
  3. It spawns a SECOND GoTrueClient racing on the same localStorage auth key
     ("Multiple GoTrueClient instances detected"), producing undefined auth behaviour.

Found on voice-handler.js + search-overlay.js (both lazy-loaded on every page via nav-hub.js),
fixed to route through window.getDb() with a raw fallback.

Contract enforced: every real `supabase.createClient(` call OUTSIDE utils.js must EITHER
  (b) live in a file that ALSO calls `getDb(`  (createClient is only the documented fallback), OR
  (c) carry an explicit `singleton-exempt` marker within +/-3 lines (standalone public page /
      test-only battery that intentionally does not load utils.js).
utils.js itself (the canonical singleton home) is always exempt (a).

Usage:  python tools/validate_client_singleton.py [--json] [--selftest]
Exit 0 = clean, 1 = violations (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent

# A REAL createClient call: `supabase.createClient(` immediately followed by an argument
# token (identifier / string). This deliberately does NOT match doc-comment mentions like
# `supabase.createClient()` (empty) or `supabase.createClient(...)` (ellipsis).
CALL_RE = re.compile(r"supabase\.createClient\s*\(\s*['\"A-Za-z_$]")
GETDB_RE = re.compile(r"\bgetDb\s*\(")
EXEMPT_RE = re.compile(r"singleton-exempt")

# utils.js is the canonical singleton home. Never flag it.
CANONICAL = {"utils.js"}


def scanned_files():
    # Shared JS modules + pages at repo root, plus the feedback subdirectory page.
    for p in sorted(ROOT.glob("*.js")):
        yield p
    for p in sorted(ROOT.glob("*.html")):
        yield p
    fb = ROOT / "feedback" / "index.html"
    if fb.exists():
        yield fb


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def analyze(text, fname):
    """Return list of violation dicts for one file's text."""
    if fname in CANONICAL:
        return []
    viols = []
    has_getdb = bool(GETDB_RE.search(text))
    lines = text.splitlines()
    for m in CALL_RE.finditer(text):
        ln = line_of(text, m.start())
        # (b) file routes through the singleton -> createClient is the documented fallback.
        if has_getdb:
            continue
        # (c) explicit exemption marker within +/-3 lines of the call.
        lo, hi = max(0, ln - 4), min(len(lines), ln + 3)
        if EXEMPT_RE.search("\n".join(lines[lo:hi])):
            continue
        viols.append({"file": fname, "line": ln})
    return viols


def scan(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return analyze(text, path.name)


def selftest():
    """Synthetic regression shapes: the real bug must FAIL, the fixes must PASS."""
    cases = [
        # name, text, expect_violation
        ("raw-bypass (the bug)",
         "let _db=null; function g(){ _db = window.supabase.createClient(URL, KEY); return _db; }",
         True),
        ("routes-through-getDb (the fix)",
         "function g(){ if (window.getDb) _db = window.getDb(URL, KEY); "
         "else _db = window.supabase.createClient(URL, KEY); }",
         False),
        ("exempt marker (standalone public page)",
         "// singleton-exempt: public standalone page, no utils.js\n"
         "const db = supabase.createClient(URL, KEY);",
         False),
        ("doc-comment mention only (not a real call)",
         "// Calling `supabase.createClient()` more than once triggers the warning.",
         False),
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
        print("client-singleton selftest:", "OK" if rc == 0 else "FAILED")
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
        print("client-singleton (every Supabase client routes through getDb() for idle-refresh)")
        if not all_viols:
            print(f"  PASS: 0 raw-createClient bypasses across {n} files")
        else:
            print(f"  FAIL: {len(all_viols)} raw createClient(s) bypass getDb():")
            for v in all_viols:
                print(f"    {v['file']}:{v['line']}  raw supabase.createClient() (route via getDb or mark singleton-exempt)")
    return 1 if all_viols else 0


if __name__ == "__main__":
    sys.exit(main())
