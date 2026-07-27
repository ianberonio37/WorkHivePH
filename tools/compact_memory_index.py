#!/usr/bin/env python3
"""
compact_memory_index.py — keep the auto-memory MEMORY.md index under the session-load cap.
============================================================================================
WHY (the deterministic flow, not a bandage): MEMORY.md is the index loaded at every session
start. It bloats as each arc appends an entry, eventually exceeding the loader cap (~24.4KB) so
older entries silently stop loading. Instead of me noticing reactively, this TOOL is the Fix
layer of a Prevent→Detect→Fix→Govern discipline:
  - Prevent : CLAUDE.md "Memory Hygiene" rule — new entries are ONE tight line.
  - Detect  : validate_memory_index_budget.py (a registered gate) flags over-budget every run.
  - Fix     : THIS tool — `--apply` curates the index back under budget (auto-backup, reversible).
  - Govern  : CLAUDE.md + knowledge-manager skill make it standing, not per-session memory.

POLICY (the "doctrine-first" curation Ian chose 2026-06-24):
  - KEEP every feedback entry (the behavioral doctrine — NEVER auto-retired) + every reference.
  - Tighten any over-long line deterministically (title/hook caps).
  - Drop exact duplicate links; collapse same-family iteration clusters to one canonical entry.
  - Keep the most-recent / highest-priority PROJECT entries that fit the byte budget; retire the
    rest from the INDEX ONLY — their topic .md files stay on disk and remain Memento-retrievable.

Aligns with Memento: the index becomes the curated always-loaded layer; Memento is the deep
retrieval layer behind it. Retiring a pointer never loses the knowledge.

USAGE:
  python tools/compact_memory_index.py --check        # report size/over-budget; exit 1 if over
  python tools/compact_memory_index.py --apply        # backup + curate + write + retire report
  python tools/compact_memory_index.py --self-test    # detector teeth
Options: --path <MEMORY.md>  --budget <bytes, default 22000>
"""
from __future__ import annotations
import argparse, collections, io, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CHECK_NAMES = ["compact_memory_index"]
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# Default auto-memory index for this project (single-dev machine path; override with --path).
DEFAULT_MEM = Path(
    r"C:\Users\ILBeronio\.claude\projects"
    r"\c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st"
    r"\memory\MEMORY.md"
)
LOAD_CAP = 24400          # the loader BYTE truncation point
DEFAULT_BUDGET = 22000    # byte target (comfortably under the cap)
LINE_CAP = 200            # the loader LINE truncation point
LINE_BUDGET = 138         # line target (single-spaced entries; under the 200 cap)

LINK = re.compile(r"^- \[(.*?)\]\(([^)]+)\)\s*(?:[—-]+\s*(.*))?$")
DATE = re.compile(r"(\d{4})[_-](\d{2})(?:[_-](\d{2}))?")


def category(link: str) -> str:
    b = link.split("/")[-1].lower()
    if b.startswith("feedback"):  return "feedback"
    if b.startswith("reference"): return "reference"
    if b.startswith("project") or b.startswith("handoff"): return "project"
    return "other"


def stars(line: str) -> int:
    head = line[:18]
    return 2 if "⭐⭐" in head else (1 if "⭐" in head else 0)


def date_of(link: str):
    m = DATE.search(link)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else (0, 0, 0)


def completeness(line: str) -> int:
    t = line.lower()
    if any(w in t for w in ["100%", "complete", "→100", "accept", "done"]): return 2
    if any(w in t for w in ["started", "in-progress", "in progress", "step "]): return 0
    return 1


def family(link: str) -> str:
    s = link.split("/")[-1].lower().replace(".md", "")
    s = re.sub(r"^(project|handoff)[_-]", "", s)
    s = re.sub(r"_\d{4}[_-]\d{2}([_-]\d{2})?", "", s)        # dates
    s = re.sub(r"[_-]s?\d+$", "", s)                          # trailing _NN / _sN
    s = re.sub(r"[_-](roadmap|plan|started|wrap|complete|live|push|loop|2)$", "", s)
    return s


def tighten(line: str, title_cap=58, hook_cap=72) -> str:
    m = LINK.match(line.strip())
    if not m:
        return line.strip()
    title, link, hook = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
    if len(title) > title_cap: title = title[:title_cap - 1].rstrip(" -—:") + "…"
    if len(hook) > hook_cap:   hook = hook[:hook_cap - 1].rstrip(" -—,;") + "…"
    return f"- [{title}]({link})" + (f" — {hook}" if hook else "")


def parse(md: str):
    out = []
    for ln in md.splitlines():
        if ln.lstrip().startswith("- ["):
            m = LINK.match(ln.strip())
            link = m.group(2).strip() if m else ""
            out.append({"raw": ln.strip(), "link": link, "cat": category(link)})
    return out


# ── Ian's escape hatch, 2026-07-27: "retire the oldest low-star pointers" ────────────────────────
# The default policy NEVER auto-retires feedback, because feedback is behavioural doctrine. That is
# right as a default and wrong as an absolute: once the index is ~190 entries and nearly all of them
# are feedback, the tool can no longer make headroom at all, and the index drifts toward the load cap
# where entries silently stop loading. So retiring feedback is possible but OPT-IN ONLY — it requires
# an explicit human instruction, never a heuristic the tool applies on its own.
#
# A pointer naming one of these is protected regardless of stars: forgetting it would change what I
# DO, not merely what I know. Losing a "how it works" lesson costs a re-read; losing "never push"
# costs a mistake against Ian's standing rules.
HARD_RULE_PROTECT = (
    "no_remote_push", "commit_only_ian_decides_push", "never_git_checkout_uncommitted",
    "never_write_probe_user_tokens", "pasted_keys_in_docs", "free_tier_only_models",
    "playwright_test_identity", "local_only_tester", "workhive_url_prefix",
    "retrieve_first_no_workflow", "momentum_stop_guard", "live_mcp_writes_pollute",
    "memento_visible_confirmation", "ai_provider", "use_ai_chain_always",
    "local_supabase_rewrite", "deploy_subst", "no_typescript_in_html", "powershell_ascii",
    "dont_stop_hold_trajectory", "skill_first_rule", "new_feature_playbook",
)


def _is_hard_rule(link: str) -> bool:
    return any(p in link for p in HARD_RULE_PROTECT)


def curate(entries, budget, retire_low_star=False):
    """Return (kept_lines_in_order, retired:list[(link,reason)]).

    retire_low_star: when True (opt-in, human-instructed only), feedback entries become eligible for
    retirement — fewest stars first, and within a star tier the LOWEST in the file first, since the
    index is newest-at-top so lowest means oldest. Hard-rule pointers stay regardless."""
    retired = []
    seen = set(); dd = []
    for e in entries:
        if not e["link"]:
            continue
        if e["link"] in seen:
            retired.append((e["link"], "duplicate link")); continue
        seen.add(e["link"]); dd.append(e)

    keep_always = [e for e in dd if e["cat"] in ("feedback", "reference", "other")]
    proj = [e for e in dd if e["cat"] == "project"]

    if retire_low_star:
        # Order of retirement: fewest stars first, then oldest (lowest position) first.
        pos = {e["link"]: i for i, e in enumerate(dd)}
        eligible = [e for e in keep_always if not _is_hard_rule(e["link"])]
        eligible.sort(key=lambda e: (stars(e["raw"]), -pos[e["link"]]))
        # How many lines must go? 2 header lines + one per surviving entry.
        overflow = (2 + len(dd)) - LINE_BUDGET
        drop = set()
        for e in eligible:
            if len(drop) >= overflow:
                break
            drop.add(e["link"])
            retired.append((e["link"],
                            f"low-star retirement ({stars(e['raw'])} stars) — INDEX only, "
                            f"topic file kept and Memento-retrievable"))
        keep_always = [e for e in keep_always if e["link"] not in drop]

    # family-collapse projects to one canonical
    byf = collections.defaultdict(list)
    for e in proj:
        byf[family(e["link"])].append(e)
    canon = []
    for f, grp in byf.items():
        if len(grp) == 1:
            canon.append(grp[0]); continue
        r = sorted(grp, key=lambda e: (stars(e["raw"]), completeness(e["raw"]), date_of(e["link"])), reverse=True)
        canon.append(r[0])
        for e in r[1:]:
            retired.append((e["link"], f"family-collapse -> {r[0]['link']}"))

    # budget: always-keep first, then projects by (stars,date) until EITHER the byte budget
    # or the line budget is hit (single-spaced index → 1 line per entry + 2 header lines).
    chosen = {}
    for e in keep_always:
        chosen[e["link"]] = tighten(e["raw"])
    used = len("# Memory Index\n\n") + sum(len(v.encode()) + 1 for v in chosen.values())
    nlines = 2 + len(chosen)
    for e in sorted(canon, key=lambda e: (stars(e["raw"]), date_of(e["link"])), reverse=True):
        line = tighten(e["raw"]); b = len(line.encode()) + 1
        if used + b <= budget and nlines + 1 <= LINE_BUDGET:
            chosen[e["link"]] = line; used += b; nlines += 1
        else:
            retired.append((e["link"], "budget: older/lower-priority project (file kept, Memento-retrievable)"))

    # emit in original order
    ordered, emitted = [], set()
    for e in entries:
        if e["link"] in chosen and e["link"] not in emitted:
            ordered.append(chosen[e["link"]]); emitted.add(e["link"])
    return ordered, retired


def self_test() -> bool:
    ok = True
    sample = ("# Memory Index\n\n"
              "- [⭐ FEEDBACK: keep me](feedback_x.md) — a rule\n\n"
              "- [Arc A](project_arc_a_2026_01_01.md) — old\n\n"
              "- [Arc A redo](project_arc_a_2026_02_01.md) — newer\n\n"
              "- [dup](project_arc_a_2026_02_01.md) — dup\n")
    kept, ret = curate(parse(sample), budget=22000)
    if not any("feedback_x.md" in k for k in kept):
        print(f"{R}self-test FAIL: dropped a feedback entry.{X}"); ok = False
    if not any("duplicate" in r[1] for r in ret):
        print(f"{R}self-test FAIL: did not catch the duplicate link.{X}"); ok = False
    if not any("family-collapse" in r[1] for r in ret):
        print(f"{R}self-test FAIL: did not collapse the arc family.{X}"); ok = False
    longline = "- [" + "T" * 200 + "](project_z.md) — " + "h" * 300
    if len(tighten(longline)) > 200:
        print(f"{R}self-test FAIL: tighten did not cap a long line.{X}"); ok = False

    # --retire-low-star (opt-in): must retire the LOWEST-star feedback first, must never touch a
    # hard-rule pointer, and must stay OFF by default. An over-budget index of pure feedback.
    over = "# Memory Index\n\n" + "".join(
        f"- [{'⭐' * ((i % 3) + 1)} FB {i}](feedback_topic_{i}.md) — hook\n" for i in range(LINE_BUDGET + 12)
    ) + "- [⭐ FB push](feedback_no_remote_push.md) — never push\n"
    kept_def, _ = curate(parse(over), budget=999999)
    if len(kept_def) < LINE_BUDGET:
        print(f"{R}self-test FAIL: default policy retired feedback without being asked.{X}"); ok = False
    kept_opt, ret_opt = curate(parse(over), budget=999999, retire_low_star=True)
    if len(kept_opt) >= len(kept_def):
        print(f"{R}self-test FAIL: --retire-low-star freed no lines.{X}"); ok = False
    if any("feedback_no_remote_push.md" in k for k in kept_opt) is False:
        print(f"{R}self-test FAIL: retired a HARD-RULE pointer (no_remote_push).{X}"); ok = False
    retired_stars = [r for r in ret_opt if "low-star retirement" in r[1]]
    if retired_stars and not all("(1 stars)" in r[1] for r in retired_stars):
        print(f"{R}self-test FAIL: retirement did not take the fewest-star entries first.{X}"); ok = False
    print((G + "self-test PASS — curation has teeth (keeps feedback, dedups, collapses, caps)." + X)
          if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(DEFAULT_MEM))
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--auto", action="store_true",
                    help="M4.2: deterministically --apply ONLY when over the HARD load cap; else no-op")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--retire-low-star", action="store_true",
                    help="OPT-IN, human-instructed only: allow FEEDBACK pointers to be retired from "
                         "the index, fewest stars first then oldest first, until the line budget is "
                         "met. Hard-rule pointers (push policy, credentials, test identity, ...) are "
                         "never retired. Topic files are untouched and stay Memento-retrievable. "
                         "Never applied by --auto; the default policy still never auto-retires "
                         "feedback, because deciding which doctrine leaves the index is a human call.")
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 1

    p = Path(a.path).resolve()   # absolute so backup/report .with_name() never depends on cwd
    if not p.exists():
        print(f"{R}MEMORY.md not found at {p}{X}"); return 2
    md = p.read_text(encoding="utf-8", errors="replace")
    size = len(md.encode("utf-8"))
    nlines = len(md.splitlines())
    entries = parse(md)
    over = size > a.budget or nlines > LINE_BUDGET

    print(f"{B}MEMORY.md index budget{X}")
    print(f"  path: {p}")
    print(f"  size: {size} bytes ({size/1024:.1f}KB)   lines: {nlines}   entries: {len(entries)}")
    print(f"  budget: {a.budget}B / {LINE_BUDGET} lines   load-cap: {LOAD_CAP}B / {LINE_CAP} lines")

    # M4.2: deterministic auto-fix — compact ONLY when over the HARD load cap (the truncation
    # point), so the index can't silently truncate at the next session load. Under the cap = no-op.
    if a.auto:
        if size > LOAD_CAP or nlines > LINE_CAP:
            print(f"  {Y}AUTO: over hard load cap — compacting deterministically (backed up).{X}")
            a.apply = True   # fall through to the --apply path below
        else:
            print(f"  {G}AUTO: under hard load cap — no compaction needed.{X}")
            return 0

    if a.check or (not a.apply):
        if size > LOAD_CAP or nlines > LINE_CAP:
            # Real failure: the index truncates at session start (older memory not loaded).
            print(f"  {R}FAIL — OVER LOAD CAP ({'bytes' if size>LOAD_CAP else ''}"
                  f"{' & ' if size>LOAD_CAP and nlines>LINE_CAP else ''}{'lines' if nlines>LINE_CAP else ''}): "
                  f"older entries truncate at session start. Run: python tools/compact_memory_index.py --apply{X}")
            return 1
        if over:
            # Advisory only — still loads fully; tighten before it reaches the cap.
            print(f"  {Y}WARN — over the soft budget ({a.budget}B / {LINE_BUDGET} lines) but under the load "
                  f"cap (still loads). Run --apply to curate before it truncates.{X}")
            return 0
        print(f"  {G}OK — under budget, fully loads at session start.{X}")
        return 0

    # --apply  (single-spaced entries → 1 line each, to stay under the LINE cap too)
    # --retire-low-star is deliberately NOT reachable from --auto: an unattended run must never
    # decide on its own which behavioural doctrine stops loading.
    kept, retired = curate(entries, a.budget, retire_low_star=a.retire_low_star)
    new_md = "# Memory Index\n\n" + "\n".join(kept) + "\n"
    nb = len(new_md.encode("utf-8")); nl = len(new_md.splitlines())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bak = p.with_name(f"MEMORY.md.bak-{stamp}")          # not *.md → Memento won't index it
    shutil.copyfile(p, bak)
    p.write_text(new_md, encoding="utf-8")
    cat = collections.Counter(w.split(":")[0].split(" ->")[0].split(" (")[0] for _, w in retired)
    lines = [f"MEMORY.md compaction {stamp} — {len(entries)}->{len(kept)} entries, "
             f"{size}->{nb} bytes; {len(retired)} retired from INDEX (topic files kept + Memento-retrievable).",
             "by reason: " + ", ".join(f"{k}={v}" for k, v in cat.most_common()), ""]
    lines += [f"  - {l}  [{w}]" for l, w in sorted(retired)]
    rep = p.with_name(f"MEMORY.retire-report-{stamp}.txt")
    rep_note = rep.name
    try:                                  # report is diagnostics — never abort a good compaction over it
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        rep_note = f"(report skipped: {e})"

    print(f"  {G}APPLIED{X}: {len(entries)}->{len(kept)} entries, {size}->{nb} bytes ({nb/1024:.1f}KB), "
          f"{nlines}->{nl} lines")
    print(f"  backup : {bak.name}")
    print(f"  report : {rep_note}  ({len(retired)} retired; reasons {dict(cat.most_common())})")
    print(f"  restore: copy the backup back over MEMORY.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
