#!/usr/bin/env python3
"""
resolve_display_anchors.py  --  Phase B of the INTERACTIVE_LINEAGE_ROADMAP.

Answers Ian's Q2: "where is this display anchored?" -- for each on-screen value,
resolve the UPSTREAM chain  tile(anchor) <- formula(view/RPC) <- source columns <- standard.

Reuse-first, composes existing artifacts (no new page parsing in this slice):
  - displayed_values_report.json : the 106 display anchors / 31 pages, bucketed
                                   contracted / raw / unknown   [tools/audit_displayed_values.py]
  - canonical/formula_contracts.json : formula_id -> {inputs[], implemented_in, standard_cite}
  - kpi_source_registry.json     : metric -> official source view.column (5 hottest)

Coverage is HONEST and measured:
  * CONTRACTED anchors  -> fully resolved (formula -> inputs -> standard).
  * RAW / UNKNOWN anchors -> heuristic link to a kpi_source metric by token if possible,
                             else marked NEEDS_JS_PARSE (Phase B.2 resolves these by
                             parsing which query populates the element id).

Outputs: display_anchor_sources.json + display_anchor_sources.md
Run:     python tools/resolve_display_anchors.py
"""
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DV = os.path.join(ROOT, "displayed_values_report.json")
FC = os.path.join(ROOT, "canonical", "formula_contracts.json")
KPI = os.path.join(ROOT, "kpi_source_registry.json")
VERIFIED = os.path.join(ROOT, "verified_anchor_binds.json")
OUT_JSON = os.path.join(ROOT, "display_anchor_sources.json")
OUT_MD = os.path.join(ROOT, "display_anchor_sources.md")


def load_verified():
    """Phase B.2 (2026-06-29): evidence-bound, adversarially-verified element-id -> source
    binds + UI-chrome exclusions, produced by the lineage-anchor-resolve workflow (each bind
    was confirmed by READING the render site, not token/nearest-.from() guessed). This is the
    data-driven hardening of the heuristic resolver: a VERIFIED bind overrides the heuristic
    (it's ground truth); a CHROME anchor (a label/counter/toggle/verdict/connection control
    with no data source) is EXCLUDED from the data denominator (no provenance to bind), so the
    resolved-% is honest (data displays only), never inflated by chrome the heuristic mis-bound.
    Shape: {"binds": {"<page>|<id>": {reads, reads_kind, what, rung, standard}},
            "chrome": ["<page>|<id>", ...]}."""
    binds, chrome = {}, set()
    if os.path.exists(VERIFIED):
        try:
            v = json.load(open(VERIFIED, encoding="utf-8"))
            binds = {tuple(k.split("|", 1)): val for k, val in v.get("binds", {}).items()}
            chrome = {tuple(x.split("|", 1)) for x in v.get("chrome", [])}
        except Exception:
            pass
    return binds, chrome


_PAGE_CACHE = {}


def _page_lines(page):
    if page not in _PAGE_CACHE:
        p = os.path.join(ROOT, page)
        try:
            _PAGE_CACHE[page] = open(p, encoding="utf-8").read().split("\n")
        except Exception:
            _PAGE_CACHE[page] = None
    return _PAGE_CACHE[page]


_SRC_RE = re.compile(r"""\.from\(\s*['"]([\w]+)['"]|\.rpc\(\s*['"]([\w]+)['"]|functions\.invoke\(\s*['"]([\w-]+)['"]""")


def js_resolve(page, anchor_id):
    """Phase B.2 heuristic: bind an element-id to the nearest data source (table/rpc/edge-fn)
    in the function that assigns its textContent/innerHTML. Approximate, labelled heuristic."""
    lines = _page_lines(page)
    if not lines:
        return None
    aid = re.escape(anchor_id)
    # 1) var that holds the element, OR direct getElementById(...).textContent= sites
    var = None
    for ln in lines:
        m = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*document\.getElementById\(\s*['\"]" + aid + r"['\"]\s*\)", ln)
        if m:
            var = m.group(1)
            break
    # 2) assignment line indices
    assign_idx = []
    for i, ln in enumerate(lines):
        if var and re.search(r"\b" + re.escape(var) + r"\.(?:textContent|innerHTML|innerText)\s*=", ln):
            assign_idx.append(i)
        elif re.search(r"getElementById\(\s*['\"]" + aid + r"['\"]\s*\)\.(?:textContent|innerHTML|innerText)\s*=", ln):
            assign_idx.append(i)
    if not assign_idx:
        return None
    # 3) nearest data source within a window around the FIRST assignment
    best = None
    best_dist = 10 ** 9
    for ai in assign_idx:
        for j in range(max(0, ai - 90), min(len(lines), ai + 30)):
            m = _SRC_RE.search(lines[j])
            if m:
                src = m.group(1) or m.group(2) or m.group(3)
                kind = "table/view" if m.group(1) else ("rpc" if m.group(2) else "edge_fn")
                d = abs(j - ai)
                if d < best_dist:
                    best, best_dist, best_kind = src, d, kind
    if best is None:
        return None
    return {"via": "js_parse_heuristic", "source": best, "source_kind": best_kind,
            "confidence": "high" if best_dist <= 25 else "medium"}


# ── Phase B.2 confidence gate (2026-06-29) ──────────────────────────────────
# The upstream displayed_values report attaches formula_ids by loose token match,
# which produced confidently-WRONG resolutions (an asset COUNT card -> "Pump Total
# Dynamic Head" on the shared word "total"; a "risk" tile -> BOTH adoption + asset
# risk formulas; logbook quality% -> MARKETPLACE seller quality). Counting those as
# RESOLVED inflates coverage with falsehoods. A formula match is accepted as RESOLVED
# only when it is TRUSTWORTHY: a single unambiguous formula sharing a SPECIFIC token
# with the anchor (strong-alone, or a non-generic token WITH page-domain agreement).
# Untrustworthy matches fall through to the JS-heuristic / NEEDS_JS_PARSE path —
# honest "not yet resolved", not a fake resolution. (Same rule as
# build_display_provenance.is_trustworthy; the E3 worklist tracks the residual.)
_GENERIC_TOKENS = {"total", "count", "num", "value", "label", "bar", "stat", "card",
                   "pct", "strip", "verdict", "the", "of", "id", "row", "list", "item",
                   "panel", "score", "days", "tier", "level"}
_STRONG_ALONE = {"risk", "health", "anomaly", "exam", "adoption", "mtbf", "mttr",
                 "weibull", "downtime", "compliance"}
_DOMAIN_WORDS = {"marketplace", "inventory", "logbook", "pm", "skill", "asset", "hive",
                 "community", "platform", "adoption", "dayplanner", "predictive",
                 "analytics", "seller", "pump"}


def _toks(s):
    return set(t for t in re.split(r"[^a-z0-9]+", str(s or "").lower()) if t)


def formula_match_trustworthy(aid, chain, page):
    names = {h.get("name") or h.get("formula_id") for h in chain if (h.get("name") or h.get("formula_id"))}
    if len(names) != 1:
        return False  # ambiguous multi-formula match
    name = next(iter(names))
    idt = _toks(aid)
    shared = idt & _toks(name)
    if shared & _STRONG_ALONE:
        return True
    specific = shared - _GENERIC_TOKENS
    if not specific:
        return False  # only generic-token overlap = loose/false match
    formula_domains = _toks(name) & _DOMAIN_WORDS
    if formula_domains and not (formula_domains & (_toks(page) | idt)):
        return False  # cross-domain bleed
    return True


def main():
    dv = json.load(open(DV, encoding="utf-8"))
    fc = {f["formula_id"]: f for f in json.load(open(FC, encoding="utf-8"))["formulas"]}
    kpi = json.load(open(KPI, encoding="utf-8")).get("metrics", {})
    verified_binds, chrome_set = load_verified()

    # token -> kpi metric (for heuristic raw-anchor linking)
    token_to_metric = {}
    for metric, meta in kpi.items():
        token_to_metric[metric] = metric
        # also index by a few obvious substrings
        for tok in metric.split("_"):
            token_to_metric.setdefault(tok, metric)

    anchors = []
    by_page = dv.get("by_page", {})
    for page, buckets in by_page.items():
        if not isinstance(buckets, dict):
            continue
        for bucket, items in buckets.items():
            if not isinstance(items, list):
                continue
            for a in items:
                if isinstance(a, str):
                    a = {"id": a, "token": "", "formula_ids": []}
                elif not isinstance(a, dict):
                    continue
                aid = a.get("id")
                token = a.get("token", "")
                fids = sorted(set(a.get("formula_ids", []) or []))
                resolved = None
                status = None
                key = (page, aid)
                # Phase B.2 verified layer takes PRECEDENCE over every heuristic: a
                # CHROME anchor is excluded (no data provenance), a VERIFIED bind is
                # ground truth (Read-confirmed element-id -> source). Both override the
                # loose formula/kpi/nearest-.from() resolution below.
                if key in chrome_set:
                    status = "EXCLUDED_CHROME"
                    resolved = {"via": "ui_chrome"}
                elif key in verified_binds:
                    vb = verified_binds[key]
                    rk = vb.get("reads_kind")
                    reads = vb.get("reads")
                    resolved = {"via": "verified_bind", "reads": reads, "rung": vb.get("rung"),
                                "chain": [{"name": vb.get("what") or aid,
                                           "reads": reads,
                                           "view": reads if rk == "view" else None,
                                           "table": reads if rk == "table" else None,
                                           "rpc": reads if rk in ("rpc", "edge_fn") else None,
                                           "standard_cite": vb.get("standard") or None,
                                           "unit": vb.get("unit")}]}
                    status = "RESOLVED_VERIFIED"
                if status is None and fids:
                    chain = []
                    for fid in fids:
                        f = fc.get(fid)
                        if f:
                            chain.append({
                                "formula_id": fid,
                                "name": f.get("name"),
                                "implemented_in": f.get("implemented_in"),
                                "inputs": f.get("inputs", []),
                                "standard_cite": f.get("standard_cite"),
                                "unit": f.get("unit"),
                            })
                    # B.2 confidence gate: accept a formula match as RESOLVED only when
                    # it is trustworthy (single unambiguous formula + specific shared token
                    # + page-domain agreement). Loose/ambiguous/cross-domain token matches
                    # fall through to the JS-heuristic / NEEDS_JS_PARSE path below — an
                    # honest "not yet resolved" instead of a confidently-wrong resolution.
                    if chain and formula_match_trustworthy(aid, chain, page):
                        resolved = {"via": "formula_contract", "chain": chain}
                        status = "RESOLVED"
                if status is None and not resolved:
                    # heuristic: token matches a kpi_source metric?
                    metric = token_to_metric.get(token)
                    if metric:
                        meta = kpi[metric]
                        resolved = {"via": "kpi_source_registry",
                                    "metric": metric,
                                    "source": meta.get("allowed_sources"),
                                    "signal": meta.get("required_signal")}
                        status = "RESOLVED_KPI"
                    else:
                        # Phase B.2: heuristic JS-parse binding to the nearest data source
                        jr = js_resolve(page, aid) if aid else None
                        if jr:
                            resolved = jr
                            status = "RESOLVED_JS"
                        elif bucket == "raw":
                            status = "RAW_NEEDS_JS_PARSE"
                        else:
                            status = "NEEDS_JS_PARSE"
                anchors.append({
                    "page": page,
                    "id": aid,
                    "token": token,
                    "bucket": bucket,
                    "status": status,
                    "source": resolved,
                })

    RESOLVED_STATUSES = ("RESOLVED", "RESOLVED_KPI", "RESOLVED_JS", "RESOLVED_VERIFIED")
    total = len(anchors)
    chrome_n = sum(1 for a in anchors if a["status"] == "EXCLUDED_CHROME")
    data_anchors = total - chrome_n  # honest denominator: UI chrome has no data provenance
    resolved_n = sum(1 for a in anchors if a["status"] in RESOLVED_STATUSES)
    js_n = sum(1 for a in anchors if a["status"] == "RESOLVED_JS")
    verified_n = sum(1 for a in anchors if a["status"] == "RESOLVED_VERIFIED")
    needs_parse = [a for a in anchors if a["status"] in ("RAW_NEEDS_JS_PARSE", "NEEDS_JS_PARSE")]
    per_page = defaultdict(lambda: {"anchors": 0, "resolved": 0})
    for a in anchors:
        per_page[a["page"]]["anchors"] += 1
        if a["status"] in RESOLVED_STATUSES:
            per_page[a["page"]]["resolved"] += 1

    out = {
        "_doc": "Display anchor -> upstream source resolution (Phase B). RESOLVED* = anchor traces to a "
                "formula contract / kpi_source metric / Read-VERIFIED element-id->source bind "
                "(verified_anchor_binds.json). EXCLUDED_CHROME = a UI control/label/counter with no data "
                "provenance (excluded from the data denominator). NEEDS_JS_PARSE = data anchor not yet bound. "
                "resolved_pct is over DATA anchors (total - chrome) so it is honest, never chrome-inflated.",
        "totals": {
            "anchors": total,
            "chrome_excluded": chrome_n,
            "data_anchors": data_anchors,
            "resolved": resolved_n,
            "resolved_pct": round(100 * resolved_n / data_anchors, 1) if data_anchors else 0,
            "resolved_pct_of_all": round(100 * resolved_n / total, 1) if total else 0,
            "resolved_by_formula_or_kpi": resolved_n - js_n - verified_n,
            "resolved_by_js_heuristic": js_n,
            "resolved_by_verified_bind": verified_n,
            "needs_js_parse": len(needs_parse),
        },
        "anchors": anchors,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    lines = ["# Display Anchor Sources — Phase B (where is each display anchored?)\n"]
    lines.append(f"_Generated by `tools/resolve_display_anchors.py`._\n")
    lines.append(f"- Display anchors: **{total}**  ·  UI chrome excluded (no data provenance): **{chrome_n}**  "
                 f"·  data anchors (honest denominator): **{data_anchors}**")
    lines.append(f"- Resolved to source: **{resolved_n}** ({out['totals']['resolved_pct']}% of data anchors) "
                 f"— {resolved_n - js_n - verified_n} via formula/kpi contract, {verified_n} via Read-verified bind, "
                 f"{js_n} via JS-parse heuristic")
    lines.append(f"- Still unresolved data anchors: **{len(needs_parse)}**\n")
    lines.append("## Resolved anchors (anchor → source)\n")
    lines.append("| Page | Anchor | Source | Detail | Via |")
    lines.append("|---|---|---|---|---|")
    for a in anchors:
        if a["status"] not in RESOLVED_STATUSES:
            continue
        src = a["source"]
        via = src["via"]
        if via == "formula_contract":
            c = src["chain"][0]
            impl = (c.get("implemented_in") or "")[:48]
            detail = ", ".join(c.get("inputs", [])[:3])
        elif via == "kpi_source_registry":
            impl = ", ".join(src.get("source") or [])
            detail = src.get("signal") or ""
        elif via == "verified_bind":
            impl = f"{src.get('reads')}"
            c0 = (src.get("chain") or [{}])[0]
            detail = (c0.get("name") or "") + (f" · {c0.get('standard_cite')}" if c0.get("standard_cite") else "")
        else:  # js_parse_heuristic
            impl = f"{src.get('source')} ({src.get('source_kind')})"
            detail = f"confidence={src.get('confidence')}"
        lines.append(f"| {a['page']} | {a['id']} | {impl} | {detail} | {via} |")
    lines.append("\n## Per page resolution\n")
    lines.append("| Page | Anchors | Resolved |")
    lines.append("|---|---:|---:|")
    for p, v in sorted(per_page.items(), key=lambda kv: -kv[1]["anchors"]):
        if v["anchors"]:
            lines.append(f"| {p} | {v['anchors']} | {v['resolved']} |")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[resolve_display_anchors] {total} anchors ({chrome_n} chrome excluded -> {data_anchors} data) | "
          f"{resolved_n} resolved ({out['totals']['resolved_pct']}% of data) "
          f"[{resolved_n - js_n - verified_n} formula/kpi + {verified_n} verified + {js_n} js-parse] "
          f"| {len(needs_parse)} unresolved")
    print(f"  -> {os.path.relpath(OUT_JSON, ROOT)} , {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
