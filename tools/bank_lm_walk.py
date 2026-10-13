"""bank_lm_walk.py - bank ONE LLM-layer row (§LM) walked through the Playwright MCP by tools/lm_walk.js.

The receipt goes through tools/record_mcp_walk.py first (it refuses an LM receipt without the sub-layer, the persona,
steps at both viewports and a named local witness), and the registry is written ONLY when that receipt is accepted
and the walk's own verdict held. The witness names everything that settled the row without a model call:

  - the walk: what the page sent to its AI at 390 and 1280 (every model function answered by a stub), and the
    foreign-hive probes sent as the person (refusals) or why a function was settled statically instead;
  - the static AI gates, run by the caller for the batch and passed in with --gates-ok (their PASS lines);
  - the postgres-MCP read the caller made for the batch (--pg), e.g. that no briefing or AI row was written.

  python tools/bank_lm_walk.py LM4 --pg "<postgres-mcp witness>" --gates-ok "<gate PASS summary>"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GATES = {"X": ["ai_prompt_injection", "ai_retrieval_isolation", "edge-fn-auth-gate", "client_hive_is_proven"],
         "G": ["grounding_contract", "ai-render-provenance", "ai_retrieval_isolation"],
         "S": ["xss", "innerhtml-eschtml", "ai-render-provenance", "ai_answer_is_text"],
         "R": ["groq-fallback", "ai-chain-mirror", "global-ai-budget", "rate_limit_key_is_verified"],
         "P": ["ai_prompt_injection", "ai_retrieval_isolation", "client_hive_is_proven", "grounding_contract"],
         "A": ["ai_write_provenance", "ai-render-provenance", "approval_authority", "supervisor-approval-backstop"],
         "V": ["ai_write_provenance", "visual-defect", "visual_defect_confidence", "asr_confidence_gate",
               "voice-refuses-ambiguous-asset", "voice_router_oracle", "capture-contracts"],
         "L": ["waiting-is-spoken", "a-busy-button-says-working", "abort-timeout", "slow-hint-reads-only", "outage-copy-honesty"],
         "E": ["ai-eval-coverage", "ai-eval-regression", "companion-dim-gate", "fb4-grounding-eval", "ai-trust"],
         "O": ["ai-cost-observability", "edge-observed-coverage", "log-correlation", "grafana-reader-reads", "slo-rollup"]}
SUBNAME = {"X": "Safety, privacy & guardrails", "G": "Grounding & citations", "S": "Structure & schema",
           "R": "Routing, fallback & cost", "P": "Prompt & context", "A": "Agents & approval",
           "V": "Voice & vision", "L": "Latency & waiting", "E": "Evals & quality gates", "O": "Observability"}


def served_in_window(started: str, finished: str) -> tuple[list[str], int, int]:
    """The models that answered in [started, finished] and the tokens they reported, read from the edge runtime's
    own log (`[ai-chain] served by <provider> / <model> (tokens N)`, 2026-10-07). An outside witness: the walk cannot
    write this line, only the chain can."""
    import re as _re
    r = subprocess.run(["docker", "logs", "-t", "--since", started, "--until", finished, "supabase_edge_runtime_workhive"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    lines = [ln for ln in ((r.stdout or "") + (r.stderr or "")).splitlines() if "[ai-chain" in ln and "served by" in ln]
    models, tokens, unreported = [], 0, 0
    for ln in lines:
        m = _re.search(r"served by (\S+) / (\S+)(?: \(tokens (\w+)\))?", ln)
        if not m:
            continue
        models.append(f"{m.group(1)}/{m.group(2)}")
        if m.group(3) and m.group(3).isdigit():
            tokens += int(m.group(3))
        else:
            unreported += 1
    return models, tokens, unreported


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--pg", required=True, help="the postgres-MCP witness for this batch")
    ap.add_argument("--gates-ok", required=True, help="the static AI gates' PASS summary for this batch")
    a = ap.parse_args()
    rid = a.id
    steps = json.load(io.open(f".tmp/w4_steps/{rid}.json", encoding="utf-8"))
    recs = json.load(io.open(f".tmp/w4_steps/{rid}.records.json", encoding="utf-8"))
    res, P = recs.get("result") or {}, recs.get("args") or {}
    sub = P.get("sublayer")
    if sub not in GATES:
        print(f"{rid}: sub-layer {sub!r} has no banker rule yet"); return 2
    live = ""
    if sub in ("G", "R"):
        models, toks, unrep = served_in_window(res.get("started"), res.get("finished"))
        if not models:
            print(f"{rid}: NOT banked - no model served in the walk window (a {sub} row closes only on a live answer)"); return 1
        # every viewport's reading must be live: one model served at 390 does not make the 1280 cache reply live (LM177)
        rk = "ground" if sub == "G" else "route"
        cached = [s.get("viewport") for s in steps if (s.get(rk) or {}).get("servedFrom") == "adaptive_cache"]
        if cached:
            print(f"{rid}: NOT banked - {', '.join(cached)} was answered from the rate-limit cache, not a live model"); return 1
        from collections import Counter
        live = (", ".join(f"{m} x{n}" for m, n in Counter(models).items()) + f"; {toks} tokens"
                + (f" (+{unrep} call(s) whose provider reported no usage)" if unrep else "") + " - free tiers, $0")
    probes = next((s.get("probes") for s in steps if s.get("probes")), []) or []
    sent = [p for p in probes if p.get("sent")]
    static = [p for p in probes if not p.get("sent")]
    probe_txt = "; ".join(f"{p['fn']} {p.get('status', '')} {p.get('verdict')} ({(p.get('code') or '')[:60]})" for p in sent) \
        or "no function was safe to probe live"
    static_txt = "; ".join(f"{p['fn']}: {p.get('why', '')[:90]}" for p in static) or "none"
    vps = [s for s in steps if s.get("viewport")]
    page_txt = " | ".join(
        f"{s['viewport']}: landed {s.get('landed')} as {s.get('worker')} ({s.get('chars')} chars), asked "
        f"{'yes' if s.get('asked') else 'no'}, sent {len(s.get('captured') or [])} model request(s) "
        f"[{', '.join(s.get('injectionFields') or []) or 'none'}]" for s in vps)
    witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}): {page_txt}. Every model function was "
               f"answered 503 by a context stub that recorded what the page sent; the typed injection travelled only in "
               f"user fields and the page named only the person's own hive. Foreign hive {P.get('foreignHiveName')} asked "
               f"as the person: {probe_txt}. Settled statically: {static_txt}. AI gates: {a.gates_ok}. "
               f"postgres-mcp: {a.pg}")
    if sub == "G":
        gtxt = " | ".join(
            f"{s['viewport']} ({(s.get('ground') or {}).get('kind')}): asked \"{(s.get('ground') or {}).get('question')}\" -> "
            f"\"{((s.get('ground') or {}).get('answer') or '')[:220]}\" [cited from the record: "
            f"{', '.join((s.get('ground') or {}).get('factsFromRecord') or []) or 'n/a'}; says it has nothing: "
            f"{(s.get('ground') or {}).get('saysNothing')}; other plants' records: {', '.join((s.get('ground') or {}).get('leaked') or []) or 'none'}]"
            for s in vps)
        witness = (f"LIVE model, as {P.get('castName')} ({P.get('persona')}) through the page's own ask: {gtxt}. "
                   f"Served: {live}. AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "A":
        aps = [(s["viewport"], s.get("approval") or {}) for s in vps]
        if not all(a0 for _, a0 in aps):
            print(f"{rid}: NOT banked - a viewport has no approval reading"); return 1
        def _a(vp, a0):
            aw = a0.get("approveWrites") or []
            if a0.get("how") == "gated":
                g = a0.get("gate") or {}
                return (f"{vp}: the page is closed to this person by its own gate {g.get('sel')} (\"{str(g.get('text') or '')[:100]}\"); "
                        f"no proposal or approval is reachable behind it, so nothing was pressed")
            if a0.get("approvedVia"):
                tail = (f"then \"{a0.get('approvedVia')}\" was pressed"
                        + (f" and confirmed (\"{a0.get('confirmedVia')}\")" if a0.get('confirmedVia') else "")
                        + " and wrote "
                        + ("; ".join(f"{w['w']} (machine authorship {'yes' if w['prov'] else 'no'}, approver {'yes' if w['approver'] else 'no'})" for w in aw)
                           if aw else "nothing")
                        + (" - a stored AI item: its machine authorship is on the stored row (generated_by / model_version), so the approval adds the approver"
                           if str(a0.get('approvedVia') or '').endswith('(the stored AI item)') else ""))
            else:
                tail = "and no visible approve / save / publish control appeared after the AI answered (nothing here turns its answer into a record)"
            return (f"{vp}: the page's own AI ({a0.get('how')}) proposed; writes before approval: "
                    f"{', '.join(a0.get('proposeWrites') or []) or 'none'}; {tail}")
        witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}) every model call was answered with a "
                   f"realistic proposal and every table write and mutating RPC was held and recorded: "
                   + " | ".join(_a(v, a0) for v, a0 in aps) + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "P":
        # every agent the ask reached, per viewport (assistant.html: 'assistant', then its 'voice-journal' fallback)
        ctxs = [(s["viewport"], c) for s in vps for c in (s.get("contexts") or ([s["context"]] if s.get("context") else []))]
        if any(not (s.get("contexts") or s.get("context")) for s in vps):
            print(f"{rid}: NOT banked - a viewport has no context reading from the gateway echo"); return 1
        def _c(vp, c):
            # the receipt names only what was checked: the snapshot/history checks apply to the companion and assistant
            # agents; another agent builds its own context downstream (its line must not read "ABSENT" on a pass)
            snap = c.get('agent') in ('voice-journal', 'assistant')
            own = (f"{'own records' if c.get('solo') else 'hive snapshot'} {'present' if c.get('hasOwn') else 'ABSENT'}, "
                   f"its history {'present' if c.get('hasHistory') else 'absent'}") if snap else \
                  "builds its asset context downstream (snapshot and history not checked at the gateway)"
            return (f"{vp}: {c.get('agent')} context for \"{c.get('subject')}\" - {own}, sections "
                    f"{', '.join(c.get('sections') or []) or 'none'}, ~{c.get('estTokens')} tokens, question intact "
                    f"{c.get('askedIntact')}, other plants' markers: {', '.join(c.get('leaked') or []) or 'none'}")
        witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}) the page's own ask was answered 503 by a "
                   f"context stub, and the exact request it sent was replayed as the person to ai-gateway's local debug echo, "
                   f"which returns the context the answering agent would receive: " + " | ".join(_c(v, c) for v, c in ctxs)
                   + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "R":
        def _r(s):
            r, f = s.get("route") or {}, s.get("routeFail") or {}
            return (f"{s['viewport']}: asked \"{r.get('question')}\" -> answered by {r.get('fn')} in "
                    f"{round((r.get('ms') or 0) / 1000, 1)} s (\"{(r.get('answer') or '')[:120]}\"); then the model call failed "
                    f"({', '.join(f.get('reached') or []) or 'not reached'}) and the page said \"{'; '.join(f.get('said') or []) or 'nothing'}\", "
                    f"page-wide outage notice: {f.get('outageNotice') or 'none'}")
        witness = (f"LIVE model, as {P.get('castName')} ({P.get('persona')}) through the page's own ask: "
                   + " | ".join(_r(s) for s in vps) + f". Served: {live}. AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "S":
        # the three bad answers a model really gives, fed to the page's own render path by a context stub (200)
        def _v(x):
            bad = ", ".join(f"{k} x{n}" for k, n in (x.get("bad") or {}).items()) or "nothing new"
            return (f"{x.get('v')}: reached {x.get('reached')} request(s), markup ran {x.get('xss')}x, newly showed {bad}"
                    + (f", hostile text shown as text: {x.get('shown')}" if x.get("v") == "hostile" else ""))
        def _o(x):
            bad = ", ".join(f"{k} x{n}" for k, n in (x.get("bad") or {}).items()) or "nothing new"
            return (f"{x.get('v')}: reached {', '.join(sorted(set(x.get('own') or []))) or 'nothing'} via "
                    f"{x.get('how') or 'page load'}, markup ran {x.get('xss')}x, newly showed {bad}")
        stxt = " | ".join(f"{s['viewport']} companion: " + "; ".join(_v(x) for x in (s.get("variants") or []))
                          + (f" / page's own AI (companion removed): " + "; ".join(_o(x) for x in s["own"]) if s.get("own") else "")
                          for s in vps)
        reached = sum(int(x.get("reached") or 0) for s in vps for x in (s.get("variants") or []))
        if not reached:
            print(f"{rid}: NOT banked - no bad answer reached the page's render path (nothing was asked)"); return 1
        witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}) every model function was answered "
                   f"200 by a context stub with the answers a model really gets wrong - hostile (an <img onerror>, markdown, "
                   f"truncated JSON), missing (an empty data object), wrongtype (an object where text belongs): {stxt}. "
                   f"Foreign hive {P.get('foreignHiveName')}: {probe_txt}. AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "V":
        vs = [(s["viewport"], s.get("voice") or {}) for s in vps]
        if not all(v.get("flows") for _, v in vs):
            print(f"{rid}: NOT banked - a viewport has no voice reading"); return 1
        def _f(f):
            if not f.get("offered"):
                return f"{f.get('label')}: not offered ({f.get('why') or f.get('refused') or 'no entry point for this person'})"
            save = " > ".join(f.get("save") or []) or "no save control"
            wrote = "; ".join(f"{w.get('w')} (draft {'yes' if w.get('carries') else 'no'}, mark {w.get('prov')})" for w in (f.get("saved") or [])) or "nothing"
            fl = f.get("fail") or {}
            heard = str(f.get("heard") or f.get("image") or "")[:80]
            filled = f.get("filled") or f.get("text") or f.get("reply") or "-"
            if isinstance(filled, list):
                filled = ", ".join(str(x) for x in filled)
            kept = fl.get("kept") if fl.get("kept") is not None else "-"
            return (f"{f.get('label')}: heard/read \"{heard}\" -> {str(filled)[:120]}; before save: "
                    f"{', '.join(str(x) for x in (f.get('beforeSave') or [])) or 'nothing written'}; {save} wrote {wrote}"
                    + (f"; embed {', '.join(str(x) for x in f['embed'])}" if f.get("embed") else "")
                    + (f"; confirm refused: {str(f.get('refused'))[:90]}" if f.get("refused") else "")
                    + f"; on failure ({', '.join(fl.get('failed') or []) or 'not reached'}) it said "
                    f"\"{'; '.join(fl.get('said') or []) or 'nothing'}\" and kept the person's entry: {kept}")
        witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}) the page's own mic (a synthetic "
                   f"MediaStream / a scripted speech recogniser) and photo input (tools/fixtures/lm_v) were used; every voice "
                   f"and vision function answered with a stub shaped like its own response, then 503 for the failure pass; "
                   f"every write was held: " + " | ".join(f"{vp}: " + " / ".join(_f(f) for f in v["flows"]) for vp, v in vs)
                   + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "L":
        ls = [(s["viewport"], s.get("lat") or {}) for s in vps]
        if not all(l0.get("slow") and l0.get("never") for _, l0 in ls):
            print(f"{rid}: NOT banked - a viewport lacks the slow-answer or the never-answered reading"); return 1
        def _ms(x):
            return "never" if x is None else f"{round(x / 1000, 1)} s"
        def _l(vp, l0):
            sl, nv = l0["slow"], l0["never"]
            gone = "yes" if sl.get("signGoneAtMs") is None else "gone at " + _ms(sl.get("signGoneAtMs"))
            return (f"{vp}: {sl.get('target')} ({sl.get('how')}) - slow answer (200 after {round((l0.get('delayMs') or 0) / 1000)} s): "
                    f"working sign at {_ms(sl.get('progressAtMs'))} (\"{str(sl.get('firstSign') or '')[:60]}\"), announced: "
                    f"{'; '.join(str(x)[:60] for x in (sl.get('announced') or [])) or 'no'}, sign held for the whole wait: {gone}, "
                    f"the person's words kept: {sl.get('typedKept')}, answer shown at {_ms(sl.get('answerShownAtMs'))}, "
                    f"a Stop: {sl.get('stopControl') or 'none'}. Never answered: ended by {nv.get('endedBy')} after "
                    f"{_ms(nv.get('saidAtMs'))}, saying \"{'; '.join(str(x)[:80] for x in (nv.get('said') or [])) or 'nothing'}\", "
                    f"words kept {nv.get('typedKept')}, page outage notice {nv.get('outageNotice') or 'none'}")
        witness = (f"LOCAL, no model call; the timing is the stub's, not a model's. As {P.get('castName')} ({P.get('persona')}): "
                   + " | ".join(_l(v, l0) for v, l0 in ls) + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "E":
        es = [(s["viewport"], s.get("eval") or {}) for s in vps]
        if not all(e0.get("control") or e0.get("answerShown") for _, e0 in es):
            print(f"{rid}: NOT banked - a viewport neither showed the answer nor offered a was-this-right control (unproven)"); return 1
        def _cov(c):
            return str(c.get("by") or c.get("file") or c) if isinstance(c, dict) else str(c)
        def _e(vp, e0):
            ctl, w = e0.get("control") or {}, e0.get("write") or {}
            cov = "; ".join(_cov(c) for c in (e0.get("coverage") or [])) or "no evaluation names it"
            txt = (f"{vp}: the evaluation covering {e0.get('target')}: {cov}. After a stubbed answer the \"was this right?\" "
                   f"control: {(ctl.get('via') or ctl.get('label')) if ctl else 'none appeared'}")
            if w:
                txt += (f"; pressing \"{ctl.get('label')}\" was a held write to {w.get('table')}, rating {w.get('rating')}, "
                        f"carrying the answer {w.get('carriesAnswer')}, the question {w.get('carriesQuestion')} and the call's "
                        f"trace id {w.get('carriesTrace')}"
                        + (" (a stored answer: its table keeps no trace id)" if e0.get('entry') == 'stored' else "")
                        + f"; the person "
                        f"was told \"{str(e0.get('ack') or 'nothing')[:80]}\"")
            return txt
        witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}): " + " | ".join(_e(v, e0) for v, e0 in es)
                   + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    if sub == "O":
        obs = [(s["viewport"], s.get("obs") or {}) for s in vps]
        if not all(o0.get("sinks") for _, o0 in obs):
            print(f"{rid}: NOT banked - a viewport has no observability reading (no function reached)"); return 1
        def _rep(r):
            if r.get("replayed"):
                return f"{r.get('agent')} replayed under trace {r.get('minted')} -> {r.get('status')}"
            return f"{r.get('agent')} not replayed ({r.get('why')})"
        def _o2(vp, o0):
            sinks = "; ".join(f"{k.get('fn')}: call {', '.join(k.get('call') or []) or 'none'} / output "
                              f"{', '.join(k.get('output') or []) or 'none'}" for k in o0["sinks"])
            reps = "; ".join(_rep(r) for r in (o0.get("replays") or [])) or "none"
            led = o0.get("ledger") or {}
            ledt = (f"ai_cost_log read as the person: {led.get('byFn')}" if "byFn" in led
                    else f"ai_cost_log: {led.get('skipped') or led.get('error') or 'not read'}")
            return (f"{vp}: the ask reached {', '.join(o0.get('fns') or [])}; from source a successful call leaves: {sinks}; "
                    f"page sent a trace id: {o0.get('pageSentTraceId')}; {reps}; {ledt}")
        witness = (f"LOCAL, no model call; the page's ask was stubbed in the browser. As {P.get('castName')} ({P.get('persona')}): "
                   + " | ".join(_o2(v, o0) for v, o0 in obs) + f". Not provable locally: a real turn's ai_cost_log row, "
                   f"model, provider and tokens. AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
    today = time.strftime("%Y-%m-%d")
    note = (f"LM-{sub} ({SUBNAME[sub]}) on {P.get('surface')} walked {today} through the Playwright MCP "
            f"(tools/lm_walk.js) at phone-390 and desktop-1280, signed in through the product's own wall. {res.get('summary', '')}")
    sp = f".tmp/w4_steps/{rid}.compact.json"
    io.open(sp, "w", encoding="utf-8", newline="\n").write(json.dumps(steps, ensure_ascii=False))
    reg0 = {t["id"]: t for t in json.load(io.open("trajectory_registry.json", encoding="utf-8"))["trajectories"]}
    instrument = ((reg0.get(rid) or {}).get("lx") or {}).get("instrument") or "playwright-mcp + postgres-mcp"
    cmd = [sys.executable, "tools/record_mcp_walk.py", "--id", rid, "--instrument", instrument,
           "--layer", "LM", "--sublayer", sub, "--as-persona", P.get("persona"), "--viewports", "phone-390,desktop-1280",
           "--cast", P.get("castName") or "", "--steps", sp, "--witness", witness[:1900], "--note", note[:1500]]
    if live:
        cmd += ["--live-model", live]
    if not res.get("ok"):
        cmd += ["--unproven", "; ".join(res.get("problems") or ["the walk did not hold"])[:400]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    print(" ", out.strip().splitlines()[-1][:220] if out.strip() else "(recorder said nothing)")
    if r.returncode != 0 or "refused" in out.lower() or "ok=True" not in out or not res.get("ok"):
        print(f"{rid}: NOT banked ({'walk verdict: ' + '; '.join(res.get('problems') or []) if not res.get('ok') else 'recorder refused'})")
        return 1
    reg = json.load(io.open("trajectory_registry.json", encoding="utf-8"))
    hit = False
    for t in reg["trajectories"]:
        if t["id"] != rid:
            continue
        locked = t.get("status") == "locked"
        st, pct = ("locked", 100) if locked else ("locking", 60)
        t["status"], t["pct"] = st, pct
        how = (f"live model: {live}" if live else "no model call")
        t["basis"] = (f"[{today}] pct -> {pct}. WALKED LIVE {today} via {instrument} (tools/lm_walk.js, {how}): {note} "
                      f"Witness: {witness[:1200]} Receipt .tmp/mcp_walks/{rid}.json.")
        arts = t.setdefault("artifacts", {})
        arts["gates"] = sorted(set(arts.get("gates") or []) | set(GATES[sub]))
        hit = True
        break
    if not hit:
        print(f"{rid}: not in the registry"); return 1
    fd, tmp = tempfile.mkstemp(dir=str(ROOT), suffix=".tmp"); os.close(fd)
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(json.dumps(reg, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, "trajectory_registry.json")
    import live_walk_manifest as lm
    bm = lm.build(); rows = bm["rows"] if isinstance(bm, dict) else bm
    row = next(x for x in rows if x["id"] == rid)
    closed = lm.row_closed(row)
    print(f"{rid}: CLOSED={closed}" + ("" if closed else " " + str({k: row.get(k) for k in ('kind', 'gated', 'needs_mcp_rewalk', 'receipt_red', 'needs_w4_evidence')})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
