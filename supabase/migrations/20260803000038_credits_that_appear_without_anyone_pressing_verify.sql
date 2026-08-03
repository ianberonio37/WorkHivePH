-- ============================================================================
-- AUTOMATIC TOP-UP VERIFICATION — credits appear without anyone pressing Verify
--
-- Ian: "can we make a less or no hassle to verify, like automatic?"
--
-- WHY IT WAS MANUAL. WorkHive has no business registration, so no GCash
-- merchant account, so no payment API and no callback. A P2P transfer to a
-- personal number tells the platform nothing. The founder had to open the
-- GCash app, find the reference, and press Verify — for every single top-up.
--
-- WHAT MAKES IT AUTOMATIC WITHOUT REGISTRATION. GCash already notifies the
-- RECIPIENT of every payment received, by SMS and email. That notification is
-- the missing signal. Forwarded once into this table (see the companion edge
-- function), a matching pending top-up verifies itself and the existing mint
-- trigger does the rest. No merchant account, no API, no new relationship with
-- GCash — the platform reads a receipt the founder already gets.
--
-- ── THE INVARIANT THIS MUST NOT BREAK ──────────────────────────────────────
-- A forwarded notification is a CLAIM. Anyone who learns the inbound address
-- could forge one, and a forged receipt that mints credits is free money. So:
--
--   CREDITS ARE NEVER MINTED FROM A RECEIPT. They are minted by VERIFYING A
--   TOP-UP THE PROVIDER ALREADY FILED, and only when the receipt matches that
--   filing on BOTH the reference number AND the amount.
--
-- The provider's filing says "I sent PHP500, ref 1234567890123". The receipt
-- says "PHP500 arrived, ref 1234567890123". Neither alone is sufficient; the
-- AGREEMENT of two independent statements is what verification has always
-- meant here, and this only automates the comparison a human was doing.
--
-- Consequences that follow, and are enforced below:
--   · a receipt matching NOTHING is kept, not discarded — it may be a genuine
--     payment whose filing has not arrived yet, and it must be visible
--   · a receipt can verify AT MOST ONE top-up, once (unique on reference)
--   · an amount that disagrees does NOT partially credit; it stays unmatched
--     with the reason recorded, because a partial credit on a money rail is
--     the worst of both outcomes
--   · a top-up already decided (verified/rejected) is never re-decided
--   · nothing here can verify a top-up the founder REJECTED
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.gcash_inbound_receipts (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The reference is the join key to a filed top-up, so it carries the same
  -- 13-digit shape the filing form enforces.
  reference      text NOT NULL,
  amount         numeric(12,2) NOT NULL CHECK (amount > 0),
  sender_name    text,
  received_at    timestamptz,
  raw_text       text NOT NULL,      -- the notification verbatim, for audit and re-parsing
  source         text NOT NULL DEFAULT 'email'
                   CHECK (source IN ('email','sms','manual')),
  matched_topup  uuid REFERENCES public.service_credit_topups(id) ON DELETE SET NULL,
  match_state    text NOT NULL DEFAULT 'unmatched'
                   CHECK (match_state IN ('unmatched','matched','ambiguous','amount_mismatch','already_decided')),
  match_note     text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- ONE receipt per reference. A forwarder that retries, or a mailbox that
-- delivers twice, must not verify anything a second time.
CREATE UNIQUE INDEX IF NOT EXISTS gcash_inbound_receipts_reference_uk
  ON public.gcash_inbound_receipts (reference);

CREATE INDEX IF NOT EXISTS gcash_inbound_receipts_unmatched_ix
  ON public.gcash_inbound_receipts (created_at DESC) WHERE match_state <> 'matched';

ALTER TABLE public.gcash_inbound_receipts ENABLE ROW LEVEL SECURITY;

-- Nobody reads these but the platform. They contain a payer's name and amount,
-- and they are not a provider's business: the provider sees their own top-up.
DROP POLICY IF EXISTS gcash_inbound_receipts_admin_read ON public.gcash_inbound_receipts;
CREATE POLICY gcash_inbound_receipts_admin_read ON public.gcash_inbound_receipts
  FOR SELECT TO authenticated
  USING (public.is_platform_admin());

REVOKE ALL ON public.gcash_inbound_receipts FROM anon, authenticated;
GRANT SELECT ON public.gcash_inbound_receipts TO authenticated;

-- ── the matcher ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.match_gcash_receipt()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_n       integer;
  v_topup   public.service_credit_topups%rowtype;
BEGIN
  -- Candidates are filings with THIS reference, whatever their status: a
  -- reference that matches an already-decided top-up is a different outcome
  -- from one that matches nothing, and the difference is worth recording.
  SELECT count(*) INTO v_n FROM public.service_credit_topups t
   WHERE t.gcash_ref = NEW.reference;

  IF v_n = 0 THEN
    NEW.match_state := 'unmatched';
    NEW.match_note  := 'No provider has filed this reference yet. Kept in case the filing arrives late.';
    RETURN NEW;
  END IF;

  IF v_n > 1 THEN
    -- Should be impossible (the filing form refuses a duplicate reference), so
    -- if it happens the honest answer is to refuse to guess.
    NEW.match_state := 'ambiguous';
    NEW.match_note  := v_n || ' filings share this reference; a human must decide.';
    RETURN NEW;
  END IF;

  SELECT * INTO v_topup FROM public.service_credit_topups t
   WHERE t.gcash_ref = NEW.reference;

  IF v_topup.status <> 'pending_verification' THEN
    NEW.matched_topup := v_topup.id;
    NEW.match_state   := 'already_decided';
    NEW.match_note    := 'That filing was already ' || v_topup.status || '; nothing changed.';
    RETURN NEW;
  END IF;

  -- THE AMOUNTS MUST AGREE. A receipt for a different sum is not confirmation
  -- of this filing, and crediting the smaller of the two would be inventing a
  -- decision nobody made.
  IF v_topup.amount IS DISTINCT FROM NEW.amount THEN
    NEW.matched_topup := v_topup.id;
    NEW.match_state   := 'amount_mismatch';
    NEW.match_note    := 'Filed ' || to_char(v_topup.amount, 'FM999G999G990D00')
                      || ' but ' || to_char(NEW.amount, 'FM999G999G990D00')
                      || ' arrived. Left for the founder to settle.';
    RETURN NEW;
  END IF;

  -- Agreement. Verify the FILING; the existing guard_service_topup_status
  -- trigger is what actually mints, so the money path is unchanged and still
  -- has exactly one writer.
  UPDATE public.service_credit_topups
     SET status = 'verified'
   WHERE id = v_topup.id AND status = 'pending_verification';

  NEW.matched_topup := v_topup.id;
  NEW.match_state   := 'matched';
  NEW.match_note    := 'Reference and amount agreed with the provider''s filing; verified automatically.';
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_match_gcash_receipt ON public.gcash_inbound_receipts;
CREATE TRIGGER trg_match_gcash_receipt
  BEFORE INSERT ON public.gcash_inbound_receipts
  FOR EACH ROW EXECUTE FUNCTION public.match_gcash_receipt();

-- ── the founder's remaining job ────────────────────────────────────────────
-- Automation that fails SILENTLY is worse than the manual queue it replaced,
-- so what did not match must be as visible as what did.
CREATE OR REPLACE VIEW public.v_gcash_receipts_needing_eyes AS
  SELECT r.id, r.reference, r.amount, r.sender_name, r.received_at,
         r.match_state, r.match_note, r.created_at
    FROM public.gcash_inbound_receipts r
   WHERE r.match_state <> 'matched'
   ORDER BY r.created_at DESC;

GRANT SELECT ON public.v_gcash_receipts_needing_eyes TO authenticated;
