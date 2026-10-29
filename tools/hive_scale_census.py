#!/usr/bin/env python3
"""hive_scale_census.py - the hive at its full size: thirty members, their roles, their tenants, at the same time (Wave HS,
2026-10-29).

Ian, 2026-10-29, after finding his workmates' older posts cluttered on community.html in production: "you have to expand
our trajectories roadmap with appropriate and necessary number of trajectories that based or anchor in the logic of my
platform, where there are multiple tenants like multi tenancy, Role Based, with up to 30 hive members, how they behave
when they have a post, or lists of, concurrency, anything needed ... just expand my ideas and understand my ideas first,
then add on for those what I have missed."

WHAT THE PLATFORM IS, AS THESE LENSES READ IT: a hive is a tenant of up to thirty members; each member holds a role in it
(worker, supervisor) and may belong to more than one hive; what members make (posts, log entries, parts, PM completions,
projects, listings) is a LIST every other member reads, and on that list the same item offers different actions to its
author, a teammate and a supervisor; and thirty people act at once - two touch the same item, a whole shift writes in the
same minutes, a new item lands while someone is reading. The community defect was all of it on one card: a supervisor's
view of a teammate's post carried four reaction pills at "0" and a row of four icon-only moderation buttons, indented
behind an avatar gutter, with the page's floating controls on top.

THE UNITS ARE MEASURED, NEVER TYPED (one place decides the size - the BRP rule):
  member lists    a (page, relation) a production or founder page reads IN ORDER (.order / .range on the read) where the
                  relation is hive-scoped (hive_id) and says who made each row (an author / worker / account column) -
                  canonical_registry.json's surfaces x the relation's own columns x the page source
  member writes   a (page, relation) the page WRITES that is hive-scoped and attributed - the trail itself excluded (an
                  append-only log is not an item two members edit)
  hive features   presence, the @mention picker, realtime channels and AI calls, found in the pages' own source

THE LENSES - Ian's six ideas first, then what they missed:
  L1 thirty members' items, read as a list     (Ian: posts / lists of 30)       F  U A
  L2 each role sees the actions it may take     (Ian: role based)                F  I U
  L7 a member of two hives                      (Ian: multi tenancy)             S  I
  W1 two members change the same item at once   (Ian: concurrency)               C  F I
  W2 a shift of thirty writes at once           (Ian: concurrency, at 30)        C  A F
  L3 a teammate's new item arrives as you read  (added: realtime at 30)          RL U F
  L4 a year of the hive                         (added: the list grows)          LB F U
  L5 a member who has left                      (added: churn - 30 is not fixed) AU F I
  L6 thirty names                               (added: identity at 30)          AU F U
  H1 presence at thirty / H2 the @mention picker at thirty / H3 thirty open channels and the Free plan's realtime budget /
  H4 thirty members on one hive's AI budget       (added: what scales with the head count, not the item count)

A cell is EMPTY when no in-scope row names its relation (or feature) AND its ask on its page; only empty cells become rows.

    python tools/hive_scale_census.py           # the table
    python tools/hive_scale_census.py --json    # the population the seeder reads
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import registry_io as _rio  # noqa: E402

CANONICAL = ROOT / "canonical_registry.json"
# a column that says WHO made the row - the attribution a list shows and a role is decided on
AUTHOR_COLS = {"auth_uid", "worker_name", "author_name", "created_by", "submitted_by", "assigned_to", "owner_name", "actor",
               "reporter_name", "buyer_name", "seller_name", "requested_by"}
TRAIL = {"hive_audit_log"}   # append-only: members add to it, nobody edits one row of it
HIVE_SIZE = 30


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _rd(p) -> str:
    return Path(p).read_text(encoding="utf-8", errors="ignore")


def _base(rel: str) -> str:
    """v_logbook_truth and logbook are one list to a person."""
    return re.sub(r"_truth$", "", re.sub(r"^v_", "", rel))


class Reg:
    """The registry's text per in-scope row (a row covers a cell when its text names the unit AND the ask on that page)."""

    def __init__(self) -> None:
        rows = [t for t in _rio.load_doc()["trajectories"] if t.get("status") != "descoped"]
        self.rows = []
        for t in rows:
            pages = t.get("pages") or []
            self.rows.append((" ".join(str(t.get(k, "")) for k in ("title", "story", "basis", "note")), pages[-1] if pages else None))

    def covers(self, unit_rx: str, ask_rx: str, page: str) -> bool:
        u, a = re.compile(unit_rx, re.I), re.compile(ask_rx, re.I)
        return any(p == page and u.search(t) and a.search(t) for t, p in self.rows)


def _classes() -> dict:
    import sublayer_inventory as si
    return si.page_classes()


def _cols(cr: dict, rel: str) -> set:
    e = cr["tables"].get(rel) or cr["views"].get(rel) or {}
    return set(e.get("columns") or [])


def _attributed(cr: dict, rel: str) -> bool:
    c = _cols(cr, rel)
    return "hive_id" in c and bool(c & AUTHOR_COLS)


def member_lists(cr: dict, pages: list[str]) -> list[tuple[str, str]]:
    """(page, list) for every hive-scoped, attributed relation the page reads IN ORDER."""
    out = set()
    for p in pages:
        if not (ROOT / p).exists():
            continue
        src = _rd(ROOT / p)
        for rel in (cr["surfaces"].get(p) or {}).get("tables_read", []):
            if not _attributed(cr, rel):
                continue
            for m in re.finditer(r"from\(\s*['\"]" + re.escape(rel) + r"['\"]\s*\)", src):
                stmt = src[m.end(): m.end() + 700].split(";")[0]
                if re.search(r"\.order\(|\.range\(", stmt):
                    out.add((p, _base(rel)))
                    break
    return sorted(out)


def member_writes(cr: dict, pages: list[str]) -> list[tuple[str, str]]:
    out = set()
    for p in pages:
        for rel in (cr["surfaces"].get(p) or {}).get("tables_written", []):
            if rel not in TRAIL and _attributed(cr, rel):
                out.add((p, rel))
    return sorted(out)


def hive_features(pages: list[str]) -> dict:
    feat: dict[str, list[str]] = {"presence": [], "mention picker": [], "realtime": [], "AI": []}
    for p in pages:
        if not (ROOT / p).exists():
            continue
        s = _rd(ROOT / p)
        if re.search(r"presenceState\(|\.track\(\s*\{", s):
            feat["presence"].append(p)
        if re.search(r"mention-(dropdown|list|picker)|showMention|mentionPicker|renderMentions?Dropdown", s):
            feat["mention picker"].append(p)
        if re.search(r"rtConn\(|\.channel\(", s):
            feat["realtime"].append(p)
        if re.search(r"functions\.invoke\(\s*['\"](ai-|agentic|voice|assistant|analytics-orchestrator|shift-planner)", s):
            feat["AI"].append(p)
    return feat


# (key, lens title, ask, layer(s), pillars, persona, coverage regex over a row's text)
LIST_LENSES = [
    ("L1", "thirty members' items, read as a list",
     "with thirty members' items on it, each item is legible at 390 and 1280: who made it, when, what - a count only when "
     "there is one, no row holding a lone control, nothing fixed over it",
     ["F"], ["U", "A"], "worker", r"clutter|thirty members|30 members|density|declutter"),
    ("L2", "each role sees the actions it may take",
     "the same item seen by its author, by a teammate and by a supervisor offers exactly that viewer's actions, named in "
     "words in one place - and the view with the most actions is as clean as the view with the fewest",
     ["F"], ["I", "U"], "supervisor", r"each role sees|per.?role (actions|controls)|post actions menu|role.{0,30}(clutter|actions on (an|the) item)"),
    ("L3", "a teammate's new item arrives as you read",
     "an item a teammate makes lands without moving what the reader is reading or typing; where the list is not live it "
     "says when it was read and refreshes honestly",
     ["RL"], ["U", "F"], "worker", r"arrives (while|as) (you|the reader)|without moving|new item lands|scroll position kept"),
    ("L4", "a year of the hive",
     "after a year of thirty members' work the list is paged or capped and says so, its counts stay honest past the cap, "
     "and a search finds an old item",
     ["LB"], ["F", "U"], "supervisor", r"a year of|of how many|past the cap|1,?000.row|paged"),
    ("L5", "a member who has left",
     "an item made by a member who has left still says who made it (as a former member), offers nobody that member's "
     "controls, and their open work is visibly re-owned",
     ["AU"], ["F", "I"], "supervisor", r"former member|member (who )?(has )?left|left the hive|leaver"),
    ("L6", "thirty names",
     "thirty members' names - long ones, alike ones, two members with one display name - are told apart on the list, and "
     "'mine' is decided by the account, never the name",
     ["AU"], ["F", "U"], "worker", r"same (display )?name|namesake|alike names|long names|name collision"),
    ("L7", "a member of two hives",
     "a member of two hives sees only the active hive's items on this list; switching hives replaces the list whole, never "
     "a mix, and an action taken lands in the hive the list belongs to",
     ["S"], ["I", "F"], "worker", r"two hives|switch(ing)? hives?|multi.?hive|active hive"),
]
WRITE_LENSES = [
    ("W1", "two members change the same item at once",
     "two members change or act on the same item in the same moment (edit, close, approve, claim, delete): one change "
     "lands, the other member is told what changed and by whom, and nothing is lost silently",
     ["C"], ["F", "I"], "worker", r"two (writers|members|sessions)|same (item|row|post|entry) at once|stale stamp|lost update|concurrency guard"),
    ("W2", "a shift of thirty writes at once",
     "at a shift change thirty members write in the same minutes: no honest write is refused by a per-person or per-hive "
     "limit, the list keeps every item in its order, and a write that waits says so",
     ["C"], ["A", "F"], "worker", r"shift change|thirty write|30 (members )?writ|burst of (writes|posts)|rate.?limit"),
]
FEATURE_LENSES = {
    "presence": ("H1", "presence at thirty",
                 "thirty members online at once: the presence row stays one line or summarises ('and 24 more'), stays "
                 "current as people come and go, and never pushes the page's own content down",
                 ["RL"], ["U", "F"], "worker", r"presence.{0,40}(thirty|30|summar|and \d+ more)"),
    "mention picker": ("H2", "the @mention picker at thirty",
                       "typing @ in a thirty-member hive offers the right member within two letters, tells namesakes apart, "
                       "and the mention reaches the account it names",
                       ["F"], ["U", "F"], "worker", r"mention.{0,40}(thirty|30|namesake|two letters)"),
    "realtime": ("H3", "thirty open channels",
                 "thirty members with this page open hold the hive's realtime channels inside the Free plan's budget "
                 "(concurrent connections and messages), and a member past it is told the list is not live",
                 ["RL"], ["A", "F"], "worker", r"realtime (budget|connections?)|concurrent connections|200 (concurrent|connections)"),
    "AI": ("H4", "thirty members on one hive's AI budget",
           "thirty members asking the AI on the same day share the hive's budget: the one who reaches it is told what it "
           "is and when it resets, and everyone else keeps working",
           ["LM"], ["A", "F"], "worker", r"(hive'?s? )?ai budget|daily (ai )?(cap|budget)|cost cap.{0,40}(member|hive)"),
}


def census() -> dict:
    reg = Reg()
    cr = json.loads(CANONICAL.read_text(encoding="utf-8"))
    classes = _classes()
    pages = classes["production"] + classes["founder"]
    lists, writes, feats = member_lists(cr, pages), member_writes(cr, pages), hive_features(pages)
    cells = []

    def add(key, lens, ask, layers, ufai, persona, unit, page, detail):
        cells.append({"key": key, "lens": lens, "ask": ask, "unit": unit, "page": page, "persona": persona,
                      "layers": layers, "ufai": ufai, "detail": detail,
                      "page_class": "founder" if page in classes["founder"] else "production"})

    for page, rel in lists:
        for key, lens, ask, layers, ufai, persona, rx in LIST_LENSES:
            # a founder page reads across every hive by design - "a member of two hives" is not its question
            if key == "L7" and page in classes["founder"]:
                continue
            if page in classes["founder"]:
                persona = "oversight"
            if not reg.covers(re.escape(rel), rx, page):
                add(key, lens, ask, layers, ufai, persona, rel, page,
                    f"{page} reads {rel} in order - a list of what the hive's members made")
    for page, rel in writes:
        for key, lens, ask, layers, ufai, persona, rx in WRITE_LENSES:
            if not reg.covers(re.escape(rel), rx, page):
                add(key, lens, ask, layers, ufai, persona, rel, page, f"{page} writes {rel} - an item members make and change")
    for feat, fpages in feats.items():
        key, lens, ask, layers, ufai, persona, rx = FEATURE_LENSES[feat]
        for page in fpages:
            if not reg.covers(r".", rx, page):
                add(key, lens, ask, layers, ufai, persona, feat, page, f"{page} carries {feat} - it scales with the head count")
    pop = {"pages": len(pages), "member lists": len(lists), "member writes": len(writes),
           **{f"{k} pages": len(v) for k, v in feats.items()}, "hive size": HIVE_SIZE}
    return {"population": pop, "cells": cells, "by_lens": dict(Counter(f"{c['key']} {c['lens']}" for c in cells)),
            "total": len(cells), "lists": lists, "writes": writes, "features": feats}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    print("\nHS - the hive at its full size (population x what each unit owes - rows already there)")
    print("=" * 96)
    print("  population: " + " · ".join(f"{k} {v}" for k, v in c["population"].items()))
    for lens, n in c["by_lens"].items():
        print(f"    {lens:<52} {n:>5}")
    print(f"  = {c['total']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
