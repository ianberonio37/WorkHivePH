#!/usr/bin/env python3
"""
bug_repro_inventory.py — the MEASURED population for the BUG-REPRO wave (BRP).

Ian, 2026-10-04: *"we have to expand and extend the number of trajectories in our roadmap, where we have
to bug reproduced and fix, so that it would improve the entire Full Stack SaaS Layers and its UFAI UI UX
for my entire platform."*

A bug-repro trajectory is not "go look at page X". It is one CONCRETE site with a known mechanism, a
reproduction that can be made to fail on demand, and a fix target. So this wave's size is DERIVED from
inventories measured against the real source and the real schema — never typed, and never invented. If a
class cannot be measured, it does not seed rows.

★WHY THE SEED IS WHAT IT IS. The wave opens on the class Ian hit himself on 2026-10-04: the logbook asset
picker was empty while Asset Hub showed the same assets, because one scoped ownership by `worker_name` (a
localStorage display string) and the other by `auth_uid`. `bind_asset_nodes_submitter()` always binds
auth_uid but only overwrites worker_name when a hive_members row matches on `hive_id = NEW.hive_id`, which
is never true for a personal asset (hive_id NULL) — so the name is frozen at whatever the client sent while
the uid stays correct forever. One fix, one gate, and then the sweep found the same shape at 100+ sites.

CLASSES (each measurable, each with its own repro recipe):

  A · OWNERSHIP-BY-DISPLAY-NAME   a page filters a table by worker_name where the table also carries
                                  auth_uid. The name is the weaker key. Repro: drift the display name by
                                  one character and the person's own rows disappear.
                                  Layer AU. Fix: union the uid query in (never swap — rows whose auth_uid
                                  was never bound are findable only by name).

  B · VIEW DROPS THE IDENTITY     a truth VIEW exposes worker_name but not the auth_uid its base table
                                  carries, so no consumer of that view can ask the question correctly at
                                  all. Layer D. Fix the view first — it unlocks every consumer at once.

  C · NO IDENTITY COLUMN ANYWHERE a table carries worker_name and no auth_uid, so ownership is only ever
                                  expressible as a name. Layer D. Fix needs a migration before the
                                  client-side fix is even sayable.

Usage:
  python tools/bug_repro_inventory.py            # human summary
  python tools/bug_repro_inventory.py --json     # the machine population (the seeder reads this)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

def _force_utf8_stdout() -> None:
    """★ONLY WHEN RUN AS A SCRIPT (2026-10-04). This used to run at IMPORT time, like the other tools in
    this directory - and those are only ever executed, never imported. This one IS imported, by
    seed_expansion_wave4.bug_repro_rows() and therefore by validate_trajectory_registry, and
    sys.stdout.detach() CLOSES the importer's stdout: the registry gate regenerated its header fine and
    then died with "ValueError: I/O operation on closed file" on its own first print. A module that
    rewrites global I/O on import poisons every caller, so the surgery lives behind __main__."""
    if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# Production scope only. Ian, 2026-09-30: "why you are including the non-production pages in the
# trajectories?" — reuse the one list, never a second copy of the same judgement.
try:
    from seed_expansion_wave4 import LX_NON_PRODUCTION
except Exception:                                      # pragma: no cover - import shape guard
    LX_NON_PRODUCTION = set()

OWNER_FILTER = re.compile(r"\.eq\(\s*['\"]worker_name['\"]\s*,\s*([A-Za-z_$][\w$.]*)\s*\)")
FROM_CALL = re.compile(r"\.from\(\s*['\"]([a-z_]+)['\"]")
# ★THE COLUMN IN A VARIABLE (2026-10-13). index.html's solo home keyed four reads as `.eq(scopeFilter.col,
# scopeFilter.val)` with `scopeFilter = HIVE_ID ? {col:'hive_id',...} : {col:'worker_name', val: workerName}` - a
# name filter the literal OWNER_FILTER can never see, so class A read 0 while a solo worker's home asked pm_assets by
# name alone (found live by the BRP33 drift walk). A scope object that CAN be {col:'worker_name', val:X}, and every
# `.eq(V.col, V.val)` that uses it, is an owner filter bound to X.
SCOPE_OBJ = re.compile(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^;]{0,240}?\{\s*col\s*:\s*['\"]worker_name['\"]\s*,"
                       r"\s*val\s*:\s*([A-Za-z_$][\w$.]*)\s*\}")
# ★THE NAME INSIDE AN EXPRESSION (2026-10-13). inventory.html's fallback edit guarded its update with
# `.eq('worker_name', HIVE_ID && HIVE_ROLE !== 'supervisor' ? WORKER_NAME : prev.worker_name || WORKER_NAME)` - a
# ternary, which OWNER_FILTER (a bare identifier, then the closing paren) can never match. Found beside the BRP16
# drift walk, the one such site on every production page. An expression argument is an owner filter bound to the
# signed-in name when it mentions it, otherwise to the first name-like identifier in it.
OWNER_FILTER_EXPR = re.compile(r"\.eq\(\s*['\"]worker_name['\"]\s*,\s*([^()]{1,220}?)\)")
_BARE_ARG = re.compile(r"^[A-Za-z_$][\w$.]*$")
_ARG_IDENTS = re.compile(r"[A-Za-z_$][\w$.]*")
_JS_WORDS = {"true", "false", "null", "undefined", "typeof", "new", "this", "void", "in", "instanceof"}


class _Hit:
    """one owner filter, whichever spelling it took (the loop below reads start(), end() and group(1))"""
    def __init__(self, start, end, bound):
        self._s, self._e, self._b = start, end, bound

    def start(self):
        return self._s

    def end(self):
        return self._e

    def group(self, _i):
        return self._b


def owner_filters(src: str) -> list:
    hits = [_Hit(m.start(), m.end(), m.group(1)) for m in OWNER_FILTER.finditer(src)]
    for d in SCOPE_OBJ.finditer(src):
        var, bound = d.group(1), d.group(2)
        use = re.compile(r"\.eq\(\s*" + re.escape(var) + r"\.col\s*,\s*" + re.escape(var) + r"\.val\s*\)")
        hits += [_Hit(u.start(), u.end(), bound) for u in use.finditer(src)]
    for e in OWNER_FILTER_EXPR.finditer(src):
        arg = e.group(1).strip()
        if _BARE_ARG.match(arg):
            continue                      # OWNER_FILTER's own spelling, already counted above
        names = [t for t in _ARG_IDENTS.findall(re.sub(r"(['\"]).*?\1", "", arg)) if t not in _JS_WORDS]
        if not names:
            continue                      # a literal: not a name taken from anyone
        bound = next((t for t in names if t in SELF_BINDINGS), None) or next(
            (t for t in names if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", t)), names[0])
        hits.append(_Hit(e.start(), e.end(), bound))
    return sorted(hits, key=lambda h: h.start())

# Reads that are NOT an ownership question, so the display name is the right key and these seed no row.
NOT_OWNERSHIP = {"marketplace_platform_admins"}

# ★hive_members IS BOTH, AND THE DISCRIMINATOR IS WHO IS BEING LOOKED UP (2026-10-04). The first version
# excluded this table wholesale as "the ROSTER: looking a teammate up by the name shown on screen is the
# point" - true for a teammate, and badly wrong for MY OWN row, which is the hive ACCESS GATE.
# logbook.html asked `hive_members.worker_name = WORKER_NAME` to decide whether to let the person in, so a
# display name that had drifted from the one stored on their membership row failed the gate, the page
# returned early, and the asset picker never loaded. That is the real shape behind Ian's report: the
# visible symptom was an empty dropdown, the actual symptom was being LOCKED OUT OF YOUR OWN HIVE. It
# showed up as a prover that passed and failed on alternate runs - the difference was only whether a hive
# was active, because with no hive the gate is skipped.
# So: bound to WORKER_NAME = my own membership = the gate = a defect site. Bound to anything else
# (a teammate, a dataset attribute, a clicked row) = a roster lookup, correctly keyed by the name on screen.
SELF_ONLY_TABLES = {"hive_members"}
SELF_BINDINGS = {"WORKER_NAME"}


def _psql(sql: str) -> list[dict]:
    """Ask the LOCAL database. Schema facts are measured, never remembered."""
    cmd = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
           "-tAF\x1f", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr.strip()[:300]}")
    out = []
    for line in r.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        # ★'t' OR 'true', AND THE FIRST VERSION ONLY ACCEPTED 't' (2026-10-04). The query casts
        # bool_or(...)::text, so psql prints "true"/"false"; a bare boolean column prints "t"/"f". Testing
        # only for "t" made EVERY table read as "no auth_uid", which put all 84 sites in class C and
        # reported classes A and B as empty — a clean-looking inventory that contradicted a direct schema
        # read taken minutes earlier. Accept both spellings so the parse cannot silently invert the result.
        def _b(v: str) -> bool:
            return v.strip().lower() in ("t", "true", "yes", "1")
        out.append({"name": parts[0], "kind": parts[1], "uid": _b(parts[2]), "wname": _b(parts[3])})
    return out


def schema_facts() -> dict[str, dict]:
    rows = _psql(
        "select c.table_name, c.table_type,"
        " bool_or(col.column_name='auth_uid')::text,"
        " bool_or(col.column_name='worker_name')::text"
        " from information_schema.tables c"
        " join information_schema.columns col"
        "   on col.table_schema=c.table_schema and col.table_name=c.table_name"
        " where c.table_schema='public'"
        " group by 1,2")
    return {r["name"]: r for r in rows}


def base_of_view(view: str) -> str | None:
    """The base table a truth view is named after: v_<thing>_truth -> <thing>."""
    m = re.fullmatch(r"v_(.+)_truth", view)
    return m.group(1) if m else None


# ★A DEFECT SITE INSIDE A FUNCTION NOTHING CALLS IS NOT A DEFECT (2026-10-05). Four class-A sites were being
# counted in assistant.html's `buildSystemPrompt` - the reads that ground the AI on a person's own logbook,
# schedule, skills and voice journal, each filtered `.eq('worker_name', name)`. That WOULD be the defect Ian
# reported, and worse on this surface, because grounding an AI answer on the wrong person's records leaks their
# work into a reply. But the function is unreachable: the page's own comments say so in three places, and it
# checks out mechanically - zero call sites outside the definition, and `_systemPrompt` (the only thing its
# result was ever assigned to) now appears exactly ONCE in the whole repo, inside a comment. An earlier session
# had already descoped these as dead code; this tool did not know, so it kept them in the population that drives
# the bug-repro ratchet - a count that can never reach 0 because four of its members are unreachable.
#
# ★THE EXCLUSION IS ASSERTED, NOT DECLARED. Naming a function dead in a dict is the "declared mechanism is not a
# mechanism" error: the day somebody wires it back up, the dict keeps vouching for the old truth and four real
# defects go uncounted. So dead_ranges() PROVES it on every run - the name must appear zero times as a CALL
# outside its own definition, with comments stripped first - and a function that fails the proof is scanned
# normally. Re-wire buildSystemPrompt and these four sites come straight back into the count.
DEAD_FUNCTIONS = {
    "assistant.html": ["buildSystemPrompt"],
}


def _strip_comments_js(src: str) -> str:
    """Comments mention a function far more often than code calls it, so they must not count as call sites.

    Both comment forms are blanked to SPACES of equal length (newlines preserved), so every byte offset and
    line number in the stripped copy still matches the original - the caller reports line numbers from it.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n - 1:
        if src[i] == "/" and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif src[i] == "/" and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def dead_ranges(page: str, src: str) -> list[tuple[int, int]]:
    """Byte ranges of functions declared dead for this page AND proven unreachable on this run."""
    ranges: list[tuple[int, int]] = []
    code = _strip_comments_js(src)
    for fn in DEAD_FUNCTIONS.get(page, []):
        decl = re.search(r"(?:async\s+)?function\s+" + re.escape(fn) + r"\s*\(", code)
        if not decl:
            continue
        calls = [m for m in re.finditer(re.escape(fn) + r"\s*\(", code)
                 if not (decl.start() <= m.start() <= decl.end())]
        if calls:
            continue                      # it IS called - the declaration is stale, so scan it normally
        brace = code.find("{", decl.end() - 1)
        if brace < 0:
            continue
        depth, k = 0, brace
        while k < len(code):
            if code[k] == "{":
                depth += 1
            elif code[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        ranges.append((decl.start(), k))
    return ranges


def collect(sources: dict | None = None) -> list[dict]:
    """sources: {page: source} read in place of the file on disk - how a teeth test runs the whole judgement on a
    committed or mutated copy of one page without writing it into the tree"""
    facts = schema_facts()
    sites: list[dict] = []
    seen_view_gap: set[str] = set()

    for f in sorted(ROOT.glob("*.html")):
        page = f.name
        if page in LX_NON_PRODUCTION or re.search(r"-test\.html$|\.backup", page):
            continue
        src = (sources or {}).get(page) or f.read_text(encoding="utf-8", errors="ignore")
        dead = dead_ranges(page, src)
        for m in owner_filters(src):
            if any(a <= m.start() <= b for a, b in dead):
                continue                  # inside a function proven unreachable on this run
            line = src[:m.start()].count("\n") + 1
            back = src[max(0, m.start() - 400):m.start()]
            tbls = FROM_CALL.findall(back)
            if not tbls:
                continue
            tbl = tbls[-1]
            if tbl in NOT_OWNERSHIP:
                continue
            # A self-only table counts ONLY when the filter names the signed-in person (see the note on
            # SELF_ONLY_TABLES): that is the access gate, not a roster lookup.
            if tbl in SELF_ONLY_TABLES and m.group(1) not in SELF_BINDINGS:
                continue
            fact = facts.get(tbl)
            if not fact:
                continue
            # ★ALREADY FIXED IS NOT A DEFECT (2026-10-04). The correct shape for class A is the name query
            # UNIONED with an auth_uid query - never a swap, because rows whose auth_uid was never bound
            # are findable only by name. So a site that still filters on worker_name BESIDE an auth_uid
            # filter on the same relation is right, and counting it would seed a row that can never
            # honestly close. The first version of this inventory had no such check and flagged the
            # logbook asset picker that had just been fixed and gated. Window, not whole file: a page may
            # scope one read by identity and another by name, and only the second is the defect.
            # ±2500, not ±900: the first window was too small to see its own evidence. In logbook's asset
            # picker the uid query sits beside the name query but behind a ~1,500-character explanatory
            # comment, so the sites read as unfixed and would have been swept a second time. This codebase
            # comments heavily by design, so the window has to clear a long comment to find the sibling
            # filter. Still a window and not the whole file: a page may scope one read by identity and
            # another by name, and only the second is the defect.
            # ★"ALREADY FIXED" MEANS IN THE SAME QUERY CHAIN, NOT MERELY NEARBY IN THE FILE
            # (2026-10-04, and a teeth test caught it). Three spellings count as the fix, because this
            # wave produced all three:
            #   .eq('auth_uid', …)        a tightened write guard, or a sibling identity query
            #   auth_uid.eq.<uid>         the PostgREST or() filter a union builds as a STRING
            #   _MINE() / _mineFilter()   the helper that builds that string
            # But the FIRST version searched a flat ±2500-char window, and once `_MINE()` was one of the
            # patterns that made the check far too permissive: on any page that uses the helper ANYWHERE,
            # a name filter 2,000 characters away read as already-fixed. Proven by mutation - reverting
            # one `.or(_MINE())` in skillmatrix.html back to a name filter did NOT move the count, so the
            # ratchet had gone blind on every page this wave had touched. The fix must therefore be in the
            # SAME STATEMENT: span from the nearest preceding `.from(` to the first `;` after the match,
            # which is exactly one PostgREST chain. The ±2500 span is still used for the ONE case that is
            # legitimately cross-statement - a sibling query in the same Promise.all, as the logbook asset
            # picker has - but there it must be a real `.eq('auth_uid'` or `auth_uid.eq.`, never the helper
            # NAME, because a helper call proves only that the file knows the idiom.
            chain_start = src.rfind(".from(", max(0, m.start() - 1200), m.start())
            chain_end = src.find(";", m.end())
            chain = src[chain_start if chain_start != -1 else max(0, m.start() - 300):
                        chain_end if chain_end != -1 else m.end() + 300]
            # A chain that also keys on the PRIMARY KEY is already correct, and more strongly than auth_uid
            # would be: `.eq('id', <row id>)` targets one exact row, so a name filter beside it is
            # belt-and-braces rather than the scope. That is how the seller trust-badge writes were fixed -
            # founder-console, platform-actions and marketplace-admin now carry the clicked row's id and
            # keep the name only as a fallback for a DOM rendered before the change. Without this the
            # inventory kept reporting those fallback branches as live defects.
            # ★BUT NOT WHEN THE NAME IS THE SIGNED-IN PERSON'S (2026-10-13). AND-ed with the id, a filter on MY name
            # is not belt-and-braces: it is the ownership guard itself, and a device whose name drifted matches NO
            # row - PostgREST answers a write that matched nothing with 204 and no error, so the page reports a save
            # that never happened (inventory.html's fallback edit). The id makes a name filter harmless only when the
            # name is someone else's, carried with the clicked row.
            if re.search(r"\.eq\(\s*['\"]auth_uid['\"]|auth_uid\.eq\.|_[mM]ineFilter\(\)|_MINE\(\)", chain):
                continue
            if re.search(r"\.eq\(\s*['\"]id['\"]\s*,", chain) and m.group(1) not in SELF_BINDINGS:
                continue
            sibling = src[max(0, m.start() - 2500):m.start() + 2500]
            if re.search(r"\.eq\(\s*['\"]auth_uid['\"]|auth_uid\.eq\.", sibling):
                continue
            # ★WHOSE ROWS IS THIS ASKING FOR? (scope, added 2026-10-04.) Two defects wear the same
            # syntax, and the fixes point in opposite directions:
            #   scope="self"   the filter names the SIGNED-IN person (WORKER_NAME) -> this is ownership,
            #                  and the fix is the union `.or(auth_uid…,worker_name…)` on a read or
            #                  `.eq('auth_uid', …)` on a write guard.
            #   scope="named"  the filter names SOMEONE ELSE (a parameter, a dataset attribute, a clicked
            #                  row) -> this is a LOOKUP of a named person, and applying the self-union
            #                  would be a serious bug: hive.html's _openWorkerProfileDrawer(workerName)
            #                  would show MY badges, XP and logbook under a TEAMMATE'S name. Still
            #                  defective - a teammate whose display name drifted shows wrong or empty
            #                  data - but the fix is to pass the identity through from the roster row,
            #                  which is a different and larger change. Counted, never swept.
            # Measured at the split: 29 self, 18 named.
            scope = "self" if m.group(1) in SELF_BINDINGS else "named"
            if fact["uid"]:
                sites.append({"cls": "A", "scope": scope, "page": page, "line": line, "table": tbl,
                              "bound_to": m.group(1), "kind": fact["kind"], "layer": "AU"})
                continue
            # no auth_uid on this relation: is it a VIEW whose BASE table has one? (class B)
            base = base_of_view(tbl)
            if base and facts.get(base, {}).get("uid"):
                sites.append({"cls": "B", "scope": scope, "page": page, "line": line, "table": tbl,
                              "base_table": base, "bound_to": m.group(1), "kind": fact["kind"],
                              "layer": "D"})
                seen_view_gap.add(tbl)
            else:
                sites.append({"cls": "C", "scope": scope, "page": page, "line": line, "table": tbl,
                              "bound_to": m.group(1), "kind": fact["kind"], "layer": "D"})
    # Stable, class-major then page then line: the wave's ids must be reproducible run to run.
    sites.sort(key=lambda s: (s["cls"], s["page"], s["line"]))
    return sites


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    args = ap.parse_args()

    sites = collect()
    if args.json:
        print(json.dumps(sites, indent=1, ensure_ascii=False))
        return 0

    from collections import Counter
    by_cls = Counter(s["cls"] for s in sites)
    print("\nBUG-REPRO INVENTORY (production pages only)")
    print("=" * 74)
    n_self = sum(1 for s in sites if s.get("scope") == "self")
    print(f"  total measured defect sites: {len(sites)}"
          f"   (scope: {n_self} SELF - the union/tighten fix applies"
          f" · {len(sites) - n_self} NAMED - a teammate lookup, fixed by passing the identity through)")
    for c, label in (("A", "ownership by DISPLAY NAME where auth_uid exists  (layer AU)"),
                     ("B", "truth VIEW drops the auth_uid its base table has (layer D)"),
                     ("C", "no identity column anywhere - needs a migration  (layer D)")):
        print(f"    {c} · {label}: {by_cls.get(c, 0)}")
    print()
    for c in ("A", "B", "C"):
        rows = [s for s in sites if s["cls"] == c]
        if not rows:
            continue
        print(f"  class {c} by page:")
        for pg, n in Counter(s["page"] for s in rows).most_common():
            tbls = sorted({s["table"] for s in rows if s["page"] == pg})
            print(f"    {pg:<30} {n:>3}  {', '.join(tbls[:4])}{' …' if len(tbls) > 4 else ''}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
