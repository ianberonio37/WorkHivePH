-- ★CROSS-TENANT IDOR: two SECURITY DEFINER XP functions were EXECUTABLE by `authenticated`.
--
-- FOUND BY tools/validate_definer_tenant_gate.py (Arc G G1), which reported 2 ungated DEFINER
-- mutators against a baseline of 0. Confirmed against the live catalog rather than inferred:
--
--   proname                    | args           | returns | authenticated may EXECUTE
--   reverse_community_post_xp  | p_post_id uuid | void    | TRUE
--   restore_community_post_xp  | p_post_id uuid | void    | TRUE
--
-- Both are SECURITY DEFINER (so RLS never applies) and both derive hive_id FROM THE ROW they are
-- given rather than checking the caller against it. Their bodies contain no membership test at all:
-- they select the award rows WHERE post_id = p_post_id and act on whatever hive those rows name.
--
-- So any signed-in user could run
--     select reverse_community_post_xp('<any post uuid>');
-- and strip a community author's XP in ANY hive -- or restore_community_post_xp() to award XP into
-- a foreign hive. Neither needs membership, a role, or any relationship to the post.
--
-- WHY A REVOKE RATHER THAN A MEMBERSHIP GATE. These are not user-facing RPCs. A repo-wide search of
-- every .html/.js/.ts/.mjs finds NO client caller; their only invocation is from
-- tg_community_post_xp_lifecycle (20260806000059:171-173), the trigger that fires when a post is
-- soft-deleted or restored. A DEFINER function invoked from a trigger owned by postgres is
-- unaffected by client EXECUTE privileges, so this closes the hole with no behavioural change.
--
-- This is exactly the protection award_achievement_xp has carried since 2026-05
-- (20260508000002:215): "Block direct client calls: XP must come from DB triggers only."
-- The reversal side was simply never given the same treatment -- the same asymmetry that left
-- trg_logbook_xp_reverse SECURITY INVOKER while its award counterpart was DEFINER.

-- ★AND THE PRECEDENT ITSELF WAS BROKEN, WHICH IS WHY THIS REVOKES **PUBLIC**.
-- Checking award_achievement_xp's actual ACL rather than trusting its migration comment:
--
--   award_achievement_xp       =X/postgres, postgres=X/postgres, service_role=X/postgres
--   reverse_community_post_xp  =X/postgres, postgres=X/postgres, anon=X/…, authenticated=X/…
--
-- The LEADING `=X/postgres` is a grant to PUBLIC -- the default every function is created with.
-- The 2026-05 statement revoked anon and authenticated (they are absent above) and left PUBLIC
-- untouched, so `authenticated` still inherits EXECUTE through PUBLIC:
--     has_function_privilege('authenticated','award_achievement_xp(...)','EXECUTE') -> TRUE
-- i.e. the platform's canonical "XP must come from DB triggers only" guard has never held, and any
-- signed-in user can still award themselves arbitrary XP. Revoking only the named roles is the
-- no-op this migration would have shipped had the ACL not been read.
--
-- So: revoke PUBLIC first (kills the inherited path), then the explicitly-granted roles, and repair
-- award_achievement_xp while we are here -- it is the function whose protection everything else was
-- modelled on.

BEGIN;

REVOKE EXECUTE ON FUNCTION public.reverse_community_post_xp(uuid) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.restore_community_post_xp(uuid) FROM PUBLIC, anon, authenticated;

-- The original guard, made real. Its own migration says "Block direct client calls: XP must come
-- from DB triggers only" (20260508000002:215); until now that sentence was aspirational.
REVOKE EXECUTE ON FUNCTION public.award_achievement_xp(text, text, int, text, text)
  FROM PUBLIC, anon, authenticated;

-- ★AND A PUSH-SPOOFING VECTOR FOUND BY THE SAME SWEEP. enqueue_service_push_uids is DEFINER, PUBLIC
-- holds EXECUTE, and its body has NO auth.uid() and NO membership test -- it inserts whatever it is
-- given straight into service_outbox for the notify-push consumer:
--     INSERT INTO public.service_outbox (consumer, payload)
--     VALUES ('notify-push', jsonb_build_object('auth_uids', ..., 'title', ..., 'body', ..., 'url', ...))
-- so any signed-in user could push an arbitrary title/body/URL to ANY user on the platform -- a
-- notification that looks like it came from WorkHive, carrying a link the sender chose.
-- Its only invocation is a trigger in 20260729000018 (service cancellation); no client and no edge
-- function calls it, so the revoke costs nothing.
REVOKE EXECUTE ON FUNCTION public.enqueue_service_push_uids(uuid[], text, text, text)
  FROM PUBLIC, anon, authenticated;

-- NOT REVOKED, DELIBERATELY, though the same sweep flagged them: store_memory_turn and
-- update_dialog_state are called from the CLIENT (voice-handler.js:1017 and :1342) and both gate
-- themselves internally (6 and 3 references to auth.uid()/hive_members). Their stale REVOKE lines
-- are load-bearing precisely BECAUSE they never took effect -- had they worked, the voice journal
-- would be broken. A membership check inside is the right protection for an RPC a page calls; a
-- revoke would be an outage wearing a security fix's clothes.

COMMIT;
