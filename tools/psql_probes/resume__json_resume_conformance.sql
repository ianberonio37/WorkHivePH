-- json_resume_conformance: the page claims "JSON Resume schema" at three sites, so every STORED doc
-- must keep its top-level keys inside that schema's vocabulary (basics, work, volunteer, education,
-- awards, certificates, publications, skills, languages, interests, references, projects, meta).
-- Population printed: 0-of-0 would be vacuous, not conforming.
-- expect: docs \| [1-9][0-9]*
-- expect: nonconforming_docs \| 0
-- expect: nonconforming_versions \| 0
SELECT 'docs | ' || count(*) FROM resume_documents;
SELECT 'nonconforming_docs | ' || count(*) FROM resume_documents rd
WHERE EXISTS (
  SELECT 1 FROM jsonb_object_keys(rd.doc) k
  WHERE k NOT IN ('basics','work','volunteer','education','awards','certificates',
                  'publications','skills','languages','interests','references','projects','meta'));

-- ★AND A VERSION IS THE SAME CLAIM. The check covered resume_documents and stopped there, so when two
-- seeded portfolios were written with `summary`/`experience` instead of `basics`/`work`, their earlier
-- VERSIONS carried the same wrong shape and no recipe looked. resume_versions is what the page shows
-- when somebody opens the history of their own CV - it is read by a person, exported, and sent to an
-- employer, so it owes the schema exactly what the current document owes it.
SELECT 'nonconforming_versions | ' || count(*) FROM resume_versions rv
WHERE EXISTS (
  SELECT 1 FROM jsonb_object_keys(rv.doc) k
  WHERE k NOT IN ('basics','work','volunteer','education','awards','certificates',
                  'publications','skills','languages','interests','references','projects','meta'));
