#!/usr/bin/env python3
"""validate_w4_write_recipes.py - is every open wave-4 WRITE lived by a person's own control? (2026-10-08)

The W4 "write" rows (subject <table>.<op>) and the W4 "rpc" rows whose function MUTATES cannot be lived by any
walker that writes for itself: a walk never writes through PostgREST and never calls a mutating rpc directly. Each
is lived instead by a RECIPE in tools/w4_write_recipes.json - the clicks and typing a seeded local persona performs
on the page that owns the write - which tools/w4_action_walk.js presses and tools/w4_write_drive.py reads back and
reverses through postgres. A recipe that names a selector the page does not have, a page outside the repo, a
delete with nothing seeded to delete, or a "step" that is really a direct call, would bank a lie or destroy real
data. This gate refuses each of those before a browser is ever opened (it opens none itself).

FAILS when:
  * an open write/rpc subject has neither a recipe nor `no_ui` (an rpc whose body writes nothing may say `no_write`
    instead, with its steps);
  * a selector token (#id, .class, [attr], a literal attribute value) does not occur in the recipe page's source or
    the local scripts that page loads (the JS that renders it);
  * a recipe's `page` (or a `nav` step) is not a page file inside the repo;
  * a `delete` recipe has no `seed_sql` carrying {MARK} (the ONLY declared exception is `seed_by_press`: the deleted
    rows are created by an earlier step of the same walk - the product's own create-then-undo - and are listed);
  * a recipe would call a mutating rpc or write through the REST API directly: a step that is not a control step
    (click/fill/select/check/waitFor/nav/confirm/upload), a step or nav aimed at /rest/v1/ or /functions/v1/, or any
    recipe SQL that calls one of the open mutating rpcs;
  * structural holes: role not worker|supervisor|anon|newcomer, an expect that does not name the subject's own table/rpc and
    method, a missing effect_sql / reverse_sql, an effect_sql that writes or that names neither {MARK} nor {SINCE},
    a non-insert recipe without reverse_check_sql.
Rows whose path holds no page of the subject's recipes are reported, and the recipe's note must say so.

  python tools/validate_w4_write_recipes.py              # selftest, then the real catalog
  python tools/validate_w4_write_recipes.py --selftest   # the failure fixtures only
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tools" / "w4_write_recipes.json"
REGISTRY = ROOT / "trajectory_registry.json"
PG = ROOT / ".tmp" / "w4_action_pg.json"

# scroll (2026-10-12): an inner box scrolled to its end, as a reader does - skillmatrix opens "Take Exam" only then
# fake_mic / pause (2026-10-12): a generated microphone for a voice control, and a moment to speak into it -
# neither aims at the API, neither takes a selector
# fake_speech / device (2026-10-12): a generated speech recogniser that hears the given sentence, and a phone the page
# is told it runs on (set before it loads) - neither aims at the API, neither takes a selector
STEP_KEYS = {"click", "fill", "select", "check", "waitFor", "nav", "confirm", "upload", "scroll", "fake_mic", "pause",
             "fake_speech", "device", "hear"}
DEVICES = {"iphone"}
# if_shown (2026-10-08): a click on a control the page offers only sometimes (asset-hub's "Show Reliability
# Workbench" toggle, whose state persists per device) - pressed when visible, skipped when not. Click steps only.
STEP_EXTRA = {"value", "filename", "content", "if_shown", "force", "content_b64", "fixture", "within"}
INTERACT = {"click", "fill", "select", "check", "upload"}
# 'anon' (2026-10-08): a story that exists only for a stranger - the landing page's e-mail form, the sign-up form -
# is walked signed out (tools/w4_write_drive.py prep --anon), never by a cast member pretending not to be one.
# 'newcomer' (2026-10-08): a story that only a person with NO hive history can live (set_worker_display_name) is
# walked by a fresh account the walker creates through the sign-up form (prep --newcomer); its reversal deletes it.
ROLES = {"worker", "supervisor", "anon", "newcomer"}
SQL_FIELDS = ("seed_sql", "before_sql", "effect_sql", "reverse_sql", "reverse_check_sql", "seed_cleanup_sql")
FORBIDDEN_RECIPE_KEYS = {"evaluate", "script", "js", "fetch", "request", "rpc_call", "rest", "invoke"}
METHOD = {"insert": "POST", "upsert": "POST", "update": "PATCH", "delete": "DELETE"}
SEED_MARKERS = ("W4M", "w4-", "{MARK}")
WRITE_SQL = re.compile(r"\b(insert\s+into|update\s+\w|delete\s+from|drop\s|alter\s|truncate\s|create\s)", re.I)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass


# ------------------------------------------------------------------------------------------------ inputs
def load_safe_map() -> dict | None:
    if not PG.exists():
        return None
    try:
        return (json.loads(PG.read_text(encoding="utf-8")).get("safe") or {})
    except Exception:
        return None


def open_subjects(trajectories: list, safe: dict | None) -> dict:
    """subject -> {kind, paths: [[pages...], ...]} for every open W4 write row, every open mutating-rpc row and (since
    2026-10-12) every open EDGE row: an edge action is "invoke <function> and see the answer land", and most functions
    run only when a person presses something - so it is lived by the same kind of recipe, keyed by the function name."""
    out: dict = {}
    for t in trajectories:
        w = t.get("w4") or {}
        if w.get("kind") != "action":
            continue
        a = w.get("action") or {}
        kind, subj = a.get("kind"), a.get("subject")
        # upload (2026-10-12): "upload a real <kind> and follow it to where it lands", keyed by the fixture kind
        if kind not in ("write", "rpc", "edge", "upload") or not subj or t.get("status") in ("locked", "descoped"):
            continue
        if kind == "rpc":
            if safe is not None:
                if safe.get(subj) is True:
                    continue
            elif t.get("status") == "locking":
                continue
        s = out.setdefault(subj, {"kind": kind, "paths": []})
        s["paths"].append(list(t.get("pages") or []))
    return out


_SRC_CACHE: dict = {}


def page_sources(root: Path, page: str) -> str:
    """The page plus every local script it loads (the JS that renders its controls)."""
    key = (str(root), page)
    if key in _SRC_CACHE:
        return _SRC_CACHE[key]
    p = root / page
    txt = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    parts = [txt]
    for src in re.findall(r"<script[^>]*\bsrc=[\"']([^\"']+)[\"']", txt, re.I):
        if re.match(r"^(https?:)?//", src):
            continue
        sp = (p.parent / src.split("?")[0].split("#")[0]).resolve()
        try:
            sp.relative_to(root.resolve())
        except ValueError:
            continue
        if sp.is_file() and sp.suffix == ".js":
            parts.append(sp.read_text(encoding="utf-8", errors="replace"))
    _SRC_CACHE[key] = "\n".join(parts)
    return _SRC_CACHE[key]


def page_ok(root: Path, page) -> bool:
    if not isinstance(page, str) or not page or page.startswith(("/", "\\")) or ".." in page or "://" in page:
        return False
    if not re.fullmatch(r"[\w./-]+\.html", page):
        return False
    rp = (root / page).resolve()
    try:
        rp.relative_to(root.resolve())
    except ValueError:
        return False
    return rp.is_file()


# ------------------------------------------------------------------------------------------------ selectors
_ATTR = re.compile(r"\[\s*([\w:-]+)\s*(?:([~|^$*]?=)\s*(?:\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'|([^\]\s]+)))?\s*\]")
_TEXTPSEUDO = re.compile(r":(?:has-text|text|text-is|text-matches)\(\s*(\"[^\"]*\"|'[^']*')\s*\)")


def selector_tokens(sel: str) -> list:
    """(kind, token) pairs a selector requires the page to contain: ('id'|'class'|'attr'|'value', text)."""
    out = []
    s = _TEXTPSEUDO.sub(" ", sel)
    for m in _ATTR.finditer(s):
        name, op = m.group(1), m.group(2)
        val = next((g for g in (m.group(3), m.group(4), m.group(5)) if g is not None), None)
        out.append(("attr", name))
        if op and val is not None:
            v = val.replace('\\"', '"').replace("\\'", "'")
            for mk in SEED_MARKERS:
                if mk in v:
                    v = v.split(mk, 1)[0]
            if len(v.strip()) >= 3:
                out.append(("value", v))
    s = _ATTR.sub(" ", s)
    s = re.sub(r":(not|has|is|where)\(", " ", s).replace(")", " ")
    s = re.sub(r":[\w-]+", " ", s)          # remaining pseudo-classes (:visible, :checked ...)
    out += [("id", m) for m in re.findall(r"#([A-Za-z_][\w-]*)", s)]
    out += [("class", m) for m in re.findall(r"\.([A-Za-z_][\w-]*)", s)]
    return out


def token_in(src: str, kind: str, tok: str) -> bool:
    if kind == "value":
        return tok in src
    return re.search(r"(?<![\w-])" + re.escape(tok) + r"(?![\w-])", src) is not None


# ------------------------------------------------------------------------------------------------ checks
def check_recipe(root: Path, subj: str, kind: str, r: dict, mut_rpcs: set, where: str, fails: list, info: dict) -> None:
    tag = f"{subj}{where}"
    if not isinstance(r, dict):
        fails.append((tag, "BAD_RECIPE", "recipe is not an object"))
        return
    if r.get("no_ui"):
        if not re.search(r"\S+\.\w+:\d+", str(r["no_ui"])):
            fails.append((tag, "NO_UI_SOURCE", "no_ui must name where it is written from as file:line"))
        return
    for k in r:
        if k.lower() in FORBIDDEN_RECIPE_KEYS:
            fails.append((tag, "DIRECT_CALL", f"recipe key '{k}' is not a control - a walk never calls the API itself"))
    page = r.get("page")
    if not page_ok(root, page):
        fails.append((tag, "PAGE_OUTSIDE_REPO", f"page {page!r} is not a page file inside the repo"))
        return
    if r.get("role") not in ROLES:
        fails.append((tag, "ROLE", f"role {r.get('role')!r} is not worker|supervisor|anon|newcomer"))
    src = page_sources(root, page)
    cur_page = page
    steps = r.get("steps")
    if not isinstance(steps, list) or not steps:
        fails.append((tag, "NO_STEPS", "a recipe needs at least one step"))
        steps = []
    interacted = False
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            fails.append((tag, "BAD_STEP", f"step {i} is not an object"))
            continue
        keys = set(st) - STEP_EXTRA
        bad = keys - STEP_KEYS
        if bad or len(keys & STEP_KEYS) != 1:
            fails.append((tag, "DIRECT_CALL" if bad else "BAD_STEP",
                          f"step {i} {sorted(st)} is not exactly one control step ({'/'.join(sorted(STEP_KEYS))})"))
            continue
        k = next(iter(keys & STEP_KEYS))
        blob = json.dumps(st)
        if re.search(r"/rest/v1/|/functions/v1/|/auth/v1/", blob):
            fails.append((tag, "DIRECT_CALL", f"step {i} aims at the API ({blob[:80]}) - only a control may write"))
        if "content_b64" in st:
            # a photo the person picks: bytes, only on an upload, and small (a generated stand-in, not a real image)
            try:
                _raw = base64.b64decode(str(st["content_b64"]), validate=True)
            except Exception:
                _raw = None
            if k != "upload" or _raw is None or not (0 < len(_raw) <= 200_000):
                fails.append((tag, "BAD_STEP", f"step {i}: content_b64 is base64 file bytes (1-200000) on an upload step"))
        # every step, before any kind below `continue`s (2026-10-13): a fixture on a microphone step went unchecked
        if "fixture" in st:
            # a real file is a file WITH PROVENANCE: it sits in _fixtures/<kind>/ and that kind's manifest lists it
            fx = str(st["fixture"])
            kind_dir = root / "_fixtures" / fx.split("/")[0]
            listed = set()
            try:
                listed = {f.get("file") for f in json.loads((kind_dir / "manifest.json").read_text(encoding="utf-8")).get("files") or []}
            except Exception:
                listed = set()
            # a microphone may PLAY a real clip (2026-10-13): fake_mic: true + fixture, the same provenance as an upload
            if k not in ("upload", "fake_mic") or fx.count("/") != 1 or ".." in fx or not (root / "_fixtures" / fx).is_file() or fx.split("/")[1] not in listed:
                fails.append((tag, "BAD_FIXTURE", f"step {i}: fixture {fx!r} is not a real file listed in _fixtures/<kind>/manifest.json"))
        if "within" in st and (k != "waitFor" or not isinstance(st["within"], (int, float)) or not (0 < st["within"] <= 180)):
            fails.append((tag, "BAD_STEP", f"step {i}: within is seconds (1-180), on a waitFor only"))
        if "force" in st and (k != "click" or st["force"] is not True):
            fails.append((tag, "BAD_STEP", f"step {i}: force is only for a click on a control that moves (force: true)"))
        if "if_shown" in st and k != "click":
            fails.append((tag, "BAD_STEP", f"step {i}: if_shown is only for a click on a control the page offers sometimes"))
        if k in INTERACT and not st.get("if_shown"):   # an optional press is not the recipe's interaction
            interacted = True
        if k == "nav":
            target = str(st["nav"]).split("?")[0].split("#")[0]
            if not page_ok(root, target):
                fails.append((tag, "PAGE_OUTSIDE_REPO", f"nav step {i} -> {st['nav']!r} is not a page file inside the repo"))
            else:
                cur_page, src = target, page_sources(root, target)   # later selectors live on the page navigated to
            continue
        if k == "confirm":
            continue
        if k == "fake_mic":
            if st[k] is not True:
                fails.append((tag, "BAD_STEP", f"step {i}: fake_mic takes true"))
            continue
        if k == "fake_speech":
            if not isinstance(st[k], str) or not st[k].strip() or len(st[k]) > 200:
                fails.append((tag, "BAD_STEP", f"step {i}: fake_speech takes the sentence the person says (1-200 characters)"))
            continue
        if k == "hear":
            if st[k] is not True:
                fails.append((tag, "BAD_STEP", f"step {i}: hear takes true (note what the page says aloud)"))
            continue
        if k == "device":
            if st[k] not in DEVICES:
                fails.append((tag, "BAD_STEP", f"step {i}: device takes one of {sorted(DEVICES)}"))
            continue
        if k == "pause":
            if not isinstance(st[k], (int, float)) or not (0 < st[k] <= 10000):
                fails.append((tag, "BAD_STEP", f"step {i}: pause takes milliseconds, 1-10000"))
            continue
        sel = st[k]
        if not isinstance(sel, str) or not sel.strip():
            fails.append((tag, "BAD_STEP", f"step {i} has an empty selector"))
            continue
        for tk, tok in selector_tokens(sel):
            if not token_in(src, tk, tok):
                fails.append((tag, "SELECTOR_NOT_IN_PAGE", f"step {i} {k} {sel!r}: {tk} '{tok}' is not in {cur_page} or its scripts"))
        if k in ("fill", "select") and "value" not in st:
            fails.append((tag, "BAD_STEP", f"step {i} {k} has no value"))
        if k == "upload" and not (st.get("fixture") or (st.get("filename") and (isinstance(st.get("content"), str) or isinstance(st.get("content_b64"), str)))):
            fails.append((tag, "BAD_STEP", f"step {i} upload needs a fixture (a real file), or filename + content (text) or content_b64 (bytes)"))
    exp = r.get("expect") or {}
    path = str(exp.get("path") or "")
    # an accepted non-2xx is a claim about the product's honest refusal - it must say why (2026-10-12, WGW4803)
    if exp.get("accept_status") and len(str(exp.get("accept_why") or "").strip()) < 30:
        fails.append((tag, "ACCEPT_UNSTATED", "expect.accept_status needs expect.accept_why: why that status is the honest outcome"))
    if kind == "write":
        table, op = subj.rsplit(".", 1)
        if not path.endswith("/rest/v1/" + table) and not path.endswith("/rest/v1/rpc/" + table):
            # a write recipe may also be lived by the rpc/edge call that performs it, but must name its own table
            if not r.get("expect_note"):
                fails.append((tag, "EXPECT", f"expect.path {path!r} does not name /rest/v1/{table}"))
        elif path.endswith("/rest/v1/" + table) and str(exp.get("method", "")).upper() != METHOD.get(op, ""):
            fails.append((tag, "EXPECT", f"expect.method {exp.get('method')!r} is not {METHOD.get(op)} for a {op}"))
    elif kind == "upload":
        # ★AN UPLOAD OF A REAL FILE (2026-10-12): the subject is a fixture KIND, so the recipe must hand the page a real
        # file of it (a fixture step - checked above for provenance) and expect the request where it lands: a table, a
        # function or the storage bucket the page's own flow writes to
        fx = [s for s in (r.get("steps") or []) if isinstance(s, dict) and s.get("fixture")]
        if not fx or any(not str(s["fixture"]).startswith(subj + "/") for s in fx):
            fails.append((tag, "UPLOAD_NOT_REAL", f"an upload recipe hands the page a real {subj} fixture (an upload or fake_mic step + fixture: '{subj}/<file>')"))
        if not re.search(r"/(rest/v1|functions/v1|storage/v1)/", path):
            fails.append((tag, "EXPECT", f"expect.path {path!r} names no table, function or storage path the file lands in"))
    elif kind == "edge":
        # the function's own invocation, made by the page in answer to the person's control - never a direct call
        if not path.endswith("/functions/v1/" + subj):
            fails.append((tag, "EXPECT", f"expect.path {path!r} does not name /functions/v1/{subj}"))
        elif exp.get("method") and str(exp.get("method")).upper() != "POST":
            fails.append((tag, "EXPECT", f"expect.method {exp.get('method')!r} is not POST for an edge function"))
    else:
        if not path.endswith("/rest/v1/rpc/" + subj):
            fails.append((tag, "EXPECT", f"expect.path {path!r} does not name /rest/v1/rpc/{subj}"))
    if not interacted and not exp.get("on_load"):
        fails.append((tag, "NO_CONTROL", "no click/fill/select/check/upload step and the request is not on_load"))
    for f in SQL_FIELDS:
        sql = r.get(f)
        if not sql:
            continue
        for name in mut_rpcs:
            if re.search(r"\b" + re.escape(name) + r"\s*\(", sql):
                fails.append((tag, "DIRECT_CALL", f"{f} calls the mutating rpc {name}() itself"))
    if r.get("no_write"):
        # ★A no_write ROW'S reverse_sql NEVER RUNS (2026-10-12, W4704). The driver skips the effect and the reversal of a
        # no_write row and runs only seed_cleanup_sql - but the control that calls a read rpc may then write something
        # else (the project wizard inserts the project after generate_project_code answers). A reversal written there
        # was dead code, and every walk left a project behind. Whatever the flow writes must be in seed_cleanup_sql.
        if r.get("reverse_sql") and not r.get("seed_cleanup_sql"):
            fails.append((tag, "NOWRITE_REVERSE_NEVER_RUNS", "a no_write recipe's reverse_sql is never run by the driver - "
                          "put what the page's flow writes in seed_cleanup_sql"))
        info["no_write"].append(tag)
        return
    eff = r.get("effect_sql") or ""
    if not eff:
        fails.append((tag, "NO_EFFECT", "effect_sql is required"))
    else:
        if not re.match(r"\s*(select|with)\b", eff, re.I) or WRITE_SQL.search(eff):
            fails.append((tag, "EFFECT_WRITES", "effect_sql must be a read-only SELECT"))
        if "{MARK}" not in eff and "{SINCE}" not in eff and "{BEFORE}" not in eff:
            fails.append((tag, "EFFECT_UNKEYED", "effect_sql names none of {MARK} / {SINCE} / {BEFORE}"))
    rs = r.get("reverse_storage")
    if rs is not None:
        # a stored file is taken back through the Storage API by the bank; its names come from a read-only, keyed query
        ns = str((rs or {}).get("names_sql") or "") if isinstance(rs, dict) else ""
        if not (isinstance(rs, dict) and rs.get("bucket") and re.match(r"\s*(select|with)\b", ns, re.I)
                and not WRITE_SQL.search(ns) and ("{SINCE}" in ns or "{MARK}" in ns)):
            fails.append((tag, "BAD_STORAGE", "reverse_storage needs {bucket, names_sql: a read-only SELECT keyed by {SINCE} or {MARK}}"))
    b = r.get("before_sql")
    if b and (not re.match(r"\s*(select|with)\b", b, re.I) or WRITE_SQL.search(b)):
        fails.append((tag, "BEFORE_WRITES", "before_sql must be a read-only SELECT"))
    if not r.get("reverse_sql"):
        fails.append((tag, "NO_REVERSE", "reverse_sql is required"))
    op = subj.rsplit(".", 1)[1] if kind == "write" else (kind if kind in ("edge", "upload") else "rpc")
    if op != "insert" and not r.get("reverse_check_sql"):
        fails.append((tag, "NO_REVERSE_CHECK", "a non-insert recipe needs reverse_check_sql"))
    if r.get("seed_sql") and re.search(r"\binsert\s+into\b", r["seed_sql"], re.I) and "{MARK}" not in r["seed_sql"]:
        fails.append((tag, "SEED_UNMARKED", "a seed that creates rows must carry {MARK} so only the seed is ever removed"))
    if op == "delete":
        if r.get("seed_sql"):
            if "{MARK}" not in r["seed_sql"]:
                fails.append((tag, "DELETE_NO_SEED", "a delete recipe's seed_sql must carry {MARK}"))
        elif r.get("seed_by_press"):
            info["seed_by_press"].append(tag)
        else:
            fails.append((tag, "DELETE_NO_SEED", "a delete recipe must create the row it deletes (seed_sql with {MARK})"))


def check_catalog(root: Path, catalog: dict, opens: dict) -> tuple:
    recipes = catalog.get("recipes", catalog) if isinstance(catalog, dict) else {}
    recipes = {k: v for k, v in recipes.items() if not k.startswith("_")}
    fails: list = []
    info = {"no_ui": [], "no_write": [], "seed_by_press": [], "uncovered_paths": [], "recipes": 0, "held": []}
    mut_rpcs = {s for s, v in opens.items() if v["kind"] == "rpc"}
    for subj, s in sorted(opens.items()):
        r = recipes.get(subj)
        # ★HELD, NOT MISSING (2026-10-12): a subject whose only control a STANDING RULE bars (report-sender's Send - "it
        # emails real recipients through Resend"). It names the control, quotes the rule and who decides; the control
        # must exist on the page. Its rows stay OPEN in the ledger - held is a reason, never a pass.
        if isinstance(r, dict) and r.get("held") and not r.get("steps"):
            h = r["held"] if isinstance(r["held"], dict) else {}
            ctl, rule, who = str(h.get("control") or ""), str(h.get("rule") or ""), str(h.get("decides") or "")
            if not (ctl and len(rule.strip()) >= 20 and who.strip() and r.get("page")):
                fails.append((subj, "BAD_HELD", "held needs page + {control, rule (quoted, 20+ chars), decides}"))
            else:
                src = page_sources(root, str(r["page"]))
                miss = [t for k, t in selector_tokens(ctl) if not token_in(src, k, t)]
                if not src or miss:
                    fails.append((subj, "HELD_CONTROL_NOT_IN_PAGE", f"held control {ctl!r} is not on {r['page']} ({miss or 'no page'})"))
                info["held"].append((subj, len(s["paths"]), f"{r['page']} {ctl} - {who}: {rule[:90]}"))
            continue
        if not r or (not r.get("steps") and not r.get("no_ui")):
            fails.append((subj, "NO_RECIPE", f"open {s['kind']} subject ({len(s['paths'])} row(s)) has neither a recipe nor no_ui"))
            continue
        if r.get("no_ui"):
            info["no_ui"].append(subj)
        info["recipes"] += 1
        check_recipe(root, subj, s["kind"], r, mut_rpcs, "", fails, info)
        pages = {r.get("page")} | {a.get("page") for a in (r.get("alternatives") or []) if isinstance(a, dict)}
        for i, a in enumerate(r.get("alternatives") or []):
            check_recipe(root, subj, s["kind"], a, mut_rpcs, f" [alt {i} {a.get('page') if isinstance(a, dict) else '?'}]", fails, info)
        if not r.get("no_ui"):
            bad = [p for p in s["paths"] if not (set(p) & pages)]
            if bad:
                info["uncovered_paths"].append((subj, len(bad), " > ".join(bad[0])))
                if "path" not in str(r.get("note", "")).lower():
                    fails.append((subj, "PATH_UNSTATED", f"{len(bad)} row(s) walk a path holding none of {sorted(pages)} and the note does not say so"))
    # ★EVERY RECIPE THE DRIVER CAN WALK IS GATED (2026-10-12). Only subjects with open write/rpc/edge rows were checked,
    # and the open list leaves out read rpcs - yet tools/w4_write_drive.py now walks a read rpc by its recipe when
    # Postgres calls it VOLATILE (get_hive_readiness_current, generate_project_code ...). Those recipes were never
    # gated, which is how generate_project_code's dead reversal leaked a project per walk. Every other recipe is
    # checked too, its kind read from its name (table.op = write, kebab-case = edge, else rpc).
    for subj, r in sorted(recipes.items()):
        if subj in opens or not isinstance(r, dict) or r.get("no_ui") or not r.get("steps"):
            continue
        # a fixture kind (a _fixtures/<kind>/ with a manifest) is an upload subject, never an edge function (2026-10-12)
        kind = ("write" if "." in subj else "upload" if (root / "_fixtures" / subj / "manifest.json").is_file()
                else ("edge" if "-" in subj else "rpc"))
        check_recipe(root, subj, kind, r, mut_rpcs, " [not in the open write list]", fails, info)
        for i, a in enumerate(r.get("alternatives") or []):
            check_recipe(root, subj, kind, a, mut_rpcs, f" [not in the open write list, alt {i}]", fails, info)
    return fails, info


# ------------------------------------------------------------------------------------------------ selftest
def selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="w4recipes_"))
    (tmp / "p.html").write_text('<html><body><form id="f"><input id="name"><button id="go" class="btn" '
                                'onclick="saveIt(\'x\')">Go</button></form><script src="u.js"></script></body></html>',
                                encoding="utf-8")
    (tmp / "u.js").write_text("b.setAttribute('data-wh-modal-ok', '');", encoding="utf-8")
    # a fixture kind with provenance (2026-10-12): f.txt is listed in the manifest, g.txt sits beside it unlisted
    (tmp / "_fixtures" / "kind-x").mkdir(parents=True)
    (tmp / "_fixtures" / "kind-x" / "f.txt").write_text("real", encoding="utf-8")
    (tmp / "_fixtures" / "kind-x" / "g.txt").write_text("no provenance", encoding="utf-8")
    (tmp / "_fixtures" / "kind-x" / "manifest.json").write_text(json.dumps({"files": [{"file": "f.txt"}]}), encoding="utf-8")
    good = {"page": "p.html", "role": "worker", "steps": [{"fill": "#name", "value": "{MARK}"}, {"click": "#go"}],
            "expect": {"method": "POST", "path": "/rest/v1/tbl"},
            "effect_sql": "select id from tbl where name = '{MARK}';", "reverse_sql": "delete from tbl where name = '{MARK}';"}
    delete_ok = dict(good, steps=[{"click": "form button[onclick^=\"saveIt('\"]"}, {"click": "[data-wh-modal-ok]"}],
                     expect={"method": "DELETE", "path": "/rest/v1/tbl"}, seed_sql="insert into tbl (name) values ('{MARK}');",
                     reverse_check_sql="select true;", effect_sql="select '{MARK}';")
    opens = {"tbl.insert": {"kind": "write", "paths": [["p.html"]]}}
    cases = {
        "clean": ({"tbl.insert": good}, opens, None),
        "clean-delete": ({"tbl.delete": delete_ok}, {"tbl.delete": {"kind": "write", "paths": [["p.html"]]}}, None),
        "missing-recipe": ({"tbl.insert": good}, dict(opens, **{"tbl.update": {"kind": "write", "paths": [["p.html"]]}}), "NO_RECIPE"),
        "selector-not-in-page": ({"tbl.insert": dict(good, steps=[{"click": "#nope"}])}, opens, "SELECTOR_NOT_IN_PAGE"),
        "attr-value-not-in-page": ({"tbl.insert": dict(good, steps=[{"click": "button[onclick^=\"deleteIt(\"]"}])}, opens, "SELECTOR_NOT_IN_PAGE"),
        "page-outside-repo": ({"tbl.insert": dict(good, page="../outside.html")}, opens, "PAGE_OUTSIDE_REPO"),
        "nav-outside-repo": ({"tbl.insert": dict(good, steps=[{"nav": "https://example.com/x.html"}, {"click": "#go"}])}, opens, "PAGE_OUTSIDE_REPO"),
        "delete-without-seed": ({"tbl.delete": {k: v for k, v in delete_ok.items() if k != "seed_sql"}},
                                {"tbl.delete": {"kind": "write", "paths": [["p.html"]]}}, "DELETE_NO_SEED"),
        "direct-rpc-step": ({"mut_rpc": dict(good, steps=[{"evaluate": "db.rpc('mut_rpc')"}], expect={"path": "/rest/v1/rpc/mut_rpc"},
                                             reverse_check_sql="select true;")},
                            {"mut_rpc": {"kind": "rpc", "paths": [["p.html"]]}}, "DIRECT_CALL"),
        "direct-rpc-nav": ({"mut_rpc": dict(good, steps=[{"nav": "p.html/rest/v1/rpc/mut_rpc"}, {"click": "#go"}],
                                            expect={"path": "/rest/v1/rpc/mut_rpc"}, reverse_check_sql="select true;")},
                           {"mut_rpc": {"kind": "rpc", "paths": [["p.html"]]}}, "DIRECT_CALL"),
        "direct-rpc-sql": ({"mut_rpc": dict(good, expect={"path": "/rest/v1/rpc/mut_rpc"}, seed_sql="select mut_rpc('{MARK}');",
                                            reverse_check_sql="select true;")},
                           {"mut_rpc": {"kind": "rpc", "paths": [["p.html"]]}}, "DIRECT_CALL"),
        "path-unstated": ({"tbl.insert": good}, {"tbl.insert": {"kind": "write", "paths": [["q.html"]]}}, "PATH_UNSTATED"),
        "nowrite-reverse-dead": ({"rd_rpc": dict(good, no_write="reads only", expect={"path": "/rest/v1/rpc/rd_rpc"})},
                                 {"rd_rpc": {"kind": "rpc", "paths": [["p.html"]]}}, "NOWRITE_REVERSE_NEVER_RUNS"),
        "nowrite-with-cleanup": ({"rd_rpc": dict(good, no_write="reads only", expect={"path": "/rest/v1/rpc/rd_rpc"},
                                                 seed_cleanup_sql="delete from tbl where name = '{MARK}';")},
                                 {"rd_rpc": {"kind": "rpc", "paths": [["p.html"]]}}, None),
        "upload-real-fixture": ({"kind-x": dict(good, steps=[{"upload": "#name", "fixture": "kind-x/f.txt"}, {"click": "#go"}],
                                                reverse_check_sql="select true;")},
                                {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, None),
        "mic-real-clip": ({"kind-x": dict(good, steps=[{"fake_mic": True, "fixture": "kind-x/f.txt"}, {"click": "#go"}],
                                          reverse_check_sql="select true;")},
                          {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, None),
        "mic-clip-unlisted": ({"kind-x": dict(good, steps=[{"fake_mic": True, "fixture": "kind-x/g.txt"}, {"click": "#go"}],
                                              reverse_check_sql="select true;")},
                              {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, "BAD_FIXTURE"),
        "mic-clip-as-string": ({"kind-x": dict(good, steps=[{"fake_mic": "kind-x/f.txt"}, {"click": "#go"}],
                                               reverse_check_sql="select true;")},
                               {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, "BAD_STEP"),
        "fixture-on-a-click": ({"kind-x": dict(good, steps=[{"click": "#go", "fixture": "kind-x/f.txt"}],
                                               reverse_check_sql="select true;")},
                               {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, "BAD_FIXTURE"),
        "upload-fixture-unlisted": ({"kind-x": dict(good, steps=[{"upload": "#name", "fixture": "kind-x/g.txt"}, {"click": "#go"}],
                                                    reverse_check_sql="select true;")},
                                    {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, "BAD_FIXTURE"),
        "upload-not-real": ({"kind-x": dict(good, steps=[{"upload": "#name", "filename": "a.txt", "content": "made up"}, {"click": "#go"}],
                                            reverse_check_sql="select true;")},
                            {"kind-x": {"kind": "upload", "paths": [["p.html"]]}}, "UPLOAD_NOT_REAL"),
        "held-clean": ({"send-it": {"page": "p.html", "held": {"control": "#go", "rule": "never press Go: it sends real mail",
                                                               "decides": "the owner"}}},
                       {"send-it": {"kind": "edge", "paths": [["p.html"]]}}, None),
        "held-control-not-in-page": ({"send-it": {"page": "p.html", "held": {"control": "#send", "rule": "never press Send: it sends real mail",
                                                                             "decides": "the owner"}}},
                                     {"send-it": {"kind": "edge", "paths": [["p.html"]]}}, "HELD_CONTROL_NOT_IN_PAGE"),
        "held-without-rule": ({"send-it": {"page": "p.html", "held": {"control": "#go", "decides": "the owner"}}},
                              {"send-it": {"kind": "edge", "paths": [["p.html"]]}}, "BAD_HELD"),
    }
    bad = 0
    for name, (recipes, op, want) in cases.items():
        _SRC_CACHE.clear()
        fails, _ = check_catalog(tmp, {"recipes": recipes}, op)
        codes = {c for _, c, _ in fails}
        ok = (not fails) if want is None else (want in codes)
        print(f"  selftest {'ok  ' if ok else 'FAIL'} {name}: {'clean' if not fails else ', '.join(sorted(codes))}")
        bad += 0 if ok else 1
    _SRC_CACHE.clear()
    print(f"selftest: {len(cases) - bad}/{len(cases)} fixtures behave")
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------ main
def main(argv: list) -> int:
    rc = selftest()
    if "--selftest" in argv:
        return rc
    if rc:
        print("FAIL: the gate's own fixtures do not behave - not trusting it on the real catalog")
        return 1
    if not CATALOG.exists():
        print(f"FAIL: {CATALOG.relative_to(ROOT)} is missing")
        return 1
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    safe = load_safe_map()
    opens = open_subjects(reg.get("trajectories") or [], safe)
    fails, info = check_catalog(ROOT, catalog, opens)
    nw = sum(1 for s in opens.values() if s["kind"] == "write")
    nr = len(opens) - nw
    print(f"open subjects: {len(opens)} ({nw} write, {nr} mutating rpc; rpc safety from "
          f"{'.tmp/w4_action_pg.json' if safe is not None else 'row status (no .tmp safe map)'})")
    print(f"recipes: {info['recipes']}  no_ui: {len(info['no_ui'])}  no_write rpcs: {len(info['no_write'])}  "
          f"seed_by_press deletes: {len(info['seed_by_press'])}")
    for t in info["seed_by_press"]:
        print(f"  seed_by_press  {t}")
    for subj, n, why in info["held"]:
        print(f"  held (OPEN)    {subj}: {n} row(s) - {why}")
    for t in info["no_write"]:
        print(f"  no_write       {t}")
    for subj, n, ex in info["uncovered_paths"]:
        print(f"  path-uncovered {subj}: {n} row(s), e.g. {ex}")
    for tag, code, msg in fails:
        print(f"FAIL {code:22s} {tag}: {msg}")
    print(("PASS" if not fails else f"FAIL ({len(fails)})") + ": w4 write recipes")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
