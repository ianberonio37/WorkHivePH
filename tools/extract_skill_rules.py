"""
AI-assisted Skill-Rule Extraction
=================================
Phase 2 of L-1.5 Skill-Rule Mining. Reads each SKILL.md file and asks
the platform's AI chain (Groq/Cerebras/OpenRouter fallback) to propose
mineable rules in the manifest's JSON shape.

Output is ALWAYS to `skill_rules_proposals.json` -- NEVER directly into
the live manifest. Human reviews each proposal, edits the regex if
needed, then copies accepted entries into `skill_rules_manifest.json`.

Why human-in-the-loop is non-negotiable:
  - The LLM may propose patterns that fire false positives on the
    codebase's specific idioms (e.g., `alert(s)` in template literals).
  - The LLM may propose rules that aren't actually mineable as text
    (e.g., "run pen test before launch").
  - The LLM may propose rules whose intent is already enforced by an
    existing L0 validator.
Each requires a code/codebase aware judgment that a per-rule LLM call
cannot make reliably. The human is the integrator.

Usage:
  python tools/extract_skill_rules.py --skill qa-tester
  python tools/extract_skill_rules.py --all
  python tools/extract_skill_rules.py --skills architect,ai-engineer,devops

Each skill becomes one entry in skill_rules_proposals.json, with all the
LLM's rule suggestions for that skill plus the prompt that was sent and
the raw model response (for audit).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_chain import call_ai_chain  # noqa: E402


ROOT          = Path(__file__).resolve().parent.parent
SKILLS_ROOT   = Path.home() / ".claude" / "skills"
PROPOSALS_OUT = ROOT / "skill_rules_proposals.json"
MANIFEST_PATH = ROOT / "skill_rules_manifest.json"


# Already-mined skills from manual Phase 1 -- skip unless --force.
PHASE_1_SKILLS = {"qa-tester", "frontend", "security", "mobile-maestro", "designer"}


SYSTEM_PROMPT = """You extract MINEABLE RULES from a software engineering skill description.

A MINEABLE RULE is a statement that:
- Can be checked by scanning a file with a regular expression
- Has a clear "pass" or "fail" outcome (a regex matches or doesn't)
- Targets a specific file scope (HTML pages, edge functions, migrations, etc.)
- Is actionable on its own without runtime context

NOT mineable: human-process rules, rules requiring runtime state, rules
already enforced by other validators, vague best-practice recommendations.

Output a single JSON object: {"rules": [...]}.

Each rule has these fields exactly:
  id           kebab_case_slug starting with the skill name
  skill        the skill name (kebab-case, no spaces)
  section      the section heading inside SKILL.md where the rule lives
  summary      one-line plain-language statement (max 120 chars)
  scope        one of: html_pages | js_modules | edge_fns | migrations | html_and_js
  polarity     convention (pattern SHOULD appear) OR anti_pattern (pattern should NOT appear)
  pattern      a Python regex (single string, no `r` prefix, escape backslashes for JSON)
  pattern_flags  optional 'i' for case-insensitive, 'm' for multiline
  triggered_by   optional Python regex -- only count files that ALSO match this pattern
  rationale    why the rule matters; quote or paraphrase the skill's reason
  severity     critical | high | medium | low | info

Be conservative. Propose 5-15 rules max. Skip anything you cannot express
as a regex. Each rule must reference an actual line/section in the skill
text -- do not invent rules from general programming knowledge.

Return ONLY the JSON. No prose around it."""


USER_PROMPT_TEMPLATE = """Skill file: {skill_name}/SKILL.md

Below is the full content. Extract mineable rules per the system prompt.

=== SKILL.md BEGIN ===
{skill_content}
=== SKILL.md END ===

Output JSON with a "rules" array. Aim for 5-15 high-confidence rules.
Each rule's `id` MUST start with "{skill_name_underscore}_" to namespace
it. Each rule's `skill` field MUST be exactly "{skill_name}"."""


def list_available_skills() -> list[str]:
    if not SKILLS_ROOT.exists():
        return []
    return sorted([
        p.name for p in SKILLS_ROOT.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    ])


def existing_manifest_ids() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {r["id"] for r in data.get("rules", [])}


# Cap per-call. Set to ~6.5K chars (~1.6K tokens) so the full request
# (system + user) fits under Groq's per-request body limit, which is
# tighter than the per-model context window on the free tier. First
# extraction run on 2026-05-18 had 4 of 6 Groq models 413 on a 30K-char
# prompt; cutting to 6500 fixes that.
PER_CALL_CHAR_BUDGET = 6500


def _split_skill_into_chunks(content: str) -> list[tuple[int, str]]:
    """Split a SKILL.md into roughly-PER_CALL_CHAR_BUDGET chunks. Prefer
    splitting at H2 / H3 headings to keep related material together.
    Returns [(chunk_index, chunk_text), ...]."""
    if len(content) <= PER_CALL_CHAR_BUDGET:
        return [(1, content)]

    # Split on H2/H3 boundaries.
    boundaries = [0] + [m.start() for m in re.finditer(r"^##\s+", content, re.MULTILINE)] + [len(content)]
    boundaries = sorted(set(boundaries))

    chunks: list[str] = []
    current = ""
    for i in range(len(boundaries) - 1):
        section = content[boundaries[i]:boundaries[i+1]]
        if len(current) + len(section) > PER_CALL_CHAR_BUDGET and current:
            chunks.append(current)
            current = section
        else:
            current += section
    if current:
        chunks.append(current)

    # If any chunk is still too big (one giant section), hard-cut it.
    out = []
    for c in chunks:
        if len(c) <= PER_CALL_CHAR_BUDGET:
            out.append(c)
        else:
            for j in range(0, len(c), PER_CALL_CHAR_BUDGET):
                out.append(c[j:j+PER_CALL_CHAR_BUDGET])
    return [(idx + 1, txt) for idx, txt in enumerate(out)]


def _salvage_json(text: str) -> dict | None:
    """Reasoning models often wrap output in prose ('We will...'), in
    markdown fences, or in <think>...</think> blocks. Best-effort:
    1. Strip <think>...</think>
    2. Strip surrounding ```json fences
    3. Find the largest balanced {...} substring
    4. json.loads on the result
    Returns parsed dict or None if all strategies fail."""
    if not text:
        return None
    # Strip reasoning-model thinking blocks.
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    # Strip markdown code fences.
    text = re.sub(r"^[\s]*```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)

    # Direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the largest balanced { ... } block.
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    return None


def _extract_one_chunk(skill_name: str, chunk_index: int, total_chunks: int, chunk_text: str) -> dict:
    skill_name_underscore = skill_name.replace("-", "_")
    chunk_header = (f"\n\n[Chunk {chunk_index} of {total_chunks} of SKILL.md]\n\n"
                    if total_chunks > 1 else "")
    user_prompt = USER_PROMPT_TEMPLATE.format(
        skill_name=skill_name,
        skill_content=chunk_header + chunk_text,
        skill_name_underscore=skill_name_underscore,
    )

    t0 = time.time()
    # Pin GPT-OSS 20B first -- chain config notes it has "strict JSON-schema
    # adherence". The rest of the chain serves as fallback if it 429s.
    response = call_ai_chain(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=4096,
        json_mode=True,
        timeout=120,
        prefer_model="gpt-oss-20b",
    )
    elapsed = round(time.time() - t0, 1)

    parsed = _salvage_json(response)
    if parsed is None:
        return {"chunk": chunk_index, "elapsed_s": elapsed,
                "error": "Could not salvage JSON from model output",
                "raw_response": response[:1500]}
    return {"chunk": chunk_index, "elapsed_s": elapsed,
            "rules": parsed.get("rules", []) if isinstance(parsed, dict) else []}


def extract_for_skill(skill_name: str) -> dict:
    skill_path = SKILLS_ROOT / skill_name / "SKILL.md"
    if not skill_path.exists():
        return {"skill": skill_name, "error": f"SKILL.md not found at {skill_path}"}

    skill_content = skill_path.read_text(encoding="utf-8", errors="replace")
    chunks = _split_skill_into_chunks(skill_content)

    total_elapsed = 0.0
    all_rules: list[dict] = []
    chunk_results: list[dict] = []
    for idx, chunk_text in chunks:
        result = _extract_one_chunk(skill_name, idx, len(chunks), chunk_text)
        chunk_results.append(result)
        total_elapsed += result.get("elapsed_s", 0)
        all_rules.extend(result.get("rules", []))

    rules = all_rules

    # Validate rule shape minimally.
    valid_rules = []
    skipped = []
    for r in rules:
        if not isinstance(r, dict) or "id" not in r or "pattern" not in r:
            skipped.append(r)
            continue
        # Try compiling the regex -- skip if invalid.
        try:
            flags = 0
            if "i" in (r.get("pattern_flags") or ""):
                flags |= re.IGNORECASE
            re.compile(r["pattern"], flags)
        except re.error as e:
            r["_invalid_regex"] = str(e)
            skipped.append(r)
            continue
        valid_rules.append(r)

    return {
        "skill":          skill_name,
        "elapsed_s":      round(total_elapsed, 1),
        "chunk_count":    len(chunks),
        "chunks":         chunk_results,
        "rule_count":     len(valid_rules),
        "skipped_count":  len(skipped),
        "rules":          valid_rules,
        "skipped":        skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill",   help="Single skill to extract from")
    parser.add_argument("--skills",  help="Comma-separated list of skills")
    parser.add_argument("--all",     action="store_true", help="All skills not yet in manifest")
    parser.add_argument("--force",   action="store_true", help="Include Phase-1 skills too")
    args = parser.parse_args()

    available = list_available_skills()
    if not available:
        print(f"ERROR: no skills directory at {SKILLS_ROOT}")
        return 1

    if args.skill:
        targets = [args.skill]
    elif args.skills:
        targets = [s.strip() for s in args.skills.split(",") if s.strip()]
    elif args.all:
        targets = [s for s in available if (args.force or s not in PHASE_1_SKILLS)]
    else:
        print("Usage: --skill NAME | --skills A,B,C | --all")
        print(f"Available skills ({len(available)}):")
        for s in available: print(f"  {s}")
        return 0

    # Load existing proposals so re-runs append per-skill.
    out_data = {"runs": []}
    if PROPOSALS_OUT.exists():
        out_data = json.loads(PROPOSALS_OUT.read_text(encoding="utf-8"))

    existing_ids = existing_manifest_ids()

    print(f"AI-assisted Skill-Rule Extraction")
    print(f"  skills root:  {SKILLS_ROOT}")
    print(f"  targets:      {len(targets)}  ->  {targets}")
    print(f"  output:       {PROPOSALS_OUT.name}")
    print(f"  existing manifest ids: {len(existing_ids)}")
    print()

    for skill in targets:
        print(f"--- {skill} ---")
        result = extract_for_skill(skill)
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            new_rules = [r for r in result["rules"] if r.get("id") not in existing_ids]
            print(f"  proposed:     {result['rule_count']} rules ({len(new_rules)} new)")
            print(f"  skipped:      {result['skipped_count']} (invalid shape/regex)")
            print(f"  elapsed:      {result['elapsed_s']}s")
            result["new_rule_count"] = len(new_rules)
        out_data["runs"].append({**result, "timestamp": int(time.time())})

        # Write after each skill so a mid-run failure doesn't lose work.
        PROPOSALS_OUT.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    print()
    print(f"All proposals written to {PROPOSALS_OUT.name}.")
    print(f"Review them and copy accepted rules into skill_rules_manifest.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
