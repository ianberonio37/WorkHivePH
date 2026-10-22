#!/usr/bin/env python3
"""operator_console_inventory.py - the MEASURED population for the OPERATOR CONSOLE wave (OPC), 2026-10-14.

Ian, 2026-10-14: the founder / admin / developer surfaces are scattered - a retired founder console whose panels
moved to Grafana, a retired marketplace admin, Platform Actions, two observability dashboards, a validator catalog,
the audit log, AI quality, a status page, six Grafana dashboards, GlitchTip and the gate board - and he runs the
platform from all of them. DECIDED (in the plan, approved in direction): un-retire `founder-console.html` as the ONE
console, a Developer tab inside it, Grafana as live numbers in-page plus a link per dashboard. Persona: `oversight`.

THE NUMBER IS DERIVED, NEVER TYPED. One cell per panel or queue a founder actually reads or acts on:
  page cells     every <h2>/<h3> heading on the 12 surfaces that names a panel (not a state line, an empty state, a
                 gate sentence or a template expression), deduplicated within the page
  grafana cells  every non-row panel of every provisioned dashboard (infra/mcp/grafana/provisioning/dashboards)
  two feeds      the GlitchTip issues feed and the gate board (platform_health.json)
then two deductions, measured:
  exact          the same panel on two surfaces (titles equal after normalisation) is ONE console cell
  near           a founder-console panel whose title contains, or is contained in, a Grafana panel's title IS that
                 Grafana panel - it lands once, as the live number

    python tools/operator_console_inventory.py            # the human report
    python tools/operator_console_inventory.py --json     # the machine population (what the seeder reads)
    python tools/operator_console_inventory.py --self-test
"""
from __future__ import annotations

import argparse
import glob
import html
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

CONSOLE = "founder-console.html"
GRAFANA = ROOT / "infra" / "mcp" / "grafana" / "provisioning" / "dashboards"
# the 12 scattered surfaces, in the order measured on 2026-10-14 (the first surface to show a panel keeps it)
SURFACES = ("founder-console.html", "marketplace-admin.html", "platform-actions.html", "audit-log.html",
            "ai-quality.html", "llm-observability.html", "agentic-rag-observability.html",
            "design-system.html", "status.html")
FEEDS = (("glitchtip", "Open errors (GlitchTip issues)"), ("board", "Gate board (platform_health.json)"))
# "Where these figures come from" is the Sources area every page carries at its foot (ENH-R, 2026-10-19): a page's
# provenance, not a panel a founder reads or acts on - it had become a phantom cell on eight surfaces at once. "Agentic
# RAG Observability is hive-scoped." is the gate sentence a hive-less visitor reads on that page, not a panel either.
NOT_PANEL = re.compile(r"^(Could not|No .* yet|Reports need|Join a hive|Supervisors only|Platform Admins Only|"
                       r"Supervisor access only|Vehicle created|Add a Vehicle|Where these figures come from|.+ is hive-scoped\.?$|\d+\. )", re.I)
# the "all hives" filter a dashboard variable adds; with the default every row passes it, so it does not make two
# queries different
HIVE_FILTER = re.compile(r"\s+and\s+\(?\s*hive_id::text\s+like\s+'\$hive'(\s+or\s+hive_id\s+is\s+null)?\s*\)?", re.I)


def query_sig(panel: dict) -> str:
    """what a Grafana panel computes: its datasource and its SQL, whitespace and the all-hives filter folded away"""
    ds = (panel.get("datasource") or {}).get("uid", "") if isinstance(panel.get("datasource"), dict) else ""
    sql = " ".join((t.get("rawSql") or "") for t in (panel.get("targets") or []))
    sql = re.sub(r"\s+", " ", HIVE_FILTER.sub("", sql)).strip().lower()
    return f"{ds}|{sql}" if sql else ""
HEAD = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)
STOP = frozenset(("the", "a", "of", "by", "and", "vs", "per", "top", "10", "5", "last", "days", "day", "24h", "7d",
                  "30d", "is", "it", "who", "s", "using", "platform"))


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def key(title: str) -> str:
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]+", " ", title.lower()).split() if w not in STOP)


def headings(src: str) -> list[str]:
    heads = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip() for h in HEAD.findall(src)]
    heads = [h for h in heads if h and not h.startswith("${") and not NOT_PANEL.match(h)
             and "+ e(" not in h and "' +" not in h]
    return list(dict.fromkeys(heads))


def raw_cells(sources: dict | None = None, dashboards: list | None = None) -> list[tuple[str, str, str]]:
    """(surface, title, what it computes) - the third is a Grafana panel's query_sig, empty for a page heading"""
    cells = []
    for p in SURFACES:
        src = sources.get(p, "") if sources is not None else (
            (ROOT / p).read_text(encoding="utf-8", errors="replace") if (ROOT / p).exists() else "")
        cells += [(p, h, "") for h in headings(src)]
    if dashboards is None:
        dashboards = []
        for f in sorted(glob.glob(str(GRAFANA / "*.json"))):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            dashboards.append(d.get("dashboard", d))
    for d in dashboards:
        for pnl in d.get("panels", []):
            if pnl.get("type") != "row":
                cells.append((f"grafana:{d.get('uid')}", pnl.get("title") or "?", query_sig(pnl)))
    cells += [(s, t, "") for s, t in FEEDS]
    return cells


def collect(sources: dict | None = None, dashboards: list | None = None) -> list[dict]:
    """The console's cells after both deductions, in measured order; each carries what it absorbed.

    ★A SHARED TITLE IS NOT A SHARED NUMBER (OPC build, 2026-10-22). Two Grafana panels titled "Events (24h)" were one
    cell, and one counts the platform's usage events while the other counts GlitchTip's error events; "New hives (7d)"
    and "New hives (30d)" folded into one because the window is a stop word. The console draws a cell once, so a false
    fold hides a real number. Two Grafana panels are one cell only when they compute the same thing (query_sig)."""
    cells = raw_cells(sources, dashboards)
    seen: dict[str, int] = {}
    kept: list[dict] = []
    for sfc, title, sig in cells:
        k = key(title)
        if k in seen and kept[seen[k]]["surface"] != sfc:
            first = kept[seen[k]]
            if not (sig and first["sig"] and sig != first["sig"]):
                first["also_on"].append(f"{sfc} :: {title}")          # exact: the same panel, another surface
                continue
        if k not in seen:
            seen[k] = len(kept)
        kept.append({"surface": sfc, "panel": title, "key": k, "sig": sig, "also_on": [], "absorbed_by": ""})
    graf = [c for c in kept if c["surface"].startswith("grafana:")]
    out = []
    for c in kept:
        if c["surface"] == CONSOLE and c["key"]:
            twin = next((g for g in graf if g["key"] and g["key"] != c["key"]
                         and (c["key"] in g["key"] or g["key"] in c["key"])), None)
            if twin is not None:
                twin["also_on"].append(f"{CONSOLE} :: {c['panel']}")      # near: the console panel IS that panel
                continue
        out.append(c)
    for c in out:
        s = c["surface"]
        c["kind"] = ("grafana" if s.startswith("grafana:") else "feed" if s in dict(FEEDS) else
                     "developer" if s in ("llm-observability.html", "agentic-rag-observability.html",
                                          "design-system.html", "status.html") else "operations")
    collect.arithmetic = {"raw": len(cells), "exact": len(cells) - len(kept), "near": len(kept) - len(out)}
    return out


def self_test() -> int:
    sources = {
        "founder-console.html": "<h2>Listings awaiting review</h2><h3>Feature heatmap</h3><h2>No sellers yet</h2>"
                                "<h3>Hive maturity</h3>",
        "platform-actions.html": "<h2>Listings awaiting review</h2><h2>Refunds</h2>",
    }
    dashboards = [{"uid": "ops", "panels": [{"type": "row", "title": "Row"}, {"title": "Top surfaces (feature heatmap)"},
                                            {"title": "Errors (24h)"}]}]
    got = collect(sources, dashboards)
    a = collect.arithmetic
    titles = {c["panel"] for c in got}
    ok = (a == {"raw": 9, "exact": 1, "near": 1} and "Refunds" in titles and "Hive maturity" in titles
          and "Feature heatmap" not in titles and "No sellers yet" not in titles and len(got) == 7)
    # a shared title on two different queries is two cells; the same query, one with the all-hives filter, is one
    sql = lambda q: [{"rawSql": q}]   # noqa: E731
    ds = {"uid": "supabase_local"}
    twins = [{"uid": "home", "panels": [
                {"title": "Events (24h)", "datasource": ds, "targets": sql("select count(*) as value from analytics_events")},
                {"title": "Active workers (24h)", "datasource": ds, "targets": sql(
                    "select count(distinct w) as value from e where x and (hive_id::text like '$hive' or hive_id is null)")}]},
             {"uid": "errors", "panels": [
                {"title": "Events (24h)", "datasource": {"uid": "glitchtip_local"}, "targets": sql("select count(*) as value from issue_events")},
                {"title": "Active workers (24h)", "datasource": ds, "targets": sql("select count(distinct w) as value from e where x")}]}]
    got2 = collect({}, twins)
    ev = [c for c in got2 if c["panel"] == "Events (24h)"]
    aw = [c for c in got2 if c["panel"] == "Active workers (24h)"]
    ok2 = len(ev) == 2 and len(aw) == 1 and aw[0]["also_on"] == ["grafana:errors :: Active workers (24h)"]
    print(("PASS" if ok and ok2 else "FAIL") + f" operator-console inventory self-test - {a}, {len(got)} cells; "
          f"a shared title on two queries stays two cells ({len(ev)}), one query under two titles folds ({len(aw)})")
    return 0 if ok and ok2 else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    cells = collect()
    a = collect.arithmetic
    if args.json:
        print(json.dumps(cells, indent=1, ensure_ascii=False))
        return 0
    print("\nOPERATOR CONSOLE INVENTORY - one cell per panel or queue a founder reads or acts on")
    print("=" * 84)
    for s, n in Counter(c["surface"] for c in cells).most_common():
        print(f"  {s:<36} {n:>3}")
    print(f"  measured {a['raw']} - {a['exact']} same panel on two surfaces - {a['near']} console panels that are "
          f"Grafana panels = {len(cells)} console cells")
    print("  by kind: " + " · ".join(f"{k} {v}" for k, v in Counter(c["kind"] for c in cells).most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
