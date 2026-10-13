#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* E
"""validate_ai_eval_answers_are_real.py - the nightly AI eval must have MEASURED answers, not graded errors.

THE FINDING (LM-E walk, 2026-10-07). ai-eval-runner had never measured an answer. All 1,765 graded rows in
ai_quality_log had actual_answer "[gateway error: 401]": the runner called ai-gateway with the SERVICE-ROLE
key as its bearer, and the gateway resolves a USER from the bearer and refuses every agent except
voice-journal without one. The judge then graded the error string, so the log read "every agent fails
quality, 0 of 1,765" - a verdict about questions nobody answered. `ai-eval-coverage` stayed green the whole
time, because it asks whether the fixtures, the cron and the log table EXIST, never whether the scores are real.

THIS GATE asks the question that was missing, in three layers:

  L1 BEARER (static)  The runner's call to ai-gateway must not carry a bearer the gateway refuses. Read from
                      BOTH sources: the gateway's own refusal rule (`if (!user && !ANON_OK_AGENTS.has(agent))
                      -> 401`) and the runner's FIXTURES agents. A key bearer (service-role / anon) FAILs when
                      any fixture agent is outside ANON_OK_AGENTS. A non-key bearer must come from a session
                      the runner actually mints (verifyOtp / signInWithPassword).
  L1b ANSWER PATH     The gateway answers through the shared envelope (`ok(ctx, {answer})` -> data.answer); the
                      runner must read data.answer. It read a top-level `answer`, so even an authorised call
                      recorded "" - the second, hidden reason nothing was measured (found by the first
                      authorised run, 2026-10-07).
  L2 HONESTY (static) An answer that is not an answer is an infrastructure failure, never a quality one: the
                      runner must record outcome "infra_error", and must judge ONLY when there is an answer
                      (`infraReason ? null : await judgeAnswer(...)`), and its ai_quality_log insert must
                      carry `outcome`.
  L3 DATA (live)      The LATEST run in ai_quality_log (grouped by run_id - the nightly slices of one night share
                      it) must be mostly measured: FAIL when infra-error rows are more than half of it, when it
                      graded nothing, or when any row anywhere still carries a grade on a gateway-error answer.
                      Rows written before run_at/outcome existed are read as one run and classified by their
                      answer text. Database unreachable -> L3 SKIPs (L1/L2 still decide).

THE SECOND FINDING (2026-10-07, the first authorised run). With the identity fixed, ~6 of 18 fixtures were STILL
never measured, every night, for a reason that is not flaky infrastructure but a deterministic gap: the eval
hive held no data and the fixtures carried no ids. asset-brain was refused 400 "Missing required fields:
question, asset_id, hive_id" (the fixture names tag_id PMP-001; the gateway forwards only context.asset_id /
asset_tag), project had no project_id, and analytics answered "No failures logged this period" - graded 0, a
measurement of an empty hive. L3's ">half infra" rule cannot see that: 3 unmeasured of 18 is a "mostly measured"
run. And the gateway's saved turns made every fixture answer with the previous ones in its prompt.

  L4 CONTEXT          static: every fixture agent whose specialist needs an id - read from the GATEWAY
                      (ASSET_ID_FORWARD_AGENTS -> asset_id; an `agent === "X"` block lifting project_id) - must
                      get one from the runner's bench (BENCH_SUBJECT), the bench must be seeded
                      (rpc ai_eval_bench_ensure), every asset/project a fixture names must be in the seeder's SQL,
                      and the gateway call must send the resolved context, not the raw fixture.context.
                      live: FAIL when the latest run, or ANY fixture's most recent measurement, was left
                      unmeasured for missing context (a 400 "Missing required field", "is not on the eval
                      bench", ...) or was graded on a non-answer an empty bench produces ("No failures logged
                      this period", "couldn't find asset", "_unavailable").
  L5 INDEPENDENCE     static: every table the gateway's imported memory modules write for a user turn
                      (derived from _shared/*.ts, minus accounting/telemetry) must be cleared by
                      ai_eval_bench_reset_memory, and the runner must call that reset inside the fixture loop,
                      BEFORE the gateway call.
  L6 TIME LIMIT       static: the runner must stop starting fixtures when its budget is spent; and no
                      scheduled eval call may carry more than MAX_FIXTURES_PER_CALL fixtures (live cron.job,
                      or the newest migration when the database is unreachable), and every fixture agent must
                      be on the schedule.

USAGE:      python tools/validate_ai_eval_answers_are_real.py
Self-test:  python tools/validate_ai_eval_answers_are_real.py --self-test
            (mutants of the CURRENT runner + the pre-fix fetch block must FAIL L1/L2/L4/L5/L6; synthetic all-error
             runs and missing-context runs must FAIL L3/L4, a mostly-graded run must PASS; the 2026-05-11 single
             cron job must FAIL L6 - the gate's teeth, no database or model needed)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
RUNNER = FUNCS / "ai-eval-runner" / "index.ts"
GATEWAY = FUNCS / "ai-gateway" / "index.ts"
SHARED = FUNCS / "_shared"
MIGRATIONS = ROOT / "supabase" / "migrations"
DB_CONTAINER = "supabase_db_workhive"
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

# The runner writes "[gateway error: <status>]" / "[gateway threw: <msg>]" as the answer when there was none.
GATEWAY_ERR_RE = re.compile(r"^\[gateway (?:error|threw)\b")
DOMINATED_SHARE = 0.5          # more than half of the latest run unmeasured = the eval did not run
KEY_BEARER_RE = re.compile(r"SERVICE|service_role|ANON|anon", re.I)
SESSION_MINT_RE = re.compile(r"\.verifyOtp\(|\.signInWithPassword\(|\.exchangeCodeForSession\(")

# L4: an infra reason that says the fixture had no context to be asked with (deterministic, never flaky) ...
MISSING_CONTEXT_RE = re.compile(
    r"missing context:|Missing required field|project_id and hive_id are required|is not on the eval bench"
    r"|Asset not found in this hive|eval bench could not be seeded", re.I)
# ... and an "answer" an empty bench produces, which grades the hive instead of the agent.
EMPTY_BENCH_ANSWER_RE = re.compile(
    r"\bNo (?:failures|downtime data)\b[^.]{0,40}\blogged this period|couldn't find asset|\"_unavailable\"\s*:\s*true"
    r"|\bProject not found\b", re.I)
# L5: tables a gateway-imported module writes that hold no answer, turn or memory - accounting and telemetry.
NOT_MEMORY_TABLES = {
    "ai_cost_log":         "per-call cost accounting",
    "wh_traces":           "request tracing",
    "ai_rate_limits":      "hive rate-limit counter",
    "ai_user_rate_limits": "per-user rate-limit counter",
    "hive_route_calls":    "per-route quota counter",
    "embedding_cache":     "text-hash -> vector; holds no answer",
}
# L6: 18 fixtures x 5-9 s met the hosted 150 s wall clock (one run died 546 WORKER_LIMIT). 6 x 9 s = 54 s.
MAX_FIXTURES_PER_CALL = 6

# The pre-fix fetch block, verbatim from the runner before 2026-10-07. L1 must FAIL it forever.
PRE_FIX_FETCH = '''
        const gwUrl = `${SUPABASE_URL}/functions/v1/ai-gateway`;
        const res = await fetch(gwUrl, { signal: AbortSignal.timeout(60000),
          method: "POST",
          headers: {
            "Authorization": `Bearer ${SERVICE_KEY}`,
            "Content-Type":  "application/json",
          },
'''


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'`])//.*$", r"\1", src)


# ── L1 ───────────────────────────────────────────────────────────────────────────────────────────────────
def gateway_anon_ok(gw_src: str) -> set[str] | None:
    """Agents the gateway answers WITHOUT a user. None = the refusal rule could not be found (unprovable)."""
    s = strip_comments(gw_src)
    m = re.search(r"ANON_OK_AGENTS\s*=\s*new\s+Set\(\s*\[([^\]]*)\]", s)
    refuses = re.search(r"if\s*\(\s*!\s*user\s*&&\s*!\s*ANON_OK_AGENTS\.has\(\s*agent\s*\)\s*\)\s*\{?\s*return[^;]*\b401\b", s, re.S)
    if not m or not refuses:
        return None
    return set(re.findall(r"[\"']([^\"']+)[\"']", m.group(1)))


def runner_agents(src: str) -> list[str]:
    m = re.search(r"const\s+FIXTURES\b[^=]*=\s*\{(.*?)\n\};", src, re.S)
    if not m:
        return []
    return re.findall(r"(?m)^\s{2}[\"']([a-z0-9-]+)[\"']\s*:\s*\[", m.group(1))


def gateway_call_bearer(src: str) -> str | None:
    """The Authorization value of the runner's fetch to ai-gateway (comment-stripped)."""
    s = strip_comments(src)
    i = s.find("functions/v1/ai-gateway")
    if i < 0:
        return None
    window = s[i:i + 1500]
    m = re.search(r"[\"']?Authorization[\"']?\s*:\s*([^,\n]+)", window)
    return m.group(1).strip() if m else None


def check_bearer(src: str, gw_src: str) -> list[str]:
    fails: list[str] = []
    bearer = gateway_call_bearer(src)
    if bearer is None:
        return ["L1 the runner has no recognisable Authorization on its ai-gateway call - nothing proves the gateway will accept it"]
    anon_ok = gateway_anon_ok(gw_src)
    agents = runner_agents(src)
    if anon_ok is None:
        fails.append("L1 the gateway's refusal rule (!user && !ANON_OK_AGENTS.has(agent) -> 401) was not found - "
                     "re-read the gateway and update this gate before trusting the runner's bearer")
        return fails
    refused = [a for a in agents if a not in anon_ok]
    if KEY_BEARER_RE.search(bearer):
        if refused:
            fails.append(f"L1 the runner sends {bearer} to ai-gateway, and the gateway refuses a bearer that is not a "
                         f"user for {len(refused)} of its {len(agents)} fixture agents ({', '.join(refused)}) - every "
                         f"one of those rows will be '[gateway error: 401]'")
    elif not SESSION_MINT_RE.search(strip_comments(src)):
        fails.append(f"L1 the runner's bearer ({bearer}) is not a key, but the runner never mints a user session "
                     f"(verifyOtp / signInWithPassword) - the token has no visible source")
    return fails


def check_answer_path(src: str, gw_src: str) -> list[str]:
    """L1b - the runner reads the answer WHERE THE GATEWAY PUTS IT. The gateway's success path is the shared
    envelope `ok(ctx, { answer, ... })` -> {ok, data: {answer}}; the runner read a top-level `answer`, so even an
    authorised call recorded "" (the second, hidden reason no answer was ever measured - found 2026-10-07)."""
    gw = strip_comments(gw_src)
    if not re.search(r"return\s+ok\(\s*ctx\s*,\s*\{\s*answer\s*:", gw):
        return []   # the gateway no longer answers through the envelope - nothing to hold the runner to
    if not re.search(r"\bdata\s*\??\.\s*answer\b", strip_comments(src)):
        return ["L1 the gateway returns its answer inside the envelope (data.answer), and the runner never reads "
                "data.answer - every authorised reply would be recorded as empty"]
    return []


# ── L2 ───────────────────────────────────────────────────────────────────────────────────────────────────
def check_honesty(src: str) -> list[str]:
    s = strip_comments(src)
    fails: list[str] = []
    if '"infra_error"' not in s:
        fails.append('L2 the runner never records outcome "infra_error" - a gateway error would be graded as a quality failure')
    if not re.search(r"infra\w*\s*\?\s*null\s*:\s*await\s+judgeAnswer\(", s):
        fails.append("L2 the judge is not conditional on there being an answer (expected `infraReason ? null : await "
                     "judgeAnswer(...)`) - an error string would be graded")
    ins = re.search(r"\.from\(\s*[\"']ai_quality_log[\"']\s*\)\s*\.insert\(\s*\{(.*?)\}\s*\)", s, re.S)
    if not ins or not re.search(r"\boutcome\s*:", ins.group(1)):
        fails.append("L2 the fixture row insert into ai_quality_log does not carry `outcome` - graded and unmeasured rows are indistinguishable")
    return fails


# ── shared parsing (L4-L6) ───────────────────────────────────────────────────────────────────────────────
def fixtures_block(src: str) -> str:
    m = re.search(r"const\s+FIXTURES\b[^=]*=\s*\{(.*?)\n\};", src, re.S)
    return m.group(1) if m else ""


def fixtures_by_agent(src: str) -> dict[str, list[str]]:
    parts = re.split(r"(?m)^\s{2}[\"']([a-z0-9-]+)[\"']\s*:\s*\[", fixtures_block(src))
    return {parts[i]: re.findall(r"\bid\s*:\s*[\"']([^\"']+)[\"']", parts[i + 1]) for i in range(1, len(parts) - 1, 2)}


def bench_subjects(src: str) -> dict[str, dict[str, str]]:
    """The runner's BENCH_SUBJECT: agent -> {asset|project|history: value}."""
    m = re.search(r"const\s+BENCH_SUBJECT\b[^=]*=\s*\{(.*?)\n\};", strip_comments(src), re.S)
    if not m:
        return {}
    return {agent: dict(re.findall(r"\b(asset|project|history)\s*:\s*[\"']?([\w-]+)[\"']?", body))
            for agent, body in re.findall(r"[\"']([a-z0-9-]+)[\"']\s*:\s*\{([^}]*)\}", m.group(1))}


def gateway_id_needs(gw_src: str) -> dict[str, str]:
    """Which agents' specialists need an id the GATEWAY forwards from context: agent -> 'asset' | 'project'."""
    s = strip_comments(gw_src)
    needs: dict[str, str] = {}
    m = re.search(r"ASSET_ID_FORWARD_AGENTS[^=]*=\s*new\s+Set\(\s*\[([^\]]*)\]", s)
    for a in re.findall(r"[\"']([^\"']+)[\"']", m.group(1) if m else ""):
        needs[a] = "asset"
    for mm in re.finditer(r"if\s*\(\s*agent\s*===\s*[\"']([\w-]+)[\"']\s*\)", s):
        nxt = re.search(r"if\s*\(\s*agent\s*===", s[mm.end():])
        block = s[mm.end(): mm.end() + (nxt.start() if nxt else 800)]
        if re.search(r"forwardExtras\.project_id\s*=", block):
            needs[mm.group(1)] = "project"
    return needs


def migration_function_body(name: str) -> tuple[str | None, str | None]:
    """(body, file name) of the NEWEST migration that creates public.<name>."""
    pat = re.compile(rf"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\.{re.escape(name)}\s*\(.*?\bAS\s+(\$\w*\$)(.*?)\1",
                     re.S | re.I)
    for f in sorted(MIGRATIONS.glob("*.sql"), reverse=True):
        m = pat.search(f.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(2), f.name
    return None, None


# ── L4 ───────────────────────────────────────────────────────────────────────────────────────────────────
def check_context_static(src: str, gw_src: str, seed_body: str | None) -> list[str]:
    s = strip_comments(src)
    fails: list[str] = []
    needs = gateway_id_needs(gw_src)
    subj = bench_subjects(src)
    for agent in runner_agents(src):
        need = needs.get(agent)
        if need and not subj.get(agent, {}).get(need):
            fails.append(f"L4 the gateway hands {agent} to a specialist that needs a {need} id from context, and the "
                         f"runner gives {agent} fixtures no {need} from the eval bench (BENCH_SUBJECT) - each one is "
                         f"refused before it reaches a model, every night")
    if not re.search(r"\.rpc\(\s*[\"']ai_eval_bench_ensure[\"']", s):
        fails.append("L4 the runner never seeds the eval bench (rpc ai_eval_bench_ensure) - the eval hive is empty, so "
                     "asset/project fixtures have nothing to resolve and analytics grades an empty hive")
    i = s.find("functions/v1/ai-gateway")
    if i >= 0 and re.search(r"\bcontext\s*:\s*fixture\.context\b", s[i:i + 1500]):
        fails.append("L4 the gateway call sends the raw fixture.context - the asset_id/project_id the bench resolved "
                     "never reach the specialist")
    named = set(re.findall(r"\b(?:tag_id|asset_tag|project_code)\s*:\s*[\"']([^\"']+)[\"']", fixtures_block(src)))
    named |= {v for d in subj.values() for k, v in d.items() if k in ("asset", "project")}
    if named and seed_body is None:
        fails.append("L4 no migration creates public.ai_eval_bench_ensure - nothing seeds "
                     f"{', '.join(sorted(named))}, which the fixtures are asked about")
    elif named:
        unseeded = sorted(t for t in named if f"'{t}'" not in seed_body)
        if unseeded:
            fails.append(f"L4 fixtures are asked about {', '.join(unseeded)}, which the bench seeder "
                         f"(ai_eval_bench_ensure) never creates - they will be recorded as missing context")
    return fails


def unmeasured_why(r: dict) -> str | None:
    """Why a row did not measure the agent for lack of context, or None."""
    if is_infra(r) and MISSING_CONTEXT_RE.search((r.get("reason") or "") + " " + (r.get("answer") or "")):
        return "missing context"
    if not is_infra(r) and r.get("passed") is not None and EMPTY_BENCH_ANSWER_RE.search(r.get("answer") or ""):
        return "graded an empty-bench non-answer"
    return None


def judge_context(run_rows: list[dict], latest_per_fixture: list[dict]) -> list[str]:
    """Pure: L4 live verdict. run_rows = the latest run; latest_per_fixture = each CURRENT fixture's newest row."""
    def evidence(r: dict, why: str) -> str:
        text = r.get("answer") if why.startswith("graded") else (r.get("reason") or r.get("answer"))
        return f"{r.get('agent')}/{r.get('question')} ({why}: {(text or '')[:70]})"

    fails: list[str] = []
    bad = [(r, w) for r in run_rows if (w := unmeasured_why(r))]
    if bad:
        fails.append(f"L4 the latest run left {len(bad)} fixture(s) unmeasured for lack of context: "
                     + "; ".join(evidence(r, w) for r, w in bad[:4]))
    seen = {(r.get("agent"), r.get("question")) for r, _ in bad}
    stale = [(r, w) for r in latest_per_fixture
             if (w := unmeasured_why(r)) and (r.get("agent"), r.get("question")) not in seen]
    if stale:
        fails.append(f"L4 {len(stale)} fixture(s) were last measured WITHOUT their context and not since: "
                     + "; ".join(evidence(r, w) for r, w in stale[:5]))
    return fails


# ── L5 ───────────────────────────────────────────────────────────────────────────────────────────────────
def gateway_memory_tables(gw_src: str) -> dict[str, str]:
    """table -> module, for every table a _shared module the gateway imports writes, minus accounting/telemetry."""
    mods = set(re.findall(r"from\s+[\"']\.\./_shared/([\w.-]+)\.ts[\"']", gw_src))
    mods |= set(re.findall(r"import\(\s*[\"']\.\./_shared/([\w.-]+)\.ts[\"']\s*\)", gw_src))
    out: dict[str, str] = {}
    for mod in sorted(mods):
        f = SHARED / f"{mod}.ts"
        if not f.exists():
            continue
        body = strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        for t in re.findall(r"\.from\(\s*[\"'](\w+)[\"']\s*\)\s*\.(?:insert|upsert)\(", body):
            if t not in NOT_MEMORY_TABLES:
                out.setdefault(t, mod)
    return out


def check_memory_reset(src: str, gw_src: str, reset_body: str | None) -> list[str]:
    fails: list[str] = []
    mem = gateway_memory_tables(gw_src)
    if reset_body is None:
        fails.append("L5 no migration creates public.ai_eval_bench_reset_memory - the eval account keeps "
                     f"{', '.join(sorted(mem))} between fixtures, so each answer carries the earlier ones")
    else:
        cleared = set(re.findall(r"DELETE\s+FROM\s+(?:public\.)?(\w+)", reset_body, re.I))
        missing = sorted(t for t in mem if t not in cleared)
        if missing:
            fails.append("L5 the gateway writes " + ", ".join(f"{t} ({mem[t]}.ts)" for t in missing)
                         + " for a user turn and ai_eval_bench_reset_memory never clears it - the next fixture "
                           "(and the next night) is answered with it in context")
    s = strip_comments(src)
    gi = s.find("functions/v1/ai-gateway")
    loop = s.rfind("for (", 0, gi) if gi >= 0 else -1
    if loop < 0 or not re.search(r"\bresetEvalMemory\(|\.rpc\(\s*[\"']ai_eval_bench_reset_memory[\"']", s[loop:gi]):
        fails.append("L5 the runner does not reset the eval account's memory inside the fixture loop, before the "
                     "gateway call - fixture N is answered with fixtures 1..N-1 in its prompt")
    return fails


# ── L6 ───────────────────────────────────────────────────────────────────────────────────────────────────
def check_time_budget(src: str) -> list[str]:
    s = strip_comments(src)
    if re.search(r"\bconst\s+RUN_BUDGET_MS\b", s) and re.search(r"if\s*\([^)]*>\s*RUN_BUDGET_MS\b", s):
        return []
    return ["L6 the runner never stops starting fixtures when its time budget is spent - a long call is killed at "
            "the hosted wall clock (546 WORKER_LIMIT) and loses its remaining fixtures and its heartbeat"]


def eval_cron_jobs_live() -> list[tuple[str, str]] | None:
    out = psql("select jobname, replace(replace(command, E'\\n', ' '), E'\\t', ' ') from cron.job "
               "where command ilike '%ai-eval-runner%' and active")
    if out is None:
        return None
    return [tuple((ln.split("\t") + [""])[:2]) for ln in out.splitlines() if ln.strip()]  # type: ignore[misc]


def eval_cron_jobs_static(text: str | None = None) -> tuple[list[tuple[str, str]], str]:
    """Jobs the newest migration that schedules ai-eval-runner creates (or those in `text`)."""
    pat = re.compile(r"cron\.schedule\(\s*'([^']+)'\s*,\s*'[^']*'\s*,\s*\$(\w*)\$(.*?)\$\2\$", re.S)
    sources = [("(given)", text)] if text is not None else [
        (f.name, f.read_text(encoding="utf-8", errors="replace")) for f in sorted(MIGRATIONS.glob("*.sql"), reverse=True)]
    for name, txt in sources:
        jobs = [(n, body) for n, _, body in pat.findall(txt) if "ai-eval-runner" in body]
        if jobs:
            return jobs, name
    return [], ""


def check_schedule(jobs: list[tuple[str, str]], by_agent: dict[str, list[str]]) -> list[str]:
    fails: list[str] = []
    total = sum(len(v) for v in by_agent.values())
    covered: set[str] = set()
    for name, cmd in jobs:
        m = re.search(r"'only'\s*,\s*'([\w-]+)'", cmd)
        n = len(by_agent.get(m.group(1), [])) if m else total
        covered |= {m.group(1)} if m else set(by_agent)
        if n > MAX_FIXTURES_PER_CALL:
            fails.append(f"L6 cron job {name} runs {n} fixtures in ONE edge call (max {MAX_FIXTURES_PER_CALL}) - at "
                         f"5-9 s each that meets the hosted wall clock; schedule one call per agent")
    uncovered = sorted(set(by_agent) - covered)
    if jobs and uncovered:
        fails.append(f"L6 no scheduled eval call runs {', '.join(uncovered)} - those fixtures are never measured nightly")
    return fails


# ── L3 ───────────────────────────────────────────────────────────────────────────────────────────────────
def psql(sql: str, timeout: int = 30) -> str | None:
    try:
        proc = subprocess.run(["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                               "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
                              capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def is_infra(row: dict) -> bool:
    return row.get("outcome") == "infra_error" or bool(GATEWAY_ERR_RE.match(row.get("answer") or ""))


def judge_run(rows: list[dict], graded_on_error_anywhere: int = 0) -> tuple[list[str], list[str]]:
    """Pure: the verdict on ONE run's fixture rows. Returns (fails, warns)."""
    fails: list[str] = []
    warns: list[str] = []
    if graded_on_error_anywhere:
        fails.append(f"L3 {graded_on_error_anywhere} row(s) in ai_quality_log carry a grade on a gateway-error answer - "
                     f"an error message was scored as if it were the model's answer")
    total = len(rows)
    if total == 0:
        warns.append("L3 ai_quality_log holds no eval rows yet - nothing to judge")
        return fails, warns
    infra = [r for r in rows if is_infra(r)]
    graded = [r for r in rows if not is_infra(r) and r.get("passed") is not None]
    on_error = [r for r in rows if GATEWAY_ERR_RE.match(r.get("answer") or "") and r.get("passed") is not None]
    if on_error and not graded_on_error_anywhere:
        fails.append(f"L3 the latest run graded {len(on_error)} gateway-error answer(s) as quality results")
    share = len(infra) / total
    if not graded:
        fails.append(f"L3 the latest run measured NOTHING: 0 of {total} rows hold a graded answer")
    elif share > DOMINATED_SHARE:
        fails.append(f"L3 the latest run is dominated by infrastructure failures: {len(infra)} of {total} rows "
                     f"({share:.0%}) were never answered or never judged")
    if infra:
        by: dict[str, list[str]] = {}
        for r in infra:
            by.setdefault(r.get("agent") or "?", []).append((r.get("reason") or r.get("answer") or "")[:90])
        for agent, reasons in sorted(by.items()):
            warns.append(f"L3 {agent}: {len(reasons)} unmeasured - {reasons[0]}")
    return fails, warns


def latest_run_rows() -> tuple[list[dict] | None, int, str]:
    """(rows of the latest run | None if DB unreachable, graded-on-error count anywhere, description)."""
    cols_out = psql("select column_name from information_schema.columns "
                    "where table_schema='public' and table_name='ai_quality_log'")
    if cols_out is None:
        return None, 0, "database unreachable"
    cols = set(cols_out.split())
    if not cols:
        return [], 0, "ai_quality_log does not exist"
    goe = psql("select count(*) from public.ai_quality_log where (actual_answer like '[gateway error:%' "
               "or actual_answer like '[gateway threw:%') and passed is not null")
    graded_on_error = int((goe or "0").strip() or 0)
    has_run = {"run_at", "outcome"} <= cols
    sel = ("agent_id, question_id, " + ("coalesce(outcome,'')" if has_run else "''") +
           ", coalesce(passed::text,''), replace(replace(left(coalesce(actual_answer,''),120), E'\\t',' '), E'\\n',' ')"
           ", replace(replace(left(coalesce(failure_reason,''),160), E'\\t',' '), E'\\n',' ')")
    base = "from public.ai_quality_log where agent_id <> '__heartbeat__'"
    if has_run:
        head = psql(f"select run_at, coalesce(run_id::text,'') {base} order by run_at desc limit 1")
        if head is None:
            return None, graded_on_error, "database read failed"
        if not head.strip():
            return [], graded_on_error, "no eval rows"
        run_at, run_id = (head.strip().split("\t") + [""])[:2]
        # a run is its run_id: the nightly cron calls the runner once per agent, and those slices share it
        where = f" and run_id = '{run_id}'" if run_id else f" and run_at = '{run_at}' and run_id is null"
        out = psql(f"select {sel} {base}{where}")
        desc = f"latest run {run_id or '(pre-run_id history)'} (newest row {run_at})"
    else:
        out = psql(f"select {sel} {base}")
        desc = "all rows (no run_at/outcome columns yet - the history reads as ONE run)"
    if out is None:
        return None, graded_on_error, "database read failed"
    return parse_rows(out), graded_on_error, desc


ROW_SELECT = ("agent_id, question_id, coalesce(outcome,''), coalesce(passed::text,'')"
              ", replace(replace(left(coalesce(actual_answer,''),160), E'\\t',' '), E'\\n',' ')"
              ", replace(replace(left(coalesce(failure_reason,''),200), E'\\t',' '), E'\\n',' ')")


def parse_rows(out: str) -> list[dict]:
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = (line.split("\t") + [""] * 6)[:6]
        rows.append({"agent": parts[0], "question": parts[1], "outcome": parts[2] or None,
                     "passed": None if parts[3] == "" else parts[3] == "true",
                     "answer": parts[4], "reason": parts[5]})
    return rows


def latest_per_fixture(fixture_ids: set[str]) -> list[dict] | None:
    """Each CURRENT fixture's newest row since runs carried a run_id (the honest log). None = unreadable."""
    out = psql(f"select distinct on (agent_id, question_id) {ROW_SELECT} from public.ai_quality_log "
               "where agent_id <> '__heartbeat__' and run_id is not null and outcome is not null "
               "order by agent_id, question_id, run_at desc")
    if out is None:
        return None
    return [r for r in parse_rows(out) if r["question"] in fixture_ids]


# ── self-test ────────────────────────────────────────────────────────────────────────────────────────────
def self_test() -> int:
    src = RUNNER.read_text(encoding="utf-8")
    gw = GATEWAY.read_text(encoding="utf-8")
    ok = True

    def expect(name: str, fails: list[str], should_fail: bool) -> None:
        nonlocal ok
        good = bool(fails) == should_fail
        ok &= good
        print(f"  {GREEN + 'ok  ' if good else RED + 'BAD '}{RST} {name}: {'FAIL' if fails else 'PASS'}"
              f" (expected {'FAIL' if should_fail else 'PASS'})" + (f" - {fails[0][:110]}" if fails and not good else ""))

    expect("current runner, L1", check_bearer(src, gw), False)
    expect("current runner, L2", check_honesty(src), False)
    expect("current runner, L1b answer path", check_answer_path(src, gw), False)
    m5 = src.replace("j?.data?.answer ?? ", "")
    expect("mutant: answer read at the pre-envelope top level", check_answer_path(m5, gw), True)

    bearer = gateway_call_bearer(src) or ""
    m1 = src.replace(bearer, "`Bearer ${SERVICE_KEY}`", 1) if bearer else src
    expect("mutant: bearer back to the service key", check_bearer(m1, gw), True)
    m2 = src.replace(".verifyOtp(", ".noSuchCall(")
    expect("mutant: the session mint removed", check_bearer(m2, gw), True)
    i = src.find("functions/v1/ai-gateway")
    pre = src[:max(0, i - 60)] + PRE_FIX_FETCH + src[i + 1500:] if i >= 0 else PRE_FIX_FETCH
    expect("the pre-fix fetch block (2026-10-07)", check_bearer(pre, gw), True)
    gw_open = re.sub(r"ANON_OK_AGENTS\s*=\s*new\s+Set\(\s*\[[^\]]*\]",
                     'ANON_OK_AGENTS = new Set(["' + '", "'.join(runner_agents(src)) + '"]', gw, count=1)
    expect("pre-fix bearer, gateway that accepts every fixture agent anonymously", check_bearer(pre, gw_open), False)
    m3 = re.sub(r"infra\w*\s*\?\s*null\s*:\s*await\s+judgeAnswer\(", "await judgeAnswer(", src)
    expect("mutant: the judge made unconditional", check_honesty(m3), True)
    m4 = src.replace('"infra_error"', '"graded"')
    expect("mutant: infra rows relabelled graded", check_honesty(m4), True)

    old = [{"agent": "analytics", "outcome": None, "passed": False, "answer": "[gateway error: 401]", "reason": "score=0"}] * 18
    expect("data: the 2026-10-07 history (18 graded 401s)", judge_run(old, graded_on_error_anywhere=18)[0], True)
    honest_dead = [{"agent": "shift", "outcome": "infra_error", "passed": None, "answer": "[gateway error: 401]",
                    "reason": "infra: gateway 401"}] * 6
    expect("data: an honest run that answered nothing", judge_run(honest_dead)[0], True)
    mostly = ([{"agent": "analytics", "outcome": "graded", "passed": True, "answer": "OEE is 71%", "reason": ""}] * 4
              + [{"agent": "asset-brain", "outcome": "infra_error", "passed": None, "answer": "[gateway error: 400]",
                  "reason": "infra: gateway 400"}] * 2)
    expect("data: a mostly-measured run (4 graded, 2 infra)", judge_run(mostly)[0], False)
    half_dead = mostly[:2] + mostly[4:] * 2
    expect("data: a run 2 graded / 4 infra", judge_run(half_dead)[0], True)

    # ── L4 / L5 / L6 ──
    seed_body, _ = migration_function_body("ai_eval_bench_ensure")
    reset_body, _ = migration_function_body("ai_eval_bench_reset_memory")
    expect("current runner, L4 context", check_context_static(src, gw, seed_body), False)
    expect("current runner, L5 independence", check_memory_reset(src, gw, reset_body), False)
    expect("current runner, L6 time budget", check_time_budget(src), False)
    jobs_now, _ = eval_cron_jobs_static()
    expect("newest eval schedule (one call per agent)", check_schedule(jobs_now, fixtures_by_agent(src)), False)

    expect("mutant: the bench is never seeded",
           check_context_static(src.replace('.rpc("ai_eval_bench_ensure"', '.rpc("no_such_seeder"'), gw, seed_body), True)
    expect("mutant: asset-brain given no bench subject",
           check_context_static(re.sub(r'"asset-brain":\s*\{\s*asset:\s*"[^"]*"\s*\}', '"asset-brain": {}', src, count=1),
                                gw, seed_body), True)
    expect("mutant: the gateway call sends the raw fixture.context",
           check_context_static(src.replace("context: gatewayContext,", "context: fixture.context || {},"), gw, seed_body), True)
    expect("mutant: a fixture asks about an asset the seeder never creates",
           check_context_static(src.replace('tag_id: "PMP-001"', 'tag_id: "PMP-404"', 1), gw, seed_body), True)
    expect("no seeder migration at all", check_context_static(src, gw, None), True)
    loop_reset = "const r = await resetEvalMemory(db, evalSession.authUid, keys);"
    expect("mutant: the per-fixture memory reset removed",
           check_memory_reset(src.replace(loop_reset, "const r = { deleted: {}, error: null };"), gw, reset_body), True)
    expect("mutant: the reset forgets agent_episodic_memory",
           check_memory_reset(src, gw, re.sub(r"DELETE\s+FROM\s+public\.agent_episodic_memory[^;]*;", "", reset_body or "")), True)
    expect("mutant: no time-budget guard",
           check_time_budget(re.sub(r"spent\s*>\s*RUN_BUDGET_MS", "false", src)), True)
    old_cron = MIGRATIONS / "20260511000006_ai_quality_log.sql"
    if old_cron.exists():
        jobs_old, _ = eval_cron_jobs_static(old_cron.read_text(encoding="utf-8", errors="replace"))
        expect("the 2026-05-11 schedule (all 18 fixtures in one call)", check_schedule(jobs_old, fixtures_by_agent(src)), True)
    expect("a sliced schedule that forgets an agent",
           check_schedule([j for j in jobs_now if "'shift'" not in j[1]], fixtures_by_agent(src)), True)

    # the runner as it stood at HEAD this morning (before the bench, the reset and the budget)
    try:
        head = subprocess.run(["git", "show", "HEAD:supabase/functions/ai-eval-runner/index.ts"], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        head_src = head.stdout if head.returncode == 0 else ""
    except Exception:
        head_src = ""
    if head_src:
        expect("HEAD runner, L4 context", check_context_static(head_src, gw, seed_body), True)
        expect("HEAD runner, L5 independence", check_memory_reset(head_src, gw, reset_body), True)
        expect("HEAD runner, L6 time budget", check_time_budget(head_src), True)

    # live-shaped rows: the state the first authorised run left behind (2026-10-07)
    ab400 = {"agent": "asset-brain", "question": "asset-brain-failure-history", "outcome": "infra_error", "passed": None,
             "answer": "[gateway error: 400]",
             "reason": 'infra: gateway 400: {"error":"Agent returned 400: {\\"error\\":\\"Missing required fields: '
                       'question, asset_id, hive_id\\"}"}'}
    an_empty = {"agent": "analytics", "question": "analytics-oee-last-week", "outcome": "graded", "passed": False,
                "answer": "No failures logged this period.", "reason": "score=0 missing=OEE"}
    lv_ok = {"agent": "logbook-voice", "question": "lv-fault-entry", "outcome": "graded", "passed": True,
             "answer": '{"ok":true,"entry":{"problem":"Pump bearing seized"}}', "reason": ""}
    an_ok = {"agent": "analytics", "question": "analytics-mtbf-trend", "outcome": "graded", "passed": False,
             "answer": "PMP-001 MTBF fell from 32 to 9 days across five seal and bearing failures.", "reason": "score=60"}
    expect("data: the latest run is clean but asset-brain was last refused 400 (missing asset_id)",
           judge_context([lv_ok], [ab400, lv_ok]), True)
    expect("data: analytics graded on an empty hive", judge_context([an_empty, lv_ok], []), True)
    expect("data: a not-on-the-bench infra row",
           judge_context([{**ab400, "reason": "infra: missing context: asset PMP-404 is not on the eval bench"}], []), True)
    expect("data: every fixture measured with context", judge_context([an_ok, lv_ok], [an_ok, lv_ok]), False)
    expect("data: an honest provider outage is not a context failure",
           judge_context([{**ab400, "reason": "infra: gateway 503: all providers at capacity"}], []), False)

    print(f"\n{'self-test PASS' if ok else 'self-test FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    print("\033[1mai-eval-answers-real - the nightly eval measured answers, not graded errors\033[0m")
    src = RUNNER.read_text(encoding="utf-8")
    gw = GATEWAY.read_text(encoding="utf-8")
    fails = check_bearer(src, gw) + check_answer_path(src, gw) + check_honesty(src)
    warns: list[str] = []

    seed_body, seed_file = migration_function_body("ai_eval_bench_ensure")
    reset_body, reset_file = migration_function_body("ai_eval_bench_reset_memory")
    fails += check_context_static(src, gw, seed_body)
    fails += check_memory_reset(src, gw, reset_body)
    fails += check_time_budget(src)
    by_agent = fixtures_by_agent(src)
    jobs = eval_cron_jobs_live()
    sched_src = "live cron.job"
    if jobs is None:
        jobs, sched_src = eval_cron_jobs_static()
        sched_src = f"migration {sched_src or '(none)'}"
    if not jobs:
        warns.append(f"L6 no scheduled ai-eval-runner call found ({sched_src}) - nothing measures the agents nightly")
    fails += check_schedule(jobs, by_agent)
    print(f"  L4-L6 seeder {seed_file or '(none)'}, reset {reset_file or '(none)'}, "
          f"{len(jobs)} scheduled eval call(s) from {sched_src}")

    rows, goe, desc = latest_run_rows()
    if rows is None:
        warns.append(f"L3 SKIP - {desc}; the static layers decide this run")
    else:
        f3, w3 = judge_run(rows, goe)
        n_inf = sum(1 for r in rows if is_infra(r))
        print(f"  L3 {desc}: {len(rows)} fixture row(s), {len(rows) - n_inf} measured, {n_inf} infra")
        fails += f3
        warns += w3
        per_fx = latest_per_fixture({q for qs in by_agent.values() for q in qs})
        if per_fx is None:
            warns.append("L4 live SKIP - the per-fixture history could not be read")
        else:
            fails += judge_context(rows, per_fx)
            never = sorted({q for qs in by_agent.values() for q in qs} - {r["question"] for r in per_fx})
            if never:
                warns.append(f"L4 {len(never)} fixture(s) have no measurement since runs carried a run_id: "
                             f"{', '.join(never[:6])}{' ...' if len(never) > 6 else ''}")
    for w in warns:
        print(f"  {YEL}WARN{RST} {w}")
    for f in fails:
        print(f"  {RED}FAIL{RST} {f}")
    if fails:
        print(f"\n{RED}ai-eval-answers-real: FAIL ({len(fails)}){RST}")
        return 1
    print(f"\n{GREEN}ai-eval-answers-real: PASS{RST} (bearer accepted, infra rows ungraded, latest run measured, "
          f"every fixture given its context, memory reset per fixture, every call inside the time limit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
