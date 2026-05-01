-- Add Facebook Messenger username to seller profiles
-- Buyers can tap a "Message on Messenger" button on listing detail / seller profile
-- which opens m.me/<username> directly. No spam-prone pre-filled text (Messenger
-- removed that feature) — buyers compose their own message inside Messenger.

ALTER TABLE public.marketplace_sellers
  ADD COLUMN IF NOT EXISTS messenger_username text;

-- Allow sellers to update their own Messenger handle (UPDATE column-level grant)
GRANT UPDATE (messenger_username, updated_at)
  ON public.marketplace_sellers TO authenticated;
