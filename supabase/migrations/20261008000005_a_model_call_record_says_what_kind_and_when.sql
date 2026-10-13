-- ★A RECORD THAT ONLY COVERED THE CALLS THAT ANSWERED (LM-O follow-up, 2026-10-08). The per-call record
-- (20261008000004, _shared/model-calls.ts) gave every SERVED text/vision call one ai_cost_log row. Three kinds of
-- model call still left nothing an operator could read:
--   * a chain that EXHAUSTED every provider - the person got a degraded answer and nothing said which providers
--     were asked or how long the walk took, unless the function happened to call logAICost itself;
--   * embedding, reranking, speech-to-text and text-to-speech calls (embed-entry, pdf-ingest, semantic-search,
--     voice-transcribe, voice-embeddings, tts-speak, and every RAG function's query embedding) - real provider
--     calls on real quotas, recorded nowhere;
--   * a call the function stopped waiting for (amc-orchestrator's 45 s race) that served AFTER the reply - its row
--     looked exactly like a call whose answer the person saw.
-- Four columns let one row say which of these it is:
--   kind             what the call was: generation (callAI / callAIMultimodal / a provider's chat completion),
--                    embedding, rerank, transcription (speech-to-text), speech (text-to-speech). Every existing
--                    row was a generation call, so the default is truthful for them.
--   providers_tried  the provider/model slots the chain asked, in order, each with its outcome
--                    ("groq/llama-3.3-70b-versatile=429", "gemini/gemini-2.5-flash=200"). On a failed row it is the
--                    whole walk; on a served row it shows how deep the answer came from.
--   audio_seconds    the length of the audio a transcription call was billed for, when the provider reports it.
--   late             true when the call finished after the function stopped waiting for it (a timeout race) or
--                    after the reply was sent. Its trace_id is still the reply's, so it joins to that request once.
-- RLS and grants are unchanged (table-level grants, no column ACLs; inserts stay service-role only). No view reads
-- the table. Forward-only and idempotent.

alter table public.ai_cost_log
  add column if not exists kind            text    not null default 'generation',
  add column if not exists providers_tried text[],
  add column if not exists audio_seconds   numeric(10,2),
  add column if not exists late            boolean not null default false;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.ai_cost_log'::regclass and conname = 'ai_cost_log_kind_check'
  ) then
    alter table public.ai_cost_log
      add constraint ai_cost_log_kind_check
      check (kind in ('generation', 'embedding', 'rerank', 'transcription', 'speech'));
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.ai_cost_log'::regclass and conname = 'ai_cost_log_audio_seconds_check'
  ) then
    alter table public.ai_cost_log
      add constraint ai_cost_log_audio_seconds_check check (audio_seconds is null or audio_seconds >= 0);
  end if;
end $$;

comment on column public.ai_cost_log.kind is
  'What the model call was: generation (text/vision answer), embedding, rerank, transcription (speech-to-text) or '
  'speech (text-to-speech). Written by _shared/model-calls.ts (LM-O, 2026-10-08).';
comment on column public.ai_cost_log.providers_tried is
  'The provider/model slots the chain asked for this call, in order, each with its outcome '
  '("groq/llama-3.3-70b-versatile=429"). On a failed row (status failed, provider chain) it is the whole exhausted walk.';
comment on column public.ai_cost_log.audio_seconds is
  'Seconds of audio a transcription call processed, when the provider reports it (Whisper verbose_json duration).';
comment on column public.ai_cost_log.late is
  'true when the call finished after the function stopped waiting for it (a timeout race) or after the reply was sent; '
  'trace_id is still the reply''s. A call the function stopped waiting for that served anyway is status fallback: the '
  'reply did not use it.';
