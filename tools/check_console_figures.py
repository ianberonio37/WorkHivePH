#!/usr/bin/env python3
"""check_console_figures.py - every figure the operator console showed, read again from the database (OPC, 2026-10-22).

The OPC walk (.tmp/slw/opc_walk.js, through the Playwright MCP) records what each marked panel of founder-console.html
drew at phone-390 and desktop-1280. This reads the same figures from the database the console reads them from - as the
same platform admin, through the same admin-only reads (console_read_<dashboard>, the founder_* rollups,
founder_dev_reads) and the files the console fetches - and compares, panel by panel:

  stat panels    the value, formatted the way the console formats it, must be in the chip (a counter that ticks between
                 the walk and this read - events, calls, active people - may move by 2 or 1 %, whichever is more)
  lists/tables   the first row's label must be in the panel, and the panel must not claim rows the database lacks
  other panels   drawn at both widths, words in it, no failure sentence

    python tools/check_console_figures.py            writes .tmp/slw/results/opc_figures.json and prints the verdicts
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / ".tmp" / "slw" / "results"
ADMIN = "leandromarquez@auth.workhiveph.com"
TICKING = re.compile(r"events|calls|active|workers|traced|errors|issues|connections|attempts|people|dau|mau|ratio", re.I)   # a cache-hit ratio moves with every query


def psql_json(sql: str):
    uid = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-At", "-c",
                          f"select id from auth.users where email = '{ADMIN}'"], capture_output=True, text=True).stdout.strip()
    script = ("begin;\nset local role authenticated;\n"
              f"select set_config('request.jwt.claims', '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true) is null;\n"
              f"select ({sql})::text;\nrollback;\n")
    r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-At"],
                       input=script, capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in r.stdout.splitlines() if l not in ("BEGIN", "SET", "ROLLBACK", "f", "t")]
    if r.returncode != 0 or not lines:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return json.loads(lines[-1])


def fmt(v, unit: str = "") -> str:
    """the console's opcFmt, for numbers"""
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        if unit == "decbytes":
            u, n, i = ["B", "kB", "MB", "GB", "TB"], float(v), 0
            while abs(n) >= 1000 and i < len(u) - 1:
                n /= 1000
                i += 1
            return (f"{n:.2f}" if n < 10 else f"{n:.1f}") + " " + u[i] if i else f"{int(v)} B"
        if unit == "percent":
            r = round(v * 10) / 10
            return (f"{r:.1f}".rstrip("0").rstrip(".") if r != int(r) else str(int(r))) + "%"
        if unit == "currencyUSD":
            return f"${v:.2f}"
        if unit == "ms":
            return f"{round(v):,} ms"
        if float(v).is_integer():
            return f"{int(v):,}"
        r = round(v * 100) / 100
        return f"{r:,}"
    return str(v)


def num(s: str):
    """the number a chip leads with: its text runs into the label ("36DB CONNECTIONS"), so read the leading figure"""
    m = re.match(r"\s*[$₱]?(-?\d[\d,]*(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def numbers(s: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", s or "")]


def close(shown: float, want: float, ticking: bool) -> bool:
    if shown == want:
        return True
    return ticking and abs(shown - want) <= max(2.0, 0.01 * abs(want))


def main() -> int:
    walks = {vp: json.loads((RES / f"opc_walk_{vp}.json").read_text(encoding="utf-8")) for vp in ("phone-390", "desktop-1280")}
    s = (ROOT / "operator-console-panels.js").read_text(encoding="utf-8")
    dashes = json.loads(s[s.index("=") + 1:].strip().rstrip(";"))
    reads, verdicts = {}, {}
    for d in dashes:
        if d.get("fn"):
            reads[d["uid"]] = psql_json(f"{d['fn']}(now() - interval '30 days', now(), null)")
    dev = psql_json("founder_dev_reads(now() - interval '30 days', now())")
    pareto, maturity = psql_json("founder_hive_pareto(30)"), psql_json("founder_maturity()")
    pulse, ai7 = psql_json("founder_marketplace_pulse()"), psql_json("founder_ai_cost(now() - interval '7 days', now())")

    def seen(mark):
        return {vp: walks[vp]["marks"].get(mark) for vp in walks}

    def base(mark):
        per = seen(mark)
        probs = [f"{vp}: not drawn" for vp, m in per.items() if not m or not m.get("drawn")]
        probs += [f"{vp}: says '{m['note']}'" for vp, m in per.items() if m and m.get("note")]
        probs += [f"{vp}: no words" for vp, m in per.items() if m and m.get("drawn") and m.get("chars", 0) < 8]
        return per, probs

    for d in dashes:
        data = reads.get(d["uid"], {})
        if data.get("connected") is False:
            continue
        for p in d["panels"]:
            if p.get("home"):
                continue
            mark = p["opc"]
            per, probs = base(mark)
            v = data.get(p["key"])
            db_said = None
            if isinstance(v, dict) and v.get("error"):
                probs.append(f"the database read failed: {v['error'][:120]}")
            elif p["type"] == "stat":
                val = v[0].get(next(iter(v[0]))) if isinstance(v, list) and v else v
                want, db_said = fmt(val, p["unit"]), val
                for vp, m in per.items():
                    if not m:
                        continue
                    if want.lower() in m["text"].lower():
                        continue
                    shown = num(m.get("text") or "")
                    if not (isinstance(val, (int, float)) and shown is not None and close(shown, float(val), bool(TICKING.search(p["title"])))):
                        probs.append(f"{vp}: shows '{m['text'][:60]}', the database says {want}")
            else:
                rows = v if isinstance(v, list) else []
                db_said = f"{len(rows)} row(s)"
                if rows:
                    lab = next((str(x) for x in rows[0].values() if isinstance(x, str) and not re.match(r"\d{4}-\d{2}-\d{2}T", x)), None)
                    for vp, m in per.items():
                        if m and lab and lab[:20].lower() not in m["text"].lower():
                            probs.append(f"{vp}: the first row '{lab[:40]}' is not in the panel")
                else:
                    for vp, m in per.items():
                        if m and "No rows" not in m["text"]:
                            probs.append(f"{vp}: the database has no rows and the panel does not say so")
            verdicts[mark] = {"ok": not probs, "problems": probs, "database": db_said,
                              "shown": {vp: (m or {}).get("text", "")[:160] for vp, m in per.items()}}

    def own(mark, want_texts, db_said):
        """a word must be in the panel (innerText carries CSS text-transform, so case is not compared); a number must
        be there within the counter tolerance, because page views and calls tick between the walk and this read"""
        per, probs = base(mark)
        for vp, m in per.items():
            for w in want_texts:
                if not m or w is None or w == "":
                    continue
                if isinstance(w, (int, float)):
                    if not any(close(n, float(w), True) for n in numbers(m["text"])):
                        probs.append(f"{vp}: {w} is not in the panel")
                elif str(w).lower() not in m["text"].lower():
                    probs.append(f"{vp}: '{w}' is not in the panel")
        verdicts[mark] = {"ok": not probs, "problems": probs, "database": db_said,
                          "shown": {vp: (m or {}).get("text", "")[:160] for vp, m in per.items()}}

    top = (pareto.get("top") or [{}])[0]
    own("founder-console.html::top-10-hives-by-activity", [top.get("hive_name"), top.get("events")],
        f"busiest hive {top.get('hive_name')} {top.get('events')} page views, {pareto.get('n_hives')} hives")
    low = (maturity.get("bottom") or [{}])[0]
    own("founder-console.html::bottom-5-needing-intervention", [low.get("hive_name"), f"{maturity.get('total')} hives"],
        f"{maturity.get('total')} hives, lowest {low.get('hive_name')} {low.get('score')}/100")
    own("founder-console.html::marketplace-pulse", [pulse.get("published")], f"{pulse.get('published')} published")
    own("founder-console.html::ai-cost-detail", [ai7.get("n_calls"), "none with a cost recorded" if ai7.get("total") is None else None],
        f"{ai7.get('n_calls')} calls in 7 days, total {ai7.get('total')}")
    own("founder-console.html::top-spending-hives", [], f"{len(ai7.get('top_hives') or [])} hive(s) with a recorded cost")
    r0 = (dev.get("per_task_routing") or [{}])[0]
    own("llm-observability.html::per-task-routing", [r0.get("fn"), f"{r0.get('calls', 0):,}"], f"busiest task {r0.get('fn')} {r0.get('calls')} calls")
    b0 = (dev.get("per_hive_budget") or [{}])[0]
    own("llm-observability.html::per-hive-budget-burn", [b0.get("hive_name"), f"{b0.get('calls_today')} of {dev.get('limit_per_day')}"],
        f"{b0.get('hive_name')}: {b0.get('calls_today')} of {dev.get('limit_per_day')} today")
    rr = (dev.get("rag_routes") or [{}])[0]
    own("agentic-rag-observability.html::route-breakdown", [rr.get("route")], f"top route {rr.get('route')} {rr.get('runs')} runs")
    own("agentic-rag-observability.html::top-10-most-token-heavy-queries", [], f"{len(dev.get('rag_heavy') or [])} traces")
    own("agentic-rag-observability.html::recent-traces", [], f"{len(dev.get('rag_recent') or [])} traces")
    health = json.loads((ROOT / "platform_health.json").read_text(encoding="utf-8"))
    sm = health.get("summary") or {}
    own("founder-console.html::tech-health", [str(sm.get("pass")), str(sm.get("fail"))], f"{sm.get('pass')} pass · {sm.get('fail')} fail")
    own("board::gate-board-platform-health-json", [str(sm.get("pass"))], f"the board's own file: {sm.get('pass')} pass")
    for mark in ("founder-console.html::is-the-platform-alive", "founder-console.html::who-s-using-it", "founder-console.html::growth-pulse",
                 "founder-console.html::money-flow", "founder-console.html::memento-memory-cache", "founder-console.html::companion-eval-phase-8",
                 "founder-console.html::what-the-builder-watches", "design-system.html::centralization-axes-measured-live",
                 "status.html::slo-targets-28-day-window"):
        own(mark, [], "drawn from the console's own reads and files")
    for mark in ("glitchtip::open-errors-glitchtip-issues", "llm-observability.html::total-calls", "llm-observability.html::cache-hit-rate",
                 "llm-observability.html::fallback-rate", "llm-observability.html::tokens-used", "llm-observability.html::p50-latency",
                 "llm-observability.html::error-rate", "agentic-rag-observability.html::observability-metrics",
                 "ai-quality.html::worker-feedback", "ai-quality.html::per-function-spend"):
        if mark not in verdicts:
            own(mark, [], "the panel it lives in, checked above")

    # ── Operations: Platform Actions' queues on the console (OPC, 2026-10-22), read as the same admin from the views the
    # queue code (operator-actions.js) reads, in its own order - each count badge, and the row the queue puts first ──
    ops = psql_json("""jsonb_build_object(
      'topups', (select count(*) from v_service_credit_topups_truth where status = 'pending_verification'),
      'topup_first', (select gcash_ref from v_service_credit_topups_truth where status = 'pending_verification' order by created_at, id limit 1),
      'receipts', (select count(*) from v_gcash_receipts_needing_eyes),
      'receipt_first', (select reference from v_gcash_receipts_needing_eyes limit 1),
      'drafts', (select count(*) from v_marketplace_listings_truth where status = 'draft'),
      'draft_first', (select title from v_marketplace_listings_truth where status = 'draft' order by created_at, id limit 1),
      'sellers', (select count(*) from v_marketplace_sellers_truth
                  where kyb_verified = false or (cert_verified = false and coalesce(certifications, '') <> '')),
      'seller_first', (select worker_name from v_marketplace_sellers_truth
                       where kyb_verified = false or (cert_verified = false and coalesce(certifications, '') <> '')
                       order by created_at desc, id limit 1),
      'waiting', (select count(*) from (select status from platform_feedback order by created_at desc, id limit 500) f
                  where status in ('new', 'triaged', 'in_progress')),
      'decision_first', (select target_name from platform_audit_log order by created_at desc, id limit 1),
      'issued', (select issued_credits from v_credit_posture limit 1),
      'authorised', (select authorised_credits from v_credit_posture limit 1))""")
    feed = psql_json("founder_audit_feed(50)") or []
    a0 = feed[0] if feed else {}
    a0_target = a0.get("target_name") if a0.get("target_name") and not re.match(r"^[0-9a-f]{8}-", str(a0.get("target_name"))) \
        and str(a0.get("target_name")).lower() != str(a0.get("actor") or "").lower() else None
    ai30 = psql_json("founder_ai_cost(now() - interval '30 days', now())")
    uses = psql_json("coalesce((select jsonb_agg(to_jsonb(u)) from founder_feature_use(30) u), '[]'::jsonb)") or []
    cap = lambda n: (str(n) if (n or 0) <= 50 else "50+")   # the queues read 50 and say "50+" past it
    badges = {vp: (walks[vp].get("queueCounts") or {}) for vp in walks}

    def queue(mark, badge, want, first, db_said):
        """a queue: its count badge (read by id in the walk) must be exactly the database's count, and the row the
        queue puts first must be in the card"""
        per, probs = base(mark)
        for vp, m in per.items():
            got = badges[vp].get(badge)
            if got is None:
                probs.append(f"{vp}: the #{badge} badge was not read")
            elif str(got).strip() != str(want):
                probs.append(f"{vp}: #{badge} shows '{got}', the database says {want}")
            if m and first and str(first).lower()[:40] not in m["text"].lower():
                probs.append(f"{vp}: the first row '{str(first)[:40]}' is not in the card")
        verdicts[mark] = {"ok": not probs, "problems": probs, "database": db_said,
                          "shown": {vp: (m or {}).get("text", "")[:160] for vp, m in per.items()}}

    issued, authorised = ops.get("issued"), ops.get("authorised")
    credit = [fmt(issued), fmt(authorised), fmt((authorised or 0) - (issued or 0))] if issued is not None else []
    for mark in ("founder-console.html::credit-economy-health", "platform-actions.html::credit-position"):
        own(mark, credit, f"issued {issued}, authorised {authorised} (v_credit_posture)")
    queue("founder-console.html::gcash-top-ups-awaiting-verification", "svc-topups-count", cap(ops.get("topups")),
          ops.get("topup_first"), f"{ops.get('topups')} waiting, oldest ref {ops.get('topup_first')}")
    queue("platform-actions.html::gcash-receipts-needing-your-eyes", "gcash-receipts-count", str(ops.get("receipts")),
          ops.get("receipt_first"), f"{ops.get('receipts')} needing eyes, newest ref {ops.get('receipt_first')}")
    for mark in ("founder-console.html::listings-awaiting-review", "marketplace-admin.html::listings-queue"):
        queue(mark, "mkt-listings-count", cap(ops.get("drafts")), ops.get("draft_first"),
              f"{ops.get('drafts')} drafts, oldest '{ops.get('draft_first')}'")
    queue("founder-console.html::sellers-awaiting-verification", "mkt-sellers-count", cap(ops.get("sellers")),
          ops.get("seller_first"), f"{ops.get('sellers')} sellers with something to verify, newest {ops.get('seller_first')}")
    for mark in ("founder-console.html::feedback-inbox", "platform-actions.html::feedback-from-users"):
        queue(mark, "fb-count-badge", str(ops.get("waiting")), None, f"{ops.get('waiting')} waiting among the latest 500")
    own("platform-actions.html::recent-decisions", [ops.get("decision_first")], f"newest decision on {ops.get('decision_first')}")
    for mark in ("founder-console.html::recent-admin-activity", "audit-log.html::activity"):
        own(mark, ["every hive", a0_target], f"{len(feed)} events, newest on {a0_target or 'an id or the actor'}")
    own("ai-quality.html::estimated-30-day-roi", [ai30.get("n_calls")], f"{ai30.get('n_calls')} AI calls in 30 days")
    u0 = uses[0] if uses else {}
    own("platform-actions.html::platform-usage", ["What people used each page for", u0.get("page")],
        f"{len(uses)} page uses, busiest {u0.get('page')} · {u0.get('action')}")
    own("founder-console.html::feedback-detail", [], "the first feedback item, opened in its drawer")
    for mark in ("founder-console.html::money-and-moderation", "founder-console.html::user-feel"):
        own(mark, [], "the section the queues above sit in")
    own("founder-console.html::founder-tools", ["Gateway status"], "the tools that are not retired")
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "opc_figures.json").write_text(json.dumps({"generated_from": {vp: w["generated"] for vp, w in walks.items()},
                                                      "verdicts": verdicts}, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = {k: v for k, v in verdicts.items() if not v["ok"]}
    print(f"{len(verdicts) - len(bad)} of {len(verdicts)} panels agree with the database")
    for k, v in bad.items():
        print(f"  DISAGREE {k}: " + "; ".join(v["problems"])[:300])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
