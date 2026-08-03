-- v_credit_posture shipped without security_invoker, so it read its base tables as the view OWNER.
--
-- Caught by the Arc G gate ("no view bypasses base-table RLS = cross-tenant read"), which ratchets on the
-- count of non-invoker views and rose by one the moment migration ...000012 created this.
--
-- The leak here is not severe: the view exposes only posture facts (is there a cash-out function, is the
-- transfer guard installed, the supply cap, the fixed rate), and `credit_treasury` is deliberately readable
-- by everyone because Ian asked for the supply and circulation to be DISPLAYED. So nothing private escapes.
--
-- It is fixed anyway, because the property the gate defends is structural rather than case-by-case: an
-- owner-executing view is a standing RLS bypass, and the reason it is harmless today is a fact about the
-- data it happens to select right now. Add one column that reads a tenant-scoped table and the same view
-- silently becomes a cross-tenant read, with no migration touching the view's security at all. The whole
-- point of the invariant is that nobody has to re-derive that risk per view.
--
-- Safe to flip: every base table it touches is readable by the caller. pg_proc and pg_trigger are public
-- catalogue, and credit_treasury grants SELECT to anon and authenticated under a permissive read policy.

alter view public.v_credit_posture set (security_invoker = true);

comment on view public.v_credit_posture is
  'The credit posture, derived from the live catalogue rather than documented: no cash-out function '
  'exists, the transfer guard is installed, the supply is capped, and 1 credit = PHP1 fixed. These are the '
  'three facts that keep credits a closed-loop prepaid instrument rather than e-money or a security, so '
  'they are asserted by a gate instead of trusted. security_invoker since 20260803000022: an '
  'owner-executing view is a standing RLS bypass even when what it currently selects is harmless.';
