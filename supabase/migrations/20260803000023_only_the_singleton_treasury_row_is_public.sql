-- credit_treasury_read was USING (true), and the RLS strict ratchet counted it: 18 -> 19.
--
-- The tempting move is to raise the baseline to 19, and it is the wrong one. That ratchet is forward-only
-- precisely so a permissive policy cannot be normalised by the person who added it; a floor you raise on
-- your own behalf is not a floor.
--
-- The better question is whether USING (true) is even what this policy MEANS. It is not. Ian asked for the
-- supply and the circulation to be DISPLAYED - "there will be a display the total WorkHive Credits, then
-- WorkHive Credits in circulation" - and the marketplace is browsable anonymously, so the SINGLETON row
-- genuinely is public. Nothing was ever decided about any OTHER row, because today there is exactly one.
--
-- USING (true) silently pre-approves rows that do not exist yet. If a per-hive treasury ever lands, every
-- hive's issued balance becomes world-readable the moment the row is inserted, with no migration touching
-- this policy and nobody deciding anything. Pinning the predicate to id = 1 states the actual intent: THE
-- PLATFORM CAP IS PUBLIC. Anything else has to be argued for.
--
-- Same shape as the security_invoker fix beside it: what makes today's permissiveness harmless is a fact
-- about the data that happens to be there, not a property of the rule.

drop policy if exists credit_treasury_read on public.credit_treasury;
create policy credit_treasury_read on public.credit_treasury
  for select using (id = 1);

comment on table public.credit_treasury is
  'The credit supply: one row (id = 1) carrying authorised_credits (10,000,000, the liability cap) and '
  'issued_credits, with a CHECK that issued never exceeds authorised. Publicly READABLE by design - the '
  'founder console and any visitor may see the supply and what is in circulation - but only row id = 1, '
  'so a future per-tenant treasury is not published by a policy nobody revisited.';
