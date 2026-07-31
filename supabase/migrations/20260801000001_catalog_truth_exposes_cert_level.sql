-- 20260801000001_catalog_truth_exposes_cert_level.sql
--
-- v_service_catalog_truth did not expose `requires_cert_level`, so the client hail picker could not tell an
-- OPEN trade from a CERTIFIED-ONLY one.
--
-- Why that matters, measured on a live client walk 2026-08-01: BOTH cert-gated services (Calibration and
-- Generator, each requiring level 2) currently have **ZERO** providers who qualify. A client could pick
-- Calibration, hail it, watch "Finding a provider…" for the whole TTL, and receive "No provider found" —
-- never learning the real reason was that nobody on the platform holds the badge. The J20 gate refuses the
-- ACCEPT with an excellent message ("needs a certified badge in Calibration (level 2+) — earn it in the
-- Skill Matrix exam"), but only the PROVIDER ever reads it. The client waits in the dark.
--
-- A truth view is a CURATED column subset and does NOT auto-inherit base columns — the column existed on
-- service_catalog all along and the client still read undefined, so the picker rendered no marker at all.
-- Same class as the OC-guard-on-a-view lesson: add it to the VIEW, not just the table.
--
-- Appended LAST because CREATE OR REPLACE VIEW may only add columns at the end (inserting it mid-list fails
-- with "cannot change name of view column"). Body copied from pg_get_viewdef rather than retyped — an
-- earlier draft written from memory got _freshness_ts, _canonical_version and the WHERE clause all wrong.
--
-- The hail stays ALLOWED for gated trades: an unfilled hail is genuine demand signal worth capturing. This
-- only lets the UI set the expectation before the wait instead of after it.
create or replace view public.v_service_catalog_truth as
 SELECT id,
    segment,
    category,
    name,
    description,
    unit,
    base_rate,
    active,
    created_at,
    updated_at,
    1 AS _source_count,
    updated_at AS _freshness_ts,
    'service_catalog_truth:v1'::text AS _canonical_version,
    requires_cert_level
   FROM service_catalog c
  WHERE active = true;
