# WorkHive Marketplace — Go-Live Roadmap

**Status as of May 1, 2026**

The marketplace is fully built and tested in Stripe sandbox. Going live requires business registration, then a clean switch from sandbox to live mode.

---

## Where you are today

| Component | Status |
|---|---|
| Frontend (marketplace.html, admin, seller) | Built, tested |
| 5 Edge Functions (checkout, webhook, connect-onboard, connect-status, release) | Deployed to Supabase |
| Database (8 tables, indexes, triggers, full-text search) | Live on Supabase |
| Stripe sandbox integration | Working end-to-end |
| Business registration | Not yet done |
| Stripe live mode | Blocked by business registration |

---

## Phase 1 — Business Registration (Week 1–2)

You need a registered business to operate a marketplace in the Philippines and to qualify for Stripe live mode. The cheapest path is a **DTI Sole Proprietorship**.

### 1.1 DTI Business Name Registration (1–2 days, ~PHP 200–500)

- Go to [bnrs.dti.gov.ph](https://bnrs.dti.gov.ph)
- Fill in proposed business name (suggestions: "WorkHive PH", "WorkHive Industrial", or your full name + "Industrial Services")
- Choose territorial scope (Barangay, City, Regional, or National — National is recommended for online business; cost increases with scope)
- Pay online via GCash, Maya, or credit card
- Download your Certificate of Business Name Registration (BNRS Certificate)

**What you get:** Legal proof you own the business name. Valid for 5 years.

### 1.2 Mayor's / Business Permit (3–7 days, ~PHP 1,000–3,000)

- Go to your local City Hall or Barangay Hall
- Bring: BNRS Certificate, valid ID, proof of address (utility bill or barangay clearance)
- Fill out application form
- Pay business tax based on your declared capital (start small to keep cost low)

**What you get:** Mayor's Permit and Barangay Clearance. Required for BIR.

### 1.3 BIR Registration (Form 1901) (1 day, ~PHP 530)

- Go to your local BIR Revenue District Office (RDO) where you live
- Bring: BNRS Certificate, Mayor's Permit, valid ID, your existing TIN
- File **BIR Form 1901** (Application for Registration for Self-Employed)
- Pay PHP 500 registration fee + PHP 30 documentary stamp
- Buy and have stamped: BIR-registered receipts/invoices (Form 0605, ~PHP 2,000 for the booklet)
- Get your **BIR Certificate of Registration (Form 2303)**

**What you get:** Form 2303 (the document Stripe will ask for) + Authority to Print receipts.

### 1.4 Business Bank Account (optional but recommended) (1–3 days)

- Open a separate bank account in your business name (or use a personal one for sole proprietor — Stripe accepts both)
- Recommended banks: BPI, BDO, Metrobank — all integrate cleanly with Stripe Philippines
- Bring: BNRS, Mayor's Permit, Form 2303, valid ID

**Why separate:** Cleaner books at tax time. Stripe deposits land here.

---

## Phase 2 — Stripe Live Mode Switch (1 hour)

Once you have your DTI Certificate + Form 2303 + bank account, switching Stripe takes under an hour.

### 2.1 Switch Stripe to Live (15 min)

- Stripe Dashboard → click **Switch to live account** (top right)
- Fill in business identity: legal name, DTI business name, registered address
- Tax ID: enter your TIN from Form 2303
- Add bank account details (where Stripe deposits your platform fees)
- Verify phone number and email
- Submit for review

**Stripe approval time:** Usually under 24 hours for PH businesses with complete documents.

### 2.2 Update STRIPE_SECRET_KEY (5 min)

- Stripe live dashboard → Developers → API keys
- Copy the new `sk_live_...` Secret key
- Supabase Dashboard → Project Settings → Edge Functions → Secrets
- Edit `STRIPE_SECRET_KEY` → paste live key → Save

### 2.3 Re-register webhook on live (10 min)

- Stripe live dashboard → Developers → Webhooks → Add destination
- URL: `https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/marketplace-webhook` (same as before)
- Events: `checkout.session.completed`, `checkout.session.expired`
- Copy the new live signing secret (`whsec_...`)
- Supabase Vault → update `STRIPE_WEBHOOK_SECRET` → Save

### 2.4 Verification test (15 min)

- Post a low-price listing (PHP 50)
- Approve it via marketplace-admin.html
- From a different account, click Buy Now
- Use a real card with PHP 50
- Verify the order moves through `escrow_hold` → `released` after Confirm Receipt
- Verify funds land in your Stripe balance (visible in Stripe dashboard immediately, payout to your bank in 1-2 business days)
- Refund yourself in Stripe to clean up

---

## Phase 3 — Soft Launch (Week 3–4)

Don't open to the public on Day 1. Soft launch with a small group.

### 3.1 Internal QA (3 days)

- Run through every flow yourself: post listing, get it approved, buy from another account, dispute, review
- Test on phone (mobile is your primary channel)
- Test on slow connection (throttle in Chrome DevTools)
- Check email notifications fire

### 3.2 Invite 5–10 trusted users (1–2 weeks)

- Pick people you trust: friends in industrial roles, your hive members, early supporters
- Get them to: post real listings, complete real transactions, give feedback
- Their listings stay private to your test pool initially (use the hive_id scoping)
- Watch for confusion in the UI. Fix anything they trip on.

### 3.3 Pricing decisions

| Lever | Default | When to change |
|---|---|---|
| Platform fee | 5% | Lower to 3% if competing with PayMongo direct |
| Escrow hold period | 7 days | Lower to 3 days for trusted Gold sellers |
| Listing rate limit | 20/hive/day | Raise once you trust the seller pool |

---

## Phase 4 — Public Launch (Week 5+)

### 4.1 Go-live announcement

- Post in WorkHive Community board (community.html) — your existing users see it first
- Update `index.html` to feature the marketplace prominently
- Email any waitlist subscribers (`early_access_emails` table already exists)
- Post on LinkedIn, Facebook industrial maintenance groups

### 4.2 First-week monitoring

- Watch `platform_health.html` daily for validator regressions
- Check `marketplace_orders` for stuck `pending_payment` rows (means buyer abandoned checkout)
- Watch `marketplace_disputes` for early signals
- Monitor Stripe Radar for fraud flags
- Reply to every inquiry yourself within 24 hours to set the response-time culture

### 4.3 Seller acquisition

The marketplace is only as valuable as the listings on it. First sellers are critical.

- **Direct outreach:** message industrial parts dealers, CMMS trainers, freelance maintenance engineers in your network
- **Onboarding flow:** offer to manually walk the first 10 sellers through Stripe Connect onboarding
- **First listings free:** waive the platform fee on the first 5 transactions per seller as an incentive
- **Reviews matter most:** prioritize getting Bronze sellers their first 5-star reviews so they can climb to Silver

---

## Phase 5 — Scale (Month 2+)

Items from your scaling strategy (already documented in skills) that activate at scale:

| Threshold | Action |
|---|---|
| 50 listings | Already handled — keyset pagination + tsvector search are live |
| 200 listings | Add image CDN (Cloudflare R2 + Image Resizer) |
| 500 listings | Move analytics queries to Postgres views/RPCs |
| 50 hives | Upgrade to Supabase Pro ($25/mo) for pgBouncer + better limits |
| 100 disputes | Activate the pg_cron auto-escalation (currently commented out in migration) |
| 500 daily transactions | Migrate to Stripe Radar for Platforms |

---

## Phase 6 — Compliance & Tax (Ongoing)

### Quarterly (every 3 months)

- File BIR Form 2551Q (Percentage Tax) by the 25th of the following month
- Or BIR Form 2550Q (VAT) if registered for VAT (only if annual gross sales > PHP 3M)

### Annually

- File BIR Form 1701 (annual income tax return) by April 15
- Renew Mayor's Permit (January each year)
- Submit Books of Accounts to BIR for stamping
- Renew DTI Certificate every 5 years

### Marketplace-specific

- Issue Stripe-generated invoices to sellers for the 5% platform fee (or set up your own BIR-stamped receipts)
- Track all marketplace_orders.released as platform revenue
- 1099-K equivalent (PH does not have this yet, but track gross seller payouts in case BIR introduces marketplace facilitator rules)

---

## Critical things NOT to skip

1. **Test in sandbox first.** Every change you make should be tested with `4242 4242 4242 4242` before going live.
2. **Always have a refund plan.** If something goes wrong with an order, you can refund from the Stripe dashboard within 90 days.
3. **Don't disable the platform fee until you can afford to.** 5% is your only revenue.
4. **Don't skip KYB on sellers.** Stripe requires it. Without it, sellers cannot receive payouts.
5. **Run the platform guardian before every commit.** `python run_platform_checks.py --fast` — already part of your workflow.
6. **Don't push to production without running guardian.** Every push has 49 PASS as the baseline.

---

## Quick reference — what's where

| Tool | URL |
|---|---|
| Marketplace (browse) | `marketplace.html` |
| Seller dashboard | `marketplace-seller.html` |
| Admin (supervisor) | `marketplace-admin.html` |
| Stripe sandbox | dashboard.stripe.com (test mode) |
| Stripe live (after Step 2.1) | dashboard.stripe.com (live mode) |
| Supabase | hzyvnjtisfgbksicrouu.supabase.co |
| GitHub | github.com/ianberonio37/WorkHivePH |
| BIR eFPS | efps.bir.gov.ph |
| DTI BNRS | bnrs.dti.gov.ph |

---

## Estimated timeline summary

| Phase | Duration | Cost |
|---|---|---|
| 1. Business registration | 1–2 weeks | ~PHP 4,000–6,000 |
| 2. Stripe live switch | 1 hour | Free |
| 3. Soft launch | 2 weeks | Free |
| 4. Public launch | Ongoing | Free |
| 5. Scale upgrades | When triggered | $25–500/mo |
| 6. Tax & compliance | Quarterly + annually | Variable |

**Total time from today to first real transaction:** 2–3 weeks if you start DTI registration this week.

---

*Generated May 1, 2026 — keep this updated as you complete each phase.*
