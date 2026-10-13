"""validate_ai_feedback_carries_trace.py - a "was this right?" rating names the call it judged.

THE CLASS (LM-E walk, 2026-10-08): public.ai_reply_feedback - where every 👍/👎 on an AI answer lands (the companion
launcher, the voice bubble, the Assistant chat, and the shared whAiTrustRow under Asset Brain / the voice journal /
the shift briefing / the analytics narrative / the resume polish) - stored the question and the answer TEXT and no id
for the call that produced the answer. The answering endpoint had already handed the page one: ai-gateway's envelope
{ ok, data, trace_id } (the wh_traces key) and agentic-rag-loop's trace_id (its agentic_rag_traces row). So a "wrong"
could be matched to its trace only by its words, which fails on a repeated question, a hydrated name, or an answer the
gateway rewrote at egress. Separately, the gateway had answers and refusals that carried no trace at all.

THE SECOND HALF (same day): thirteen surfaces called a specialist DIRECTLY, and those functions returned no id - they
logged one they never returned, or minted a throwaway per log line, or had none - so the walk measured a "wrong" on
project-manager's AI-drafted lessons landing with trace_id NULL. The first version of this gate accepted that as
"CANNOT"; a caller whose producer returns no id is now a FAILURE to fix at the function, not a state to list. The fix
is _shared/trace-reply.ts: tracedReply(route, handler) mints the id once and stamps it on every JSON reply.

THE RULES
  R1 WRITERS     every .from('ai_reply_feedback').insert({...}) in a production page/script sends a `trace_id` key.
  R2 AVAILABLE   a writer in a file that calls a TRACED endpoint sends an expression, never a bare null/undefined.
  R3 SHARED ROW  utils.js whAiTrustRow forwards opts.traceId into that key.
  R4 CALLERS     every whAiTrustRow(...) call rates an answer from a PRODUCER - the edge function its `agent` names when
                 that is a function this file calls, else the endpoints the file calls (a gateway agent label) - and
                 must pass a non-null `traceId` when that producer is TRACED. A producer that returns no id fails the
                 row (fix the function). A row may pass null only when its answer is a STORED row whose table keeps no
                 id, declared with a `trace-allow: <why>` comment on the call or the three lines above it.
  R5 NOT MINTED  a trace value is never made on the client (crypto / Math.random / randomUUID / the request-side
                 _whTrace ids): it is the id the endpoint RETURNED, or null.
  R6 SCHEMA      a migration adds ai_reply_feedback.trace_id.
  R7 GATEWAY     ai-gateway answers only through ok() (no flat 200 jsonResponse), every refusal built after
                 beginRequest() carries the request's trace id (jsonResponse(..., ctx.trace_id) / withTrace(...) around
                 the shared rate-limit helpers), and the specialist forward carries x-wh-trace: ctx.trace_id.
  R8 ONE ID      _shared/trace-reply.ts's tracedReply mints the id with beginRequest and returns every reply through
                 stampTraceId, which writes `trace_id` into the body; a function wrapped by it does not mint a second
                 id of its own (no beginRequest / newTraceId / logRequestStart call - it logs with the `trace` it is
                 handed).

TRACED (computed from the function sources, never listed by hand): a function's SUCCESS reply carries trace_id when it
answers through ok() (envelope.ts baseEnvelope sets trace_id), returns a JSON.stringify({...}) literal with a trace_id
key, or is wrapped `serveObserved("<fn>", tracedReply("<fn>", ...))` while the shared stamp passes R8.

    python tools/validate_ai_feedback_carries_trace.py               # PASS / FAIL over the working tree
    python tools/validate_ai_feedback_carries_trace.py --root DIR    # the same rules over another copy of the tree
    python tools/validate_ai_feedback_carries_trace.py --rev REV     # the same rules over a git revision (read via git)
    python tools/validate_ai_feedback_carries_trace.py --selftest    # the rules' teeth on fixed fixtures
Static, no DB, no browser.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

INSERT = re.compile(r"""\.from\(\s*['"]ai_reply_feedback['"]\s*\)\s*\.insert\(""")
# db.functions.invoke('fn' / a wrapper like invokeWithTimeout('fn' / a raw fetch to /functions/v1/fn
CALL = re.compile(r"""\b\w*[iI]nvoke\w*\(\s*['"]([\w-]+)['"]|functions/v1/([\w-]+)""")
TRUST_CALL = re.compile(r"(?<![\w$.])whAiTrustRow\(")
MINTED = re.compile(r"getRandomValues|Math\.random|randomUUID|\b_whTrace(?:Rag)?\b|Date\.now")
NULLISH = re.compile(r"^\s*(?:null|undefined|''|\"\")\s*$")
ALLOW = re.compile(r"trace-allow:\s*(\S.{14,})")
REFUSAL_HELPERS = re.compile(r"\b(soloRateLimitedResponse|userRateLimitedResponse|routeRateLimitedResponse|"
                             r"rateLimitedResponse|globalBudgetResponse)\(")
SHARED_REL = "supabase/functions/_shared/trace-reply.ts"


# ── where the sources come from: a directory, or a git revision ──────────────────────────────────────────────────
class FsTree:
    def __init__(self, root: Path):
        self.root = root
        self.label = str(root)

    def read(self, rel: str) -> str | None:
        p = self.root / rel
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None

    def root_files(self) -> list[str]:
        return sorted(p.name for p in list(self.root.glob("*.html")) + list(self.root.glob("*.js")))

    def function_dirs(self) -> list[str]:
        fdir = self.root / "supabase" / "functions"
        return sorted(d.name for d in fdir.iterdir() if (d / "index.ts").is_file()) if fdir.is_dir() else []

    def migrations(self) -> list[str]:
        mdir = self.root / "supabase" / "migrations"
        return sorted(f"supabase/migrations/{f.name}" for f in mdir.glob("*.sql")) if mdir.is_dir() else []


class GitTree:
    """the same files as FsTree, read from a git revision with one `git cat-file --batch` (no checkout, no stash)."""

    def __init__(self, repo: Path, rev: str):
        self.repo, self.rev, self.label = repo, rev, f"git {rev}"
        out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", rev],
                             capture_output=True, text=True, encoding="utf-8")
        if out.returncode != 0:
            raise SystemExit(f"git ls-tree {rev} failed: {out.stderr.strip()}")
        self.paths = set(out.stdout.splitlines())
        self._cache: dict[str, str | None] = {}

    def _load(self, rels: list[str]) -> None:
        want = [r for r in rels if r not in self._cache]
        if not want:
            return
        proc = subprocess.run(["git", "-C", str(self.repo), "cat-file", "--batch"],
                              input="".join(f"{self.rev}:{r}\n" for r in want).encode("utf-8"), capture_output=True)
        buf, pos = proc.stdout, 0
        for rel in want:
            nl = buf.index(b"\n", pos)
            head = buf[pos:nl].decode("utf-8", "replace").split()
            pos = nl + 1
            if len(head) < 3 or head[1] == "missing":
                self._cache[rel] = None
                continue
            size = int(head[2])
            self._cache[rel] = buf[pos:pos + size].decode("utf-8", "replace")
            pos += size + 1

    def read(self, rel: str) -> str | None:
        if rel not in self.paths:
            return None
        self._load([rel])
        return self._cache.get(rel)

    def prefetch(self, rels: list[str]) -> None:
        self._load([r for r in rels if r in self.paths])

    def root_files(self) -> list[str]:
        return sorted(p for p in self.paths if "/" not in p and p.endswith((".html", ".js")))

    def function_dirs(self) -> list[str]:
        return sorted({p.split("/")[2] for p in self.paths
                       if p.startswith("supabase/functions/") and p.count("/") == 3 and p.endswith("/index.ts")})

    def migrations(self) -> list[str]:
        return sorted(p for p in self.paths if p.startswith("supabase/migrations/") and p.endswith(".sql")
                      and p.count("/") == 2)


# ── small JS reader: balanced spans that skip strings and comments ───────────────────────────────────────────────
def _span(text: str, start: int, open_ch: str, close_ch: str) -> str:
    """text[start] must be open_ch; return the balanced span including both delimiters ('' if unbalanced)."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            q = c
            i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 1
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return ""


def _top_level_args(call_span: str) -> list[str]:
    """'(a, {b, c}, d)' -> ['a', '{b, c}', 'd'] (commas inside (), {}, [] and strings do not split)."""
    inner, args, depth, cur, i = call_span[1:-1], [], 0, [], 0
    while i < len(inner):
        c = inner[i]
        if c in "'\"`":
            q, j = c, i + 1
            while j < len(inner) and inner[j] != q:
                j += 2 if inner[j] == "\\" else 1
            cur.append(inner[i:j + 1])
            i = j + 1
            continue
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
        if c == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _strip_comments(src: str) -> str:
    """comments become blanks; every newline survives, so a line number in the result is the line in the source."""
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"\\])//[^\n]*", r"\1", out)


def _trace_value(literal: str) -> str | None:
    """the expression after a top-level `trace_id:` in an object literal, or None when the key is absent."""
    body = literal[1:-1]
    for arg in _top_level_args("(" + body + ")"):
        m = re.match(r"^\s*['\"]?trace_id['\"]?\s*:\s*(.+)$", arg, re.S)
        if m:
            return m.group(1).strip()
    return None


def _code_lines(src: str) -> str:
    """the source without comments and without import lines (an import names a helper; it does not call it)."""
    return "\n".join(ln for ln in _strip_comments(src).splitlines() if not ln.lstrip().startswith("import "))


# ── what the endpoints return ────────────────────────────────────────────────────────────────────────────────────
def check_stamp(src: str | None) -> list[str]:
    """R8 (shared half): tracedReply mints with beginRequest and returns through stampTraceId, which writes trace_id."""
    if src is None:
        return [f"R8 {SHARED_REL} not found - a function wrapped by tracedReply has no stamp"]
    code = _strip_comments(src)
    fails = []
    d = re.search(r"function\s+tracedReply\s*\([^)]*\)[^{]*\{", code)
    body = _span(code, d.end() - 1, "{", "}") if d else ""
    if not body:
        fails.append("R8 trace-reply.ts: no tracedReply(route, handler) function")
    else:
        if "beginRequest(" not in body:
            fails.append("R8 trace-reply.ts: tracedReply does not mint the request's id with beginRequest()")
        if not re.search(r"\breturn\s+(?:await\s+)?stampTraceId\(", body):
            fails.append("R8 trace-reply.ts: tracedReply does not return the handler's reply through stampTraceId()")
    s = re.search(r"function\s+stampTraceId\s*\([^)]*\)[^{]*\{", code)
    sbody = _span(code, s.end() - 1, "{", "}") if s else ""
    if not sbody:
        fails.append("R8 trace-reply.ts: no stampTraceId(res, traceId) function")
    elif not re.search(r"JSON\.stringify\(\s*\{[^;]*?\btrace_id\s*:", sbody, re.S):
        fails.append("R8 trace-reply.ts: stampTraceId does not write `trace_id` into the reply body - the id is dropped")
    return fails


def wrapped_by_traced_reply(name: str, src: str) -> bool:
    code = _strip_comments(src)
    return bool(re.search(r"""from\s+["']\.\./_shared/trace-reply\.ts["']""", code)) and bool(re.search(
        r"""serveObserved\(\s*["']""" + re.escape(name) + r"""["']\s*,\s*tracedReply\(\s*["']""" + re.escape(name)
        + r"""["']""", code))


def check_one_id(name: str, src: str) -> list[str]:
    """R8 (function half): a wrapped function logs with the trace it is handed and mints no second id."""
    code = _code_lines(src)
    return [f"R8 {name}: wrapped by tracedReply but calls {m.group(1)}() - a second id beside the one it returns; "
            f"log with the `trace` the wrapper hands the handler"
            for m in re.finditer(r"(?<![\w$.])(beginRequest|newTraceId|logRequestStart)\(", code)]


def fn_carries_trace(name: str, src: str, envelope_traces: bool, stamp_ok: bool) -> str | None:
    """how this function's success reply carries trace_id, or None."""
    if wrapped_by_traced_reply(name, src):
        return "tracedReply" if stamp_ok else None
    if envelope_traces and re.search(r"\breturn\s+ok\(", src):
        return "ok() envelope"
    if re.search(r"JSON\.stringify\(\s*\{[^;]*?\btrace_id\s*:", src, re.S):
        return "trace_id reply literal"
    return None


def traced_functions(tree) -> tuple[dict[str, str], list[str], list[str]]:
    """({fn: how its reply carries trace_id}, all function dirs, R8 findings)."""
    env = tree.read("supabase/functions/_shared/envelope.ts") or ""
    envelope_traces = bool(re.search(r"function\s+baseEnvelope[\s\S]*?trace_id\s*:", env))
    dirs = tree.function_dirs()
    if isinstance(tree, GitTree):
        tree.prefetch([f"supabase/functions/{d}/index.ts" for d in dirs] + [SHARED_REL])
    srcs = {d: tree.read(f"supabase/functions/{d}/index.ts") or "" for d in dirs}
    wrapped = [d for d, s in srcs.items() if wrapped_by_traced_reply(d, s)]
    fails = check_stamp(tree.read(SHARED_REL)) if wrapped or tree.read(SHARED_REL) is not None else []
    stamp_ok = not fails
    for d in wrapped:
        fails += check_one_id(d, srcs[d])
    out = {}
    for d, s in srcs.items():
        how = fn_carries_trace(d, s, envelope_traces, stamp_ok)
        if how:
            out[d] = how
    return out, dirs, fails


def called_functions(src: str, fn_dirs: set[str] | None = None) -> set[str]:
    found = {(m.group(1) or m.group(2)) for m in CALL.finditer(src)}
    return found & fn_dirs if fn_dirs is not None else found


# ── R1/R2/R3/R5 writers ──────────────────────────────────────────────────────────────────────────────────────────
def check_writers(name: str, src: str, traced, fn_dirs: set[str] | None = None) -> tuple[list[str], list[str]]:
    fails, rows = [], []
    code = _strip_comments(src)
    available = sorted(called_functions(code, fn_dirs) & set(traced))
    # the shared row's body: an insert inside it must forward opts.traceId (R3)
    shared = (0, -1)
    d = re.search(r"function\s+whAiTrustRow\s*\([^)]*\)\s*\{", code)
    if d:
        body = _span(code, d.end() - 1, "{", "}")
        shared = (d.end() - 1, d.end() - 1 + len(body))
    for m in INSERT.finditer(code):
        brace = code.find("{", m.end())
        literal = _span(code, brace, "{", "}") if brace >= 0 and not code[m.end():brace].strip() else ""
        where = f"{name}:{_line(code, m.start())}"
        if not literal:
            fails.append(f"R1 {where}: ai_reply_feedback insert is not an object literal the gate can read")
            continue
        val = _trace_value(literal)
        if val is None:
            fails.append(f"R1 {where}: ai_reply_feedback insert sends no trace_id - the rating cannot name the call it judged")
            rows.append(f"{where}  OMITS trace_id")
            continue
        if MINTED.search(val):
            fails.append(f"R5 {where}: trace_id `{val[:80]}` is made on the client - it must be the id the endpoint returned")
        if available and NULLISH.match(val):
            fails.append(f"R2 {where}: trace_id is `{val}` although this file calls {', '.join(available)}, "
                         f"whose reply carries one")
        if shared[0] < m.start() < shared[1] and not re.search(r"\bopts\.traceId\b", val):
            fails.append(f"R3 {where}: whAiTrustRow's insert does not forward opts.traceId (sends `{val[:60]}`)")
        rows.append(f"{where}  trace_id <- {val[:70]}")
    return fails, rows


# ── R4/R5 whAiTrustRow callers ───────────────────────────────────────────────────────────────────────────────────
def check_callers(name: str, src: str, traced, fn_dirs: set[str]) -> tuple[list[str], list[str]]:
    """returns (findings, rows); each row starts with PASSES / STORED / FAILS so the counts can be read off it."""
    fails, rows = [], []
    code = _strip_comments(src)
    raw_lines = src.splitlines()
    calls = called_functions(code, fn_dirs)
    traced = set(traced)
    for m in TRUST_CALL.finditer(code):
        before = code[max(0, m.start() - 12):m.start()]
        if re.search(r"function\s+$", before):
            continue          # the definition itself
        paren = m.end() - 1
        span = _span(code, paren, "(", ")")
        args = _top_level_args(span)
        opts = args[1] if len(args) > 1 else ""
        l0, l1 = _line(code, m.start()), _line(code, paren + max(len(span), 1) - 1)
        where = f"{name}:{l0}"
        agent_m = re.search(r"\bagent\s*:\s*['\"]([\w-]+)['\"]", opts)
        agent = agent_m.group(1) if agent_m else "?"
        label = f"{where} ({agent})"
        # the producer: the function the agent label names when this file calls it; a function this file does NOT
        # call produced a STORED answer; any other label (a gateway agent) is answered by whatever the file calls
        if agent in fn_dirs:
            producers, stored = ({agent}, False) if agent in calls else ({agent}, True)
        else:
            producers, stored = set(calls), False
        traced_p = sorted(producers & traced)
        tmatch = re.search(r"(?<![\w$.])traceId\s*(?::\s*([^,}]+))?\s*(?:,|\}|$)", opts)
        val = (tmatch.group(1) or "traceId").strip() if tmatch else None
        if val is not None and MINTED.search(val):
            fails.append(f"R5 {where}: whAiTrustRow traceId `{val[:60]}` is made on the client")
        if val is not None and not NULLISH.match(val):
            rows.append(f"PASSES {label}  traceId <- {val[:60]}")
            continue
        allow = None
        for ln in raw_lines[max(0, l0 - 4):l1]:
            a = ALLOW.search(ln)
            if a:
                allow = a.group(1).strip()
                break
        what = "omits traceId" if val is None else f"passes traceId: {val}"
        if allow:
            rows.append(f"STORED {label}  {what} - declared: {allow[:90]}")
        elif traced_p:
            fails.append(f"R4 {where}: whAiTrustRow ({agent}) {what} although its answer comes from "
                         f"{', '.join(traced_p)}, whose reply carries trace_id - pass traceId: whTraceIdOf(<reply>)")
            rows.append(f"FAILS  {label}  {what} beside {', '.join(traced_p)}")
        elif stored:
            fails.append(f"R4 {where}: whAiTrustRow ({agent}) rates a STORED answer from {agent}, which this file never "
                         f"calls - pass the id the stored row keeps, or declare `trace-allow: <why none>` on the call")
            rows.append(f"FAILS  {label}  stored answer from {agent}, undeclared")
        else:
            why = ", ".join(sorted(producers)) or "no edge function the gate can see"
            fails.append(f"R4 {where}: whAiTrustRow ({agent}) rates an answer from {why}, which return(s) no trace id - "
                         f"make the function return one (serveObserved(fn, tracedReply(fn, ...))) and pass it")
            rows.append(f"FAILS  {label}  CANNOT - {why} return(s) no trace id")
    return fails, rows


# ── R6 schema ────────────────────────────────────────────────────────────────────────────────────────────────────
def check_schema(tree) -> list[str]:
    rx = re.compile(r"alter\s+table\s+(?:public\.)?ai_reply_feedback\s+add\s+column\s+(?:if\s+not\s+exists\s+)?trace_id\b",
                    re.I)
    migs = tree.migrations()
    if isinstance(tree, GitTree):
        tree.prefetch(migs)
    for rel in migs:
        if rx.search(tree.read(rel) or ""):
            return []
    return ["R6 no migration adds ai_reply_feedback.trace_id - the writers would send a column the table does not have"]


# ── R7 gateway ───────────────────────────────────────────────────────────────────────────────────────────────────
def check_gateway(src: str) -> list[str]:
    fails = []
    code = _strip_comments(src)
    begin = code.find("beginRequest(req")
    if begin < 0:
        return ["R7 ai-gateway: no beginRequest(req ...) - the request has no trace id to carry"]
    for m in re.finditer(r"(?<![\w$.])jsonResponse\(", code):
        if code[max(0, m.start() - 12):m.start()].rstrip().endswith("function"):
            continue
        args = _top_level_args(_span(code, m.end() - 1, "(", ")"))
        where = f"ai-gateway:{_line(code, m.start())}"
        if len(args) >= 2 and args[1].strip() == "200":
            fails.append(f"R7 {where}: an answer leaves flat through jsonResponse(..., 200, ...) - no envelope, "
                         f"no trace_id, no wh_traces row; answer through ok(ctx, ...)")
            continue
        if m.start() > begin and (len(args) < 4 or "trace_id" not in args[3]):
            fails.append(f"R7 {where}: a refusal after beginRequest() carries no trace id "
                         f"(pass ctx.trace_id as jsonResponse's 4th argument)")
    for m in REFUSAL_HELPERS.finditer(code):
        if m.start() < begin:
            continue
        line_start = code.rfind("\n", 0, m.start()) + 1
        if "withTrace(" not in code[line_start:m.start()]:
            fails.append(f"R7 ai-gateway:{_line(code, m.start())}: {m.group(1)}(...) is returned without "
                         f"withTrace(..., ctx.trace_id) - the 429 names no trace")
    if not re.search(r"""["']x-wh-trace["']\s*:\s*ctx\.trace_id""", code):
        fails.append("R7 ai-gateway: the specialist forward carries no x-wh-trace: ctx.trace_id - the specialist "
                     "mints its own id and the turn has two traces")
    return fails


# ── drivers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def production_files(tree) -> list[str]:
    return [n for n in tree.root_files()
            if not n.startswith(("test", "_", "survey_")) and not n.endswith((".test.js", ".spec.js", "_battery.js"))]


def run(tree) -> int:
    traced, dirs, fails = traced_functions(tree)
    fn_dirs = set(dirs)
    writers, callers = [], []
    files = production_files(tree)
    if isinstance(tree, GitTree):
        tree.prefetch(files)
    for name in files:
        src = tree.read(name) or ""
        if "ai_reply_feedback" in src:
            f, r = check_writers(name, src, traced, fn_dirs)
            fails += f
            writers += r
        if "whAiTrustRow(" in src:
            f, r = check_callers(name, src, traced, fn_dirs)
            fails += f
            callers += r
    fails += check_schema(tree)
    gw = tree.read("supabase/functions/ai-gateway/index.ts")
    fails += check_gateway(gw) if gw is not None else ["R7 supabase/functions/ai-gateway/index.ts not found"]
    print(f"tree: {tree.label}")
    print(f"traced endpoints ({len(traced)}, success reply carries trace_id): "
          + (", ".join(f"{k} [{v}]" for k, v in sorted(traced.items())) or "none"))
    print(f"ai_reply_feedback writers ({len(writers)}):")
    for r in writers:
        print("  " + r)
    n_pass = sum(r.startswith("PASSES") for r in callers)
    n_stored = sum(r.startswith("STORED") for r in callers)
    n_fail = sum(r.startswith("FAILS") for r in callers)
    print(f"whAiTrustRow callers ({len(callers)}): {n_pass} pass the producing call's id, {n_stored} rate a stored "
          f"answer by declaration, {n_fail} fail")
    for r in callers:
        print("  " + r)
    if not writers:
        fails.append("R1 no ai_reply_feedback writer found - the scan is reading the wrong tree")
    if fails:
        print(f"FAIL ai_feedback_carries_trace - {len(fails)} finding(s):")
        for f in fails:
            print("  " + f)
        return 1
    print(f"PASS ai_feedback_carries_trace - {len(writers)} writer(s) send trace_id; {n_pass} of {len(callers)} "
          f"whAiTrustRow callers pass the id their producer returned and {n_stored} declare a stored answer; "
          f"{len(traced)} endpoints return trace_id; ai-gateway traces every answer and refusal")
    return 0


# ── selftest ─────────────────────────────────────────────────────────────────────────────────────────────────────
STAMP_GOOD = """
import { beginRequest } from "./envelope.ts";
export function tracedReply(route: string, handler: TracedHandler): (req: Request) => Promise<Response> {
  return async (req: Request): Promise<Response> => {
    const trace = beginRequest(req, { route });
    if (req.method === "OPTIONS") return await handler(req, trace);
    const res = await handler(req, trace);
    return await stampTraceId(res, trace.trace_id);
  };
}
export async function stampTraceId(res: Response, traceId: string): Promise<Response> {
  const body = JSON.parse(await res.clone().text());
  return new Response(JSON.stringify({ ...body, trace_id: traceId }), { status: res.status });
}
"""
FN_WRAPPED = """import { tracedReply } from "../_shared/trace-reply.ts";
serveObserved("an-fn", tracedReply("an-fn", async (req, trace) => {
  log.info(trace, "request_start", { method: req.method });
  return new Response(JSON.stringify({ answer: "x" }), { status: 200 });
}));
"""
FN_PLAIN = """serveObserved("an-fn", async (req) => {
  logRequestStart(req, "an-fn");
  return new Response(JSON.stringify({ answer: "x" }), { status: 200 });
});
"""


def selftest() -> int:
    traced = {"ai-gateway", "agentic-rag-loop", "analytics-orchestrator", "intelligence-report"}
    fn_dirs = traced | {"foo-fn", "amc-orchestrator"}
    good_writer = ("async function rec(r, q, a, traceId) {\n  await db.from('ai_reply_feedback').insert({\n"
                   "    agent: 'x', question: q, answer: a, rating: r,\n    trace_id: _traceIdOf(traceId),\n  });\n}\n"
                   "const { data } = await db.functions.invoke('ai-gateway', { body });")
    w = lambda name, src: check_writers(name, src, traced, fn_dirs)    # noqa: E731
    c = lambda name, src: check_callers(name, src, traced, fn_dirs)    # noqa: E731
    bad = {
        "writer omits trace_id": (w, "x.js", "await db.from('ai_reply_feedback').insert({ agent: 'x', question: q, rating: r });"),
        "writer sends null beside the gateway": (w, "x.js", "const r = await db.functions.invoke('ai-gateway', { body });\n"
                                                 "await db.from('ai_reply_feedback').insert({ rating: 1, trace_id: null });"),
        "writer mints the id": (w, "x.js", "await db.from('ai_reply_feedback').insert({ rating: 1, trace_id: crypto.randomUUID() });"),
        "writer sends the REQUEST-side id": (w, "x.js", "await db.from('ai_reply_feedback').insert({ rating: 1, trace_id: _whTrace });"),
        "shared row drops opts.traceId": (w, "utils.js", "function whAiTrustRow(c, opts) {\n  db.from('ai_reply_feedback').insert({\n"
                                          "    rating: 1, trace_id: null,\n  });\n}"),
        "gateway page caller omits traceId": (c, "p.html", "const r = await db.functions.invoke('ai-gateway', { body });\n"
                                              "whAiTrustRow(el, { db, agent: 'asset-brain', question, answer });"),
        # the second half: a specialist the page calls directly
        "specialist caller DROPS the id its function returns": (
            c, "a.html", "fetch(`${U}/functions/v1/analytics-orchestrator`, o);\n"
                         "whAiTrustRow(el, { db, agent: 'analytics-orchestrator', question, answer });"),
        "specialist caller passes null with no declaration": (
            c, "a.html", "const { data } = await invokeWithTimeout('analytics-orchestrator', { body });\n"
                         "whAiTrustRow(el, { db, agent: 'analytics-orchestrator', traceId: null });"),
        "a producer that returns no id is a failure, not 'cannot'": (
            c, "q.html", "const { data } = await db.functions.invoke('foo-fn', { body });\n"
                         "whAiTrustRow(el, { db, agent: 'foo-fn', question, answer });"),
        "a stored answer with no declaration": (
            c, "s.html", "const { data } = await db.from('amc_briefings').select('*');\n"
                         "whAiTrustRow(el, { db, agent: 'amc-orchestrator', traceId: null });"),
        "a declaration with no reason": (
            c, "s.html", "// trace-allow: x\nwhAiTrustRow(el, { db, agent: 'amc-orchestrator', traceId: null });"),
    }
    good = {
        "writer carries the returned id": (w, "x.js", good_writer),
        "untraced page writer may send null": (w, "y.js", "await db.from('ai_reply_feedback').insert({ rating: 1, trace_id: null });"),
        "gateway page caller passes shorthand traceId": (
            c, "p.html", "const r = await db.functions.invoke('ai-gateway', { body });\n"
                         "whAiTrustRow(el, { db, agent: 'a', question, answer, traceId, groundedOn: g });"),
        "gateway page caller passes keyed traceId": (
            c, "p.html", "fetch(`${U}/functions/v1/ai-gateway`, o);\nwhAiTrustRow(el, { db, agent: 'a', traceId: _turn.traceId });"),
        "specialist caller passes the reply's id": (
            c, "a.html", "const { data } = await invokeWithTimeout('analytics-orchestrator', { body });\n"
                         "whAiTrustRow(el, { db, agent: 'analytics-orchestrator', traceId: whTraceIdOf(data) });"),
        "a stored answer declared with its reason": (
            c, "s.html", "await db.functions.invoke('intelligence-report', { body: {} });\n"
                         "// trace-allow: the report shown is the stored row and that table keeps no trace id\n"
                         "whAiTrustRow(el, { db, agent: 'intelligence-report', traceId: null });"),
        "the definition is not a call": (c, "utils.js", "function whAiTrustRow(container, opts) {}"),
    }
    fails = []
    for k, (fn, name, src) in bad.items():
        if not fn(name, src)[0]:
            fails.append(f"bad fixture '{k}' was NOT flagged")
    for k, (fn, name, src) in good.items():
        hits = fn(name, src)[0]
        if hits:
            fails.append(f"good fixture '{k}' WAS flagged: {hits}")
    # the function side: a wrapped function is traced only while the shared stamp writes trace_id
    if fn_carries_trace("an-fn", FN_WRAPPED, True, not check_stamp(STAMP_GOOD)) != "tracedReply":
        fails.append("good fixture 'wrapped function is traced' was NOT traced")
    if check_one_id("an-fn", FN_WRAPPED):
        fails.append(f"good fixture 'wrapped function logs with its trace' WAS flagged: {check_one_id('an-fn', FN_WRAPPED)}")
    if fn_carries_trace("an-fn", FN_PLAIN, True, True) is not None:
        fails.append("bad fixture 'unwrapped function that returns no id' WAS counted as traced")
    stamp_bad = {
        "stamp DROPS the id": STAMP_GOOD.replace("{ ...body, trace_id: traceId }", "{ ...body }"),
        "wrapper skips the stamp": STAMP_GOOD.replace("return await stampTraceId(res, trace.trace_id);", "return res;"),
        "wrapper mints no id": STAMP_GOOD.replace("const trace = beginRequest(req, { route });",
                                                  "const trace = { trace_id: '' };"),
    }
    if check_stamp(STAMP_GOOD):
        fails.append(f"good stamp fixture WAS flagged: {check_stamp(STAMP_GOOD)}")
    for k, s in stamp_bad.items():
        if not check_stamp(s):
            fails.append(f"bad stamp fixture '{k}' was NOT flagged")
        elif fn_carries_trace("an-fn", FN_WRAPPED, True, not check_stamp(s)) is not None:
            fails.append(f"bad stamp fixture '{k}' still counted the wrapped function as traced")
    second_ids = {
        "wrapped function keeps logRequestStart": FN_WRAPPED.replace('log.info(trace, "request_start", { method: req.method });',
                                                                     'logRequestStart(req, "an-fn");'),
        "wrapped function mints its own ctx": FN_WRAPPED.replace('log.info(trace,', 'const c2 = beginRequest(req, { route: "an-fn" });\n  log.info(c2,'),
    }
    for k, s in second_ids.items():
        if not check_one_id("an-fn", s):
            fails.append(f"bad fixture '{k}' was NOT flagged")
    gw_good = ("const ctx = beginRequest(req, { route: 'ai-gateway' });\n"
               "if (!agent) return jsonResponse(corsHeaders, 400, { error: 'Missing agent' }, ctx.trace_id);\n"
               "return await withTrace(userRateLimitedResponse(corsHeaders, 25, 60), ctx.trace_id);\n"
               "await fetch(u, { headers: { 'x-wh-trace': ctx.trace_id } });\nreturn ok(ctx, { answer });")
    gw_bad = {
        "flat 200 answer": gw_good.replace("return ok(ctx, { answer });",
                                           "return jsonResponse(corsHeaders, 200, { answer }, ctx.trace_id);"),
        "refusal without trace": gw_good.replace(", ctx.trace_id);\nreturn await", ");\nreturn await"),
        "429 not wrapped": gw_good.replace("return await withTrace(userRateLimitedResponse(corsHeaders, 25, 60), ctx.trace_id);",
                                           "return userRateLimitedResponse(corsHeaders, 25, 60);"),
        "forward drops the id": gw_good.replace("'x-wh-trace': ctx.trace_id", "'x-other': 1"),
    }
    if check_gateway(gw_good):
        fails.append(f"good gateway fixture WAS flagged: {check_gateway(gw_good)}")
    for k, src in gw_bad.items():
        if not check_gateway(src):
            fails.append(f"bad gateway fixture '{k}' was NOT flagged")
    for f in fails:
        print("  SELFTEST FAIL", f)
    n_bad = len(bad) + 1 + len(stamp_bad) + len(second_ids) + len(gw_bad)
    n_good = len(good) + 2 + 1 + 1
    print(f"selftest: {n_bad} bad fixtures flagged, {n_good} good fixtures clean" if not fails else "selftest FAILED")
    return 1 if fails else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if "--rev" in sys.argv:
        return run(GitTree(ROOT, sys.argv[sys.argv.index("--rev") + 1]))
    root = ROOT
    if "--root" in sys.argv:
        # not .resolve(): that expands a short (8.3) Windows path past MAX_PATH for deep migration file names
        root = Path(sys.argv[sys.argv.index("--root") + 1])
    return run(FsTree(root))


if __name__ == "__main__":
    sys.exit(main())
