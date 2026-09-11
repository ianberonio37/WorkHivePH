-- A per-hive monthly AI cost ceiling, so the cap the companion already knows how to enforce has something
-- to read.
--
-- WHAT WAS WRONG. voice-handler.js carries `_getMonthlyCost(db, hiveId)` and `_exceededCostCap(spent, cap)`
-- under a comment that states the intent exactly: "per-hive monthly cost ceiling. Reads aggregate USD spend
-- from ai_cost_log; when the running total breaches the cap, the next turn is short-circuited to a 'monthly
-- cap reached' reply." Neither function has a call site anywhere in the repo, and - measured 2026-09-08 -
-- there is no cap VALUE anywhere either: no column, no constant, no config. A comparison with nothing to
-- compare against.
--
-- WHAT THIS DOES NOT DO: pick a number. What a hive may spend per month is a commercial decision, and the
-- AI chain currently runs on permanently-free provider tiers where a turn costs $0, so any figure written
-- here would be invented rather than derived. The column therefore defaults to **0, which
-- `_exceededCostCap` already treats as no cap at all** (`if (c <= 0) return false`). Nothing changes for any
-- hive until somebody sets one, and the moment somebody does, the enforcement is real.
--
-- The client reads this ONCE per session and, when it is 0, does no further work: the spend query walks up
-- to 10,000 cost rows, and running that every turn to enforce a cap nobody set would be a latency bill for
-- a feature that is off.
--
-- numeric(12,4): USD to a hundredth of a cent, up to eight figures. CHECK (>= 0) because a negative ceiling
-- is not "unlimited", it is a typo, and the client's own guard reads any non-positive value as no cap.

ALTER TABLE public.hives
  ADD COLUMN IF NOT EXISTS ai_monthly_cost_cap_usd numeric(12,4) NOT NULL DEFAULT 0;

DO $$
BEGIN
  ALTER TABLE public.hives
    ADD CONSTRAINT hives_ai_cost_cap_non_negative CHECK (ai_monthly_cost_cap_usd >= 0);
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

COMMENT ON COLUMN public.hives.ai_monthly_cost_cap_usd IS
  'Monthly AI spend ceiling in USD for this hive. 0 = no cap (the default, and what every hive carries '
  'until an owner sets one). voice-handler reads it once per session and short-circuits the turn with a '
  '"monthly cap reached" reply when ai_cost_log for the current month reaches it.';
