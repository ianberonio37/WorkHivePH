-- SL S4 (2026-10-15): a logbook id is an identifier, never text a person can shape.
--
-- logbook.id is a TEXT column. Its default is a uuid, but the client writes its own ids ('pm-<time><random>' for an
-- entry logged from the PM scheduler), and nothing constrained what an id may contain: the insert policy checks the hive
-- and the author, not the id. The S4 walk, answering every read with a hostile payload in the stored text, saw logbook
-- run that payload FOUR times through the one place an id is drawn - onclick="openModal('<id>')" on every entry card -
-- so any active member of a hive could have stored an entry whose id closes that attribute and adds a handler of its
-- own, run for every colleague who opens the logbook.
--
-- The render is fixed in the page (the id passes through escJsAttr, and validate_handler_values_escaped holds every
-- inline handler on the platform to it). This is the other half: the database refuses an id that is not a token. Every
-- id the product writes is one - all 31,257 local rows match, the longest 40 characters.
--
-- NOT VALID: the rule holds for every write from now on without re-reading the rows already stored, so the migration
-- can never fail on a production row nobody has measured. VALIDATE it after a read of production confirms every
-- existing id matches.
alter table public.logbook drop constraint if exists logbook_id_is_a_token;
alter table public.logbook
  add constraint logbook_id_is_a_token check (id ~ '^[A-Za-z0-9_-]{1,80}$') not valid;
