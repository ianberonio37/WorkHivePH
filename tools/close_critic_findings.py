#!/usr/bin/env python3
"""
close_critic_findings — close critic findings against the page's CURRENT rubric dimensions (2026-09-05).

The critic bank's open findings are rubric dimensions that failed on a page at walk time (e.g. "platform-actions.html:
S1 50% — declared=[8,12,16] · offRadius=5/42"). When a later fix wave clears that dimension and a --page sweep
re-verifies the page, the finding is resolved - but the bank must say so per finding, with a receipt, never by
bulk. Rules:
  * a finding is CLEAN when its page's latest sweep (family_rubric_scoreboard.page.json, then the board's
    family_rubric_scoreboard.json) does not list its dim among the page's failing dims;
  * a row closes (status -> improving, improvement_refs written) ONLY when EVERY one of its findings is clean -
    a partially-clean row stays open and is reported with its remaining dims (an honest backlog, never a
    bulk close). Rows that are not rubric-dimension findings (evidence without "<page>: <DIM> <n>%") are skipped;
  * the ref names the sweep, the page, its overall and the date; the lock is the board's family-rubric-ratchet.
  python tools/close_critic_findings.py            # dry run: what would close, what stays open (top remaining dims)
  python tools/close_critic_findings.py --apply    # write improvement_refs + status improving; validate the bank
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
PAGE_JSON = ROOT / "family_rubric_scoreboard.page.json"
BOARD_JSON = ROOT / "family_rubric_scoreboard.json"
# ★THE CLOSER COULD ONLY READ THE BOARD'S NAMESPACE, SO AN MCP WALK'S FINDINGS COULD NEVER CLOSE
# (2026-09-11). This pattern required `<page>.html:` and the two bankers do not agree on that string:
# `critic_from_board.py` writes the board's FILENAME ("offline-fallback.html: A2 50% ...") while
# `bank_critic_walk.py` writes the survey's `pageId`, which is a bare stem ("hive: A2 50% ..."), because
# that is what a walker passes to `__RUBRIC.survey({pageId:'hive'})`. So every finding banked by an
# in-motion MCP walk fell into the "skip" branch below - counted as non-dimension evidence and skipped
# forever, no matter how many times the page was later fixed and re-swept. 109 hive findings sat in
# exactly that state. This is the SAME structural gap `record_mcp_walk.py` was written to close on the
# trajectory side: the MCP half writes into a namespace the consumer cannot read, and the fix belongs in
# the READER so that no banked evidence has to be rewritten - history stays as it was recorded.
# `.html` is now optional and a bare stem is resolved against the state's filename keys (see _state_for).
DIM_RE = re.compile(r"^(?P<page>[\w./-]+?)(?:\.html)?:\s*(?P<dim>[A-Z]{1,2}\d)\s+\d+%")
TODAY = date.today().isoformat()


LATEST = ROOT / ".tmp" / "critic_page_state.json"   # the closer's own memory: newest sweep per page, merged across page-set runs


def _state_for(pg: str, state: dict):
    """Resolve a finding's page NAME to the sweep state's key, and return (resolved_name, state_or_None).

    The two bankers write two different names for the same page (see DIM_RE above), and the sweep state is
    keyed by PATH: 'hive.html', but also 'learn/mtbf-vs-mttr-for-supervisors/index.html'. A survey's
    `pageId` for a learn article is just its slug ('best-free-cmms-software-philippines'), so a plain
    `state.get(pg)` misses it and the row is reported as "page not swept" - which is a different problem
    from "page never measured" and sends a reader off to run a sweep that already ran. Tried in order:
    the exact name, the '<pg>.html' filename, then any state key ending '/<pg>/index.html' (learn/, tools/
    and any future nested family). Returns the resolved key so the closer's refs name the real path.
    """
    # `<pg>/index.html` before the suffix scan: a TOP-LEVEL family index ("learn" -> "learn/index.html")
    # has no leading slash, so the `/<pg>/index.html` tail below cannot match it. Found by 12 rows that
    # stayed blocked on the page id `learn` after its own sweep had already run.
    for cand in (pg, f"{pg}.html", f"{pg}/index.html"):
        if cand in state:
            return cand, state[cand]
    tail = f"/{pg}/index.html"
    for k in state:
        if k.endswith(tail):
            return k, state[k]
    return pg, None


def page_state() -> dict:
    """page -> {'overall': n, 'failing_dims': set, 'source': name}.
    Each --page sweep OVERWRITES family_rubric_scoreboard.page.json with only its set, so a closer that read it alone
    saw one set fresh and the days-old board for every other page - a row whose findings span two sets could never
    close (2026-09-06). The closer keeps its own merged state (.tmp/critic_page_state.json): the newest result per
    page, updated from every page run it sees, with the board as the floor for pages never swept alone."""
    dim_re = re.compile(r"^([A-Z]{1,2}\d)\b")
    def parse(d, name):
        got = {}
        for pg, v in (d.get("pages") or {}).items():
            fails = sorted({m.group(1) for f in (v.get("failing") or []) for m in [dim_re.match(str(f))] if m})
            got[pg] = {"overall": v.get("overall"), "failing": fails, "source": name}
        return got
    latest = {}
    if LATEST.exists():
        try:
            latest = json.loads(LATEST.read_text(encoding="utf-8"))
        except Exception:
            latest = {}
    board = {}
    if BOARD_JSON.exists():
        try:
            board = parse(json.loads(BOARD_JSON.read_text(encoding="utf-8")), "board")
        except Exception:
            pass
    if PAGE_JSON.exists():
        try:
            run = parse(json.loads(PAGE_JSON.read_text(encoding="utf-8")), "page-run")
            mtime = PAGE_JSON.stat().st_mtime
            for pg, v in run.items():
                v["mtime"] = mtime
                prev = latest.get(pg)
                if not prev or mtime >= float(prev.get("mtime") or 0):
                    latest[pg] = v
            LATEST.parent.mkdir(parents=True, exist_ok=True)
            LATEST.write_text(json.dumps(latest, indent=1), encoding="utf-8")
        except Exception:
            pass
    out = {}
    for pg, v in board.items():
        out[pg] = {"overall": v["overall"], "failing_dims": set(v["failing"]), "source": "board"}
    for pg, v in latest.items():
        out[pg] = {"overall": v["overall"], "failing_dims": set(v["failing"]), "source": "page-run"}
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    critic = json.loads(CRITIC.read_text(encoding="utf-8"))
    state = page_state()
    closable, partial, skipped = [], [], 0
    unparseable = unswept = 0
    unswept_pages: Counter = Counter()
    remaining = Counter()
    for r in critic["rows"]:
        if r.get("status") not in ("critiqued", "improving") or not (r.get("findings") or []) or (r.get("improvement_refs") or []):
            continue
        verdicts = []
        for f in r["findings"]:
            m = DIM_RE.match(str(f.get("evidence") or ""))
            if not m:
                verdicts.append(("skip", None, None)); continue
            pg, dim = m.group("page"), m.group("dim")
            pg, st = _state_for(pg, state)
            if st is None:
                verdicts.append(("unknown", pg, dim)); continue
            verdicts.append(("clean" if dim not in st["failing_dims"] else "open", pg, dim))
        # ★ONE COUNTER FOR TWO DIFFERENT PROBLEMS SENDS THE READER TO THE WRONG FIX (2026-09-11).
        # "skipped: 670" merged rows whose evidence this tool CANNOT PARSE with rows whose page has simply
        # NEVER BEEN SWEPT. The first is a tooling bug to fix here; the second is a sweep to go and run.
        # Reported as one number, the honest reading of a 670 was unavailable - and the real split was
        # 0 unparseable and 286 findings on five learn articles. Kin of
        # [[feedback_the_instrument_must_explain_its_own_number]].
        if any(v[0] == "skip" for v in verdicts):
            skipped += 1; unparseable += 1; continue
        if any(v[0] == "unknown" for v in verdicts):
            skipped += 1; unswept += 1
            for v in verdicts:
                if v[0] == "unknown":
                    unswept_pages[v[1]] += 1
            continue
        if all(v[0] == "clean" for v in verdicts):
            closable.append((r, verdicts))
        else:
            partial.append((r, verdicts))
            for v in verdicts:
                if v[0] == "open":
                    remaining[f"{v[1]} {v[2]}"] += 1
    print(f"open rows examined: {len(closable) + len(partial) + skipped} · closable (every finding clean): {len(closable)} · partial (stay open): {len(partial)} · skipped: {skipped}")
    print(f"  skipped, split by CAUSE (a merged count sends you to the wrong fix): "
          f"evidence this tool cannot parse = {unparseable} (a bug HERE) · page never swept = {unswept} (a sweep to RUN)")
    if unswept_pages:
        print("  pages a row is waiting on (page: rows blocked) — run family_rubric_sweep --page for these:")
        for k, n in unswept_pages.most_common(10):
            print(f"    {n:4} {k}")
    print("remaining open dims across partial rows (page dim: findings):")
    for k, n in remaining.most_common(14):
        print(f"  {n:3} {k}")
    if not apply:
        return 0
    for r, verdicts in closable:
        pages = sorted({v[1] for v in verdicts}); dims = sorted({v[2] for v in verdicts})
        refs = []
        for pg in pages:
            st = state[pg]
            refs.append(f"{TODAY}: {pg} re-swept at {st['overall']}% ({st['source']}) with {', '.join(d for d in dims)} clean - the P-program fix waves of 2026-09-05 (radius scale, KPI numerals, help affordance, copy, back link, CLS reserves, contrast tints, headings); lock = family-rubric-ratchet on the full board")
        r["improvement_refs"] = refs
        r["status"] = "improving"
    critic["updated"] = TODAY
    CRITIC.write_text(json.dumps(critic, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"applied: {len(closable)} rows -> improving with improvement_refs")
    v = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_critic_registry.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((v.stdout or v.stderr).strip().splitlines()[-1][:160])
    s = subprocess.run([sys.executable, str(ROOT / "tools" / "update_critic_scoreboard.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((s.stdout or s.stderr).strip().splitlines()[-1][:160] if (s.stdout or s.stderr).strip() else "scoreboard updated")
    return 0 if v.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
