-- 20260731000010_hail_starts_at_hive_radius.sql
--
-- THE THIRD UNREAD KNOB IN THE SAME FEATURE. `broadcast_radius_start_m` was created by 20260731000007 and
-- read by NOTHING — the sweep only uses `broadcast_radius_max_m` as its cap, because widening doubles from
-- whatever radius the request already has. So the knob that decides how WIDE a hail starts had no consumer,
-- which is write-only configuration for the third time in one feature.
--
-- The natural consumer is BIRTH, not the sweep. `service_requests.broadcast_radius_m` has a column DEFAULT
-- of 3000, so a caller who does not choose a radius silently gets a platform constant — exactly the decision
-- the knob exists to make per hive. A sparse rural hive should start its search wider than a dense urban
-- one, and that is not something a client should have to know or be trusted to send.
--
-- WHEN IT APPLIES, deliberately narrow: only when the caller did NOT choose (the value is still the column
-- default) and only on a hail that is actually broadcasting. An explicit radius from the client is honoured
-- untouched — the knob sets the DEFAULT, it does not override intent. A hive with no settings row resolves
-- to the platform default through service_knob(), so nothing changes for anyone who has not tuned it.
--
-- BEFORE INSERT, because a column DEFAULT cannot consult another table.

CREATE OR REPLACE FUNCTION public.apply_hive_broadcast_radius()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
BEGIN
  -- Only fill in what the caller left unchosen. 3000 is the column default: if the row still carries it, no
  -- one expressed a preference, so the hive's knob decides. Any other value is a deliberate choice and is
  -- left exactly as sent.
  IF NEW.status = 'broadcasting' AND NEW.broadcast_radius_m = 3000 THEN
    NEW.broadcast_radius_m := public.service_knob(NEW.hive_id, 'broadcast_radius_start_m');
  END IF;
  RETURN NEW;
END
$fn$;

COMMENT ON FUNCTION public.apply_hive_broadcast_radius() IS
  'Births a broadcasting hail at its hive''s D9 start radius when the caller did not choose one (the column '
  'default 3000 means "unchosen"). An explicit radius is honoured untouched - the knob sets the default, not '
  'the intent. A hive with no settings row resolves to the platform default.';

DROP TRIGGER IF EXISTS trg_apply_hive_broadcast_radius ON public.service_requests;
CREATE TRIGGER trg_apply_hive_broadcast_radius
  BEFORE INSERT ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.apply_hive_broadcast_radius();
