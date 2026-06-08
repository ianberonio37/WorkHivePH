"""
ia_semantic_critic.py — Gap-5: the REASONING IA critic (the "intelligence" layer)
================================================================================
The deterministic surveyor (survey_ia_redundancy.py) can say "the word 'overdue'
appears on 3 pages". It CANNOT say "these two alert surfaces should be one",
"AMC lives on 3 pages — pick a home and deep-link", "shift-handover duplicates
the logbook's last-shift view — transfer, don't rebuild". That judgment is what
the owner flagged missing (BATTERY_INTELLIGENCE_GAPS.md, Gap 5).

This tool feeds the GROUNDED corpus (ia_inventory_corpus.json — real unitIds ×
page × label × theme × value, produced by Layer A+B) to a free-tier LLM acting
as a senior product/IA architect, and asks for proposals in 4 verbs —
TRANSFER · STREAMLINE/CONSOLIDATE · REDUNDANT/REMOVE · RELABEL/DIFFERENTIATE —
each with a user-confusion rationale.

HONESTY GUARDRAILS (so the LLM can't hallucinate the product):
  - the corpus is the ONLY source of pages/units; the prompt says "cite real
    unitIds, invent nothing".
  - every returned proposal is VALIDATED post-hoc: each cited unitId must exist
    in the corpus; a proposal with zero valid citations is DROPPED.
  - the deterministic theme clusters are passed in as PRIORS (not gospel).
  - output = CRITIC candidates → ufai_ingest.py → disposition. NEVER auto-applied.

Reuses tools/ai_chain.py (Groq→Cerebras→Gemini→Mistral→OpenRouter free chain).

USAGE:
  python tools/ia_semantic_critic.py                 # reason → write candidates + .md
  python tools/ia_semantic_critic.py --ingest        # also merge into sweep_critiques.json
  python tools/ia_semantic_critic.py --dry-run       # print the prompt, don't call the LLM
"""
from __future__ import annotations
import io, os, sys, json, argparse, re
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from ai_chain import call_ai_chain, _load_env  # reuse the free-tier fallback chain

CORPUS = ROOT / "ia_inventory_corpus.json"
OUT_JSON = ROOT / "ia_semantic_critic_candidates.json"
OUT_MD = ROOT / "ia_semantic_critic.md"

# Domains the owner named explicitly — steer the critic to look HARD here.
FOCUS_DOMAINS = ["alerts", "shift-handover", "AMC", "risk", "approvals",
                 "overdue / due", "OEE", "predictive", "maintenance KPIs"]

VERBS = {
    "TRANSFER":     "this unit belongs on page Y, not where it is (wrong home).",
    "CONSOLIDATE":  "these N surfaces serve ONE job → one canonical home + deep-links.",
    "REMOVE":       "this duplicates another and adds no context (pure redundancy).",
    "RELABEL":      "same word, different meaning across pages → disambiguate.",
}

SYSTEM = (
    "You are a SENIOR PRODUCT / INFORMATION-ARCHITECTURE ARCHITECT reviewing WorkHive, a "
    "mobile-first industrial-maintenance app used by Filipino field technicians and supervisors. "
    "You are reviewing a cross-page INVENTORY of every info-unit (KPI tile, list, panel) the app "
    "renders. Your job is the judgment a dumb string-matcher lacks: spot where the SAME job or "
    "information is SPLIT across pages (consolidate), where a unit sits on the WRONG page "
    "(transfer), where two things DUPLICATE and confuse a user (remove), and where one LABEL means "
    "two different things (relabel). Think like someone who has to onboard a new technician and is "
    "embarrassed by every place the app makes them ask 'wait, is this the same number as that?'. "
    "GROUND EVERY claim in the real unitIds given — invent NOTHING; if you are unsure two units are "
    "the same, say so and propose a CHECK, not a merge. Prefer a few high-confidence, specific "
    "proposals over many vague ones."
)


def load_corpus():
    c = json.loads(CORPUS.read_text(encoding="utf-8"))
    return c["corpus"], c.get("groups", {})


def compact_view(corpus: dict) -> tuple[str, set]:
    """A token-lean, fully-grounded rendering: page → units. Returns (text, valid_unitIds)."""
    valid = set()
    lines = []
    for page in sorted(corpus):
        units = corpus[page].get("infoUnits", [])
        if not units:
            continue
        lines.append(f"\n## {page}")
        for u in units:
            uid = u.get("unitId")
            if not uid:
                continue
            valid.add(uid)
            label = u.get("label") or "(no label)"
            theme = u.get("theme") or "-"
            val = u.get("value")
            val = f" = {val}" if val not in (None, "", "null") else ""
            tag = " [UNTAGGED]" if u.get("kind") == "kpi-untagged" else ""
            lines.append(f"  - {label}{val}  ·  theme:{theme}  ·  ⟨{uid}⟩{tag}")
    return "\n".join(lines), valid


def priors_view(groups: dict) -> str:
    """Feed the deterministic clusters as PRIORS the LLM should reason ABOUT, not just echo."""
    out = ["### Deterministic priors (a dumb matcher already found these — go DEEPER than them):"]
    for c in (groups.get("info_theme_clusters") or [])[:12]:
        pages = ", ".join(c.get("pages", []))
        labels = "; ".join(c.get("labels", []) or c.get("key", ""))
        out.append(f"  - theme '{c.get('theme', c.get('key',''))}' on [{pages}] as: {labels}")
    for c in (groups.get("info_redundancy_by_label") or [])[:8]:
        out.append(f"  - SAME LABEL '{c.get('key')}' on [{', '.join(c.get('pages', []))}]")
    return "\n".join(out)


def build_prompt(corpus, groups) -> tuple[str, set]:
    view, valid = compact_view(corpus)
    priors = priors_view(groups)
    verbs = "\n".join(f"  - {v}: {d}" for v, d in VERBS.items())
    schema = (
        '{"proposals": [{"verb": "TRANSFER|CONSOLIDATE|REMOVE|RELABEL", '
        '"title": "<short imperative>", "unit_ids": ["page:key", ...], '
        '"pages": ["x.html", ...], "canonical_home": "<page or n/a>", '
        '"user_confusion": "<the concrete way this confuses a tech/supervisor>", '
        '"recommendation": "<what to do>", "confidence": "high|medium|low", '
        '"severity": "Major|Minor|Polish"}]}'
    )
    prompt = f"""Here is the WorkHive cross-page info-unit inventory ({len(valid)} units). Every ⟨unitId⟩ is real.

{view}

{priors}

LOOK HARDEST at these owner-named domains (they suspect redundancy/confusion here):
  {', '.join(FOCUS_DOMAINS)}

Produce proposals using ONLY these verbs:
{verbs}

Rules:
  - cite ONLY real ⟨unitId⟩s from the list above in "unit_ids". Invent nothing.
  - each proposal needs ≥1 unit_id and a CONCRETE "user_confusion" (not generic).
  - a per-list-item repeat (one card template × N rows) is NOT redundancy — do not flag it.
  - if two units MIGHT be the same but you can't be sure from labels, use verb RELABEL or
    recommendation "VERIFY same-derivation first", confidence low.
  - prefer 4-10 specific, high-confidence proposals over many weak ones.

Return STRICT JSON, no prose:
{schema}"""
    return prompt, valid


def validate(proposals: list, valid: set) -> tuple[list, list]:
    kept, dropped = [], []
    for p in proposals:
        cited = [u for u in (p.get("unit_ids") or []) if u in valid]
        if not cited:
            dropped.append(p)
            continue
        p["unit_ids"] = cited                 # strip any hallucinated ids
        p["_hallucinated_dropped"] = [u for u in (p.get("unit_ids_raw") or p.get("unit_ids") or []) if u not in valid]
        kept.append(p)
    return kept, dropped


def to_candidates(proposals: list) -> list:
    """Map to the sweep_critiques schema (ufai_ingest REQUIRED keys)."""
    verb_pillar = {"TRANSFER": "IA", "CONSOLIDATE": "IA", "REMOVE": "IA", "RELABEL": "C"}
    cands = []
    for i, p in enumerate(proposals):
        verb = (p.get("verb") or "REVIEW").upper()
        slug = re.sub(r"[^a-z0-9]+", "-", (p.get("title") or f"item-{i}").lower()).strip("-")[:48]
        cands.append({
            "key": f"sweep:ia:semantic:{verb.lower()}:{slug}",
            "page": ",".join(p.get("pages", [])) or "platform",
            "title": p.get("title", "")[:120],
            "pillar": verb_pillar.get(verb, "IA"),
            "severity": p.get("severity", "Minor"),
            "flag": (f"[SEMANTIC CRITIC · {verb} · conf={p.get('confidence','?')}] "
                     f"units={p.get('unit_ids')} · CONFUSION: {p.get('user_confusion','')}"),
            "should_be": (f"{p.get('recommendation','')} "
                          f"(canonical_home={p.get('canonical_home','n/a')}). "
                          f"Human disposes; if confidence<high VERIFY same-derivation first."),
            "source": "ia-semantic-critic",
        })
    return cands


def render_md(proposals, dropped, valid_n, model_note) -> str:
    L = ["# IA Semantic Critic — reasoned consolidation/transfer/relabel proposals",
         "",
         "> Gap-5 of BATTERY_INTELLIGENCE_GAPS.md. A free-tier LLM product-architect reasons over the",
         "> grounded info-unit corpus. **Proposals, not actions** — engine proposes, owner disposes.",
         f"> Grounded on {valid_n} real units. {model_note}",
         ""]
    by_verb = {}
    for p in proposals:
        by_verb.setdefault((p.get("verb") or "REVIEW").upper(), []).append(p)
    for verb in ["CONSOLIDATE", "TRANSFER", "REMOVE", "RELABEL"]:
        items = by_verb.get(verb, [])
        if not items:
            continue
        L.append(f"## {verb} — {VERBS.get(verb,'')}")
        L.append("")
        for p in items:
            L.append(f"### {p.get('title','(untitled)')}  ·  _{p.get('confidence','?')} confidence · {p.get('severity','Minor')}_")
            L.append(f"- **Units:** {', '.join('`'+u+'`' for u in p.get('unit_ids', []))}")
            if p.get("canonical_home"):
                L.append(f"- **Canonical home:** {p['canonical_home']}")
            L.append(f"- **Why it confuses the user:** {p.get('user_confusion','')}")
            L.append(f"- **Recommendation:** {p.get('recommendation','')}")
            L.append("")
    if dropped:
        L.append(f"## Dropped (hallucinated — cited no real unitId): {len(dropped)}")
        for p in dropped:
            L.append(f"- {p.get('title','?')} (cited {p.get('unit_ids')})")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true", help="merge candidates into sweep_critiques.json")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt, do not call the LLM")
    args = ap.parse_args()

    _load_env()
    corpus, groups = load_corpus()
    prompt, valid = build_prompt(corpus, groups)

    if args.dry_run:
        print(prompt)
        print(f"\n--- {len(valid)} valid unitIds ---")
        return

    raw = call_ai_chain(prompt, system_prompt=SYSTEM, temperature=0.4,
                        max_tokens=4096, json_mode=True, prefer_model="gpt-oss-120b")
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {"proposals": []}
    proposals = data.get("proposals", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    kept, dropped = validate(proposals, valid)
    model_note = f"LLM returned {len(proposals)} proposals; {len(kept)} grounded, {len(dropped)} dropped (hallucinated)."
    cands = to_candidates(kept)

    OUT_JSON.write_text(json.dumps(cands, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(render_md(kept, dropped, len(valid), model_note), encoding="utf-8")
    print(f"IA semantic critic — {model_note}")
    for c in cands:
        print(f"  + {c['key']}  [{c['severity']}]  {c['title']}")
    print(f"  -> {OUT_JSON.name} + {OUT_MD.name}")

    if args.ingest and cands:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "ufai_ingest.py"), str(OUT_JSON)], cwd=str(ROOT))
    elif cands:
        print(f"  (review {OUT_MD.name}; then: python ufai_ingest.py {OUT_JSON.name})")


if __name__ == "__main__":
    main()
