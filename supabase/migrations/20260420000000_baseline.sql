-- ============================================================
-- Extensions required by the dumped schema (added for local dev)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA "public";
CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "public";
CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA "public";
-- ============================================================


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE OR REPLACE FUNCTION "public"."check_listing_rate"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
DECLARE daily_count integer;
BEGIN
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO daily_count
    FROM public.marketplace_listings
    WHERE hive_id = NEW.hive_id
      AND created_at > NOW() - INTERVAL '24 hours';
  IF daily_count >= 20 THEN
    RAISE EXCEPTION 'Daily listing limit of 20 reached for this hive';
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."check_listing_rate"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."community_post_rate_limit"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF (
    SELECT count(*) FROM community_posts
    WHERE author_name = NEW.author_name
      AND hive_id = NEW.hive_id
      AND created_at > NOW() - INTERVAL '30 seconds'
  ) >= 3 THEN
    RAISE EXCEPTION 'Posting too fast. Wait a few seconds.'
      USING HINT = 'rate_limit';
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."community_post_rate_limit"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."community_reply_rate_limit"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF (
    SELECT count(*) FROM community_replies
    WHERE author_name = NEW.author_name
      AND hive_id = NEW.hive_id
      AND created_at > NOW() - INTERVAL '15 seconds'
  ) >= 5 THEN
    RAISE EXCEPTION 'Replying too fast. Wait a few seconds.'
      USING HINT = 'rate_limit';
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."community_reply_rate_limit"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_downtime_pareto"("p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" DEFAULT NULL::"text", "p_period_days" integer DEFAULT 90) RETURNS TABLE("machine" "text", "downtime_hours" numeric, "pct_of_total" numeric, "cumulative_pct" numeric)
    LANGUAGE "sql" STABLE
    AS $$
  WITH totals AS (
    SELECT
      machine,
      ROUND(SUM(downtime_hours)::numeric, 1) AS downtime_hours
    FROM logbook
    WHERE maintenance_type = 'Breakdown / Corrective'
      AND downtime_hours   > 0
      AND created_at      >= NOW() - (p_period_days || ' days')::interval
      AND (p_hive_id IS NULL OR hive_id = p_hive_id)
      AND (p_worker  IS NULL OR worker_name = p_worker)
    GROUP BY machine
  ),
  grand AS (SELECT SUM(downtime_hours) AS grand_total FROM totals)
  SELECT
    t.machine,
    t.downtime_hours,
    ROUND(t.downtime_hours / g.grand_total * 100, 1)   AS pct_of_total,
    ROUND(
      SUM(t.downtime_hours) OVER (ORDER BY t.downtime_hours DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
      / g.grand_total * 100,
    1) AS cumulative_pct
  FROM totals t, grand g
  ORDER BY t.downtime_hours DESC;
$$;


ALTER FUNCTION "public"."get_downtime_pareto"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_failure_frequency"("p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" DEFAULT NULL::"text", "p_period_days" integer DEFAULT 90) RETURNS TABLE("machine" "text", "failure_count" bigint)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    machine,
    COUNT(*) AS failure_count
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY COUNT(*) DESC;
$$;


ALTER FUNCTION "public"."get_failure_frequency"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_mtbf_by_machine"("p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" DEFAULT NULL::"text", "p_period_days" integer DEFAULT 90) RETURNS TABLE("machine" "text", "failure_count" bigint, "mtbf_days" numeric, "min_interval_days" numeric, "max_interval_days" numeric)
    LANGUAGE "sql" STABLE
    AS $$
  WITH failures AS (
    SELECT
      machine,
      created_at,
      LAG(created_at) OVER (PARTITION BY machine ORDER BY created_at) AS prev_failure
    FROM logbook
    WHERE maintenance_type = 'Breakdown / Corrective'
      AND created_at >= NOW() - (p_period_days || ' days')::interval
      AND (p_hive_id IS NULL OR hive_id = p_hive_id)
      AND (p_worker  IS NULL OR worker_name = p_worker)
  ),
  intervals AS (
    SELECT
      machine,
      EXTRACT(EPOCH FROM (created_at - prev_failure)) / 86400.0 AS interval_days
    FROM failures
    WHERE prev_failure IS NOT NULL
  )
  SELECT
    machine,
    COUNT(*) + 1                              AS failure_count,
    ROUND(AVG(interval_days)::numeric, 1)    AS mtbf_days,
    ROUND(MIN(interval_days)::numeric, 1)    AS min_interval_days,
    ROUND(MAX(interval_days)::numeric, 1)    AS max_interval_days
  FROM intervals
  GROUP BY machine
  HAVING COUNT(*) >= 1  -- need at least 2 failures (1 interval)
  ORDER BY AVG(interval_days) ASC;  -- worst (shortest MTBF) first
$$;


ALTER FUNCTION "public"."get_mtbf_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_mttr_by_machine"("p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" DEFAULT NULL::"text", "p_period_days" integer DEFAULT 90) RETURNS TABLE("machine" "text", "repair_count" bigint, "total_downtime_h" numeric, "mttr_hours" numeric)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    machine,
    COUNT(*)                                        AS repair_count,
    ROUND(SUM(downtime_hours)::numeric, 1)          AS total_downtime_h,
    ROUND(AVG(downtime_hours)::numeric, 1)          AS mttr_hours
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND status            = 'Closed'
    AND downtime_hours    > 0
    AND created_at       >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine
  ORDER BY AVG(downtime_hours) DESC;  -- worst (longest MTTR) first
$$;


ALTER FUNCTION "public"."get_mttr_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_repeat_failures"("p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" DEFAULT NULL::"text", "p_period_days" integer DEFAULT 90) RETURNS TABLE("machine" "text", "root_cause" "text", "occurrences" bigint)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    machine,
    root_cause,
    COUNT(*) AS occurrences
  FROM logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND root_cause IS NOT NULL
    AND root_cause <> ''
    AND created_at >= NOW() - (p_period_days || ' days')::interval
    AND (p_hive_id IS NULL OR hive_id = p_hive_id)
    AND (p_worker  IS NULL OR worker_name = p_worker)
  GROUP BY machine, root_cause
  HAVING COUNT(*) >= 2
  ORDER BY COUNT(*) DESC;
$$;


ALTER FUNCTION "public"."get_repeat_failures"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_community_post_xp"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  post_count integer;
BEGIN
  SELECT COUNT(*) INTO post_count
  FROM community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id;

  -- First post in this hive: +50 XP
  IF post_count = 1 THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 50);
  END IF;

  -- Safety category: +25 XP (stacks with first-post bonus)
  IF NEW.category = 'safety' THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 25);
  END IF;

  -- 10th post milestone: Voice of the Hive badge
  IF post_count = 10 THEN
    INSERT INTO skill_badges (worker_name, discipline, level, badge_key, earned_at)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now())
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_community_post_xp"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_community_reaction_xp"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  reaction_count integer;
  v_author       text;
  v_hive_id      uuid;
BEGIN
  SELECT COUNT(*) INTO reaction_count
  FROM community_reactions WHERE post_id = NEW.post_id;

  -- Award +20 XP to the post author the moment their post hits exactly 3 reactions
  IF reaction_count = 3 THEN
    SELECT author_name, hive_id INTO v_author, v_hive_id
    FROM community_posts WHERE id = NEW.post_id;
    IF v_author IS NOT NULL THEN
      PERFORM increment_community_xp(v_author, v_hive_id, 20);
    END IF;
  END IF;

  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_community_reaction_xp"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_community_reply_xp"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 10);
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_community_reply_xp"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."increment_community_xp"("p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integer) RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  INSERT INTO community_xp (worker_name, hive_id, xp_total, updated_at)
  VALUES (p_worker_name, p_hive_id, p_amount, now())
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = community_xp.xp_total + p_amount,
      updated_at = now();
END;
$$;


ALTER FUNCTION "public"."increment_community_xp"("p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."increment_listing_view"("p_listing_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
BEGIN
  UPDATE public.marketplace_listings
  SET view_count = view_count + 1
  WHERE id = p_listing_id
    AND status = 'published';   -- only count views on live listings
END;
$$;


ALTER FUNCTION "public"."increment_listing_view"("p_listing_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_all_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 3) RETURNS TABLE("source" "text", "summary" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT source, summary, similarity FROM (
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM fault_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) f

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'skill' AS source,
      CONCAT('Worker: ', worker_name, ' | Discipline: ', discipline,
             ' | Level: ', level::text, ' | Primary: ', primary_skill) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM skill_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) s

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'pm' AS source,
      CONCAT('Asset: ', asset_name, ' | Category: ', category,
             ' | Overdue tasks: ', overdue_count::text, ' | ', health_summary) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM pm_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) p;
$$;


ALTER FUNCTION "public"."search_all_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_bom_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "project_name" "text", "calc_type" "text", "key_spec" "text", "item_count" integer, "notes" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    id, project_name, calc_type, key_spec, item_count, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM bom_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_bom_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_calc_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "calc_type" "text", "project_ref" "text", "key_inputs" "jsonb", "key_outputs" "jsonb", "notes" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    id, calc_type, project_ref, key_inputs, key_outputs, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM calc_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_calc_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_fault_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "machine" "text", "problem" "text", "root_cause" "text", "action" "text", "knowledge" "text", "worker_name" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    id, machine, problem, root_cause, action, knowledge, worker_name,
    1 - (embedding <=> query_embedding) AS similarity
  FROM fault_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_fault_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_pm_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "asset_name" "text", "category" "text", "overdue_count" integer, "last_completed" timestamp with time zone, "health_summary" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    id, asset_name, category, overdue_count, last_completed, health_summary,
    1 - (embedding <=> query_embedding) AS similarity
  FROM pm_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_pm_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_skill_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "worker_name" "text", "discipline" "text", "level" integer, "primary_skill" "text", "similarity" double precision)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT
    id, worker_name, discipline, level, primary_skill,
    1 - (embedding <=> query_embedding) AS similarity
  FROM skill_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_skill_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."sync_auth_uid_on_signup"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  UPDATE hive_members           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE logbook                SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE community_posts        SET auth_uid = NEW.auth_uid WHERE author_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_items        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE assets                 SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE pm_completions         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE schedule_items         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_profiles         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_badges           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE skill_exam_attempts    SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE engineering_calcs      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."sync_auth_uid_on_signup"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_seller_rating"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
  v_seller_name text;
  v_new_avg     numeric(3,2);
  v_new_count   integer;
BEGIN
  -- Find the seller from the reviewed listing
  SELECT seller_name INTO v_seller_name
  FROM public.marketplace_listings
  WHERE id = NEW.listing_id;

  IF v_seller_name IS NULL THEN
    RETURN NEW;
  END IF;

  -- Compute new average and count across all this seller's listings
  SELECT
    ROUND(AVG(r.rating::numeric), 2),
    COUNT(*)::integer
  INTO v_new_avg, v_new_count
  FROM public.marketplace_reviews r
  JOIN public.marketplace_listings l ON r.listing_id = l.id
  WHERE l.seller_name = v_seller_name;

  -- Upsert seller profile (creates row if first review)
  INSERT INTO public.marketplace_sellers (worker_name, rating_avg, rating_count, updated_at)
  VALUES (v_seller_name, v_new_avg, v_new_count, now())
  ON CONFLICT (worker_name) DO UPDATE SET
    rating_avg   = v_new_avg,
    rating_count = v_new_count,
    updated_at   = now();

  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_seller_rating"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_seller_tier"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF NEW.status = 'released' AND OLD.status <> 'released' THEN
    INSERT INTO public.marketplace_sellers (worker_name, total_sales, tier)
    VALUES (NEW.seller_name, 1, 'bronze')
    ON CONFLICT (worker_name) DO UPDATE SET
      total_sales = marketplace_sellers.total_sales + 1,
      tier = CASE
        WHEN marketplace_sellers.total_sales + 1 >= 51 THEN 'gold'
        WHEN marketplace_sellers.total_sales + 1 >= 11 THEN 'silver'
        ELSE 'bronze'
      END,
      updated_at = now();
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_seller_tier"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."ai_reports" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "report_type" "text" NOT NULL,
    "generated_at" timestamp with time zone DEFAULT "now"(),
    "report_json" "jsonb",
    "summary" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."ai_reports" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."assets" (
    "id" "text" NOT NULL,
    "worker_name" "text" NOT NULL,
    "asset_id" "text" NOT NULL,
    "name" "text" DEFAULT ''::"text",
    "type" "text" DEFAULT ''::"text",
    "location" "text" DEFAULT ''::"text",
    "criticality" "text" DEFAULT ''::"text",
    "registered_at" timestamp with time zone DEFAULT "now"(),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'approved'::"text",
    "hive_id" "uuid",
    "submitted_by" "text",
    "approved_by" "text",
    "approved_at" timestamp with time zone,
    "auth_uid" "uuid"
);


ALTER TABLE "public"."assets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."automation_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "job_name" "text" NOT NULL,
    "hive_id" "uuid",
    "triggered_at" timestamp with time zone DEFAULT "now"(),
    "status" "text",
    "detail" "text",
    CONSTRAINT "automation_log_status_check" CHECK (("status" = ANY (ARRAY['success'::"text", 'failed'::"text", 'skipped'::"text"])))
);


ALTER TABLE "public"."automation_log" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bom_knowledge" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "project_name" "text",
    "calc_type" "text",
    "key_spec" "text",
    "item_count" integer DEFAULT 0,
    "notes" "text",
    "embedding" "public"."vector"(384),
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."bom_knowledge" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."calc_knowledge" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "calc_type" "text",
    "project_ref" "text",
    "key_inputs" "jsonb",
    "key_outputs" "jsonb",
    "notes" "text",
    "embedding" "public"."vector"(384),
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."calc_knowledge" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."community_posts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid" NOT NULL,
    "author_name" "text" NOT NULL,
    "content" "text" NOT NULL,
    "category" "text" DEFAULT 'general'::"text" NOT NULL,
    "pinned" boolean DEFAULT false NOT NULL,
    "flagged" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "auth_uid" "uuid",
    "public" boolean DEFAULT false NOT NULL,
    "edited_at" timestamp with time zone,
    "deleted_at" timestamp with time zone,
    "mentions" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    CONSTRAINT "community_posts_category_check" CHECK (("category" = ANY (ARRAY['general'::"text", 'safety'::"text", 'technical'::"text", 'announcement'::"text"]))),
    CONSTRAINT "community_posts_content_check" CHECK ((("char_length"("content") >= 1) AND ("char_length"("content") <= 2000)))
);


ALTER TABLE "public"."community_posts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."community_reactions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "post_id" "uuid" NOT NULL,
    "hive_id" "uuid" NOT NULL,
    "worker_name" "text" NOT NULL,
    "emoji" "text" DEFAULT 'thumbs_up'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "community_reactions_emoji_check" CHECK (("emoji" = ANY (ARRAY['thumbs_up'::"text", 'wrench'::"text", 'fire'::"text", 'eyes'::"text"])))
);


ALTER TABLE "public"."community_reactions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."community_replies" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "post_id" "uuid" NOT NULL,
    "hive_id" "uuid" NOT NULL,
    "author_name" "text" NOT NULL,
    "content" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "community_replies_content_check" CHECK ((("char_length"("content") >= 1) AND ("char_length"("content") <= 1000)))
);


ALTER TABLE "public"."community_replies" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."community_xp" (
    "worker_name" "text" NOT NULL,
    "hive_id" "uuid" NOT NULL,
    "xp_total" integer DEFAULT 0 NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."community_xp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."early_access_emails" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "email" "text" NOT NULL,
    "signed_up_at" timestamp with time zone DEFAULT "now"(),
    "source" "text" DEFAULT 'landing_page'::"text"
);


ALTER TABLE "public"."early_access_emails" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."engineering_calcs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "worker_name" "text",
    "discipline" "text",
    "calc_type" "text",
    "project_name" "text",
    "inputs" "jsonb",
    "results" "jsonb",
    "narrative" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "bom_data" "jsonb",
    "sow_text" "text",
    "auth_uid" "uuid"
);


ALTER TABLE "public"."engineering_calcs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."equipment_reading_templates" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "category" "text" NOT NULL,
    "reading_key" "text" NOT NULL,
    "label" "text" NOT NULL,
    "unit" "text" NOT NULL,
    "placeholder" "text" NOT NULL,
    "sort_order" integer DEFAULT 0,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."equipment_reading_templates" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fault_knowledge" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "logbook_id" "text",
    "machine" "text",
    "category" "text",
    "problem" "text",
    "root_cause" "text",
    "action" "text",
    "knowledge" "text",
    "worker_name" "text",
    "embedding" "public"."vector"(384),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "embedding_model" "text" DEFAULT 'nomic-embed-text-v1_5'::"text",
    "maintenance_type" "text"
);


ALTER TABLE "public"."fault_knowledge" OWNER TO "postgres";


COMMENT ON TABLE "public"."fault_knowledge" IS 'RAG knowledge base for fault history. Schema v2: worker_name, embedding_model, maintenance_type added 2026-04-29.';



CREATE TABLE IF NOT EXISTS "public"."hive_analytics_cache" (
    "hive_id" "uuid" NOT NULL,
    "mtbf_by_machine" "jsonb",
    "mttr_by_machine" "jsonb",
    "computed_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."hive_analytics_cache" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."hive_audit_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid" NOT NULL,
    "actor" "text" NOT NULL,
    "action" "text" NOT NULL,
    "target_type" "text",
    "target_id" "text",
    "target_name" "text",
    "meta" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."hive_audit_log" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."hive_members" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "worker_name" "text" NOT NULL,
    "role" "text" DEFAULT 'worker'::"text" NOT NULL,
    "joined_at" timestamp with time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "auth_uid" "uuid",
    CONSTRAINT "hive_members_role_check" CHECK (("role" = ANY (ARRAY['worker'::"text", 'supervisor'::"text"])))
);


ALTER TABLE "public"."hive_members" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."hives" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "invite_code" character(6) NOT NULL,
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."hives" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."inventory_items" (
    "id" "text" NOT NULL,
    "worker_name" "text" NOT NULL,
    "part_number" "text" DEFAULT ''::"text" NOT NULL,
    "part_name" "text" DEFAULT ''::"text" NOT NULL,
    "category" "text" DEFAULT ''::"text",
    "unit" "text" DEFAULT 'pcs'::"text",
    "qty_on_hand" numeric DEFAULT 0 NOT NULL,
    "min_qty" numeric DEFAULT 0 NOT NULL,
    "bin_location" "text" DEFAULT ''::"text",
    "linked_asset_ids" "text"[] DEFAULT '{}'::"text"[],
    "notes" "text" DEFAULT ''::"text",
    "photo" "text" DEFAULT ''::"text",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'approved'::"text",
    "hive_id" "uuid",
    "submitted_by" "text",
    "approved_by" "text",
    "approved_at" timestamp with time zone,
    "auth_uid" "uuid"
);


ALTER TABLE "public"."inventory_items" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."inventory_transactions" (
    "id" "text" NOT NULL,
    "worker_name" "text" NOT NULL,
    "item_id" "text" NOT NULL,
    "type" "text" NOT NULL,
    "qty_change" numeric NOT NULL,
    "qty_after" numeric NOT NULL,
    "note" "text" DEFAULT ''::"text",
    "job_ref" "text" DEFAULT ''::"text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "hive_id" "uuid",
    "auth_uid" "uuid"
);


ALTER TABLE "public"."inventory_transactions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."logbook" (
    "id" "text" NOT NULL,
    "worker_name" "text" NOT NULL,
    "date" timestamp with time zone NOT NULL,
    "machine" "text",
    "category" "text",
    "problem" "text",
    "action" "text",
    "knowledge" "text",
    "photo" "text",
    "status" "text" DEFAULT 'Open'::"text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "maintenance_type" "text",
    "root_cause" "text",
    "downtime_hours" numeric,
    "hive_id" "uuid",
    "asset_ref_id" "text",
    "parts_used" "jsonb" DEFAULT '[]'::"jsonb",
    "closed_at" timestamp with time zone,
    "tasklist_acknowledged" boolean DEFAULT false,
    "tasklist_note" "text",
    "pm_completion_id" "uuid",
    "failure_consequence" "text",
    "readings_json" "jsonb",
    "production_output" "jsonb",
    "auth_uid" "uuid"
);


ALTER TABLE "public"."logbook" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_disputes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "order_id" "uuid",
    "listing_id" "uuid",
    "opened_by" "text" NOT NULL,
    "seller_name" "text" NOT NULL,
    "reason" "text" NOT NULL,
    "evidence_urls" "text"[],
    "status" "text" DEFAULT 'open'::"text" NOT NULL,
    "seller_reply" "text",
    "seller_replied_at" timestamp with time zone,
    "admin_decision" "text",
    "admin_decided_at" timestamp with time zone,
    "resolved_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "marketplace_disputes_status_check" CHECK (("status" = ANY (ARRAY['open'::"text", 'seller_responded'::"text", 'admin_review'::"text", 'resolved_refund'::"text", 'resolved_release'::"text"])))
);


ALTER TABLE "public"."marketplace_disputes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_inquiries" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "listing_id" "uuid",
    "hive_id" "uuid",
    "buyer_name" "text" NOT NULL,
    "buyer_contact" "text",
    "message" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "seller_name" "text",
    "reply_text" "text",
    "replied_at" timestamp with time zone,
    CONSTRAINT "marketplace_inquiries_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'replied'::"text", 'closed'::"text"])))
);


ALTER TABLE "public"."marketplace_inquiries" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_listings" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "seller_name" "text" NOT NULL,
    "seller_contact" "text",
    "seller_verified" boolean DEFAULT false NOT NULL,
    "completed_sales" integer DEFAULT 0 NOT NULL,
    "rating_avg" numeric(3,2),
    "section" "text" NOT NULL,
    "category" "text",
    "title" "text" NOT NULL,
    "description" "text",
    "price" numeric(14,2),
    "condition" "text",
    "location" "text",
    "image_url" "text",
    "status" "text" DEFAULT 'draft'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "search_vector" "tsvector" GENERATED ALWAYS AS ("to_tsvector"('"english"'::"regconfig", ((((((((COALESCE("title", ''::"text") || ' '::"text") || COALESCE("description", ''::"text")) || ' '::"text") || COALESCE("category", ''::"text")) || ' '::"text") || COALESCE("location", ''::"text")) || ' '::"text") || COALESCE("seller_name", ''::"text")))) STORED,
    "view_count" integer DEFAULT 0 NOT NULL,
    CONSTRAINT "marketplace_listings_condition_check" CHECK (("condition" = ANY (ARRAY['new'::"text", 'used'::"text", 'refurb'::"text"]))),
    CONSTRAINT "marketplace_listings_section_check" CHECK (("section" = ANY (ARRAY['parts'::"text", 'training'::"text", 'jobs'::"text"]))),
    CONSTRAINT "marketplace_listings_status_check" CHECK (("status" = ANY (ARRAY['draft'::"text", 'published'::"text", 'sold'::"text", 'removed'::"text"])))
);


ALTER TABLE "public"."marketplace_listings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_orders" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "listing_id" "uuid",
    "hive_id" "uuid",
    "buyer_name" "text" NOT NULL,
    "seller_name" "text" NOT NULL,
    "price" numeric(14,2) NOT NULL,
    "currency" "text" DEFAULT 'PHP'::"text" NOT NULL,
    "stripe_session_id" "text",
    "stripe_payment_id" "text",
    "stripe_transfer_id" "text",
    "status" "text" DEFAULT 'pending_payment'::"text" NOT NULL,
    "escrow_release_at" timestamp with time zone,
    "buyer_confirmed_at" timestamp with time zone,
    "released_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "reviewed_at" timestamp with time zone,
    CONSTRAINT "marketplace_orders_status_check" CHECK (("status" = ANY (ARRAY['pending_payment'::"text", 'escrow_hold'::"text", 'buyer_confirmed'::"text", 'released'::"text", 'refunded'::"text", 'disputed'::"text"])))
);


ALTER TABLE "public"."marketplace_orders" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_platform_admins" (
    "worker_name" "text" NOT NULL,
    "granted_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "granted_by" "text" NOT NULL
);


ALTER TABLE "public"."marketplace_platform_admins" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_reviews" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "listing_id" "uuid",
    "reviewer_name" "text" NOT NULL,
    "rating" integer NOT NULL,
    "comment" "text",
    "verified_purchase" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "marketplace_reviews_rating_check" CHECK ((("rating" >= 1) AND ("rating" <= 5)))
);


ALTER TABLE "public"."marketplace_reviews" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_saved_searches" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "email" "text",
    "search_name" "text" NOT NULL,
    "section" "text",
    "category" "text",
    "query_text" "text",
    "price_min" numeric(14,2),
    "price_max" numeric(14,2),
    "last_sent_at" timestamp with time zone,
    "active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."marketplace_saved_searches" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_sellers" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "auth_uid" "uuid",
    "hive_id" "uuid",
    "tier" "text" DEFAULT 'bronze'::"text" NOT NULL,
    "kyb_verified" boolean DEFAULT false NOT NULL,
    "kyb_verified_at" timestamp with time zone,
    "total_sales" integer DEFAULT 0 NOT NULL,
    "rating_avg" numeric(3,2),
    "rating_count" integer DEFAULT 0 NOT NULL,
    "response_rate" numeric(5,2),
    "response_time_h" numeric(6,1),
    "stripe_account_id" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "messenger_username" "text",
    "certifications" "text",
    "cert_verified" boolean DEFAULT false NOT NULL,
    "cert_verified_at" timestamp with time zone,
    CONSTRAINT "marketplace_sellers_tier_check" CHECK (("tier" = ANY (ARRAY['bronze'::"text", 'silver'::"text", 'gold'::"text"])))
);


ALTER TABLE "public"."marketplace_sellers" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."marketplace_watchlist" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "listing_id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."marketplace_watchlist" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."parts_records" (
    "id" bigint NOT NULL,
    "worker_name" "text" NOT NULL,
    "job_ref" "text",
    "job_type" "text",
    "date" "text",
    "duration" bigint,
    "parts" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "hive_id" "uuid",
    "asset_ref_id" "text"
);


ALTER TABLE "public"."parts_records" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."pm_assets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "worker_name" "text" NOT NULL,
    "asset_name" "text" NOT NULL,
    "tag_id" "text",
    "location" "text",
    "category" "text" NOT NULL,
    "criticality" "text" DEFAULT 'Major'::"text",
    "last_anchor_date" "date",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "auth_uid" "uuid"
);


ALTER TABLE "public"."pm_assets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."pm_completions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "asset_id" "uuid",
    "scope_item_id" "uuid",
    "hive_id" "uuid",
    "worker_name" "text" NOT NULL,
    "status" "text" DEFAULT 'done'::"text",
    "notes" "text",
    "completed_at" timestamp with time zone DEFAULT "now"(),
    "auth_uid" "uuid"
);


ALTER TABLE "public"."pm_completions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."pm_knowledge" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "asset_id" "uuid",
    "asset_name" "text",
    "category" "text",
    "overdue_count" integer DEFAULT 0,
    "last_completed" timestamp with time zone,
    "health_summary" "text",
    "embedding" "public"."vector"(384),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "worker_name" "text",
    "embedding_model" "text" DEFAULT 'nomic-embed-text-v1_5'::"text"
);


ALTER TABLE "public"."pm_knowledge" OWNER TO "postgres";


COMMENT ON TABLE "public"."pm_knowledge" IS 'RAG knowledge base for PM health snapshots. Schema v2: worker_name, embedding_model added 2026-04-29.';



CREATE TABLE IF NOT EXISTS "public"."pm_scope_items" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "asset_id" "uuid",
    "hive_id" "uuid",
    "item_text" "text" NOT NULL,
    "frequency" "text" NOT NULL,
    "anchor_date" "date",
    "is_custom" boolean DEFAULT false,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."pm_scope_items" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."report_contacts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "name" "text" NOT NULL,
    "email" "text",
    "label" "text" DEFAULT 'Team'::"text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."report_contacts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."schedule_items" (
    "id" "text" NOT NULL,
    "worker_name" "text" NOT NULL,
    "title" "text",
    "date" "text",
    "start_time" "text",
    "end_time" "text",
    "category" "text",
    "notes" "text",
    "logbook_ref" "text",
    "item_status" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "auth_uid" "uuid"
);


ALTER TABLE "public"."schedule_items" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."skill_badges" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "discipline" "text" NOT NULL,
    "level" integer NOT NULL,
    "earned_at" timestamp with time zone DEFAULT "now"(),
    "exam_score" integer NOT NULL,
    "auth_uid" "uuid",
    CONSTRAINT "skill_badges_level_check" CHECK ((("level" >= 1) AND ("level" <= 5)))
);


ALTER TABLE "public"."skill_badges" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."skill_exam_attempts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "discipline" "text" NOT NULL,
    "level" integer NOT NULL,
    "score" integer NOT NULL,
    "passed" boolean NOT NULL,
    "answers" "jsonb",
    "attempted_at" timestamp with time zone DEFAULT "now"(),
    "auth_uid" "uuid"
);


ALTER TABLE "public"."skill_exam_attempts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."skill_knowledge" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "hive_id" "uuid",
    "worker_name" "text",
    "discipline" "text",
    "level" integer,
    "primary_skill" "text",
    "embedding" "public"."vector"(384),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "embedding_model" "text" DEFAULT 'nomic-embed-text-v1_5'::"text"
);


ALTER TABLE "public"."skill_knowledge" OWNER TO "postgres";


COMMENT ON TABLE "public"."skill_knowledge" IS 'RAG knowledge base for worker skill profiles. Schema v2: embedding_model added 2026-04-29.';



CREATE TABLE IF NOT EXISTS "public"."skill_profiles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "worker_name" "text" NOT NULL,
    "primary_skill" "text" NOT NULL,
    "targets" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "auth_uid" "uuid"
);


ALTER TABLE "public"."skill_profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."worker_profiles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "auth_uid" "uuid" NOT NULL,
    "username" "text" NOT NULL,
    "display_name" "text" NOT NULL,
    "email" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "worker_profiles_display_name_check" CHECK ((("char_length"("display_name") >= 1) AND ("char_length"("display_name") <= 50))),
    CONSTRAINT "worker_profiles_username_check" CHECK (("username" ~ '^[a-z0-9_]{3,30}$'::"text"))
);


ALTER TABLE "public"."worker_profiles" OWNER TO "postgres";


ALTER TABLE ONLY "public"."ai_reports"
    ADD CONSTRAINT "ai_reports_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."assets"
    ADD CONSTRAINT "assets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."automation_log"
    ADD CONSTRAINT "automation_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."bom_knowledge"
    ADD CONSTRAINT "bom_knowledge_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."calc_knowledge"
    ADD CONSTRAINT "calc_knowledge_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."community_posts"
    ADD CONSTRAINT "community_posts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."community_reactions"
    ADD CONSTRAINT "community_reactions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."community_reactions"
    ADD CONSTRAINT "community_reactions_post_id_worker_name_emoji_key" UNIQUE ("post_id", "worker_name", "emoji");



ALTER TABLE ONLY "public"."community_replies"
    ADD CONSTRAINT "community_replies_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."community_xp"
    ADD CONSTRAINT "community_xp_pkey" PRIMARY KEY ("worker_name", "hive_id");



ALTER TABLE ONLY "public"."early_access_emails"
    ADD CONSTRAINT "early_access_emails_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."engineering_calcs"
    ADD CONSTRAINT "engineering_calcs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."equipment_reading_templates"
    ADD CONSTRAINT "equipment_reading_templates_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."fault_knowledge"
    ADD CONSTRAINT "fault_knowledge_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."hive_analytics_cache"
    ADD CONSTRAINT "hive_analytics_cache_pkey" PRIMARY KEY ("hive_id");



ALTER TABLE ONLY "public"."hive_audit_log"
    ADD CONSTRAINT "hive_audit_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."hive_members"
    ADD CONSTRAINT "hive_members_hive_id_worker_name_key" UNIQUE ("hive_id", "worker_name");



ALTER TABLE ONLY "public"."hive_members"
    ADD CONSTRAINT "hive_members_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."hives"
    ADD CONSTRAINT "hives_invite_code_key" UNIQUE ("invite_code");



ALTER TABLE ONLY "public"."hives"
    ADD CONSTRAINT "hives_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."inventory_items"
    ADD CONSTRAINT "inventory_items_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."inventory_transactions"
    ADD CONSTRAINT "inventory_transactions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."logbook"
    ADD CONSTRAINT "logbook_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_disputes"
    ADD CONSTRAINT "marketplace_disputes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_inquiries"
    ADD CONSTRAINT "marketplace_inquiries_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_listings"
    ADD CONSTRAINT "marketplace_listings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_orders"
    ADD CONSTRAINT "marketplace_orders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_orders"
    ADD CONSTRAINT "marketplace_orders_stripe_session_id_key" UNIQUE ("stripe_session_id");



ALTER TABLE ONLY "public"."marketplace_platform_admins"
    ADD CONSTRAINT "marketplace_platform_admins_pkey" PRIMARY KEY ("worker_name");



ALTER TABLE ONLY "public"."marketplace_reviews"
    ADD CONSTRAINT "marketplace_reviews_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_saved_searches"
    ADD CONSTRAINT "marketplace_saved_searches_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_sellers"
    ADD CONSTRAINT "marketplace_sellers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_sellers"
    ADD CONSTRAINT "marketplace_sellers_worker_name_key" UNIQUE ("worker_name");



ALTER TABLE ONLY "public"."marketplace_watchlist"
    ADD CONSTRAINT "marketplace_watchlist_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."marketplace_watchlist"
    ADD CONSTRAINT "marketplace_watchlist_worker_name_listing_id_key" UNIQUE ("worker_name", "listing_id");



ALTER TABLE ONLY "public"."parts_records"
    ADD CONSTRAINT "parts_records_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pm_assets"
    ADD CONSTRAINT "pm_assets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pm_completions"
    ADD CONSTRAINT "pm_completions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pm_knowledge"
    ADD CONSTRAINT "pm_knowledge_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pm_scope_items"
    ADD CONSTRAINT "pm_scope_items_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."report_contacts"
    ADD CONSTRAINT "report_contacts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."schedule_items"
    ADD CONSTRAINT "schedule_items_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."skill_badges"
    ADD CONSTRAINT "skill_badges_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."skill_badges"
    ADD CONSTRAINT "skill_badges_worker_name_discipline_level_key" UNIQUE ("worker_name", "discipline", "level");



ALTER TABLE ONLY "public"."skill_exam_attempts"
    ADD CONSTRAINT "skill_exam_attempts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."skill_knowledge"
    ADD CONSTRAINT "skill_knowledge_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."skill_profiles"
    ADD CONSTRAINT "skill_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."skill_profiles"
    ADD CONSTRAINT "skill_profiles_worker_name_key" UNIQUE ("worker_name");



ALTER TABLE ONLY "public"."worker_profiles"
    ADD CONSTRAINT "worker_profiles_auth_uid_key" UNIQUE ("auth_uid");



ALTER TABLE ONLY "public"."worker_profiles"
    ADD CONSTRAINT "worker_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."worker_profiles"
    ADD CONSTRAINT "worker_profiles_username_key" UNIQUE ("username");



CREATE INDEX "assets_worker_name_idx" ON "public"."assets" USING "btree" ("worker_name");



CREATE INDEX "idx_ai_reports_hive_type" ON "public"."ai_reports" USING "btree" ("hive_id", "report_type", "generated_at" DESC);



CREATE INDEX "idx_assets_auth_uid" ON "public"."assets" USING "btree" ("auth_uid");



CREATE INDEX "idx_automation_log_job" ON "public"."automation_log" USING "btree" ("job_name", "triggered_at" DESC);



CREATE INDEX "idx_bom_knowledge_embedding" ON "public"."bom_knowledge" USING "ivfflat" ("embedding" "public"."vector_cosine_ops") WITH ("lists"='50');



CREATE INDEX "idx_bom_knowledge_hive" ON "public"."bom_knowledge" USING "btree" ("hive_id");



CREATE INDEX "idx_calc_knowledge_calc_type" ON "public"."calc_knowledge" USING "btree" ("calc_type");



CREATE INDEX "idx_calc_knowledge_embedding" ON "public"."calc_knowledge" USING "ivfflat" ("embedding" "public"."vector_cosine_ops") WITH ("lists"='50');



CREATE INDEX "idx_calc_knowledge_hive" ON "public"."calc_knowledge" USING "btree" ("hive_id");



CREATE INDEX "idx_community_posts_auth_uid" ON "public"."community_posts" USING "btree" ("auth_uid");



CREATE INDEX "idx_community_posts_hive_created" ON "public"."community_posts" USING "btree" ("hive_id", "created_at" DESC);



CREATE INDEX "idx_community_posts_pinned" ON "public"."community_posts" USING "btree" ("hive_id", "pinned") WHERE ("pinned" = true);



CREATE INDEX "idx_community_posts_public" ON "public"."community_posts" USING "btree" ("public") WHERE ("public" = true);



CREATE INDEX "idx_community_reactions_post" ON "public"."community_reactions" USING "btree" ("post_id");



CREATE INDEX "idx_community_replies_hive" ON "public"."community_replies" USING "btree" ("hive_id");



CREATE INDEX "idx_community_replies_post" ON "public"."community_replies" USING "btree" ("post_id", "created_at");



CREATE UNIQUE INDEX "idx_early_access_email" ON "public"."early_access_emails" USING "btree" ("lower"("email"));



CREATE INDEX "idx_eng_calcs_hive" ON "public"."engineering_calcs" USING "btree" ("hive_id");



CREATE INDEX "idx_engineering_calcs_auth_uid" ON "public"."engineering_calcs" USING "btree" ("auth_uid");



CREATE INDEX "idx_fault_knowledge_embedding" ON "public"."fault_knowledge" USING "ivfflat" ("embedding" "public"."vector_cosine_ops") WITH ("lists"='50');



CREATE INDEX "idx_fault_knowledge_hive" ON "public"."fault_knowledge" USING "btree" ("hive_id");



CREATE INDEX "idx_hive_audit_log_hive_created" ON "public"."hive_audit_log" USING "btree" ("hive_id", "created_at" DESC);



CREATE INDEX "idx_hive_members_auth_uid" ON "public"."hive_members" USING "btree" ("auth_uid");



CREATE INDEX "idx_inv_txns_hive_type_date" ON "public"."inventory_transactions" USING "btree" ("hive_id", "type", "created_at" DESC) WHERE ("type" = 'use'::"text");



CREATE INDEX "idx_inv_txns_worker_type_date" ON "public"."inventory_transactions" USING "btree" ("worker_name", "type", "created_at" DESC) WHERE ("type" = 'use'::"text");



CREATE INDEX "idx_inventory_items_auth_uid" ON "public"."inventory_items" USING "btree" ("auth_uid");



CREATE INDEX "idx_inventory_transactions_auth_uid" ON "public"."inventory_transactions" USING "btree" ("auth_uid");



CREATE INDEX "idx_logbook_auth_uid" ON "public"."logbook" USING "btree" ("auth_uid");



CREATE INDEX "idx_logbook_consequence" ON "public"."logbook" USING "btree" ("hive_id", "failure_consequence") WHERE ("failure_consequence" IS NOT NULL);



CREATE INDEX "idx_logbook_hive_date" ON "public"."logbook" USING "btree" ("hive_id", "created_at" DESC);



CREATE INDEX "idx_logbook_hive_type" ON "public"."logbook" USING "btree" ("hive_id", "maintenance_type");



CREATE INDEX "idx_logbook_hive_type_status" ON "public"."logbook" USING "btree" ("hive_id", "maintenance_type", "status", "closed_at" DESC);



CREATE INDEX "idx_logbook_production_gin" ON "public"."logbook" USING "gin" ("production_output") WHERE ("production_output" IS NOT NULL);



CREATE INDEX "idx_logbook_readings_gin" ON "public"."logbook" USING "gin" ("readings_json") WHERE ("readings_json" IS NOT NULL);



CREATE INDEX "idx_logbook_worker_date" ON "public"."logbook" USING "btree" ("worker_name", "created_at" DESC) WHERE ("hive_id" IS NULL);



CREATE INDEX "idx_mkt_disputes_order" ON "public"."marketplace_disputes" USING "btree" ("order_id");



CREATE INDEX "idx_mkt_disputes_status" ON "public"."marketplace_disputes" USING "btree" ("status", "created_at");



CREATE INDEX "idx_mkt_inquiries_created" ON "public"."marketplace_inquiries" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_mkt_inquiries_listing" ON "public"."marketplace_inquiries" USING "btree" ("listing_id", "status");



CREATE INDEX "idx_mkt_inquiries_seller" ON "public"."marketplace_inquiries" USING "btree" ("seller_name", "status");



CREATE INDEX "idx_mkt_listings_created" ON "public"."marketplace_listings" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_mkt_listings_fts" ON "public"."marketplace_listings" USING "gin" ("search_vector");



CREATE INDEX "idx_mkt_listings_hive_section" ON "public"."marketplace_listings" USING "btree" ("hive_id", "section", "status");



CREATE INDEX "idx_mkt_listings_section_status" ON "public"."marketplace_listings" USING "btree" ("section", "status");



CREATE INDEX "idx_mkt_listings_seller" ON "public"."marketplace_listings" USING "btree" ("seller_name", "status");



CREATE INDEX "idx_mkt_listings_view_count" ON "public"."marketplace_listings" USING "btree" ("view_count" DESC);



CREATE INDEX "idx_mkt_orders_buyer" ON "public"."marketplace_orders" USING "btree" ("buyer_name", "status");



CREATE INDEX "idx_mkt_orders_listing" ON "public"."marketplace_orders" USING "btree" ("listing_id");



CREATE INDEX "idx_mkt_orders_seller" ON "public"."marketplace_orders" USING "btree" ("seller_name", "status");



CREATE INDEX "idx_mkt_orders_stripe_session" ON "public"."marketplace_orders" USING "btree" ("stripe_session_id");



CREATE INDEX "idx_mkt_platform_admins_worker" ON "public"."marketplace_platform_admins" USING "btree" ("worker_name");



CREATE INDEX "idx_mkt_reviews_listing" ON "public"."marketplace_reviews" USING "btree" ("listing_id");



CREATE INDEX "idx_mkt_saved_search_email" ON "public"."marketplace_saved_searches" USING "btree" ("email") WHERE (("email" IS NOT NULL) AND ("active" = true));



CREATE INDEX "idx_mkt_saved_search_worker" ON "public"."marketplace_saved_searches" USING "btree" ("worker_name", "active");



CREATE INDEX "idx_mkt_sellers_tier" ON "public"."marketplace_sellers" USING "btree" ("tier", "kyb_verified");



CREATE INDEX "idx_mkt_sellers_worker" ON "public"."marketplace_sellers" USING "btree" ("worker_name");



CREATE INDEX "idx_mkt_watchlist_listing" ON "public"."marketplace_watchlist" USING "btree" ("listing_id");



CREATE INDEX "idx_mkt_watchlist_worker" ON "public"."marketplace_watchlist" USING "btree" ("worker_name");



CREATE INDEX "idx_pm_assets_auth_uid" ON "public"."pm_assets" USING "btree" ("auth_uid");



CREATE INDEX "idx_pm_completions_asset_date" ON "public"."pm_completions" USING "btree" ("asset_id", "completed_at" DESC);



CREATE INDEX "idx_pm_completions_auth_uid" ON "public"."pm_completions" USING "btree" ("auth_uid");



CREATE INDEX "idx_pm_knowledge_embedding" ON "public"."pm_knowledge" USING "ivfflat" ("embedding" "public"."vector_cosine_ops") WITH ("lists"='50');



CREATE INDEX "idx_pm_knowledge_hive" ON "public"."pm_knowledge" USING "btree" ("hive_id");



CREATE UNIQUE INDEX "idx_reading_templates_cat_key" ON "public"."equipment_reading_templates" USING "btree" ("category", "reading_key");



CREATE INDEX "idx_reading_templates_category" ON "public"."equipment_reading_templates" USING "btree" ("category", "sort_order");



CREATE INDEX "idx_report_contacts_hive" ON "public"."report_contacts" USING "btree" ("hive_id", "created_at" DESC);



CREATE INDEX "idx_schedule_items_auth_uid" ON "public"."schedule_items" USING "btree" ("auth_uid");



CREATE INDEX "idx_skill_badges_auth_uid" ON "public"."skill_badges" USING "btree" ("auth_uid");



CREATE INDEX "idx_skill_exam_attempts_auth_uid" ON "public"."skill_exam_attempts" USING "btree" ("auth_uid");



CREATE INDEX "idx_skill_knowledge_embedding" ON "public"."skill_knowledge" USING "ivfflat" ("embedding" "public"."vector_cosine_ops") WITH ("lists"='50');



CREATE INDEX "idx_skill_knowledge_hive" ON "public"."skill_knowledge" USING "btree" ("hive_id");



CREATE INDEX "idx_skill_profiles_auth_uid" ON "public"."skill_profiles" USING "btree" ("auth_uid");



CREATE INDEX "idx_worker_profiles_auth_uid" ON "public"."worker_profiles" USING "btree" ("auth_uid");



CREATE INDEX "idx_worker_profiles_username" ON "public"."worker_profiles" USING "btree" ("username");



CREATE INDEX "inventory_items_worker_name_idx" ON "public"."inventory_items" USING "btree" ("worker_name");



CREATE INDEX "inventory_transactions_item_id_idx" ON "public"."inventory_transactions" USING "btree" ("item_id");



CREATE INDEX "inventory_transactions_worker_name_idx" ON "public"."inventory_transactions" USING "btree" ("worker_name");



CREATE INDEX "logbook_asset_ref_id_idx" ON "public"."logbook" USING "btree" ("asset_ref_id");



CREATE INDEX "logbook_hive_id_idx" ON "public"."logbook" USING "btree" ("hive_id");



CREATE INDEX "marketplace_inquiries_listing_id" ON "public"."marketplace_inquiries" USING "btree" ("listing_id");



CREATE INDEX "marketplace_listings_hive_id" ON "public"."marketplace_listings" USING "btree" ("hive_id");



CREATE INDEX "marketplace_listings_section_status" ON "public"."marketplace_listings" USING "btree" ("section", "status");



CREATE INDEX "marketplace_reviews_listing_id" ON "public"."marketplace_reviews" USING "btree" ("listing_id");



CREATE INDEX "parts_records_hive_id_idx" ON "public"."parts_records" USING "btree" ("hive_id");



CREATE OR REPLACE TRIGGER "embed-logbook" AFTER INSERT ON "public"."logbook" FOR EACH ROW EXECUTE FUNCTION "supabase_functions"."http_request"('https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/embed-entry', 'POST', '{"Content-type":"application/json","Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6eXZuanRpc2ZnYmtzaWNyb3V1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTU4MTYwNCwiZXhwIjoyMDkxMTU3NjA0fQ.11e3HPOmwCAHBoYa1NAtaEerFKd3pjIl5FtTEhOu5Hg"}', '{}', '5000');



CREATE OR REPLACE TRIGGER "embed-pm-completions" AFTER INSERT ON "public"."pm_completions" FOR EACH ROW EXECUTE FUNCTION "supabase_functions"."http_request"('https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/embed-entry', 'POST', '{"Content-type":"application/json","Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6eXZuanRpc2ZnYmtzaWNyb3V1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTU4MTYwNCwiZXhwIjoyMDkxMTU3NjA0fQ.11e3HPOmwCAHBoYa1NAtaEerFKd3pjIl5FtTEhOu5Hg"}', '{}', '5000');



CREATE OR REPLACE TRIGGER "embed-skill-badges" AFTER INSERT ON "public"."skill_badges" FOR EACH ROW EXECUTE FUNCTION "supabase_functions"."http_request"('https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/embed-entry', 'POST', '{"Content-type":"application/json","Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6eXZuanRpc2ZnYmtzaWNyb3V1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTU4MTYwNCwiZXhwIjoyMDkxMTU3NjA0fQ.11e3HPOmwCAHBoYa1NAtaEerFKd3pjIl5FtTEhOu5Hg"}', '{}', '5000');



CREATE OR REPLACE TRIGGER "trg_community_post_rate_limit" BEFORE INSERT ON "public"."community_posts" FOR EACH ROW EXECUTE FUNCTION "public"."community_post_rate_limit"();



CREATE OR REPLACE TRIGGER "trg_community_post_xp" AFTER INSERT ON "public"."community_posts" FOR EACH ROW EXECUTE FUNCTION "public"."handle_community_post_xp"();



CREATE OR REPLACE TRIGGER "trg_community_reaction_xp" AFTER INSERT ON "public"."community_reactions" FOR EACH ROW EXECUTE FUNCTION "public"."handle_community_reaction_xp"();



CREATE OR REPLACE TRIGGER "trg_community_reply_rate_limit" BEFORE INSERT ON "public"."community_replies" FOR EACH ROW EXECUTE FUNCTION "public"."community_reply_rate_limit"();



CREATE OR REPLACE TRIGGER "trg_community_reply_xp" AFTER INSERT ON "public"."community_replies" FOR EACH ROW EXECUTE FUNCTION "public"."handle_community_reply_xp"();



CREATE OR REPLACE TRIGGER "trg_listing_rate" BEFORE INSERT ON "public"."marketplace_listings" FOR EACH ROW EXECUTE FUNCTION "public"."check_listing_rate"();



CREATE OR REPLACE TRIGGER "trg_seller_tier" AFTER UPDATE OF "status" ON "public"."marketplace_orders" FOR EACH ROW EXECUTE FUNCTION "public"."update_seller_tier"();



CREATE OR REPLACE TRIGGER "trg_sync_auth_uid_on_signup" AFTER INSERT ON "public"."worker_profiles" FOR EACH ROW EXECUTE FUNCTION "public"."sync_auth_uid_on_signup"();



CREATE OR REPLACE TRIGGER "trg_update_seller_rating" AFTER INSERT ON "public"."marketplace_reviews" FOR EACH ROW EXECUTE FUNCTION "public"."update_seller_rating"();



ALTER TABLE ONLY "public"."ai_reports"
    ADD CONSTRAINT "ai_reports_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."assets"
    ADD CONSTRAINT "assets_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."bom_knowledge"
    ADD CONSTRAINT "bom_knowledge_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."calc_knowledge"
    ADD CONSTRAINT "calc_knowledge_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."community_posts"
    ADD CONSTRAINT "community_posts_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."community_posts"
    ADD CONSTRAINT "community_posts_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."community_reactions"
    ADD CONSTRAINT "community_reactions_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "public"."community_posts"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."community_replies"
    ADD CONSTRAINT "community_replies_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "public"."community_posts"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."community_xp"
    ADD CONSTRAINT "community_xp_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."engineering_calcs"
    ADD CONSTRAINT "engineering_calcs_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."fault_knowledge"
    ADD CONSTRAINT "fault_knowledge_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."hive_analytics_cache"
    ADD CONSTRAINT "hive_analytics_cache_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."hive_audit_log"
    ADD CONSTRAINT "hive_audit_log_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."hive_members"
    ADD CONSTRAINT "hive_members_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."hive_members"
    ADD CONSTRAINT "hive_members_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."inventory_items"
    ADD CONSTRAINT "inventory_items_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."inventory_transactions"
    ADD CONSTRAINT "inventory_transactions_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."inventory_transactions"
    ADD CONSTRAINT "inventory_transactions_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."inventory_transactions"
    ADD CONSTRAINT "inventory_transactions_item_id_fkey" FOREIGN KEY ("item_id") REFERENCES "public"."inventory_items"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."logbook"
    ADD CONSTRAINT "logbook_asset_ref_id_fkey" FOREIGN KEY ("asset_ref_id") REFERENCES "public"."assets"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."logbook"
    ADD CONSTRAINT "logbook_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."logbook"
    ADD CONSTRAINT "logbook_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."logbook"
    ADD CONSTRAINT "logbook_pm_completion_id_fkey" FOREIGN KEY ("pm_completion_id") REFERENCES "public"."pm_completions"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_disputes"
    ADD CONSTRAINT "marketplace_disputes_listing_id_fkey" FOREIGN KEY ("listing_id") REFERENCES "public"."marketplace_listings"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_disputes"
    ADD CONSTRAINT "marketplace_disputes_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."marketplace_orders"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."marketplace_inquiries"
    ADD CONSTRAINT "marketplace_inquiries_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_inquiries"
    ADD CONSTRAINT "marketplace_inquiries_listing_id_fkey" FOREIGN KEY ("listing_id") REFERENCES "public"."marketplace_listings"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."marketplace_listings"
    ADD CONSTRAINT "marketplace_listings_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_orders"
    ADD CONSTRAINT "marketplace_orders_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_orders"
    ADD CONSTRAINT "marketplace_orders_listing_id_fkey" FOREIGN KEY ("listing_id") REFERENCES "public"."marketplace_listings"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_reviews"
    ADD CONSTRAINT "marketplace_reviews_listing_id_fkey" FOREIGN KEY ("listing_id") REFERENCES "public"."marketplace_listings"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."marketplace_sellers"
    ADD CONSTRAINT "marketplace_sellers_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."marketplace_watchlist"
    ADD CONSTRAINT "marketplace_watchlist_listing_id_fkey" FOREIGN KEY ("listing_id") REFERENCES "public"."marketplace_listings"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."parts_records"
    ADD CONSTRAINT "parts_records_asset_ref_id_fkey" FOREIGN KEY ("asset_ref_id") REFERENCES "public"."assets"("id");



ALTER TABLE ONLY "public"."parts_records"
    ADD CONSTRAINT "parts_records_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."pm_assets"
    ADD CONSTRAINT "pm_assets_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."pm_assets"
    ADD CONSTRAINT "pm_assets_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pm_completions"
    ADD CONSTRAINT "pm_completions_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."pm_assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pm_completions"
    ADD CONSTRAINT "pm_completions_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."pm_completions"
    ADD CONSTRAINT "pm_completions_scope_item_id_fkey" FOREIGN KEY ("scope_item_id") REFERENCES "public"."pm_scope_items"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pm_knowledge"
    ADD CONSTRAINT "pm_knowledge_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."pm_scope_items"
    ADD CONSTRAINT "pm_scope_items_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."pm_assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."report_contacts"
    ADD CONSTRAINT "report_contacts_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."schedule_items"
    ADD CONSTRAINT "schedule_items_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."skill_badges"
    ADD CONSTRAINT "skill_badges_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."skill_exam_attempts"
    ADD CONSTRAINT "skill_exam_attempts_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."skill_knowledge"
    ADD CONSTRAINT "skill_knowledge_hive_id_fkey" FOREIGN KEY ("hive_id") REFERENCES "public"."hives"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."skill_profiles"
    ADD CONSTRAINT "skill_profiles_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."worker_profiles"
    ADD CONSTRAINT "worker_profiles_auth_uid_fkey" FOREIGN KEY ("auth_uid") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE "public"."ai_reports" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "ai_reports_read" ON "public"."ai_reports" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."status" = 'active'::"text"))))));



CREATE POLICY "allow_anon_all" ON "public"."assets" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."engineering_calcs" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."hive_members" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."hives" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."inventory_items" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."inventory_transactions" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."logbook" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."parts_records" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."pm_assets" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."pm_completions" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."pm_scope_items" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."schedule_items" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."skill_badges" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."skill_exam_attempts" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "allow_anon_all" ON "public"."skill_profiles" TO "anon" USING (true) WITH CHECK (true);



CREATE POLICY "anon can insert early access email" ON "public"."early_access_emails" FOR INSERT WITH CHECK (true);



CREATE POLICY "anon delete community_reactions" ON "public"."community_reactions" FOR DELETE USING (true);



CREATE POLICY "anon delete community_replies" ON "public"."community_replies" FOR DELETE USING (true);



CREATE POLICY "anon insert pm_scope_items" ON "public"."pm_scope_items" FOR INSERT WITH CHECK (true);



CREATE POLICY "anon read pm_scope_items" ON "public"."pm_scope_items" FOR SELECT USING (true);



CREATE POLICY "anon_delete_members" ON "public"."hive_members" FOR DELETE TO "anon" USING (true);



CREATE POLICY "anon_insert_hives" ON "public"."hives" FOR INSERT TO "anon" WITH CHECK (true);



CREATE POLICY "anon_insert_members" ON "public"."hive_members" FOR INSERT TO "anon" WITH CHECK (true);



CREATE POLICY "anon_select_hives" ON "public"."hives" FOR SELECT TO "anon" USING (true);



CREATE POLICY "anon_select_members" ON "public"."hive_members" FOR SELECT TO "anon" USING (true);



CREATE POLICY "anon_upsert_members" ON "public"."hive_members" FOR UPDATE TO "anon" USING (true);



ALTER TABLE "public"."assets" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "assets_read" ON "public"."assets" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



CREATE POLICY "assets_write" ON "public"."assets" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR (EXISTS ( SELECT 1
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."hive_id" = "assets"."hive_id") AND ("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."role" = 'supervisor'::"text") AND ("hm"."status" = 'active'::"text")))))));



ALTER TABLE "public"."automation_log" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "automation_log_read" ON "public"."automation_log" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."status" = 'active'::"text"))))));



ALTER TABLE "public"."community_posts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "community_posts_delete" ON "public"."community_posts" FOR DELETE USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR (EXISTS ( SELECT 1
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."hive_id" = "community_posts"."hive_id") AND ("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."role" = 'supervisor'::"text") AND ("hm"."status" = 'active'::"text")))))));



CREATE POLICY "community_posts_insert" ON "public"."community_posts" FOR INSERT WITH CHECK ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL)) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



CREATE POLICY "community_posts_read" ON "public"."community_posts" FOR SELECT USING (((("public" = true) AND ("flagged" = false)) OR (("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))));



CREATE POLICY "community_posts_update" ON "public"."community_posts" FOR UPDATE USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR (EXISTS ( SELECT 1
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."hive_id" = "community_posts"."hive_id") AND ("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."role" = 'supervisor'::"text") AND ("hm"."status" = 'active'::"text")))))));



ALTER TABLE "public"."community_reactions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "community_reactions_read" ON "public"."community_reactions" FOR SELECT USING (((("auth"."uid"() IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM "public"."community_posts" "cp"
  WHERE (("cp"."id" = "community_reactions"."post_id") AND ("cp"."public" = true))))) OR (("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))));



CREATE POLICY "community_reactions_write" ON "public"."community_reactions" USING ((("auth"."uid"() IS NOT NULL) AND ((EXISTS ( SELECT 1
   FROM "public"."community_posts" "cp"
  WHERE (("cp"."id" = "community_reactions"."post_id") AND ("cp"."public" = true)))) OR ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))));



ALTER TABLE "public"."community_replies" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "community_replies_read" ON "public"."community_replies" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



CREATE POLICY "community_replies_write" ON "public"."community_replies" USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



ALTER TABLE "public"."community_xp" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "community_xp_write" ON "public"."community_xp" USING (("auth"."uid"() IS NOT NULL));



ALTER TABLE "public"."early_access_emails" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."engineering_calcs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "engineering_calcs_read" ON "public"."engineering_calcs" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND ("auth_uid" = "auth"."uid"())))));



CREATE POLICY "engineering_calcs_write" ON "public"."engineering_calcs" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL)))) WITH CHECK (("auth"."uid"() IS NOT NULL));



CREATE POLICY "hive xp open read" ON "public"."community_xp" FOR SELECT USING (true);



ALTER TABLE "public"."hive_members" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "hive_members_delete" ON "public"."hive_members" FOR DELETE USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "hive_members_insert" ON "public"."hive_members" FOR INSERT WITH CHECK ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL))));



CREATE POLICY "hive_members_read" ON "public"."hive_members" FOR SELECT USING (true);



CREATE POLICY "hive_members_update" ON "public"."hive_members" FOR UPDATE USING ((("auth"."uid"() IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM "public"."hive_members" "sup"
  WHERE (("sup"."hive_id" = "hive_members"."hive_id") AND ("sup"."auth_uid" = "auth"."uid"()) AND ("sup"."role" = 'supervisor'::"text") AND ("sup"."status" = 'active'::"text"))))));



ALTER TABLE "public"."hives" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "hives_delete" ON "public"."hives" FOR DELETE USING ((("auth"."uid"() IS NOT NULL) AND ("id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."role" = 'supervisor'::"text") AND ("hive_members"."status" = 'active'::"text"))))));



CREATE POLICY "hives_insert" ON "public"."hives" FOR INSERT WITH CHECK (("auth"."uid"() IS NOT NULL));



CREATE POLICY "hives_open_read" ON "public"."hives" FOR SELECT USING (true);



CREATE POLICY "hives_read" ON "public"."hives" FOR SELECT USING (true);



CREATE POLICY "hives_update" ON "public"."hives" FOR UPDATE USING ((("auth"."uid"() IS NOT NULL) AND ("id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."role" = 'supervisor'::"text") AND ("hive_members"."status" = 'active'::"text"))))));



ALTER TABLE "public"."inventory_items" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "inventory_items_read" ON "public"."inventory_items" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



CREATE POLICY "inventory_items_write" ON "public"."inventory_items" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR (EXISTS ( SELECT 1
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."hive_id" = "inventory_items"."hive_id") AND ("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))));



ALTER TABLE "public"."inventory_transactions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "inventory_transactions_read" ON "public"."inventory_transactions" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND ("auth_uid" = "auth"."uid"())))));



CREATE POLICY "inventory_transactions_write" ON "public"."inventory_transactions" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL)))) WITH CHECK (("auth"."uid"() IS NOT NULL));



ALTER TABLE "public"."logbook" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "logbook_delete" ON "public"."logbook" FOR DELETE USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "logbook_insert" ON "public"."logbook" FOR INSERT WITH CHECK ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL))))));



CREATE POLICY "logbook_read" ON "public"."logbook" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND ("auth_uid" = "auth"."uid"())))));



CREATE POLICY "logbook_update" ON "public"."logbook" FOR UPDATE USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "open" ON "public"."assets" USING (true) WITH CHECK (true);



CREATE POLICY "open" ON "public"."inventory_items" USING (true) WITH CHECK (true);



CREATE POLICY "open" ON "public"."inventory_transactions" USING (true) WITH CHECK (true);



ALTER TABLE "public"."parts_records" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pm_assets" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "pm_assets_read" ON "public"."pm_assets" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND ("auth_uid" = "auth"."uid"())))));



CREATE POLICY "pm_assets_write" ON "public"."pm_assets" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR (EXISTS ( SELECT 1
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."hive_id" = "pm_assets"."hive_id") AND ("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))));



ALTER TABLE "public"."pm_completions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "pm_completions_read" ON "public"."pm_completions" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ((("hive_id" IS NOT NULL) AND ("hive_id" IN ( SELECT "hm"."hive_id"
   FROM "public"."hive_members" "hm"
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))) OR (("hive_id" IS NULL) AND ("auth_uid" = "auth"."uid"())))));



CREATE POLICY "pm_completions_write" ON "public"."pm_completions" USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



ALTER TABLE "public"."pm_scope_items" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "pm_scope_items_read" ON "public"."pm_scope_items" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("asset_id" IN ( SELECT "pa"."id"
   FROM ("public"."pm_assets" "pa"
     JOIN "public"."hive_members" "hm" ON (("pa"."hive_id" = "hm"."hive_id")))
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text"))))));



CREATE POLICY "pm_scope_items_write" ON "public"."pm_scope_items" USING ((("auth"."uid"() IS NOT NULL) AND ("asset_id" IN ( SELECT "pa"."id"
   FROM ("public"."pm_assets" "pa"
     JOIN "public"."hive_members" "hm" ON (("pa"."hive_id" = "hm"."hive_id")))
  WHERE (("hm"."auth_uid" = "auth"."uid"()) AND ("hm"."status" = 'active'::"text")))))) WITH CHECK (("auth"."uid"() IS NOT NULL));



CREATE POLICY "profiles insert own" ON "public"."worker_profiles" FOR INSERT WITH CHECK ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "profiles open read" ON "public"."worker_profiles" FOR SELECT USING (true);



CREATE POLICY "profiles update own" ON "public"."worker_profiles" FOR UPDATE USING (("auth"."uid"() = "auth_uid"));



ALTER TABLE "public"."report_contacts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "report_contacts_read" ON "public"."report_contacts" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."status" = 'active'::"text"))))));



CREATE POLICY "report_contacts_write" ON "public"."report_contacts" USING ((("auth"."uid"() IS NOT NULL) AND ("hive_id" IN ( SELECT "hive_members"."hive_id"
   FROM "public"."hive_members"
  WHERE (("hive_members"."auth_uid" = "auth"."uid"()) AND ("hive_members"."status" = 'active'::"text")))))) WITH CHECK (("auth"."uid"() IS NOT NULL));



ALTER TABLE "public"."schedule_items" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "schedule_items_read" ON "public"."schedule_items" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "schedule_items_write" ON "public"."schedule_items" USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "service role can read early access emails" ON "public"."early_access_emails" FOR SELECT USING (("auth"."role"() = 'service_role'::"text"));



ALTER TABLE "public"."skill_badges" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "skill_badges_read" ON "public"."skill_badges" FOR SELECT USING (true);



CREATE POLICY "skill_badges_write" ON "public"."skill_badges" USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



ALTER TABLE "public"."skill_exam_attempts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "skill_exam_attempts_read" ON "public"."skill_exam_attempts" FOR SELECT USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



CREATE POLICY "skill_exam_attempts_write" ON "public"."skill_exam_attempts" USING ((("auth"."uid"() IS NOT NULL) AND ("auth_uid" = "auth"."uid"())));



ALTER TABLE "public"."skill_profiles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "skill_profiles_read" ON "public"."skill_profiles" FOR SELECT USING (true);



CREATE POLICY "skill_profiles_write" ON "public"."skill_profiles" USING ((("auth"."uid"() IS NOT NULL) AND (("auth_uid" = "auth"."uid"()) OR ("auth_uid" IS NULL)))) WITH CHECK (("auth"."uid"() IS NOT NULL));



ALTER TABLE "public"."worker_profiles" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."check_listing_rate"() TO "anon";
GRANT ALL ON FUNCTION "public"."check_listing_rate"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."check_listing_rate"() TO "service_role";



GRANT ALL ON FUNCTION "public"."community_post_rate_limit"() TO "anon";
GRANT ALL ON FUNCTION "public"."community_post_rate_limit"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."community_post_rate_limit"() TO "service_role";



GRANT ALL ON FUNCTION "public"."community_reply_rate_limit"() TO "anon";
GRANT ALL ON FUNCTION "public"."community_reply_rate_limit"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."community_reply_rate_limit"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_downtime_pareto"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_downtime_pareto"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_downtime_pareto"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_failure_frequency"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_failure_frequency"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_failure_frequency"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_mtbf_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_mtbf_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_mtbf_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_mttr_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_mttr_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_mttr_by_machine"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_repeat_failures"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_repeat_failures"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_repeat_failures"("p_hive_id" "uuid", "p_worker" "text", "p_period_days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_community_post_xp"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_community_post_xp"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_community_post_xp"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_community_reaction_xp"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_community_reaction_xp"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_community_reaction_xp"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_community_reply_xp"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_community_reply_xp"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_community_reply_xp"() TO "service_role";



GRANT ALL ON FUNCTION "public"."increment_community_xp"("p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."increment_community_xp"("p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment_community_xp"("p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."increment_listing_view"("p_listing_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."increment_listing_view"("p_listing_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment_listing_view"("p_listing_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."search_all_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_all_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_all_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_bom_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_bom_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_bom_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_calc_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_calc_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_calc_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_fault_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_fault_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_fault_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_pm_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_pm_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_pm_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_skill_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_skill_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_skill_knowledge"("query_embedding" "public"."vector", "match_hive_id" "uuid", "match_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."sync_auth_uid_on_signup"() TO "anon";
GRANT ALL ON FUNCTION "public"."sync_auth_uid_on_signup"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."sync_auth_uid_on_signup"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_seller_rating"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_seller_rating"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_seller_rating"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_seller_tier"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_seller_tier"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_seller_tier"() TO "service_role";



GRANT ALL ON TABLE "public"."ai_reports" TO "anon";
GRANT ALL ON TABLE "public"."ai_reports" TO "authenticated";
GRANT ALL ON TABLE "public"."ai_reports" TO "service_role";



GRANT ALL ON TABLE "public"."assets" TO "anon";
GRANT ALL ON TABLE "public"."assets" TO "authenticated";
GRANT ALL ON TABLE "public"."assets" TO "service_role";



GRANT ALL ON TABLE "public"."automation_log" TO "anon";
GRANT ALL ON TABLE "public"."automation_log" TO "authenticated";
GRANT ALL ON TABLE "public"."automation_log" TO "service_role";



GRANT ALL ON TABLE "public"."bom_knowledge" TO "anon";
GRANT ALL ON TABLE "public"."bom_knowledge" TO "authenticated";
GRANT ALL ON TABLE "public"."bom_knowledge" TO "service_role";



GRANT ALL ON TABLE "public"."calc_knowledge" TO "anon";
GRANT ALL ON TABLE "public"."calc_knowledge" TO "authenticated";
GRANT ALL ON TABLE "public"."calc_knowledge" TO "service_role";



GRANT ALL ON TABLE "public"."community_posts" TO "anon";
GRANT ALL ON TABLE "public"."community_posts" TO "authenticated";
GRANT ALL ON TABLE "public"."community_posts" TO "service_role";



GRANT ALL ON TABLE "public"."community_reactions" TO "anon";
GRANT ALL ON TABLE "public"."community_reactions" TO "authenticated";
GRANT ALL ON TABLE "public"."community_reactions" TO "service_role";



GRANT ALL ON TABLE "public"."community_replies" TO "anon";
GRANT ALL ON TABLE "public"."community_replies" TO "authenticated";
GRANT ALL ON TABLE "public"."community_replies" TO "service_role";



GRANT ALL ON TABLE "public"."community_xp" TO "anon";
GRANT ALL ON TABLE "public"."community_xp" TO "authenticated";
GRANT ALL ON TABLE "public"."community_xp" TO "service_role";



GRANT ALL ON TABLE "public"."early_access_emails" TO "anon";
GRANT ALL ON TABLE "public"."early_access_emails" TO "authenticated";
GRANT ALL ON TABLE "public"."early_access_emails" TO "service_role";



GRANT ALL ON TABLE "public"."engineering_calcs" TO "anon";
GRANT ALL ON TABLE "public"."engineering_calcs" TO "authenticated";
GRANT ALL ON TABLE "public"."engineering_calcs" TO "service_role";



GRANT ALL ON TABLE "public"."equipment_reading_templates" TO "anon";
GRANT ALL ON TABLE "public"."equipment_reading_templates" TO "authenticated";
GRANT ALL ON TABLE "public"."equipment_reading_templates" TO "service_role";



GRANT ALL ON TABLE "public"."fault_knowledge" TO "anon";
GRANT ALL ON TABLE "public"."fault_knowledge" TO "authenticated";
GRANT ALL ON TABLE "public"."fault_knowledge" TO "service_role";



GRANT ALL ON TABLE "public"."hive_analytics_cache" TO "anon";
GRANT ALL ON TABLE "public"."hive_analytics_cache" TO "authenticated";
GRANT ALL ON TABLE "public"."hive_analytics_cache" TO "service_role";



GRANT ALL ON TABLE "public"."hive_audit_log" TO "anon";
GRANT ALL ON TABLE "public"."hive_audit_log" TO "authenticated";
GRANT ALL ON TABLE "public"."hive_audit_log" TO "service_role";



GRANT ALL ON TABLE "public"."hive_members" TO "anon";
GRANT ALL ON TABLE "public"."hive_members" TO "authenticated";
GRANT ALL ON TABLE "public"."hive_members" TO "service_role";



GRANT ALL ON TABLE "public"."hives" TO "anon";
GRANT ALL ON TABLE "public"."hives" TO "authenticated";
GRANT ALL ON TABLE "public"."hives" TO "service_role";



GRANT ALL ON TABLE "public"."inventory_items" TO "anon";
GRANT ALL ON TABLE "public"."inventory_items" TO "authenticated";
GRANT ALL ON TABLE "public"."inventory_items" TO "service_role";



GRANT ALL ON TABLE "public"."inventory_transactions" TO "anon";
GRANT ALL ON TABLE "public"."inventory_transactions" TO "authenticated";
GRANT ALL ON TABLE "public"."inventory_transactions" TO "service_role";



GRANT ALL ON TABLE "public"."logbook" TO "anon";
GRANT ALL ON TABLE "public"."logbook" TO "authenticated";
GRANT ALL ON TABLE "public"."logbook" TO "service_role";



GRANT ALL ON TABLE "public"."marketplace_disputes" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_disputes" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_disputes" TO "service_role";



GRANT UPDATE("status") ON TABLE "public"."marketplace_disputes" TO "authenticated";



GRANT UPDATE("seller_reply") ON TABLE "public"."marketplace_disputes" TO "authenticated";



GRANT UPDATE("seller_replied_at") ON TABLE "public"."marketplace_disputes" TO "authenticated";



GRANT ALL ON TABLE "public"."marketplace_inquiries" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_inquiries" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_inquiries" TO "service_role";



GRANT UPDATE("status") ON TABLE "public"."marketplace_inquiries" TO "authenticated";



GRANT UPDATE("reply_text") ON TABLE "public"."marketplace_inquiries" TO "authenticated";



GRANT UPDATE("replied_at") ON TABLE "public"."marketplace_inquiries" TO "authenticated";



GRANT ALL ON TABLE "public"."marketplace_listings" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_listings" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_listings" TO "service_role";



GRANT UPDATE("status") ON TABLE "public"."marketplace_listings" TO "authenticated";



GRANT UPDATE("updated_at") ON TABLE "public"."marketplace_listings" TO "authenticated";



GRANT ALL ON TABLE "public"."marketplace_orders" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_orders" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_orders" TO "service_role";



GRANT UPDATE("status") ON TABLE "public"."marketplace_orders" TO "authenticated";



GRANT UPDATE("buyer_confirmed_at") ON TABLE "public"."marketplace_orders" TO "authenticated";



GRANT UPDATE("released_at") ON TABLE "public"."marketplace_orders" TO "authenticated";



GRANT UPDATE("updated_at") ON TABLE "public"."marketplace_orders" TO "authenticated";



GRANT UPDATE("reviewed_at") ON TABLE "public"."marketplace_orders" TO "authenticated";



GRANT ALL ON TABLE "public"."marketplace_platform_admins" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_platform_admins" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_platform_admins" TO "service_role";



GRANT ALL ON TABLE "public"."marketplace_reviews" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_reviews" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_reviews" TO "service_role";



GRANT ALL ON TABLE "public"."marketplace_saved_searches" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_saved_searches" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_saved_searches" TO "service_role";



GRANT ALL ON TABLE "public"."marketplace_sellers" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_sellers" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_sellers" TO "service_role";



GRANT UPDATE("tier") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("kyb_verified") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("kyb_verified_at") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("total_sales") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("rating_avg") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("rating_count") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("response_rate") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("response_time_h") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("updated_at") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("messenger_username") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("certifications") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("cert_verified") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT UPDATE("cert_verified_at") ON TABLE "public"."marketplace_sellers" TO "authenticated";



GRANT ALL ON TABLE "public"."marketplace_watchlist" TO "anon";
GRANT ALL ON TABLE "public"."marketplace_watchlist" TO "authenticated";
GRANT ALL ON TABLE "public"."marketplace_watchlist" TO "service_role";



GRANT ALL ON TABLE "public"."parts_records" TO "anon";
GRANT ALL ON TABLE "public"."parts_records" TO "authenticated";
GRANT ALL ON TABLE "public"."parts_records" TO "service_role";



GRANT ALL ON TABLE "public"."pm_assets" TO "anon";
GRANT ALL ON TABLE "public"."pm_assets" TO "authenticated";
GRANT ALL ON TABLE "public"."pm_assets" TO "service_role";



GRANT ALL ON TABLE "public"."pm_completions" TO "anon";
GRANT ALL ON TABLE "public"."pm_completions" TO "authenticated";
GRANT ALL ON TABLE "public"."pm_completions" TO "service_role";



GRANT ALL ON TABLE "public"."pm_knowledge" TO "anon";
GRANT ALL ON TABLE "public"."pm_knowledge" TO "authenticated";
GRANT ALL ON TABLE "public"."pm_knowledge" TO "service_role";



GRANT ALL ON TABLE "public"."pm_scope_items" TO "anon";
GRANT ALL ON TABLE "public"."pm_scope_items" TO "authenticated";
GRANT ALL ON TABLE "public"."pm_scope_items" TO "service_role";



GRANT ALL ON TABLE "public"."report_contacts" TO "anon";
GRANT ALL ON TABLE "public"."report_contacts" TO "authenticated";
GRANT ALL ON TABLE "public"."report_contacts" TO "service_role";



GRANT ALL ON TABLE "public"."schedule_items" TO "anon";
GRANT ALL ON TABLE "public"."schedule_items" TO "authenticated";
GRANT ALL ON TABLE "public"."schedule_items" TO "service_role";



GRANT ALL ON TABLE "public"."skill_badges" TO "anon";
GRANT ALL ON TABLE "public"."skill_badges" TO "authenticated";
GRANT ALL ON TABLE "public"."skill_badges" TO "service_role";



GRANT ALL ON TABLE "public"."skill_exam_attempts" TO "anon";
GRANT ALL ON TABLE "public"."skill_exam_attempts" TO "authenticated";
GRANT ALL ON TABLE "public"."skill_exam_attempts" TO "service_role";



GRANT ALL ON TABLE "public"."skill_knowledge" TO "anon";
GRANT ALL ON TABLE "public"."skill_knowledge" TO "authenticated";
GRANT ALL ON TABLE "public"."skill_knowledge" TO "service_role";



GRANT ALL ON TABLE "public"."skill_profiles" TO "anon";
GRANT ALL ON TABLE "public"."skill_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."skill_profiles" TO "service_role";



GRANT ALL ON TABLE "public"."worker_profiles" TO "anon";
GRANT ALL ON TABLE "public"."worker_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."worker_profiles" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







