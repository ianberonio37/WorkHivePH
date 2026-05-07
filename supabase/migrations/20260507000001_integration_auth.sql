-- Phase 3.1: Add auth_token + sync status to integration_configs.
-- auth_token stores the API key / OAuth token for the CMMS endpoint.
-- Encrypted at rest by Supabase disk encryption.
-- NOTE: Migrate to Supabase Vault (supabase.vault.secrets) before enterprise GA.

ALTER TABLE integration_configs
  ADD COLUMN IF NOT EXISTS auth_token      text,          -- API key / bearer token
  ADD COLUMN IF NOT EXISTS last_sync_status text,         -- 'success' | 'failed' | 'partial'
  ADD COLUMN IF NOT EXISTS last_sync_error  text,         -- error message if last sync failed
  ADD COLUMN IF NOT EXISTS delta_cursor     text;         -- last synced date for delta queries
