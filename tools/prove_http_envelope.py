# -*- coding: utf-8 -*-
"""What the HTTP gateway actually returns — `envelope_shape`, `status_body_agreement`,
and the one that matters most, `boundary_not_emptiness`.

These three oracles sat OWED across sessions on a false premise. Two provers documented that they
"need the REST gateway, which is not reachable from this shell (kong publishes no host port)", and one
copied that sentence into banked evidence. It was wrong: `docker ps` shows
`supabase_kong_workhive  0.0.0.0:54321->8000/tcp`, and a GET with the publishable key answers 200. A
ceiling written into a tool's docstring stops reading like a claim and starts reading like
documentation, which is why it survived — see the correction now in prove_read_idempotency.py.

THE THREE QUESTIONS, ASKED WITH REAL REQUESTS AGAINST THE LOCAL GATEWAY. The PostgREST half is GET-only
and cannot write. **The EDGE half does POST an empty body, and that is not effect-free** — see POST_SKIP:
on the first run `benchmark-compute` answered 200 and recomputed hive/network benchmarks, twice. Both
offenders are now OPTIONS-only. The original wording here claimed "nothing here writes", which was true
of the gateway half and false of the edge half; it is corrected rather than deleted, because a tool that
overstates its own safety is how a probe becomes a mutation nobody expected.

The three questions:

  envelope_shape          a collection read returns a JSON ARRAY; an `Accept:
                          application/vnd.pgrst.object+json` read of 0 rows returns PGRST116; an error
                          body carries ALL FOUR of {code, message, details, hint}; a `Prefer:
                          count=exact` read returns a Content-Range header.
  status_body_agreement   no 2xx carries an error object, every 4xx carries a machine-readable `code`,
                          and an unknown column is a 400 rather than a 500.
  boundary_not_emptiness  can a caller tell REFUSAL from ABSENCE? This is the sharp one, and the
                          answer here is NO — measured, not argued.

WHAT THE MEASUREMENT SHOWS, and why it is a finding rather than a pass. For `logbook`, `hive_members`
and `inventory_items`, an anonymous caller and an authenticated member get:

    anon  -> HTTP 200, body `[]`      (0 rows)
    auth  -> HTTP 200, body `[{...}]` (3 rows)

Same status. Same body TYPE. The only difference is the row count. And a request carrying **no apikey
at all** also returns `200 []`. So nothing in the response distinguishes "you are not permitted",
"you are not signed in", and "this hive genuinely has no entries" — the client must decide it from
session state, and if it does not, a signed-out or expired session renders as an empty plant. That is
the read-path half of the 401-vs-403 lesson this platform already carries, and it is exactly what
`boundary_not_emptiness` asks. It is inherent to PostgREST + RLS (row filtering is not request
refusal), so it is reported as a MEASURED CONTRACT of the gateway that every surface inherits, not as
a bug in the gateway.

THREE NON-VACUITY CONTROLS, because every one of the six provers before this reported a false alarm on
its first run and the pass has to cost something:
  1. an unknown column MUST return 400 — proves the prober can observe a failure at all
  2. `community_posts` MUST return rows to an anon caller (it is the public feed) — proves anon is not
     blanket-denied, so `200 []` on a tenant table is RLS doing its job rather than a dead key
  3. authenticated MUST return rows where anon returns none — proves the two personas genuinely differ,
     without which "refusal is indistinguishable from absence" would be vacuously true

    python tools/prove_http_envelope.py            # human report
    python tools/prove_http_envelope.py --gate      # exit 1 on an envelope/status defect
    python tools/prove_http_envelope.py --json
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "http_envelope_report.json")
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[31m", "\033[2m", "\033[0m"
BASE = "http://127.0.0.1:54321/rest/v1"
IMPOSSIBLE = "00000000-0000-0000-0000-000000000000"
ERROR_KEYS = ("code", "message", "details", "hint")

ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]


# The LOCAL publishable key, the same constant tools/companion_live_capture.py and its siblings carry.
# It is not a secret: a publishable key is client-side by design (utils.js hands it to createClient in
# the browser), and this one addresses 127.0.0.1 only. Env and the container are still preferred, so a
# reseed that rotates it does not need this file edited.
LOCAL_PUBLISHABLE = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"


def resolve_key(bep):
    """Prefer the environment, then the container, then the local constant.

    backend_edge_probe.anon_key() alone returns "" on this stack: it accepts only a legacy `eyJ...` JWT
    and this project has moved to the `sb_publishable_...` format, so reusing it unchanged made the
    whole prover SKIP. Reuse was still right — the fallback chain is the fix, not a second helper.
    """
    for var in ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"):
        v = os.environ.get(var, "").strip()
        if v:
            return v, var
    k = bep.anon_key()
    if k:
        return k, "container SUPABASE_ANON_KEY (legacy JWT)"
    return LOCAL_PUBLISHABLE, "local publishable constant"


def _probe_mod():
    """Reuse the credential helpers that already exist rather than re-deriving them."""
    spec = importlib.util.spec_from_file_location(
        "_bep", os.path.join(ROOT, "tools", "backend_edge_probe.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def get(path, key, jwt=None, accept=None, prefer=None):
    """One GET. Returns (status, headers, parsed-or-raw body)."""
    req = urllib.request.Request(BASE + path, method="GET")
    if key:
        req.add_header("apikey", key)
    if jwt:
        req.add_header("Authorization", "Bearer " + jwt)
    if accept:
        req.add_header("Accept", accept)
    if prefer:
        req.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, dict(r.headers), _parse(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return e.code, dict(e.headers or {}), _parse(raw)
    except Exception as e:
        return None, {}, {"_transport_error": str(e)[:120]}


def _parse(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {"_unparseable": raw[:160]}


def page_relations(page):
    src = ""
    for f in (page + ".html", page + ".js"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            src += "\n" + open(p, encoding="utf-8", errors="replace").read()
    return sorted({m.group(1) for m in
                   re.finditer(r"""\.from\(\s*['"]([a-z_0-9]+)['"]\s*\)""", src)})


# ── THE OTHER HALF OF boundary_not_emptiness: DOES THE PAGE DECIDE WHAT THE GATEWAY CANNOT? ───────
# The gateway genuinely cannot separate refusal from absence — that is measured below and it is not in
# dispute. But the oracle asks whether a READER is misled, and that is decided on the page. Reporting
# the gateway fact as a per-page defect produced 28 findings that were ALL false: 18 of the 22 pages
# redirect an unauthenticated visitor to sign-in before anything renders, three more are anon-by-design
# (public-feed is the public feed, engineering-design is the free public calculators, achievements has a
# public profile view), and assistant.html already carries a comment describing this precise failure —
# its six RLS grounding reads 401'd on a cold load and "the system prompt is built with EMPTY records ->
# the assistant answers UNGROUNDED for the session, silently" — fixed by forcing getUser() to settle
# auth before the reads. So the page layer already answers it, and the honest verdict is a PASS that
# NAMES the mechanism rather than a finding that ignores it.
# whSignInWall IS the redirect - the detector just knew only its PRE-CENTRALISATION spellings
# (2026-08-28). T2 moved the sign-in wall into ONE utils.js helper:
#     function whSignInWall() { window.location.href = 'index.html?signin=1&return=' + here }
# so the pages that adopted it stopped containing the literal `signin=1` this pattern looks for, and
# EIGHT of them (analytics, analytics-report, asset-hub, dayplanner, hive, pm-scheduler,
# project-manager, skillmatrix) were reported as having "no session gate" while each carries 1-3
# whSignInWall call sites. Verified live the same day: report-sender.html sends an unauthenticated
# visitor to index.html?signin=1&return=report-sender.html, and after sign-in the browser lands back
# on the page. A centralised mechanism is still a mechanism; a detector that only knows the old
# spelling reports the REFACTOR as a regression.
GATE_RE = re.compile(r"""signin=1|whRequireAuth|requireAuth\(|whSignInWall""")
ANON_BY_DESIGN = {
    "public-feed": "this IS the public feed; an anon visitor seeing the public set is the product",
    "engineering-design": "the calculators are free public tools, anon is the primary persona",
    "achievements": "a public profile view is an intended anon persona for this page",
}
AUTH_SETTLED_RE = re.compile(r"""getUser\(\)""")


def page_session_gate(page):
    """How this page keeps the gateway's ambiguity away from a reader."""
    src = ""
    for f in (page + ".html", page + ".js"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            src += "\n" + open(p, encoding="utf-8", errors="replace").read()
    if not src.strip():
        return {"mechanism": None, "detail": "no source found"}
    if GATE_RE.search(src):
        return {"mechanism": "redirects-unauthenticated",
                "detail": "an unauthenticated visitor is sent to sign-in before any render, so a "
                          "200-with-no-rows caused by having no session cannot reach a reader here"}
    if page in ANON_BY_DESIGN:
        return {"mechanism": "anon-by-design", "detail": ANON_BY_DESIGN[page]}
    if AUTH_SETTLED_RE.search(src):
        return {"mechanism": "settles-auth-before-reads",
                "detail": "getUser() forces a validated round-trip so the reads do not run before the "
                          "JWT is attached, which is the cold-load version of this same defect"}
    return {"mechanism": None,
            "detail": "no session gate, no anon-by-design rationale and no auth settling found - a "
                      "200-with-no-rows from having no session could render as 'nothing here'"}


# ── THE EDGE LAYER IS A DIFFERENT ENVELOPE, AND CONFLATING THEM COST 62 FALSE GREENS ──────────────
# The first version of this prover measured PostgREST and the banker applied that one reading to EVERY
# CA layer row on a page — including subjects named `edge`, `ai`, `external-send`, `cron`, `realtime`,
# `print`. It is a different question and the answer is visibly different: POST {} to
# /functions/v1/ai-gateway returns 400 with `{"error":"Missing agent"}` — ONE key — where PostgREST
# returns {code, message, details, hint}. Worse, supabase_edge_runtime_workhive had been
# "Exited (255) 4 days ago" at the time, so every edge function was answering 503 while rows were being
# banked green about edge behaviour. All 62 were withdrawn; this section is what lets them be re-earned
# against the layer they actually name.
EDGE_BASE = "http://127.0.0.1:54321/functions/v1"
INVOKE_RE = re.compile(r"""functions\.invoke\(\s*['"]([a-z0-9-]+)['"]|functions/v1/([a-z0-9-]+)""")
# NEVER POST to these: money, at-least-once delivery, an outward send — or, as of the first run, any
# function that turned out to DO ITS JOB on an empty body.
#
# I CAUSED A SIDE EFFECT AND THIS LIST IS THE FIX. The first run POSTed `{}` to all 27 functions on the
# reasoning that an empty body carries no instruction, so a well-built function refuses it at validation.
# 25 did exactly that (400/403 with an error key). TWO DID NOT: `benchmark-compute` answered
# 200 {hives_computed, ok} — it RAN, twice (once unauthenticated, once as a member), recomputing hive and
# network benchmarks against the shared local database — and `equipment-label-ocr` answered 200 as well.
# "An empty body cannot cause an effect" was an assumption, not a measurement, and it was wrong for 2 of
# 27. Both are now OPTIONS-only, so a re-run cannot repeat it.
POST_SKIP = re.compile(r"marketplace|webhook|release|checkout|connect|cmms-push|send-report"
                       r"|benchmark-compute|equipment-label-ocr")


# ── A FINDING THE SAFETY FIX WOULD OTHERWISE HAVE BURIED ──────────────────────────────────────────
# Adding equipment-label-ocr to POST_SKIP stopped my probe from re-invoking it — and simultaneously
# stopped the prover REPORTING what that invocation had already proven. A safety exclusion that silences
# a real finding is worse than the side effect it prevents, so the finding is declared here, with the
# measurement that produced it, and re-reported on every run until it is fixed.
# RETRACTED. This list held one entry -- equipment-label-ocr returning 200 with `azure_unavailable` --
# and reading the function killed it. supabase/functions/equipment-label-ocr/index.ts:237-250 carries the
# decision explicitly: "graceful degradation -- Azure OCR not configured; frontend reads
# `azure_unavailable` flag + parsed nulls and renders the manual-entry fallback. Request DID succeed
# (200) -- service unavailable", and it is tagged `// edge-status-allow`, a marker
# tools/verify_layer_invariants.py already recognises. So the 200 is a DELIBERATE, DOCUMENTED,
# ALREADY-GATED disposition and my finding was the 11th first-run over-report of this session.
# The marker is honoured below rather than re-litigated -- an existing convention beats a second opinion.
KNOWN_EDGE_FINDINGS = []
EDGE_STATUS_ALLOW = "edge-status-allow"


def edge_status_exempt(fn):
    """Does this function DECLARE that a 2xx-with-error is intentional? Read its source and see."""
    p = os.path.join(ROOT, "supabase", "functions", fn, "index.ts")
    if not os.path.exists(p):
        return False
    return EDGE_STATUS_ALLOW in open(p, encoding="utf-8", errors="replace").read()


def edge_get(fn, key, jwt=None, method="OPTIONS", body=None):
    req = urllib.request.Request(EDGE_BASE + "/" + fn, method=method,
                                 data=(body.encode() if body else None))
    if key:
        req.add_header("apikey", key)
    if jwt:
        req.add_header("Authorization", "Bearer " + jwt)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, _parse(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, _parse(e.read().decode("utf-8", "replace"))
    except Exception as e:
        return None, {"_transport_error": str(e)[:120]}


def page_edge_fns(page):
    src = ""
    for f in (page + ".html", page + ".js"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            src += "\n" + open(p, encoding="utf-8", errors="replace").read()
    return sorted({(m.group(1) or m.group(2)) for m in INVOKE_RE.finditer(src)
                   if (m.group(1) or m.group(2))})


def probe_edge(fn, key, jwt):
    """The envelope questions that can be asked of an edge function WITHOUT causing an effect."""
    out = {"function": fn}
    s_opt, _ = edge_get(fn, key)                                   # CORS preflight
    out["options"] = {"status": s_opt}
    out["post_skipped"] = bool(POST_SKIP.search(fn))
    if not out["post_skipped"]:
        # An EMPTY body is the safest possible POST: it cannot carry an instruction, so a well-built
        # function refuses it on validation before doing anything.
        s_no, b_no = edge_get(fn, key, method="POST", body="{}")
        out["post_noauth"] = {"status": s_no,
                              "keys": sorted(b_no)[:6] if isinstance(b_no, dict) else None,
                              "has_error_key": isinstance(b_no, dict) and bool(
                                  {"error", "message", "code"} & set(b_no))}
        s_au, b_au = edge_get(fn, key, jwt=jwt, method="POST", body="{}")
        out["post_auth"] = {"status": s_au,
                            "keys": sorted(b_au)[:6] if isinstance(b_au, dict) else None,
                            "has_error_key": isinstance(b_au, dict) and bool(
                                {"error", "message", "code"} & set(b_au))}
    # ── EDGE IDEMPOTENCY, AND EXACTLY WHAT IT DOES AND DOES NOT PROVE ─────────────────────────────
    # The same request issued twice must produce the same status and the same body. What this covers is
    # the VALIDATION path: a refusal that is not deterministic means two identical calls get two
    # different answers, which is unusable for a client. What it does NOT cover is the SUCCESS path -
    # proving that would need valid per-function inputs, and invoking these functions for real is what
    # made benchmark-compute recompute the benchmarks. So the claim is narrow and stated narrowly rather
    # than sold as full idempotency.
    if not out["post_skipped"]:
        s_r2, b_r2 = edge_get(fn, key, jwt=jwt, method="POST", body="{}")
        pa0 = out.get("post_auth") or {}
        same_status = s_r2 == pa0.get("status")
        same_keys = (sorted(b_r2) if isinstance(b_r2, dict) else None) == pa0.get("keys")
        out["repeat"] = {"status": s_r2, "same_status": same_status, "same_keys": same_keys}
        out["idempotent_refusal"] = bool(same_status and same_keys)
    else:
        out["repeat"] = {"skipped": "POST is skipped for this function"}
        out["idempotent_refusal"] = None

    shape, agree = [], []
    if out["options"]["status"] is None:
        shape.append("the function did not answer at all (is the edge runtime up?)")
    elif out["options"]["status"] not in (200, 204):
        shape.append("OPTIONS returned %s, so a browser preflight would fail" % out["options"]["status"])
    # JUDGE THE FUNCTION, NOT THE GATEWAY IN FRONT OF IT. The unauthenticated POST was the wrong
    # instrument for the error-key question: it reported "a 401 carries no error/message/code key" for
    # supervisor-reset-password, whose source plainly returns json(401, {error:"unauthenticated"}) at
    # index.ts:60. The 401 my probe saw came from kong rejecting a request with no JWT before the
    # function ran at all -- so it measured the platform's auth edge and attributed it to the function.
    # The AUTHENTICATED probe is the one that actually reaches the function body.
    pa = out.get("post_auth")
    if pa and pa["status"] is not None:
        if pa["status"] >= 400 and not pa["has_error_key"]:
            shape.append("a %s carries no error/message/code key a caller could read" % pa["status"])
        if pa["status"] == 500:
            agree.append("an empty body produced 500 rather than a 4xx validation refusal")
        if 200 <= pa["status"] < 300 and pa["has_error_key"] and not edge_status_exempt(fn):
            agree.append("a 2xx body carries an error key")
    out["envelope_shape"] = shape or None
    if out.get("idempotent_refusal") is False:
        agree.append("two identical requests returned different answers (status %s vs %s)"
                     % ((out.get("post_auth") or {}).get("status"), out["repeat"].get("status")))
    out["status_body_agreement"] = agree or None
    return out


def id_columns():
    """Relations that actually HAVE an `id` column.

    The first run probed `?id=eq.<uuid>` on every relation and reported two envelope defects, BOTH of
    them mine. community_xp is keyed (worker_name, hive_id) and has no `id` at all, so the filter
    returned 42703 "column does not exist" — my malformed request, read back as the gateway's
    misbehaviour. A probe that assumes a schema it did not check produces findings about itself.
    """
    import subprocess
    p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                        "-d", "postgres", "-At", "-c",
                        "SELECT table_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND column_name='id'"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()}


# Postgres/PostgREST codes that mean "your request was understood and REFUSED", which is a correct
# envelope, not a shape defect. 42501 = insufficient privilege: `projects` answers with this rather than
# 200 [], and that is BETTER behaviour than the 26 relations that hide a refusal inside an empty array.
REFUSAL_CODES = {"42501", "PGRST301", "PGRST302", "42P01"}


def probe_relation(rel, key, jwt, has_id=True):
    """Every envelope question, for one relation."""
    out = {"relation": rel, "has_id_column": has_id}
    s, h, b = get("/%s?select=*&limit=2" % rel, key)
    out["anon"] = {"status": s, "is_array": isinstance(b, list),
                   "rows": len(b) if isinstance(b, list) else None,
                   "body_keys": sorted(b)[:4] if isinstance(b, dict) else None}
    s2, h2, b2 = get("/%s?select=*&limit=2" % rel, key, jwt=jwt)
    out["auth"] = {"status": s2, "is_array": isinstance(b2, list),
                   "rows": len(b2) if isinstance(b2, list) else None}
    s3, _, b3 = get("/%s?select=*&limit=1" % rel, None)
    out["nokey"] = {"status": s3, "is_array": isinstance(b3, list),
                    "rows": len(b3) if isinstance(b3, list) else None}
    # A single-object read of a row that cannot exist: PostgREST's documented shape is 406 + PGRST116.
    if has_id:
        s4, _, b4 = get("/%s?select=*&id=eq.%s" % (rel, IMPOSSIBLE), key, jwt=jwt,
                        accept="application/vnd.pgrst.object+json")
        out["single_zero"] = {"status": s4, "code": b4.get("code") if isinstance(b4, dict) else None,
                              "has_all_error_keys": (isinstance(b4, dict)
                                                     and all(k in b4 for k in ERROR_KEYS))}
    else:
        out["single_zero"] = {"status": None, "code": None, "has_all_error_keys": None,
                              "skipped": "this relation has no id column, so a single-object read "
                                         "keyed on id is not a question that can be asked of it"}
    s5, _, b5 = get("/%s?select=wh_no_such_column" % rel, key, jwt=jwt)
    out["bad_column"] = {"status": s5, "code": b5.get("code") if isinstance(b5, dict) else None,
                         "has_all_error_keys": (isinstance(b5, dict)
                                                and all(k in b5 for k in ERROR_KEYS))}
    s6, h6, _ = get("/%s?select=id&limit=1" % rel, key, jwt=jwt, prefer="count=exact")
    out["count_header"] = {"status": s6,
                           "content_range": (h6 or {}).get("Content-Range")}

    # ── the verdicts ──────────────────────────────────────────────────────────────────────────────
    shape = []
    if not out["anon"]["is_array"] and out["anon"]["status"] == 200:
        shape.append("a 200 collection read did not return a JSON array")
    sz = out["single_zero"]
    if sz["status"] == 200:
        shape.append("a single-object read of 0 rows returned 200 instead of 406/PGRST116")
    elif sz["code"] in REFUSAL_CODES:
        # Understood and REFUSED with a machine-readable code. That is a correct envelope - and on this
        # platform it is the GOOD behaviour, since the alternative most relations show is 200 [].
        out["refuses_with_code"] = sz["code"]
    elif sz["status"] is not None and sz["code"] not in (None, "PGRST116"):
        shape.append("a single-object read of 0 rows returned code %s, which is neither PGRST116 nor a "
                     "recognised refusal code" % sz["code"])
    if out["bad_column"]["status"] and out["bad_column"]["status"] >= 400 \
            and not out["bad_column"]["has_all_error_keys"]:
        shape.append("an error body is missing one of %s" % ", ".join(ERROR_KEYS))
    cr = out["count_header"]
    if cr["content_range"] is None and cr["status"] and 200 <= cr["status"] < 300:
        shape.append("Prefer: count=exact returned no Content-Range header on a 2xx")
    out["envelope_shape"] = shape or None

    agree = []
    if out["bad_column"]["status"] == 500:
        agree.append("an unknown column produced 500, not 400")
    if out["bad_column"]["status"] and 200 <= out["bad_column"]["status"] < 300:
        agree.append("an unknown column returned a 2xx")
    for name in ("anon", "auth"):
        st = out[name]["status"]
        if st and 200 <= st < 300 and out[name].get("body_keys") and \
                "code" in (out[name]["body_keys"] or []):
            agree.append("a %s 2xx carried an error object" % name)
    if out["bad_column"]["status"] and out["bad_column"]["status"] >= 400 \
            and not out["bad_column"]["code"]:
        agree.append("a 4xx carried no machine-readable code")
    out["status_body_agreement"] = agree or None

    # REFUSAL vs ABSENCE: only meaningful when the two personas genuinely see different data.
    a, u = out["anon"], out["auth"]
    if a["rows"] is not None and u["rows"] is not None and u["rows"] > 0 and a["rows"] == 0:
        out["boundary"] = ("indistinguishable" if a["status"] == u["status"] else "distinguishable")
    else:
        out["boundary"] = "not-exercised"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit-relations", type=int, default=40)
    a = ap.parse_args(argv)

    bep = _probe_mod()
    key, key_src = resolve_key(bep)
    if not key:
        print("  %sSKIP%s no local publishable/anon key could be resolved" % (YEL, RST))
        return 0
    s, _, _ = get("/", key)
    if s is None:
        print("  %sSKIP%s the local REST gateway is not answering on 127.0.0.1:54321" % (YEL, RST))
        return 0
    jwt = bep.user_jwt(key) or None

    wanted = {}
    for page in ALL_PAGES:
        for rel in page_relations(page):
            wanted.setdefault(rel, []).append(page)
    rels = sorted(wanted)[:a.limit_relations]

    ids = id_columns()
    results = [probe_relation(r, key, jwt, has_id=(r in ids)) for r in rels]

    # ── the three controls ────────────────────────────────────────────────────────────────────────
    ctl = {}
    ctl["bad_column_400"] = {"ok": any(r["bad_column"]["status"] == 400 for r in results),
                             "note": "an unknown column must produce a 400, or this prober cannot "
                                     "observe a failure at all"}
    pub = next((r for r in results if r["relation"] == "community_posts"), None)
    # The star-read CANNOT carry this control any more: 20260831000001 revoked auth_uid from anon at
    # the COLUMN level, and a column revoke makes anon's select=* fail wholesale (42501/401) even
    # though anon reads of the permitted columns succeed - the exact incident the
    # a-column-revoke-is-inert-under-a-table-grant lesson records. The star result stays REPORTED
    # (that 401 is the designed envelope for anon select-star now); the control judges "anon sees
    # rows" on an explicit permitted-column read, which is what every real anon surface issues.
    sctl, _, bctl = get("/community_posts?select=id&limit=2", key)
    ctl_rows = len(bctl) if isinstance(bctl, list) else None
    ctl["anon_not_blanket_denied"] = {
        "ok": bool((ctl_rows or 0) > 0),
        "note": "community_posts is the public feed, so an anon caller must see rows - otherwise a "
                "200 [] on a tenant table would just mean a dead key (judged on select=id: anon "
                "select=* is 401 by design since the auth_uid column revoke)",
        "rows": ctl_rows, "star_rows": (pub["anon"]["rows"] if pub else None)}
    ctl["personas_differ"] = {
        "ok": any(r["boundary"] == "indistinguishable" or
                  (r["auth"]["rows"] or 0) > (r["anon"]["rows"] or 0) for r in results),
        "note": "authenticated must out-read anon somewhere, or 'refusal looks like absence' would be "
                "vacuously true"}

    shape_bad = [r for r in results if r["envelope_shape"]]
    agree_bad = [r for r in results if r["status_body_agreement"]]
    indist = [r for r in results if r["boundary"] == "indistinguishable"]

    edge_fns = sorted({f for pg in ALL_PAGES for f in page_edge_fns(pg)})
    edge = [probe_edge(f, key, jwt) for f in edge_fns]
    edge_bad = [e for e in edge if e['envelope_shape'] or e['status_body_agreement']]
    edge_up = any(e['options']['status'] in (200, 204) for e in edge)
    gates = {pg: page_session_gate(pg) for pg in ALL_PAGES}
    ungated = sorted(pg for pg, g in gates.items() if not g["mechanism"])
    payload = {"relations": results, "controls": ctl, "jwt": bool(jwt), "key_source": key_src,
               "page_session_gates": gates, "ungated_pages": ungated,
               "edge_functions": edge, "edge_runtime_up": edge_up,
               "known_edge_findings": KNOWN_EDGE_FINDINGS,
               "edge_functions_by_page": {pg: page_edge_fns(pg) for pg in ALL_PAGES},
               "counts": {"probed": len(results), "envelope_defects": len(shape_bad),
                          "status_defects": len(agree_bad),
                          "refusal_indistinguishable_from_absence": len(indist)},
               "pages_by_relation": wanted}
    with open(REPORT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    os.replace(REPORT + ".tmp", REPORT)
    if a.json:
        print(json.dumps(payload, indent=1))
        return 1 if (shape_bad or agree_bad) else 0

    print("  %sHTTP ENVELOPE AT THE LIVE GATEWAY%s  %d relation(s) probed, authenticated=%s, "
          "key from %s" % (DIM, RST, len(results), bool(jwt), key_src))
    for name, c in ctl.items():
        print("    %s%s%s control %-26s %s"
              % (GREEN if c["ok"] else RED, "ok  " if c["ok"] else "FAIL", RST, name, c["note"][:88]))
    if not all(c["ok"] for c in ctl.values()):
        print("  %sa control failed - every verdict below is unproven%s" % (RED, RST))

    print("\n  %senvelope_shape%s      %d relation(s) with a defect" % (DIM, RST, len(shape_bad)))
    for r in shape_bad[:8]:
        print("    %-26s %s" % (r["relation"], "; ".join(r["envelope_shape"])[:110]))
    print("  %sstatus_body_agree%s   %d relation(s) with a defect" % (DIM, RST, len(agree_bad)))
    for r in agree_bad[:8]:
        print("    %-26s %s" % (r["relation"], "; ".join(r["status_body_agreement"])[:110]))

    print("\n  %sboundary_not_emptiness%s" % (DIM, RST))
    for v, n in collections.Counter(r["boundary"] for r in results).most_common():
        print("    %4d  %s" % (n, v))
    if indist:
        print("    %sREFUSAL IS INDISTINGUISHABLE FROM ABSENCE on %d relation(s): anon and an "
              "authenticated member receive the SAME status and the same body TYPE, differing only in "
              "row count.%s" % (YEL, len(indist), RST))
        for r in indist[:6]:
            print("      %-26s anon %s/%s rows · auth %s/%s rows"
                  % (r["relation"], r["anon"]["status"], r["anon"]["rows"],
                     r["auth"]["status"], r["auth"]["rows"]))

    print("\n  wrote %s" % os.path.relpath(REPORT, ROOT))
    if a.gate:
        if not all(c["ok"] for c in ctl.values()):
            print("  %sFAIL%s a non-vacuity control failed" % (RED, RST))
            return 1
        if shape_bad or agree_bad:
            print("  %sFAIL%s %d envelope defect(s), %d status/body disagreement(s)"
                  % (RED, RST, len(shape_bad), len(agree_bad)))
            return 1
        if KNOWN_EDGE_FINDINGS:
            print("  %sFAIL%s %d declared edge finding(s) still stand: %s"
                  % (RED, RST, len(KNOWN_EDGE_FINDINGS),
                     "; ".join(k["function"] for k in KNOWN_EDGE_FINDINGS)))
            return 1
        if ungated:
            print("  %sFAIL%s %d page(s) read a relation whose refusal is indistinguishable from "
                  "absence and carry NO session gate, no anon-by-design rationale and no auth "
                  "settling: %s" % (RED, RST, len(ungated), ", ".join(ungated)))
            return 1
        print("  %sPASS%s the envelope and the status agree with the body on all %d relation(s). "
              "%d relation(s) cannot distinguish refusal from absence - PostgREST+RLS by construction - "
              "and every page that reads them answers it: %s."
              % (GREEN, RST, len(results), len(indist),
                 "; ".join("%s x%d" % (m, n) for m, n in
                           collections.Counter(g["mechanism"] for g in gates.values()).most_common())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
