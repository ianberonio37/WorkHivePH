-- Declare what happens to a listing when the inquiry that bought it is deleted (2026-09-07).
--
-- marketplace_listings.sold_to_inquiry_id was the ONE foreign key of 204 that left its delete behaviour
-- at NO ACTION. Nothing in the product deletes an inquiry today - marketplace-seller.html closes them by
-- setting status = 'closed' - so no person can reach this yet. That is exactly why it is worth declaring
-- now: it is a loaded trap, not a live defect. The day a delete path is added, the person deleting an
-- inquiry would meet a raw constraint error naming a foreign key, which tells them nothing about what
-- they did or what to do instead.
--
-- SET NULL is the honest intent: the listing was still sold, it simply no longer knows which inquiry
-- bought it. NO ACTION would refuse the delete; CASCADE would delete a sold listing to tidy up an
-- inquiry, which is the more destructive reading of a weaker relationship.
alter table public.marketplace_listings
  drop constraint if exists marketplace_listings_sold_to_inquiry_id_fkey;

alter table public.marketplace_listings
  add constraint marketplace_listings_sold_to_inquiry_id_fkey
  foreign key (sold_to_inquiry_id) references public.marketplace_inquiries(id)
  on delete set null;
