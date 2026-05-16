-- Phase 11: Multilingual Support (Tagalog + Visayan + English)

create table if not exists multilingual_terms (
  id bigserial primary key,
  domain text not null,  -- maintenance, inventory, pm, risk, etc.
  english_term text not null,
  tagalog_term text,
  visayan_term text,
  context text,
  created_at timestamptz default now()
);

create index if not exists idx_terms_domain on multilingual_terms(domain, english_term);

-- Language preference per worker
create table if not exists language_preferences (
  worker_id uuid primary key,
  preferred_language text default 'en',  -- en, tl, ceb
  code_switch_allowed boolean default true,
  updated_at timestamptz default now()
);

-- Terminology coverage tracking
create table if not exists terminology_gaps (
  id bigserial primary key,
  language text,
  missing_term text,
  domain text,
  reported_by uuid,
  created_at timestamptz default now()
);

create index if not exists idx_gaps_language on terminology_gaps(language, domain);
