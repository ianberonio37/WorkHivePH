#!/usr/bin/env python3
"""critic_edge_fn_copy - grade the COPY an edge function speaks to a person (2026-09-06).

The critic deepwalk's 38 P-F rows carry `no_ui_basis`: an edge function has no page to walk, so the
UI rubric could not reach them and they sat `pending` forever - a permanent drag on the program that
"covered-by-nature" would have quietly accepted. But a function DOES speak to people: every `error`
string it returns is rendered by the client verbatim (a toast, a banner, an inline notice). That copy
is gradeable by the same rules the page lenses use, so the structure that makes these rows live-able
is this file - not a redefinition of the target.

Three dims per function, each MEASURED against its own returned strings:
  B3  readability  - every user-facing string <= 20 words and FK grade <= 8 (the page rule)
  E4  actionable   - a FAILURE string tells the person what to do next (retry / check / sign in /
                     contact / a named field), not only what broke. A 4xx that names the missing
                     field IS actionable; a bare "Internal error" is not.
  G3  no-leak      - no stack frame, SQL, driver text, env name or internal cast in the string a
                     person reads (a leak is both an ugly message and an information leak)

  python tools/critic_edge_fn_copy.py                 # report every function, exit 1 if any dim fails
  python tools/critic_edge_fn_copy.py --write         # bank the verdicts onto the pending P-F rows
  python tools/critic_edge_fn_copy.py --fn ai-gateway
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FNS = ROOT / "supabase" / "functions"
CRITIC = ROOT / "critic_registry.json"

# a string returned to the client. THREE call styles, because a function that speaks through a shared helper speaks
# just as loudly (2026-09-06): the object key, the fail(ctx, code, message) helper, and a RAW error value passed straight
# back to the caller - the last one is a finding in itself, never copy.
STR_RE = re.compile(r"""(?:error|message|detail|hint)\s*:\s*(['"`])(?P<s>(?:\\.|(?!\1).){6,200})\1""")
FAILFN_RE = re.compile(r"""\bfail\s*\(\s*\w+\s*,\s*['"][\w.\-]+['"]\s*,\s*(['"`])(?P<s>(?:\\.|(?!\1).){4,200})\1""")
# a local error responder taking the message FIRST: project-orchestrator's errJson('...', 405, req). Without this the
# function reads as "no user-facing string" while every one of its replies is a sentence (2026-09-06).
ERRFN_RE = re.compile(r"""\b(?:errJson|jsonError|errorResponse|badRequest|errResponse|sendError)\s*\(\s*(['"`])(?P<s>(?:\\.|(?!\1).){4,200})\1""")
# ONLY an exception identifier counts as raw: `tenancy.message` / `gate.message` carry curated copy from
# _shared (tenant-context.ts: "Sign-in required."), and flagging those would be the instrument inventing a defect.
# The key must be a real OBJECT KEY: `(?<![\w.])` keeps the pattern out of `err.message` and out of the ternary
# `err instanceof Error ? err.message : String(err)`, which is an assignment to a local, not a reply to a person.
RAW_RE = re.compile(r"""(?<![\w.])(?:error|message)\s*:\s*String\s*\(\s*(?:err|error|e|ex|exception)\s*\)"""
                    r"""|(?<![\w.])(?:error|message)\s*:\s*(?:err|e|ex|exception)\s*[,)}\n]"""   # not bare `error`: `errJson(error: string)` passes curated copy under that name
                    r"""|(?<![\w.])(?:error|message)\s*:\s*(?:err|error|e|ex|exception)\.message\b"""
                    r"""|(?<![\w.])(?:error|message)\s*:\s*\(?\s*(?:err|error|e|ex)\s+as\s+Error\s*\)?\.message"""
                    r"""|\bfail\s*\(\s*\w+\s*,\s*['"][\w.\-]+['"]\s*,\s*\(?\s*(?:err|error|e|ex)\s+as\s+Error\s*\)?\.message"""
                    r"""|\bfail\s*\(\s*\w+\s*,\s*['"][\w.\-]+['"]\s*,\s*String\s*\(\s*(?:err|error|e|ex)\s*\)""")
LEAK_RE = re.compile(r"(at\s+\w+\s*\(|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE FROM\b|SUPABASE_[A-Z_]+|[A-Z][A-Z0-9_]{6,}_(URL|KEY|SECRET|TOKEN))")   # UPPERCASE only: SQL and env names leak verbatim, while "Insert failed" is prose (2026-09-06)
LEAK_CI_RE = re.compile(r"(\bpg_[a-z]+|\berrno\b|::[a-z_]+\b|process\.env|Deno\.env|\bstack trace\b)", re.I)
ACTION_RE = re.compile(r"\b(try again|retry|check|sign in|log in|contact|ask|refresh|wait|reduce|shorten|choose|provide|include|use|set|add|remove|upgrade|top up|missing|required|must be|expected|only|cap|limit|max|at most|later|shortly|smaller|fewer|try|fill|reload|split|again|retried|retries|automatically|no action|send)\b", re.I)
FAILISH = re.compile(r"\b(fail|failed|error|unavailable|could not|couldn't|cannot|denied|invalid|missing|not allowed|too many|timeout|timed out|unauthor)", re.I)


def syllables(w: str) -> int:
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w:
        return 1
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def fk_grade(t: str) -> float:
    words = [w for w in re.split(r"\s+", t.strip()) if re.search(r"[a-zA-Z]", w)]
    if not words:
        return 0.0
    sents = max(1, len(re.findall(r"[.!?]+", t)) or 1)
    sy = sum(syllables(w) for w in words)
    return 0.39 * (len(words) / sents) + 11.8 * (sy / len(words)) - 15.59


def strings_of(src: str) -> list:
    out = []
    for m in list(STR_RE.finditer(src)) + list(FAILFN_RE.finditer(src)) + list(ERRFN_RE.finditer(src)):
        s = m.group("s").replace("\\n", " ").replace('\\"', '"').strip()
        bare = re.sub(r"\$\{[^}]*\}", "", s).strip()
        if "${" in s and len(bare) < 6:          # a pure interpolation, not prose
            continue
        s = re.sub(r"\$\{[^}]*\}", "<value>", s)
        if len(s) < 6 or s.startswith("http"):
            continue
        # a machine CODE is not copy: login returns {error: "invalid_credentials", message: "Wrong username or password."}
        # - the code is for the client's own switch, the message is what a person reads (2026-09-06)
        if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", s):
            continue
        out.append(s)
    return sorted(set(out))


def grade(fn_dir: Path) -> dict:
    src = ""
    for f in sorted(fn_dir.rglob("*.ts")):
        try:
            src += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass
    ss = strings_of(src)
    # a RAW error value handed straight to the caller is not copy at all: the person is shown whatever the runtime
    # threw ("TypeError: x is undefined", a Postgres detail). It is a G3 finding wherever it appears (2026-09-06).
    # ...but only where it reaches a CLIENT RESPONSE. `.catch((err) => ({ data: null, error: err }))` is an internal
    # result object and `errJson(error: string, ...)` is a helper whose parameter happens to be named `error`; neither
    # is copy. Grade the windows that actually serialize a reply (2026-09-06).
    windows = []
    for m in re.finditer(r"(JSON\.stringify\s*\(|jsonResponse\s*\(|\bjson\s*\(|\bfail\s*\()", src):
        windows.append(src[m.end(): m.end() + 260])
    raws = sorted(set(m.group(0).strip() for w in windows for m in RAW_RE.finditer(w)))
    long_ones = [s for s in ss if len(s.split()) > 20]
    # FK is noise below a real sentence: the page rubric grades only >=12-word sentences, and a 6-word error
    # ("AI providers all at capacity. Try again shortly.") scores >8 purely because its words are polysyllabic.
    # grade the WORDS a person reads: a <value> placeholder is a runtime number, not vocabulary (it cost
    # "Property data not available for <value> at evap <value>C" a whole grade level)
    hard = [s for s in ss if len(s.split()) >= 12 and fk_grade(s.replace("<value>", "")) > 8]
    leaks = [s for s in ss if LEAK_RE.search(s) or LEAK_CI_RE.search(s)]
    # an OPS SUMMARY is not a failure message: "Scanned 12 hive(s). 3 alerts upserted. 1 error." is a cron's own
    # report to a log, and it matched FAILISH on the word "error". A failure string is one a person is SHOWN.
    OPSISH = re.compile(r"^(Generated|Scanned|Scored|Processed|Synced|Upserted|Sent|Queued|Skipped|Backfilled)", re.I)
    fails = [s for s in ss if FAILISH.search(s) and not OPSISH.match(s)]
    mute = [s for s in fails if not ACTION_RE.search(s)]
    dims = []
    if ss or raws:
        worst = (long_ones or hard)
        dims.append(("B3", not long_ones and not hard,
                     "%d user-facing string(s) - over-20-words=%d - grade-over-8=%d%s"
                     % (len(ss), len(long_ones), len(hard),
                        (' - worst: "%s"' % worst[0][:60]) if worst else "")))
        dims.append(("E4", not mute,
                     "%d failure string(s) - without a next step: %d%s"
                     % (len(fails), len(mute), (' - e.g. "%s"' % mute[0][:60]) if mute else "")))
        dims.append(("G3", not leaks and not raws,
                     "%d string(s) leak internals, %d raw error value(s) returned%s"
                     % (len(leaks), len(raws),
                        (' - e.g. "%s"' % (leaks or raws)[0][:60]) if (leaks or raws) else "")))
    return {"fn": fn_dir.name, "strings": len(ss), "dims": dims}


def main() -> int:
    only = sys.argv[sys.argv.index("--fn") + 1] if "--fn" in sys.argv else None
    write = "--write" in sys.argv
    rows = []
    # _shared is graded too: it is where most of the platform's returned copy actually lives (tenant-context's
    # "Sign-in required.", observability's "An unexpected error occurred."), reached through tenancy.message
    for d in sorted(p for p in FNS.iterdir() if p.is_dir() and (not p.name.startswith("_") or p.name == "_shared")):
        if only and d.name != only:
            continue
        rows.append(grade(d))
    bad = 0
    for r in rows:
        if not r["dims"]:
            print("  n/a  %-34s no user-facing string to grade" % r["fn"])
            continue
        fails = [d for d in r["dims"] if not d[1]]
        bad += 1 if fails else 0
        print("  %s %-34s %s" % ("FAIL" if fails else "ok  ", r["fn"],
                                 " - ".join("%s %s" % (k, "ok" if ok else "FAIL") for k, ok, _ in r["dims"])))
        for k, ok, note in r["dims"]:
            if not ok:
                print("        %s: %s" % (k, note[:150]))
    print("%s edge-fn-copy - %d/%d functions speak clean, actionable, leak-free copy"
          % ("FAIL" if bad else "PASS", len(rows) - bad, len(rows)))

    if write:
        reg = json.loads(CRITIC.read_text(encoding="utf-8"))
        by_fn = {r["fn"]: r for r in rows}
        moved = 0
        # ★A RECEIPT MUST BE DATED WHEN IT WAS EARNED, AND COUNT WHAT IT ACTUALLY COUNTED (2026-09-10).
        # These were literals - walked_at "2026-09-06" and "62/62 functions" - so every later run banked a
        # receipt four days stale claiming a total that had already moved (63 functions today, all clean).
        # A banked receipt is evidence; evidence carrying the wrong date and the wrong denominator is the
        # kind of quiet drift this program keeps finding in other people's tools. Derived from the run.
        today = _dt.date.today().isoformat()
        n_clean = sum(1 for r in rows if all(ok for _, ok, _ in r["dims"]))
        n_total = len(rows)
        for row in reg["rows"]:
            # a row this instrument already critiqued is RE-graded: when its function now speaks clean copy, the row
            # closes to `improving` with a receipt, exactly as tools/close_critic_findings.py closes a page row
            if row.get("status") not in ("pending", "critiqued") or not (row.get("no_ui_basis") or ""):
                continue
            m = re.search(r"supabase/functions/([\w-]+)", row.get("no_ui_basis", ""))
            r = by_fn.get(m.group(1)) if m else None
            if not r or not r["dims"]:
                continue
            row["dims_graded"] = [k for k, _, _ in r["dims"]]
            row["walked_at"] = today
            row["findings"] = [
                {"dim": k, "layer": "floor", "severity": 2, "owner": "AI Engineer",
                 "evidence": "supabase/functions/%s: %s - %s" % (r["fn"], k, note),
                 "receipt": "tools/critic_edge_fn_copy.py (%s)" % today}
                for k, ok, note in r["dims"] if not ok]
            row["clean_note"] = ("Graded by tools/critic_edge_fn_copy.py over the %d strings this function returns to a "
                                 "person (the copy a client renders verbatim): %s"
                                 % (r["strings"], " - ".join("%s %s" % (k, "ok" if ok else "FAIL") for k, ok, _ in r["dims"])))
            had = bool(row.get("findings"))
            if not row["findings"]:
                row["status"] = "improving"
                row["improvement_refs"] = [
                    "tools/critic_edge_fn_copy.py %s: supabase/functions/%s now passes B3/E4/G3 "
                    "(gate edge-fn-copy, %d/%d functions clean)" % (today, r["fn"], n_clean, n_total)]
            else:
                row["status"] = "critiqued"
                row.pop("improvement_refs", None)
            moved += 1
        reg["count"] = len(reg["rows"])
        tmp = CRITIC.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, CRITIC)
        print("banked: %d P-F row(s) pending -> critiqued with dims + findings" % moved)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
