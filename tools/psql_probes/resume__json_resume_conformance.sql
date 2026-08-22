-- json_resume_conformance: the page claims "JSON Resume schema" at three sites, so every STORED doc
-- must keep its top-level keys inside that schema's vocabulary (basics, work, volunteer, education,
-- awards, certificates, publications, skills, languages, interests, references, projects, meta).
-- Population printed: 0-of-0 would be vacuous, not conforming.
-- expect: docs \| [1-9][0-9]*
-- expect: nonconforming_docs \| 0
SELECT 'docs | ' || count(*) FROM resume_documents;
SELECT 'nonconforming_docs | ' || count(*) FROM resume_documents rd
WHERE EXISTS (
  SELECT 1 FROM jsonb_object_keys(rd.doc) k
  WHERE k NOT IN ('basics','work','volunteer','education','awards','certificates',
                  'publications','skills','languages','interests','references','projects','meta'));
