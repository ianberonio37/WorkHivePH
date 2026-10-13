-- ★A LISTING THE AI DRAFTED WAS SAVED AS IF THE SELLER WROTE ALL OF IT (LM-A walk, LM332, 2026-10-07).
-- marketplace.html's listing assist fills the category and drafts the description, the seller reviews it and posts -
-- the approval is the seller's, and that part was always recorded (seller_name, the audit row). What the listing never
-- recorded was WHICH of its words the AI wrote, so a buyer-facing description drafted by a model was indistinguishable
-- from one a seller typed. This column holds the fields the AI filled that the seller kept (empty when the seller wrote
-- or rewrote them) - the same accountability project lessons already carry (_ai_generated_lessons, PJ14).
alter table public.marketplace_listings
  add column if not exists ai_assisted_fields text[] not null default '{}';

comment on column public.marketplace_listings.ai_assisted_fields is
  'Fields of this listing the AI listing assist drafted and the seller kept unchanged (e.g. {description,category}); '
  'empty when the seller wrote them. Written by marketplace.html at post time (LM-A, 2026-10-07).';
