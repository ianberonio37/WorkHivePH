"""validate_list_caps_say_more.py - SL LB1 (2026-10-21): every list on the LB1 pages is paged or capped, and says when more
exists than it shows.

Measured on the 33 LB1 pages: 241 capped list reads. 47 said nothing past their cap, 85 had some "more" wording somewhere
nearby (not necessarily for THAT list), and 97 carried a note - 23 of them "cap-ok: rows only", which meant "no total is
painted", never "nothing is hidden". Against today's local data 58 caps BIT: alert-hub's alert feed showed 20 of 64
signature alerts, plant-connections' gateway audit 50 of 164, hive's logbook analytics read 2,000 of 7,700 entries under a
note that said "never truncates". A capped list that says nothing reads as everything.

Every capped read (a .from(...)/.rpc(...) statement with .limit(N >= 2) or .range(...), not .single()/.maybeSingle()/
head:true) carries ONE disposition in a comment on the statement's own lines (or a comment-only line beside them):

  more-said    the list says when more exists: the read is an overflow probe (`.limit(N + 1)`), asks for a count, or sits
               beside a count-only read of the same source; and its function calls whMoreNote(...) - the shared sentence
               "Showing the 20 newest of 64 alerts." / "... There are more." with the way to the rest when there is one.
  more-said: by <fn>   the same, where the page's OWN sentence says it in <fn> ("the 5 most recent of 64", "50+", an
               AI prompt that states its slice) - <fn> must exist on the page.
  paged:<fn>   the list pages: a control calls <fn> (Load more), or the read sits in a loop that reads to the last page
               (for (let from = 0; ; from += PAGE) ... .length < PAGE) break/return) - an export, a vocabulary pass.
  cap-ok[cols] the cap never bites: sized LIVE - the largest group the read can return today (its literal filters as
               WHERE, its variable filters - or the named cols - as the group) must be at most HALF the cap. A STREAM
               (a trail, a log, a feed, a history, a queue) may not be cap-ok: the local data cannot see production's
               volume, so a stream says more by construction.
  window-ok[Nd] a stream read bounded by a time window in the query (.gte('<time column>', ...)), sized live over it.
  in-list[cols] bounded by construction: a chunk of known keys (.in(col, keys.slice(j, j + N)) / .slice(0, N)) under
               .limit(N), and a UNIQUE index over exactly the named cols, so each key returns at most one row.
  exact-count:<var> the cap IS the size of the set: <var> holds a count read from the database in the same function
               (integrations' rollback reads exactly the batch's recorded rows_written sync rows - nothing is shown, and
               the cap is what stops it reaching into an earlier batch). The limit must be <var> itself.
A RETIRED page whose overlay branch ends in a return before its work (founder-console) runs none of its reads; held
structurally, so bringing the page back makes every read come due.

A read built in steps (`let q = db.from(...)`; `q = q.eq(...)`; `await q.limit(N)`) is traced through the variable it was
assigned to, and held like any other.

STATIC  S0 every cap traces to a read; S9 a read chains one cap (the earlier of two is never sent);
        S1 every capped read has a disposition; S2 more-said reads probe or count and say it (whMoreNote or by <fn>);
        S3 paged:<fn> is called by a control or loops to the last page; S4 utils.js whMoreNote renders one note after
        the list, says the count it was given, offers a 44px way to the rest, removes itself when nothing more exists;
        S5 no stream is cap-ok; S6 window-ok has a time window; S7 in-list reads a sliced key chunk under a matching limit;
        S8 exact-count:<var> caps at <var> itself, and <var> is a count the same function read from the database;
        S10 every cap declared inside a function (RPC_CAPS) names a page that calls it, reads the key, and says it.
LIVE    V1 every cap-ok / window-ok read's largest group today is at most half its cap; V2 every in-list names columns a
        unique index covers exactly; V3 every literal LIMIT N >= 2 inside a function an LB1 page calls is declared in
        RPC_CAPS, and every declaration still caps (the local database's definitions, read-only).
SELF-TEST (--self-test): static mutants on synthetic sources, and live mutants (a cap-ok on a read whose largest group
        is larger than its cap; an undeclared inner cap; a declaration no function backs).

    python tools/validate_list_caps_say_more.py [--self-test] [--json] [--list]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    # reconfigure in place: a NEW wrapper here closes the one a gate importing this module made (its old wrapper is
    # dropped and collected, closing the shared buffer - "I/O operation on closed file")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
PAGES = ["achievements.html", "alert-hub.html", "analytics.html", "asset-hub.html", "assistant.html", "community.html",
         "dayplanner.html", "hive.html", "index.html", "integrations.html", "inventory.html", "logbook.html",
         "marketplace-seller-profile.html", "marketplace-seller.html", "marketplace.html", "ph-intelligence.html",
         "plant-connections.html", "pm-scheduler.html", "project-manager.html", "project-report.html", "public-feed.html",
         "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html", "agentic-rag-observability.html",
         "ai-quality.html", "audit-log.html", "founder-console.html", "llm-observability.html", "marketplace-admin.html",
         "platform-actions.html", "feedback/index.html"]
START = re.compile(r"\.from\(\s*['\"]([a-z_0-9]+)['\"]\s*\)|\.rpc\(\s*['\"]([a-z_0-9]+)['\"]")
LIMIT = re.compile(r"\.limit\(\s*([^()]*?(?:\([^()]*\)[^()]*?)*)\s*\)")
PLIMIT = re.compile(r"p_(?:limit|max|n|top|rows|page_size)\s*:\s*([A-Za-z_0-9.+ ]+)")
RANGE = re.compile(r"\.range\(")
COUNT = re.compile(r"count:\s*['\"](exact|planned|estimated)['\"]")
SINGLE = re.compile(r"\.(single|maybeSingle)\(\)|head:\s*true")
DISP = re.compile(r"\b(more-said(?::\s*by\s+([A-Za-z_$][\w$]*))?|paged:\s*([A-Za-z_$][\w$]*)|cap-ok(?:\[([a-z_, ]+)\])?"
                  r"|limit-as-count-allow|window-ok\[(\d+)\s*([hd])\]|in-list\[([a-z_, ]+)\]|exact-count:\s*([A-Za-z_$][\w$]*))", re.I)
# a read bounded BY CONSTRUCTION: it asks for a chunk of known keys (.in('col', keys.slice(j, j + N))) under .limit(N), and
# a UNIQUE index over the named columns means each key returns at most one row - alert-hub's dismissals for the feed's keys
# keys.slice(j, j + N) for a chunk loop, or list.slice(0, N) (optionally .map(...) after it) for a fixed head
INLIST = re.compile(r"\.in\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*[\w$.]+\.slice\(\s*(?:0|[\w$]+)\s*,\s*(?:[\w$]+\s*\+\s*)?(\d+)\s*\)")
# a stream read that is bounded by a TIME WINDOW in the query (.gte('<time column>', ...)): window-ok[1d] is sized live
# over that window - analytics' snapshot lookup reads today's rows, not the hive's whole history
WINDOW_COL = re.compile(r"\.gte\(\s*['\"]([a-z_0-9]*(?:_at|date))['\"]")
# A STREAM grows with time - a trail, a log, a feed, a history, a queue of requests. The live check sizes the LOCAL data,
# which cannot see production's volume, so "far from its cap today" proves nothing about a stream: a busy hive's audit
# trail outruns any cap a page picks. A stream says more by construction (it probes or counts); cap-ok is for a set the
# physical world bounds - a hive's people, assets, parts, templates, one project's items.
STREAM = re.compile(r"(_log$|_logs$|_events$|history|_transactions|completions$|logbook|posts|replies|inquiries|reviews"
                    r"|feedback$|request_truth|requests$|payments$|redemptions$|receipts|topups|briefings|_runs$"
                    r"|external_sync|ai_reports|journal|calcs$|broadcasts|notifications$|alert_truth|snapshots"
                    r"|listings|dismissals)")
SCOPE = {"hive_id", "asset_id", "asset_node_id", "node_id", "worker_name", "auth_uid", "project_id", "listing_id",
         "seller_id", "seller_auth_uid", "buyer_auth_uid", "post_id", "thread_id", "alert_kind", "user_id", "machine",
         "provider_auth_uid", "account_id", "inquiry_id", "contact_id", "item_id", "resume_id", "author_auth_uid",
         "status", "category", "discipline", "section", "consumer", "route", "actor"}


def blank_comments(src: str) -> str:
    """Keep line structure and offsets; blank comments so a mention is never a site (a disposition is read from RAW)."""
    out = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), out, flags=re.S)
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)


def enclosing_body(src: str, pos: int) -> str:
    """The text of the innermost { ... } block that holds pos and is a function body (or the whole script if none)."""
    depth, i = 0, pos
    while i > 0:
        i -= 1
        c = src[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                head = src[max(0, i - 160):i]
                if re.search(r"(function\b[^{;]*|=>\s*|\)\s*)$", head):
                    j, d = i, 0
                    while j < len(src):
                        if src[j] == "{":
                            d += 1
                        elif src[j] == "}":
                            d -= 1
                            if d == 0:
                                return src[i:j + 1]
                        j += 1
                    return src[i:]
            else:
                depth -= 1
    return src


LIT = r"(?:'[^']*'|\"[^\"]*\"|true|false|null|-?\d+(?:\.\d+)?)"


def parse_filters(stmt: str) -> dict:
    """What the read asks the database for, as far as the source says it.
    A filter on a LITERAL becomes a WHERE condition the live check applies (.eq('status', 'Open') reads only open rows);
    a filter on a VARIABLE (.eq('hive_id', HIVE_ID)) is one group of many, so the live check groups by it and takes the
    largest. Anything it cannot read (a date window, an .or()) is left out, which can only make the group LARGER."""
    where, group = [], []

    def lit_sql(v: str) -> str:
        v = v.strip()
        if v[0] in "'\"":
            return "'" + v[1:-1].replace("'", "''") + "'"
        return v

    for m in re.finditer(r"\.(eq|neq)\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*(" + LIT + r"|[^)]+)\)", stmt):
        op, col, val = m.group(1), m.group(2), m.group(3).strip()
        if re.fullmatch(LIT, val):
            if val == "null":
                where.append(f"{col} is {'not ' if op == 'neq' else ''}null")
            else:
                where.append(f"{col} {'=' if op == 'eq' else 'is distinct from'} {lit_sql(val)}")
        elif op == "eq":
            group.append(col)
    for m in re.finditer(r"\.is\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*(null|true|false)\s*\)", stmt):
        where.append(f"{m.group(1)} is {m.group(2)}")
    for m in re.finditer(r"\.not\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*['\"]is['\"]\s*,\s*null\s*\)", stmt):
        where.append(f"{m.group(1)} is not null")
    # .not('status', 'in', '(Closed,Resolved)') - PostgREST's list form, values unquoted
    for m in re.finditer(r"\.not\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*['\"]in['\"]\s*,\s*['\"]\(([^)'\"]*)\)['\"]\s*\)", stmt):
        vals = [v.strip().strip('"') for v in m.group(2).split(",") if v.strip()]
        if vals:
            where.append(f"{m.group(1)} is not null and {m.group(1)} not in ({', '.join(lit_sql(repr(v)) for v in vals)})")
    for m in re.finditer(r"\.in\(\s*['\"]([a-z_0-9]+)['\"]\s*,\s*\[([^\]]*)\]\s*\)", stmt):
        vals = [v.strip() for v in m.group(2).split(",") if v.strip()]
        if vals and all(re.fullmatch(LIT, v) for v in vals):
            where.append(f"{m.group(1)} in ({', '.join(lit_sql(v) for v in vals)})")
    return {"where": where, "group": sorted(set(group))}


def _close_paren(src: str, i: int) -> int:
    """src[i] opens a bracket; the index just past the bracket that closes it (strings and template literals skipped)."""
    depth, j, n = 0, i, len(src)
    while j < n:
        c = src[j]
        if c in "'\"":
            j += 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
        elif c == "`":
            j += 1
            while j < n and src[j] != "`":
                j += 2 if src[j] == "\\" else 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


CHAIN_LINK = re.compile(r"\s*\.\s*[A-Za-z_$][\w$]*\s*\(")


def chain_end(src: str, m: re.Match) -> int:
    """★THE STATEMENT IS ITS CHAIN, NOT A WINDOW (2026-10-21). The read used to end at the first ';' or blank line within
    900 characters - and marketplace's grid read (a long select list, then a six-line comment on its tiebreaker) put its
    .limit(PAGE_SIZE) past the window, so the gate never saw the cap: 8 reads on 7 pages were invisible, 5 with no
    disposition. Widening the window swallowed the NEXT statement's .limit instead. The read is now followed link by link -
    .from(...) / .rpc(...) and every .method(...) chained after it, brackets balanced - and ends where the chain ends."""
    j = _close_paren(src, src.index("(", m.start() + 1)) if m.group(2) else m.end()
    # the read handed to a wrapper (`scopeNodes(db.from(...))`, `_ownScope(db.from(...))`) or written as one branch of a
    # parenthesised ternary (`(them ? db.from(A)... : db.from(B)...)`) is capped by the chain AFTER the closing paren
    return _follow(src, j, _ternary_open(src, m.start()))


def _follow(src: str, j: int, tern: int | None) -> int:
    """From j: every .method(...) chained on, out through a wrapper's or a ternary group's paren; where the chain ends."""
    while True:
        lk = CHAIN_LINK.match(src, j)
        if lk:
            j = _close_paren(src, lk.end() - 1)
            continue
        k = j
        while k < len(src) and src[k] in " \t\r\n":
            k += 1
        if k < len(src) and src[k] == ")":
            j = k + 1   # out of the wrapper's (or the ternary group's) paren; the chain continues on what it returns
            continue
        if k < len(src) and src[k] == ":" and tern is not None:
            j, tern = _close_paren(src, tern), None   # the first branch: its cap is the group's
            continue
        return j


def _ternary_open(src: str, pos: int) -> int | None:
    """The '(' that opens `(cond ? ` right before a read, when the read is the first branch of a parenthesised ternary."""
    k = src.rfind("(", max(0, pos - 160), pos)
    if k >= 0 and re.fullmatch(r"\(\s*[\w$.!]+\s*\?\s*(?:await\s+)?", src[k:pos]):
        return k
    return None


# ★A READ BUILT IN STEPS (2026-10-21). `let q = db.from('x')...;  if (uid) q = q.eq(...);  await q.order(...).limit(N)` -
# the cap sits on the VARIABLE, so no .from(...) chain reaches it: achievements re-read a worker's achievements this way and
# dayplanner its plant-PM rail, and the gate held neither to a disposition. A variable is BOUND where a read is assigned to it
# (`q = db.from(...)`, `q = scopeNodes(db.from(...))` - never an awaited result), and a cap on a chain that starts at the
# variable belongs to the LAST binding of that name before it. A cap no chain and no binding reaches fails S0.
BIND = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*(?:[A-Za-z_$][\w$]*\(\s*)?[A-Za-z_$][\w$.]*$")
CAP = re.compile(r"\.(?:limit|range)\(")


def step_built(src: str) -> tuple[list[dict], list[int]]:
    """Caps that no read's own chain reaches: ([{"m": the bound read's START match, "parts": [(start, end) of the binding
    read and of every chain on the variable up to the capped one], "use": (start, end)}], [positions left unattributed])."""
    spans = [(m.start(), chain_end(src, m)) for m in START.finditer(src)]
    caps = [c.start() for c in CAP.finditer(src) if not any(a <= c.start() < b for a, b in spans)]
    if not caps:
        return [], []
    binds = []
    for m in START.finditer(src):
        b = BIND.search(src, max(0, m.start() - 200), m.start())
        if b and b.end() == m.start():
            binds.append((b.group(1), m, chain_end(src, m)))
    names = {var for var, _, _ in binds}
    found, left = [], []
    for c in caps:
        # the chain the cap sits on starts at a bound name: the latest such start whose chain reaches the cap
        use = None
        for var in names:
            for u in re.compile(r"(?<![\w$.])" + re.escape(var) + r"(?=\s*\.\s*[A-Za-z_$][\w$]*\s*\()").finditer(src, max(0, c - 4000)):
                if u.start() > c:
                    break
                e = _follow(src, u.end(), _ternary_open(src, u.start()))
                if c < e and (use is None or u.start() > use[1]):
                    use = (var, u.start(), e)
        # ...and the read it was assigned is the LAST binding of that name whose block holds the use: a `q` bound in
        # another function is a different variable (a let/const is visible only inside its own { ... })
        bound = None
        if use:
            for var, m, bend in reversed(binds):
                if var == use[0] and bend <= use[1]:
                    bs, be = _block(src, m.start())
                    if bs <= use[1] < be:
                        bound = (m, bend)
                        break
        if not bound:
            left.append(c)
            continue
        m, bend = bound
        parts = [(m.start(), bend)]
        for u in re.compile(r"(?<![\w$.])" + re.escape(use[0]) + r"(?=\s*\.\s*[A-Za-z_$][\w$]*\s*\()").finditer(src, bend):
            if u.start() >= use[1]:
                break
            parts.append((u.start(), _follow(src, u.end(), _ternary_open(src, u.start()))))   # refinements: q = q.eq(...)
        parts.append((use[1], use[2]))
        found.append({"m": m, "parts": parts, "use": (use[1], use[2])})
    return found, left


def _block(src: str, pos: int) -> tuple[int, int]:
    """The innermost { ... } holding pos (where a let / const bound at pos is visible); the whole source at top level."""
    depth, i = 0, pos
    while i > 0:
        i -= 1
        ch = src[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                return i, _close_paren(src, i)
            depth -= 1
    return 0, len(src)


def _site(page: str, src: str, lines: list[str], name: str, is_rpc: bool, stmt: str, pos: int, end: int) -> dict | None:
    """One capped read: `stmt` is what it asks the database for, src[pos:end] the lines its disposition is read beside."""
    if SINGLE.search(stmt):
        return None
    # the LAST .limit() is the one PostgREST sends - alert-hub chained .limit(200) ... .limit(10) and asked for 10
    lims = list(LIMIT.finditer(stmt))
    lim = lims[-1] if lims else None
    pl = PLIMIT.search(stmt) if is_rpc else None
    rng = RANGE.search(stmt)
    if not (lim or pl or rng):
        return None
    expr = (lim or pl).group(1).strip() if (lim or pl) else ""
    num = re.match(r"^(\d+)", expr)
    n = int(num.group(1)) if num else None
    # a .range(a, b) with literal bounds is a window of b - a + 1 rows (resume prunes versions with .range(10, 49))
    rlit = re.search(r"\.range\(\s*(\d+)\s*,\s*(\d+)\s*\)", stmt)
    if not expr and rlit:
        expr, n = f"range({rlit.group(1)}, {rlit.group(2)})", int(rlit.group(2)) - int(rlit.group(1)) + 1
    if n is not None and n < 2 and "+" not in expr:
        return None
    line = src.count("\n", 0, pos) + 1
    end_line = src.count("\n", 0, end) + 1
    # the statement's own lines, plus the line before / after it ONLY when that line is a comment and nothing else -
    # a wider window read the NEXT statement's note as this one's (inventory: a solo asset read two lines below)
    span = lines[line - 1:end_line]
    if line >= 2 and lines[line - 2].strip().startswith("//"):
        span = [lines[line - 2]] + span
    if end_line < len(lines) and lines[end_line].strip().startswith("//"):
        span = span + [lines[end_line]]
    note = "\n".join(span)
    d = DISP.search(note)
    return {"page": page, "line": line, "pos": pos, "src": name if not is_rpc else "rpc:" + name,
            "expr": expr, "n": n, "probe": bool(re.search(r"\+\s*1\b", expr)), "count": bool(COUNT.search(stmt)),
            "paged": bool(rng), "filters": parse_filters(stmt),
            # every cap but the last is never sent: a reader trusts the first one they see (S9)
            "caps": len(lims) + len(RANGE.findall(stmt)),
            "disp": (d.group(1).split(":")[0].split("[")[0].lower() if d else ""),
            "by_fn": (d.group(2) if d and d.group(2) else ""),
            "paged_fn": (d.group(3) if d and d.group(3) else ""),
            "scope": ([c.strip() for c in d.group(4).split(",")] if d and d.group(4) else None),
            "window": ((int(d.group(5)), d.group(6).lower()) if d and d.group(5) else None),
            "unique": ([c.strip() for c in d.group(7).split(",")] if d and d.group(7) else None),
            "count_var": (d.group(8) if d and d.group(8) else ""),
            "inlist": ((INLIST.search(stmt).group(1), int(INLIST.search(stmt).group(2))) if INLIST.search(stmt) else None),
            "window_col": (WINDOW_COL.search(stmt).group(1) if WINDOW_COL.search(stmt) else ""),
            "body": enclosing_body(src, pos),
            # what ran BEFORE the read: its innermost block can be an if (integrations' rollback reads inside
            # `if (_batchSize > 0) {`, and the count it caps at is assigned just above that block)
            "pre": src[max(0, pos - 6000):pos]}


def sites_of(page: str, raw: str, unattributed: list[int] | None = None) -> list[dict]:
    src = blank_comments(raw)
    lines = raw.split("\n")
    out = []
    for m in START.finditer(src):
        end = chain_end(src, m)
        s = _site(page, src, lines, m.group(1) or m.group(2), bool(m.group(2)), src[m.start():end], m.start(), end)
        if s:
            out.append(s)
    found, left = step_built(src)
    for f in found:
        m = f["m"]
        s = _site(page, src, lines, m.group(1) or m.group(2), bool(m.group(2)),
                  "\n".join(src[a:b] for a, b in f["parts"]), f["use"][0], f["use"][1])
        if s:
            s["step_built"] = True
            out.append(s)
    if unattributed is not None:
        unattributed.extend(src.count("\n", 0, c) + 1 for c in left)
    return out


# A RETIRED page whose boot returns before its work runs shows no lists at all: founder-console keeps its view (and logs
# it) behind #wh-retired-overlay and returns before refreshAll(), so none of its reads ever executes. Held structurally -
# the overlay must be in the markup and a return must stand between the overlay branch and the work - so the day the
# console is brought back, the exemption stops holding and every read comes due.
RETIRED_INERT = {"founder-console.html": "refreshAll"}


def retired_inert(page: str, raw: str) -> bool:
    fn = RETIRED_INERT.get(page)
    if not fn or 'id="wh-retired-overlay"' not in raw:
        return False
    i = raw.find("if (_retiredOv) {")
    j = raw.find("await " + fn + "()", i)
    if i < 0 or j < i:
        return False
    # the overlay BRANCH (brace-matched) must end in its own return - containing one is not enough: its cannot-ask
    # path returns too, and the live branch below it returns before the work as well
    k, depth = i + len("if (_retiredOv) "), 0
    while k < j:
        if raw[k] == "{":
            depth += 1
        elif raw[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    block = blank_comments(raw[i:k + 1])
    return "whApplyRetiredInert" in block and bool(re.search(r"return;\s*\}\s*$", block))


def _loops_to_last_page(raw: str, fn: str, pos: int) -> bool:
    """The read sits in `fn` inside a loop that pages to the end: for (let from = 0; ; from += PAGE) ... and a break on a
    short page (data.length < PAGE). Read from fn's definition to just past the read - a loop's own braces hide its header
    from the statement's nearest block."""
    m = re.search(r"(?:function\s+" + re.escape(fn) + r"\s*\(|\b" + re.escape(fn) + r"\s*=\s*(?:async\s*)?(?:function|\())", raw)
    if not m or m.start() > pos:
        return False
    span = raw[m.start():pos + 3000]
    return bool(re.search(r"for\s*\(\s*let\s+(\w+)\s*=\s*0\s*;\s*;\s*\1\s*\+=", span)
                and re.search(r"\.length\s*<\s*[A-Z_]+\s*\)\s*(?:break|return)\b", span))   # a short page ends the loop


def _exact_count_unproven(s: dict) -> str:
    """'' when the read caps at a count the same function read from the database; else why not. The count must come from a
    row (`const { data: row } = await db.from(...)...` then `const n = (row && row.rows_written) || 0`) - a literal or a
    page constant is a cap, not a count, and says nothing about how many rows exist."""
    var, pre = s["count_var"], s.get("pre", "")
    if s["expr"] != var:
        return f"the read caps at {s['expr'] or 'a range'}, not at {var}"
    found = list(re.finditer(r"\b(?:const|let|var)\s+" + re.escape(var) + r"\s*=\s*([^;\n]+)", pre))
    a = found[-1] if found else None   # the assignment the read sees is the last one before it
    if not a:
        return f"{var} is not assigned before the read"
    rows = set(re.findall(r"\{\s*data\s*:\s*([A-Za-z_$][\w$]*)\s*\}\s*=\s*await\s+[\w$.]+\.(?:from|rpc)\(", pre[:a.start()]))
    rhs_ids = set(re.findall(r"[A-Za-z_$][\w$]*", a.group(1)))
    if not (rows & rhs_ids) and not re.search(r"await\s+[\w$.]+\.(?:from|rpc)\(", a.group(1)):
        return f"{var} is not read from the database in that function (a literal cap says nothing about how many rows exist)"
    return ""


def check_helper(utils: str) -> list[str]:
    m = re.search(r"function whMoreNote\(listEl, state\) \{(.*?)\n\}", utils, re.S)
    if not m:
        return ["S4 utils.js has no whMoreNote(listEl, state)"]
    body, issues = m.group(1), []
    for need, why in (("data-wh-more-note", "marks its one note so a re-render replaces it"),
                      ("if (!state || !state.more)", "removes the note when nothing more exists"),
                      ("' of ' + ", "says the total when it was given one"),
                      ("There are more.", "says more exists when no total was given"),
                      ("var e = escHtml;", "escapes what it is given"),
                      ("role', 'note'", "is a note a screen reader can find"),
                      ("insertAdjacentElement('afterend', note)", "puts its note directly after the list")):
        if need not in body:
            issues.append(f"S4 whMoreNote no longer {why}")
    # the way to the rest is a 44px target - the button and the link, in the shared style block every page loads
    for sel in (".wh-more-note .wh-more-btn{", ".wh-more-note .wh-more-link{"):
        k = utils.find(sel)
        if k < 0 or "min-height:44px" not in utils[k:k + 300]:
            issues.append(f"S4 {sel.rstrip('{')} is no longer a 44px target")
    return issues


def check_static(files: dict[str, str] | None = None) -> tuple[list[str], list[dict]]:
    def text(rel: str) -> str:
        if files and rel in files:
            return files[rel]
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    issues, live, unique_checks = [], [], []
    issues += check_helper(text("utils.js"))
    for page in PAGES:
        raw = text(page)
        if retired_inert(page, raw):
            continue   # its boot returns before any of its reads runs - see RETIRED_INERT
        left: list[int] = []
        sites = sites_of(page, raw, left)
        for ln in left:
            issues.append(f"S0 {page}:{ln} caps a read the gate cannot trace to its source (no .from(...)/.rpc(...) chain "
                          "and no variable a read was assigned to reaches it) - chain the cap onto the read")
        for s in sites:
            where = f"{page}:{s['line']} {s['src']} limit {s['expr'] or 'range'}"
            if s["caps"] >= 2:
                issues.append(f"S9 {where} chains {s['caps']} caps - only the last is sent, so the earlier one is a number "
                              "nobody asked for; keep the one the read means")
            if not s["disp"]:
                issues.append(f"S1 {where} has no disposition (more-said / paged:<fn> / cap-ok)")
            elif s["disp"] == "more-said":
                # the total may come from a SIBLING count-only read of the same source in the same function (index's
                # priority list shows 5 open jobs; the tile beside it already counts them with head:true)
                sib = (not s["src"].startswith("rpc:")) and re.search(
                    r"\.from\(\s*['\"]" + re.escape(s["src"]) + r"['\"]\s*\)\s*\.select\([^)]*count:\s*['\"](?:exact|planned)['\"]", s["body"])
                if not (s["probe"] or s["count"] or s["paged"] or sib):
                    issues.append(f"S2 {where} is more-said but neither probes one row past its cap (N + 1) nor counts")
                if s["by_fn"]:
                    # the page's OWN sentence says it (report-sender: "the 5 most recent of 64"), in the function named
                    if not re.search(r"(?:function\s+" + re.escape(s["by_fn"]) + r"\s*\(|\b" + re.escape(s["by_fn"]) + r"\s*=\s*(?:async\s*)?(?:function|\())", raw):
                        issues.append(f"S2 {where} is more-said by {s['by_fn']}, which is not defined on the page")
                elif "whMoreNote(" not in s["body"]:
                    issues.append(f"S2 {where} is more-said but its function never calls whMoreNote "
                                  "(or names the one that says it: more-said: by <fn>)")
            elif s["disp"] == "paged":
                fn = s["paged_fn"]
                if not re.search(r"(?:function\s+" + re.escape(fn) + r"\s*\(|\b" + re.escape(fn) + r"\s*=\s*(?:async\s*)?(?:function|\())", raw):
                    issues.append(f"S3 {where} is paged:{fn}, and {fn} is not defined on the page")
                elif not re.search(r"(onclick=\"[^\"]*\b" + re.escape(fn) + r"\(|addEventListener\(\s*'click'[^;]{0,200}\b" + re.escape(fn) + r"\b|\.onclick\s*=\s*" + re.escape(fn) + r"\b)", raw) \
                        and not _loops_to_last_page(raw, fn, s["pos"]):
                    # no control pages it - unless the read sits in a loop that reads EVERY page (for (let from = 0; ;
                    # from += PAGE) ... if (data.length < PAGE) break) - an export, a vocabulary pass
                    issues.append(f"S3 {where} is paged:{fn}, and no control calls {fn} (nor does it loop to the last page)")
            elif s["disp"] == "in-list":
                il = s["inlist"]
                if not il or il[1] != s["n"]:
                    issues.append(f"S7 {where} is in-list, and the read is not .in('<col>', keys.slice(j, j + N)) under .limit(N)")
                elif il[0] not in (s["unique"] or []):
                    issues.append(f"S7 {where} is in-list[{', '.join(s['unique'] or [])}], which does not name the listed column {il[0]}")
                else:
                    unique_checks.append(s)
            elif s["disp"] == "exact-count":
                why = _exact_count_unproven(s)
                if why:
                    issues.append(f"S8 {where} is exact-count:{s['count_var']}, and {why}")
            elif s["disp"] == "window-ok":
                if not s["window_col"]:
                    issues.append(f"S6 {where} is window-ok, and the read has no .gte('<time column>', ...) window")
                elif s["src"].startswith("rpc:") or s["n"] is None:
                    issues.append(f"S6 {where} is window-ok on a read the database cannot be asked to size")
                else:
                    live.append(s)
            else:   # cap-ok / limit-as-count-allow: proven live
                if STREAM.search(s["src"]):
                    issues.append(f"S5 {where} is cap-ok on a stream ({s['src']} grows with time; the local data cannot "
                                  "see production's volume) - probe or count, and say more")
                elif s["src"].startswith("rpc:") or s["n"] is None:
                    issues.append(f"S1 {where} is cap-ok on a read the database cannot be asked to size (an RPC or a "
                                  "computed limit) - say more instead")
                else:
                    live.append(s)
    issues += check_rpc_decl(text)
    for s in unique_checks:
        s["check"] = "unique"
    return issues, live + unique_checks


def psql(sql: str, timeout: int = 180) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At",
                            "-v", "ON_ERROR_STOP=1", "-f", "-"], input="set statement_timeout = '30s';\n" + sql,
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", str(e)


def size_sites(sites: list[dict]) -> str:
    """Set s['max'] / s['group'] / s['sized']: the largest set of rows the read can return today. Returns an error or ''."""
    sized = [s for s in sites if not s["src"].startswith("rpc:")]
    if not sized:
        return ""
    tables = sorted({s["src"] for s in sized})
    code, out, err = psql("select table_name || '|' || string_agg(column_name, ',') from information_schema.columns "
                          "where table_schema = 'public' and table_name in (" + ", ".join("'" + t + "'" for t in tables)
                          + ") group by table_name;")
    if code != 0:
        return f"could not read the catalog: {(err or out).strip()[-200:]}"
    cols = {ln.split("|")[0]: set(ln.split("|")[1].split(",")) for ln in out.splitlines() if "|" in ln}
    queries, keys = [], []
    for i, s in enumerate(sized):
        tc = cols.get(s["src"])
        if not tc:
            continue
        f = s.get("filters") or {"where": [], "group": []}
        grp = [c for c in (s["scope"] if s["scope"] is not None else f["group"]) if c in tc]
        # a literal filter on a column the table lacks would fail the query - such a read is sized without it (larger)
        where = [w for w in f["where"] if w.split(" ")[0] in tc]
        if s.get("window") and s.get("window_col") in tc:
            k, unit = s["window"]
            where.append(f"{s['window_col']} >= now() - interval '{k} {'hours' if unit == 'h' else 'days'}'")
        # a NULL group key is a group no read can ask for (eq(col, x) never matches NULL), so it is not counted
        where += [f"{c} is not null" for c in grp]
        wsql = (" where " + " and ".join(where)) if where else ""
        q = (f"select coalesce(max(c), 0) from (select count(*) c from public.{s['src']}{wsql} group by {', '.join(grp)}) x"
             if grp else f"select count(*) from public.{s['src']}{wsql}")
        queries.append(f"select '{i}|' || ({q});")
        keys.append((i, grp, where))
    code, out, err = psql("\n".join(queries), timeout=900)
    if code != 0:
        return f"sizing failed: {(err or out).strip()[-300:]}"
    got = {int(ln.split("|")[0]): int(ln.split("|")[1]) for ln in out.splitlines() if "|" in ln}
    for i, grp, where in keys:
        s = sized[i]
        if i in got:
            s["max"], s["group"], s["where"], s["sized"] = got[i], grp, where, True
    return ""


def check_unique(sites: list[dict]) -> list[str]:
    """in-list reads: a UNIQUE index must cover exactly the named columns, or one key can return many rows."""
    if not sites:
        return []
    code, out, err = psql("select tablename || '|' || indexdef from pg_indexes where schemaname = 'public' and indexdef ilike 'create unique index%' "
                          "and tablename in (" + ", ".join("'" + s['src'] + "'" for s in sites) + ");")
    if code != 0:
        return [f"V2 LIVE could not read the indexes: {(err or out).strip()[-200:]}"]
    idx = {}
    for ln in out.splitlines():
        tbl, _, d = ln.partition('|')
        m = re.search(r"\(([^)]*)\)", d)
        if m:
            idx.setdefault(tbl, []).append({c.strip() for c in m.group(1).split(',')})
    issues = []
    for s in sites:
        if set(s['unique']) not in idx.get(s['src'], []):
            issues.append(f"V2 {s['page']}:{s['line']} {s['src']} is in-list[{', '.join(s['unique'])}], and no unique index covers "
                          "exactly those columns - one key could return many rows past the cap")
    return issues


# ★THE CAP INSIDE THE FUNCTION (2026-10-21). An RPC can cap its own arrays (`... ORDER BY created_at DESC LIMIT 40`), and
# the page that renders them sees no .limit() at all: hive's board feed, audit trail, alerts and benchmarks and index's
# open jobs, risks and low stock all arrive capped by get_hive_board_dashboard / get_hive_dashboard - and the marketplace's
# "parts for your assets" rail arrived capped at 24 by its own function, the 24 smallest UUIDs, with no word that more
# matched. Every literal LIMIT N (N >= 2) inside a function an LB1 page calls is declared here, read LIVE from the local
# database's definitions, so a cap added inside a function fails until someone decides how its page says more:
#   the page function that says when the array came back full (it must exist on the page, and the page must read the key)
#   "lookup"            an array the page searches by key and never lists
#   "sample: <words>"   an aggregate over a bounded window, which the page names in those words
RPC_CAPS = {
    # (function, the table it caps, N): (page, the key the page reads the array from, how the page says it)
    ("get_hive_board_dashboard", "v_logbook_truth", 40): ("hive.html", "feed_logbook", "renderFeed"),
    ("get_hive_board_dashboard", "pm_completions", 20): ("hive.html", "feed_pm", "renderFeed"),
    ("get_hive_board_dashboard", "v_logbook_truth", 5): ("hive.html", "own_old_wos", "buildNotifications"),
    ("get_hive_board_dashboard", "v_alert_truth", 5): ("hive.html", "pattern_alerts", "loadPatternAlerts"),
    ("get_hive_board_dashboard", "hive_benchmarks", 5): ("hive.html", "benchmarks", "loadBenchmarks"),
    ("get_hive_board_dashboard", "network_benchmarks", 10): ("hive.html", "benchmarks", "lookup"),   # the PH figure beside each of the hive's categories
    ("get_hive_board_dashboard", "hive_audit_log", 50): ("hive.html", "audit_log", "loadAuditLog"),
    ("get_hive_dashboard", "v_logbook_truth", 5): ("index.html", "open_jobs", "renderOnboardingLadder"),
    ("get_hive_dashboard", "v_risk_truth", 5): ("index.html", "risks", "renderOnboardingLadder"),
    ("get_hive_dashboard", "v_inventory_items_truth", 100): ("index.html", "low_stock_items", "renderOnboardingLadder"),
    ("marketplace_platform_response_hours", "marketplace_inquiries", 500): ("marketplace-seller.html", "", "sample: up to the latest 500 replies"),
}


def rpc_called(files: dict[str, str] | None = None) -> list[str]:
    """Every function an LB1 page calls with .rpc(...) (a retired page's reads never run, so its calls are not counted)."""
    names = set()
    for page in PAGES:
        raw = files[page] if files and page in files else (ROOT / page).read_text(encoding="utf-8", errors="replace")
        if retired_inert(page, raw):
            continue
        names |= {m.group(1) for m in re.finditer(r"\.rpc\(\s*['\"]([a-z_0-9]+)['\"]", blank_comments(raw))}
    return sorted(names)


def check_rpc_decl(text, decl: dict | None = None) -> list[str]:
    """S10 (static): each declared inner cap names a page that still calls the function, reads the key, and says it."""
    issues = []
    for (fn, table, n), (page, key, how) in (RPC_CAPS if decl is None else decl).items():
        raw = text(page)
        where = f"{fn} caps {table} at {n}"
        if not re.search(r"\.rpc\(\s*['\"]" + re.escape(fn) + r"['\"]", blank_comments(raw)):
            issues.append(f"S10 {where} is declared for {page}, which no longer calls {fn} - remove the entry")
            continue
        if key and not re.search(r"\b" + re.escape(key) + r"\b", raw):
            issues.append(f"S10 {where}: {page} never reads the array's key {key}")
        if how == "lookup":
            continue
        if how.startswith("sample:"):
            words = how.split(":", 1)[1].strip()
            if words not in raw:
                issues.append(f"S10 {where} is a sample, and {page} never names it (\"{words}\")")
        elif not re.search(r"(?:function\s+" + re.escape(how) + r"\s*\(|\b" + re.escape(how) + r"\s*=\s*(?:async\s*)?(?:function|\())", raw):
            issues.append(f"S10 {where} is said by {how}, which {page} does not define")
    return issues


def rpc_inner_caps(names: list[str]) -> tuple[dict, str]:
    """{(function, table, N): times} for every literal LIMIT N >= 2 in the named functions' live definitions."""
    if not names:
        return {}, ""
    code, out, err = psql("select p.proname || '|' || translate(pg_get_functiondef(p.oid), chr(10), chr(31)) from pg_proc p "
                          "join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.prokind = 'f' "
                          "and p.proname in (" + ", ".join("'" + x + "'" for x in names) + ");")
    if code != 0:
        return {}, f"could not read the function definitions: {(err or out).strip()[-200:]}"
    caps: dict = {}
    for ln in out.splitlines():
        fn, _, body = ln.partition("|")
        body = re.sub(r"--[^\n]*", "", body.replace(chr(31), "\n"))
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        for m in re.finditer(r"\blimit\s+(\d+)\b", body, re.I):
            if int(m.group(1)) < 2:
                continue
            frm = list(re.finditer(r"\bfrom\s+(?:public\.)?([a-z_0-9]+)", body[:m.start()], re.I))
            k = (fn, frm[-1].group(1) if frm else "?", int(m.group(1)))
            caps[k] = caps.get(k, 0) + 1
    return caps, ""


def check_rpc_live(names: list[str], decl: dict | None = None) -> list[str]:
    """V3 (live): every inner cap is declared, and every declaration still caps."""
    decl = RPC_CAPS if decl is None else decl
    caps, err = rpc_inner_caps(names)
    if err:
        return [f"V3 LIVE {err}"]
    issues = []
    for k, times in sorted(caps.items()):
        if k not in decl:
            issues.append(f"V3 {k[0]} caps {k[1]} at {k[2]} inside the function, and no page is declared to say when that "
                          "array comes back full - declare it in RPC_CAPS (page, key, how the page says it)")
        elif times > 1:
            issues.append(f"V3 {k[0]} caps {k[1]} at {k[2]} {times} times, and one declaration cannot tell them apart")
    for k in decl:
        if k[0] in names and k not in caps:
            issues.append(f"V3 RPC_CAPS declares {k[0]} capping {k[1]} at {k[2]}, and the function no longer does - remove the entry")
    return issues


def check_live(live: list[dict]) -> list[str]:
    if not live:
        return []
    uniq = [s for s in live if s.get('check') == 'unique']
    live = [s for s in live if s.get('check') != 'unique']
    pre = check_unique(uniq)
    if not live:
        return pre
    err = size_sites(live)
    if err:
        return pre + [f"V1 LIVE {err}"]
    issues = list(pre)
    for s in live:
        if not s.get("sized"):
            continue
        mx, grp = s["max"], s["group"]
        if mx > s["n"] / 2:
            issues.append(f"V1 {s['page']}:{s['line']} {s['src']} is cap-ok at {s['n']}, and its largest group today "
                          f"({', '.join(grp) or 'the whole table'}) holds {mx} - the cap {'BITES' if mx > s['n'] else 'is past half'}; "
                          "say more, or name the true scope as cap-ok[col]")
    return issues


SYNTH = """<script>
async function loadA() {
  const { data } = await db.from('logbook').select('id').eq('hive_id', H).order('created_at', { ascending: false }).limit(20 + 1);   // more-said
  whMoreNote(listA, { shown: Math.min(20, (data || []).length), more: (data || []).length > 20, noun: 'entries' });
}
async function loadB() {
  const { data } = await db.from('logbook').select('id').eq('hive_id', H).range(0, 19);   // paged:loadMoreB
}
function loadMoreB() { }
async function loadC() {
  const { data: row } = await db.from('cmms_audit_log').select('rows_written').eq('batch_id', B).maybeSingle();
  const n = (row && row.rows_written) || 0;
  const { data } = await db.from('v_external_sync_truth').select('id').eq('hive_id', H).limit(n);   // exact-count: n
}
async function loadE() {
  let q = db.from('logbook').select('id', { count: 'exact' }).eq('hive_id', H);
  if (U) q = q.eq('worker_name', U);
  const { data, count } = await q.order('created_at', { ascending: false }).order('id').limit(10);   // more-said: by loadE
}
</script><button onclick="loadMoreB()">Load more</button>"""


def self_test() -> list[str]:
    fails = []
    issues, live = check_static()
    if issues:
        fails.append(f"static is not clean on the real files: {issues[:3]}")
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    # a synthetic page stands in for the first LB1 page; utils.js stays the real one
    page0 = PAGES[0]
    real0 = (ROOT / page0).read_text(encoding="utf-8")
    base = {page0: real0 + SYNTH}
    got, _ = check_static(base)
    if got:
        fails.append(f"the clean synthetic page is not green: {got[:2]}")
    mutants = [
        ("a capped read with no disposition", {page0: real0 + SYNTH.replace("   // more-said", "", 1)}, "S1"),
        ("more-said without a probe or a count", {page0: real0 + SYNTH.replace(".limit(20 + 1)", ".limit(20)", 1)}, "S2"),
        ("more-said whose function never says", {page0: real0 + SYNTH.replace("whMoreNote(listA", "console.log(listA", 1)}, "S2"),
        ("paged: names a function nothing calls", {page0: real0 + SYNTH.replace('<button onclick="loadMoreB()">', "<button>", 1)}, "S3"),
        ("the helper stops removing its note", {"utils.js": utils.replace("if (!state || !state.more)", "if (false)", 1)}, "S4"),
        ("the helper stops saying the total", {"utils.js": utils.replace("head + ' of ' + total.toLocaleString('en-PH')", "head + ' ' + total.toLocaleString('en-PH')", 1)}, "S4"),
        ("a stream marked cap-ok", {page0: real0 + SYNTH.replace(".limit(20 + 1);   // more-said", ".limit(20);   // cap-ok", 1)}, "S5"),
        ("exact-count on a literal, not a count read", {page0: real0 + SYNTH.replace("const n = (row && row.rows_written) || 0;", "const n = 500;", 1)}, "S8"),
        ("exact-count whose read caps at something else", {page0: real0 + SYNTH.replace(".limit(n);   // exact-count: n", ".limit(n * 2);   // exact-count: n", 1)}, "S8"),
        # a read built in steps is traced through its variable: without its note it is a read with no disposition (S1),
        # which only the tracing can say - untraced it would be an unattributed cap (S0)
        ("a read built in steps loses its note", {page0: real0 + SYNTH.replace(".limit(10);   // more-said: by loadE", ".limit(10);", 1)}, "S1"),
        ("a cap on something no read reaches", {page0: real0 + SYNTH.replace("let q = db.from('logbook')", "let q = makeQuery('logbook')", 1)}, "S0"),
        ("a read that chains two caps", {page0: real0 + SYNTH.replace(".limit(20 + 1);   // more-said", ".limit(50).limit(20 + 1);   // more-said", 1)}, "S9"),
        ("the retired console brought back (its early return gone)", {"founder-console.html": (ROOT / "founder-console.html").read_text(encoding="utf-8").replace(
            "        else document.getElementById('no-access-gate').hidden = false;\n        return;\n      }",
            "        else document.getElementById('no-access-gate').hidden = false;\n      }", 1)}, "S"),
        ("the way to the rest shrinks below 44px", {"utils.js": utils.replace(".wh-more-note .wh-more-btn{min-height:44px;", ".wh-more-note .wh-more-btn{min-height:32px;", 1)}, "S4"),
    ]
    for name, files, want in mutants:
        merged = dict(files)
        if all(merged[k] == ((real0 + SYNTH) if k == page0 else (ROOT / k).read_text(encoding="utf-8")) for k in merged):
            fails.append(f"mutant '{name}' did not apply (its anchor has drifted)")
            continue
        if page0 not in merged:
            merged[page0] = real0 + SYNTH
        got, _ = check_static(merged)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    # live: the clean cap-ok set is green, and a cap-ok on a read whose largest group exceeds its cap is caught
    if check_live(live):
        fails.append("the clean live run is not green")
    lie = {"page": "synthetic", "line": 1, "src": "hive_audit_log", "n": 50, "scope": None,
           "filters": {"where": [], "group": ["hive_id"]}}
    if not any(x.startswith("V1 synthetic") for x in check_live([lie])):
        fails.append("live mutant 'cap-ok at 50 on a hive's audit log' was not caught - the live check has no teeth")
    # the caps inside functions: a declaration whose page function is gone (static), a cap nobody declared, and a
    # declaration the function no longer backs (live)
    audit = ("get_hive_board_dashboard", "hive_audit_log", 50)
    read = lambda rel: (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    if not any(x.startswith("S10") for x in check_rpc_decl(read, {**RPC_CAPS, audit: ("hive.html", "audit_log", "loadAuditLogGone")})):
        fails.append("mutant 'an inner cap said by a function the page no longer has' was not caught")
    names = rpc_called()
    if check_rpc_live(names):
        fails.append(f"the clean inner-cap run is not green: {check_rpc_live(names)[:2]}")
    if not any(x.startswith("V3 get_hive_board_dashboard caps hive_audit_log") for x in check_rpc_live(names, {k: v for k, v in RPC_CAPS.items() if k != audit})):
        fails.append("live mutant 'the audit trail's inner cap undeclared' was not caught")
    if not any(x.startswith("V3 RPC_CAPS declares") for x in check_rpc_live(names, {**RPC_CAPS, ("get_hive_dashboard", "v_risk_truth", 7): ("index.html", "risks", "renderOnboardingLadder")})):
        fails.append("live mutant 'a declaration the function no longer backs' was not caught")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (15 static mutants caught; a cap-ok that bites, an undeclared inner cap and a stale one are caught live; the clean runs are green)"
               if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
        return 1 if fails else 0
    if "--measure" in sys.argv:
        # every capped read on the LB1 pages, sized against today's data (a planning view, not a verdict)
        allsites = [s for p in PAGES for s in sites_of(p, (ROOT / p).read_text(encoding="utf-8", errors="replace"))]
        err = size_sites([s for s in allsites if s["n"] is not None])
        if err:
            print("measure failed: " + err)
            return 1
        for s in allsites:
            mx, n = s.get("max"), s["n"]
            band = "-" if mx is None or n is None else "BITES" if mx > n else "near" if mx > n / 2 else "far"
            print(f"{band:5} {s['page']}:{s['line']} {s['src']} cap {s['expr'] or 'range'} max {mx} "
                  f"by {s.get('group')} where {s.get('where')} -> {s['disp'] or '-'}")
        return 0
    issues, live = check_static()
    issues += check_live(live)
    issues += check_rpc_live(rpc_called())
    if "--list" in sys.argv:
        for page in PAGES:
            for s in sites_of(page, (ROOT / page).read_text(encoding="utf-8", errors="replace")):
                print(f"{page}:{s['line']} {s['src']} limit {s['expr'] or 'range'} -> {s['disp'] or '-'}")
    if as_json:
        print(json.dumps({"validator": "list_caps_say_more", "status": "FAIL" if issues else "PASS", "issues": issues}, indent=1))
    else:
        print("List caps say more (SL LB1): every list on the LB1 pages is paged or capped, and says when more exists")
        for i in issues[:80]:
            print("  [FAIL] " + i)
        if len(issues) > 80:
            print(f"  ... and {len(issues) - 80} more")
        print(f"  PASS - {len(PAGES)} pages; every capped read is paged, says more, or is proven never to bite ({len(live)} live)"
              if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
