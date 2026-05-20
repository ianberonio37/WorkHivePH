# AI Prompt Standards Audit (Tier B grounding check)

Edge-fn prompts that mention a registered metric should cite the
metric's canonical standard short_name. Without that, AI
explanations drift from the deterministic calc's contract.

## Summary

- Files scanned:      **52**
- Metric mentions:    **5**
- Cite the standard:  **0** ✅
- Mention without cite: **5** ⚠️

## Mentions missing standard citation (5)

| File | Line | Metric | Should cite | Snippet |
|---|---:|---|---|---|
| `supabase/functions/analytics-orchestrator/index.ts` | 369 | `\bMTBF\b` | `ISO 14224:2016` | You are a senior maintenance manager writing a weekly action plan for an industr |
| `supabase/functions/analytics-orchestrator/index.ts` | 369 | `\bMTTR\b` | `ISO 14224:2016` | You are a senior maintenance manager writing a weekly action plan for an industr |
| `supabase/functions/analytics-orchestrator/index.ts` | 369 | `\bOEE\b` | `ISO 22400-2:2014` | You are a senior maintenance manager writing a weekly action plan for an industr |
| `supabase/functions/asset-brain-query/index.ts` | 35 | `\brisk score\b` | `SAE JA1011` | You are WorkHive Asset Brain, an industrial maintenance assistant grounded in re |
| `supabase/functions/intelligence-report/index.ts` | 157 | `\bMTBF\b` | `ISO 14224:2016` | Data for the Philippine Industrial Intelligence Report:  Active plants: ${(data. |