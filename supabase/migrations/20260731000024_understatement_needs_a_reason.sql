-- 20260731000024_understatement_needs_a_reason.sql
--
-- CLOSES THE A3 ATTACK, the last open hole the fraud model found. Commission bills what was actually PAID
-- — the right fix, because a job settled at a different real price should not be billed off a catalogue
-- number — but it hands both parties a lever. A client and provider who agree PHP50,000 and then declare
-- PHP1 on the payment record pay PHP0.10 commission instead of PHP2,500. The attack probe measured exactly
-- that: nothing refused it and nothing noticed.
--
-- WHY NOT SIMPLY REFUSE A LOW PAYMENT. A declared payment below the quote is often legitimate — the job
-- came in under scope, the provider gave a discount, part was paid in materials. Refusing those would block
-- honest work and push people off-platform entirely, which costs the platform more than the leak.
--
-- WHY COUNTER-CONFIRMATION DOES NOT WORK HERE, since it is the obvious idea: BOTH parties gain from
-- understating. The provider pays less commission and the client pays less. The platform is the only loser,
-- so asking the other side to agree just asks a co-beneficiary.
--
-- SO: YOU MAY PAY LESS, YOU JUST HAVE TO SAY WHY. A materially-understated payment must carry a
-- `variance_reason`. That is deliberately cheap for an honest user (one sentence about a real discount) and
-- expensive for a dishonest one, because it converts a silent gap into a WRITTEN, attributable claim sitting
-- next to an immutable payment record — and a pattern of identical reasons across many jobs is a detection
-- signal the leakage gate can actually act on. An attack that is neither refused nor recorded is the one
-- that runs for months; this makes it recorded.
--
-- AND ONE DEFINITION OF "THE AGREED PRICE". The COALESCE chain (selected offer -> catalogue rate -> stated
-- budget) was written out THREE times — in mint_settlement_commission, in mint_service_cashback, and again
-- in validate_commission_leakage.py. Three copies of a money rule drift, and the drift would be silent. It
-- now lives in `service_agreed_base()` and every consumer calls it.

-- ── the single definition ────────────────────────────────────────────────────────────────────────────
create or replace function public.service_agreed_base(p_request_id uuid)
returns numeric
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  SELECT COALESCE(
           -- the selected offer IS the contract; a catalogue rate is the list price; the budget is the
           -- client's stated wish, and is the weakest of the three, so it comes last.
           (SELECT o.price FROM public.service_offers o
             WHERE o.request_id = p_request_id AND o.status = 'selected' AND o.price IS NOT NULL
             ORDER BY o.updated_at DESC LIMIT 1),
           (SELECT c.base_rate FROM public.service_catalog c
             JOIN public.service_requests r ON r.catalog_item_id = c.id
            WHERE r.id = p_request_id),
           (SELECT r.budget FROM public.service_requests r WHERE r.id = p_request_id),
           0);
$$;

comment on function public.service_agreed_base(uuid) is
  'THE agreed price for a job: selected offer, else catalogue rate, else stated budget. One definition, '
  'because this chain was written out three times and three copies of a money rule drift silently.';

alter table public.service_payments
  add column if not exists variance_reason text;

comment on column public.service_payments.variance_reason is
  'Why the declared payment is materially below the agreed price. Required under 50% on a job over '
  'PHP1,000 — you may pay less, you just have to say why. Converts a silent commission gap into a written, '
  'attributable claim beside an immutable record.';

-- ── the refusal ──────────────────────────────────────────────────────────────────────────────────────
create or replace function public.guard_payment_variance_explained()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  v_agreed numeric;
  v_ratio  numeric;
BEGIN
  -- Backend / seeder writes (no JWT) are already vetted, matching the parity rule the sibling guards use.
  IF auth.uid() IS NULL THEN
    RETURN new;
  END IF;

  v_agreed := public.service_agreed_base(new.request_id);

  -- Only MATERIAL jobs. A PHP200 job declared at PHP80 is noise, and demanding prose for it would train
  -- people to type "discount" reflexively — which would destroy the signal on the jobs that matter.
  IF v_agreed < 1000 THEN
    RETURN new;
  END IF;

  v_ratio := new.amount_paid / nullif(v_agreed, 0);

  IF v_ratio < 0.5 AND coalesce(btrim(new.variance_reason), '') = '' THEN
    RAISE EXCEPTION
      'This is % of the agreed %. That may be perfectly fine — a smaller job, a discount, part paid in '
      'materials — but please say why, so it is on the record.',
      to_char(v_ratio * 100, 'FM990.0') || '%', to_char(v_agreed, 'FM999G999G990.00')
      USING ERRCODE = 'check_violation',
            HINT = 'Add a short variance_reason to the payment record.';
  END IF;

  -- A reason that is present but meaningless ("ok", "-") is not a reason. Cheap to satisfy honestly,
  -- and it stops a single character from discharging the obligation.
  IF v_ratio < 0.5 AND length(btrim(new.variance_reason)) < 8 THEN
    RAISE EXCEPTION 'Please give a little more detail about why the amount differs (at least a few words).'
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN new;
END
$$;

drop trigger if exists trg_guard_payment_variance_explained on public.service_payments;
create trigger trg_guard_payment_variance_explained
  before insert on public.service_payments
  for each row execute function public.guard_payment_variance_explained();

-- ── and the two minters now call the ONE definition ──────────────────────────────────────────────────
-- Surgery on the live definition rather than a retype: rebuilding a money function from memory has cost
-- this repo three regressions, most recently a draft that silently dropped hive scoping and the
-- Asia/Manila day boundary. Each replace is asserted, and a miss RAISES rather than leaving the duplicate
-- chain in place while reporting success.
do $mig$
declare
  v_def text; v_new text; v_hits int;
begin
  -- commission: the chain is preceded by the amount_paid preference, so the whole COALESCE is replaced
  select pg_get_functiondef(oid) into v_def from pg_proc where proname='mint_settlement_commission';
  if position('service_agreed_base' in v_def) = 0 then
    v_new := regexp_replace(
      v_def,
      'SELECT COALESCE\(.*?\)\s*INTO v_base;',
      'SELECT COALESCE((SELECT p.amount_paid FROM public.service_payments p '
      || 'WHERE p.request_id = new.id), public.service_agreed_base(new.id), 0) INTO v_base;',
      'ns');
    if v_new = v_def then raise exception 'commission base chain not matched; refusing to guess'; end if;
    execute v_new;
    raise notice 'mint_settlement_commission now calls service_agreed_base()';
  end if;

  select pg_get_functiondef(oid) into v_def from pg_proc where proname='mint_service_cashback';
  if position('service_agreed_base' in v_def) = 0 then
    v_new := regexp_replace(
      v_def,
      'SELECT COALESCE\(.*?\)\s*INTO v_base;',
      'SELECT COALESCE((SELECT p.amount_paid FROM public.service_payments p '
      || 'WHERE p.request_id = r.id), public.service_agreed_base(r.id), 0) INTO v_base;',
      'ns');
    if v_new = v_def then raise exception 'cashback base chain not matched; refusing to guess'; end if;
    execute v_new;
    raise notice 'mint_service_cashback now calls service_agreed_base()';
  end if;
end
$mig$;
