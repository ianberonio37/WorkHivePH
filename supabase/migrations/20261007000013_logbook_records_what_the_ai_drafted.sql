-- ★AN ENTRY THE AI DRAFTED WAS SAVED AS IF THE TECHNICIAN WROTE ALL OF IT (LM-V walk, LM422, 2026-10-07).
-- logbook.html has three AI paths that fill the entry form - "Speak to fill" (voice-logbook-entry), "Photo defect
-- capture" (visual-defect-capture) and the companion's logbook.create voice intent - and one that fills the Register
-- Asset form ("Scan nameplate", equipment-label-ocr). In every case the person reviews and taps Save, so the approval
-- is theirs and that part was always recorded (worker_name, auth_uid, the audit row). What the saved row never recorded
-- was WHICH of its words the AI wrote: the logbook POST, the fault_knowledge row embed-entry upserts from it (source
-- 'manual') and the asset_nodes upsert were indistinguishable from rows a person typed. fault_knowledge is the RAG
-- corpus intelligence-api / intelligence-report / semantic-search cite back as field experience, so a model's draft
-- re-entered the knowledge base as a technician's own account.
--
-- Same column, same meaning, as the marketplace precedent (20261007000001, LM332): the fields the AI filled that the
-- person KEPT unchanged; empty when the person wrote or rewrote them. It does not change authorship (the person
-- approved the row) and it does not change fault_knowledge.source: a person-saved entry stays 'manual', which keeps
-- fault_knowledge_ai_provenance_pairing ((source LIKE 'ai\_%') = (ai_model IS NOT NULL)) satisfied. source='ai_*' stays
-- reserved for rows a model wrote with no person in between (visual-defect-capture's analyze-time insert).
--
-- No view, policy, grant or trigger needs to change: the views over these tables were expanded at creation and do not
-- pick the column up; the table-level grants already cover a new column (no column ACLs exist on these tables); the
-- row-diffing triggers (wh_guard_supervisor_approval, audit_logbook_post_close_amendment, enqueue_for_embedding) read
-- named keys or whole rows and are indifferent to one more column. Forward-only and idempotent.

alter table public.logbook
  add column if not exists ai_assisted_fields text[] not null default '{}';

alter table public.fault_knowledge
  add column if not exists ai_assisted_fields text[] not null default '{}';

alter table public.asset_nodes
  add column if not exists ai_assisted_fields text[] not null default '{}';

comment on column public.logbook.ai_assisted_fields is
  'Fields of this entry an AI path drafted (voice fill, photo defect capture, companion logbook.create) and the person '
  'kept unchanged (e.g. {problem,action,root_cause}); empty when the person wrote them. Written by logbook.html at save '
  'time (LM-V, LM422, 2026-10-07).';

comment on column public.fault_knowledge.ai_assisted_fields is
  'For a person-saved entry (source manual): which of this row''s fields the AI drafted and the person kept, carried from '
  'the source logbook entry by embed-entry. A row a model wrote on its own is marked by source/ai_model instead '
  '(LM-V, LM422, 2026-10-07).';

comment on column public.asset_nodes.ai_assisted_fields is
  'Fields of this asset the nameplate OCR (equipment-label-ocr) filled and the person kept unchanged '
  '(e.g. {manufacturer,model,serial_no}); empty when typed. Written by logbook.html Register Asset (LM-V, LM422, 2026-10-07).';
