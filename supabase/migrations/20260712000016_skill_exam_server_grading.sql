-- 20260712000016_skill_exam_server_grading.sql
-- Dayplanner/Growth PDDA arc (2026-07-12) — X/I-axis keystone K1: lock skill-badge minting.
--
-- CONFABULATION VECTOR (live-confirmed): skillmatrix.html scored its exam ENTIRELY client-side
-- (submitExam: `const passed = score >= 7`) then the CLIENT directly inserted skill_exam_attempts
-- and upserted skill_badges (RLS allowed auth_uid=self). The AFTER-INSERT trigger
-- trg_skill_badge_achievement_xp() mints +250 XP (skill_climber). So a worker could console-mint
-- ANY discipline/level badge + 250 XP with NO real exam — forging BOTH the Skill-Matrix credential
-- AND Achievements XP (the skill_badge is a 250-XP source). No server grader existed
-- (usesServerGrading:false). The answer key lived only in client-side skill-content.js.
--
-- FIX (the community_xp-lockdown analog, security-skill DEFINER rules honored):
--   1. Move the answer key SERVER-SIDE into skill_exam_keys (RLS-on, NO client policy → the key can
--      never be read by a client; the DEFINER grader reads it as owner).
--   2. grade_skill_exam(discipline, level, answers[]) — SECURITY DEFINER + SET search_path=public.
--      Grades server-side against the locked key, resolves the caller's worker_name from
--      auth_worker_names() (client cannot spoof identity), records the attempt, and on a real pass
--      (>=7/10) awards the badge (idempotent; fires the existing +250 XP trigger, now trustworthy).
--   3. LOCK client writes: drop the client write policies on skill_badges + skill_exam_attempts.
--      Reads stay own-scoped. Only the DEFINER grader (+ service_role) writes them now.
--   REVOKE EXECUTE from public/anon, GRANT to authenticated (the PUBLIC-default blind spot).
-- Verified live: pre-fix client badge insert succeeds (exploit); post-fix 42501-blocked; the RPC
-- grades correct→pass→badge+XP, wrong→fail→no badge; skill_exam_keys unreadable by the client.
-- Idempotent (DROP IF EXISTS / CREATE OR REPLACE / ON CONFLICT DO NOTHING).

-- ── 1. Server-held answer key (25 exams × 10 questions; 0-based option indices, from skill-content.js) ──
CREATE TABLE IF NOT EXISTS public.skill_exam_keys (
  discipline  text    NOT NULL,
  level       int     NOT NULL,
  answer_key  int[]   NOT NULL,
  PRIMARY KEY (discipline, level)
);
ALTER TABLE public.skill_exam_keys ENABLE ROW LEVEL SECURITY;
-- No client policy: RLS-on + no permissive policy => anon/authenticated denied all access.
-- The DEFINER grader reads it as table owner (RLS not forced). Belt-and-suspenders revoke:
REVOKE ALL ON public.skill_exam_keys FROM anon, authenticated;

INSERT INTO public.skill_exam_keys (discipline, level, answer_key) VALUES
  ('Mechanical',1,'{1,2,1,2,1,2,1,2,1,2}'), ('Mechanical',2,'{1,1,2,2,1,2,1,1,1,1}'),
  ('Mechanical',3,'{1,1,1,2,1,2,1,1,1,1}'), ('Mechanical',4,'{1,2,1,1,2,1,1,1,1,1}'),
  ('Mechanical',5,'{1,1,1,2,1,1,2,1,2,1}'),
  ('Electrical',1,'{2,1,1,1,1,1,1,0,1,1}'), ('Electrical',2,'{1,2,2,1,1,2,1,1,1,1}'),
  ('Electrical',3,'{1,2,1,1,1,1,1,1,1,2}'), ('Electrical',4,'{1,0,1,1,1,2,1,1,1,1}'),
  ('Electrical',5,'{1,1,2,1,1,1,1,1,2,1}'),
  ('Instrumentation',1,'{1,1,1,0,1,1,1,1,1,2}'), ('Instrumentation',2,'{1,1,1,2,1,1,1,2,2,1}'),
  ('Instrumentation',3,'{1,2,2,1,2,1,1,1,1,1}'), ('Instrumentation',4,'{1,1,1,1,1,1,1,1,1,1}'),
  ('Instrumentation',5,'{1,1,0,1,1,1,1,1,1,1}'),
  ('Facilities Management',1,'{2,1,1,1,1,1,1,1,1,1}'), ('Facilities Management',2,'{3,2,1,2,1,1,1,1,1,1}'),
  ('Facilities Management',3,'{2,1,2,2,1,1,2,1,1,1}'), ('Facilities Management',4,'{1,1,1,1,1,1,1,2,1,1}'),
  ('Facilities Management',5,'{1,1,1,1,1,1,1,1,2,1}'),
  ('Production Lines',1,'{2,1,1,2,1,1,1,2,1,1}'), ('Production Lines',2,'{1,2,1,2,1,1,1,1,1,1}'),
  ('Production Lines',3,'{0,1,1,1,2,1,1,1,1,1}'), ('Production Lines',4,'{1,1,1,1,1,1,1,1,1,1}'),
  ('Production Lines',5,'{1,2,1,1,1,1,1,1,1,1}')
ON CONFLICT (discipline, level) DO UPDATE SET answer_key = EXCLUDED.answer_key;

-- ── 2. Server-side grader (SECURITY DEFINER) ──────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.grade_skill_exam(
  p_discipline text, p_level int, p_answers int[]
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  v_key     int[];
  v_worker  text;
  v_score   int := 0;
  v_passed  boolean;
  v_answers jsonb := '[]'::jsonb;
  i         int;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'authentication required';
  END IF;
  -- Resolve the caller's worker identity server-side (client cannot spoof worker_name).
  SELECT n INTO v_worker FROM auth_worker_names() AS n LIMIT 1;
  IF v_worker IS NULL THEN
    RAISE EXCEPTION 'no worker identity for this account';
  END IF;
  -- Fetch the server-held key (DEFINER reads past the key table's RLS as owner).
  SELECT answer_key INTO v_key FROM skill_exam_keys
    WHERE discipline = p_discipline AND level = p_level;
  IF v_key IS NULL THEN
    RAISE EXCEPTION 'unknown exam: % level %', p_discipline, p_level;
  END IF;
  IF p_answers IS NULL
     OR array_length(p_answers,1) IS DISTINCT FROM array_length(v_key,1) THEN
    RAISE EXCEPTION 'answer count mismatch (expected %)', array_length(v_key,1);
  END IF;
  -- Grade + build the per-question review jsonb (matches the old client shape).
  FOR i IN 1..array_length(v_key,1) LOOP
    IF p_answers[i] = v_key[i] THEN v_score := v_score + 1; END IF;
    v_answers := v_answers || jsonb_build_object(
      'q', i-1, 'chosen', p_answers[i], 'correct', (p_answers[i] = v_key[i]));
  END LOOP;
  v_passed := v_score >= 7;
  -- Record the attempt (server-authoritative; feeds the 24h cooldown).
  INSERT INTO skill_exam_attempts(worker_name, auth_uid, discipline, level, score, passed, answers, attempted_at)
  VALUES (v_worker, auth.uid(), p_discipline, p_level, v_score, v_passed, v_answers, now());
  -- Award the badge only on a real pass (idempotent; fires trg_skill_badge_achievement_xp → +250 XP).
  IF v_passed THEN
    INSERT INTO skill_badges(worker_name, auth_uid, discipline, level, exam_score, earned_at)
    VALUES (v_worker, auth.uid(), p_discipline, p_level, v_score, now())
    ON CONFLICT (worker_name, discipline, level) DO NOTHING;
  END IF;
  RETURN jsonb_build_object('score', v_score, 'passed', v_passed, 'worker_name', v_worker);
END;
$$;

REVOKE ALL ON FUNCTION public.grade_skill_exam(text,int,int[]) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.grade_skill_exam(text,int,int[]) TO authenticated, service_role;

-- ── 3. Lock client writes on the credential + attempt tables (grader/service-role only) ────────
DROP POLICY IF EXISTS skill_badges_write        ON public.skill_badges;
DROP POLICY IF EXISTS skill_exam_attempts_write ON public.skill_exam_attempts;
-- Reads stay own-scoped (skill_badges_read / skill_exam_attempts_read unchanged). With RLS enabled
-- and no permissive write policy, client INSERT/UPDATE/DELETE is denied; the SECURITY DEFINER
-- grade_skill_exam() (and the service-role seeders) are the only writers.
