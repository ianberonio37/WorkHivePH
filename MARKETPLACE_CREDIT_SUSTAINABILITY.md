# Is the credit economy sustainable? — the study

> **Ian, 2026-07-31 (DECIDED):** *"I'll just go on completion, 5%, then 1% cashback in a form of credits for
> consumer. But we still have to study more first for the overall economics of this credits economy, for the
> sustainable approach for running this platform."*

The model is locked: **5% commission on verified completion · 1% consumer cashback in credits · free to
list.** This studies whether it can actually carry the platform, and where it breaks.

## §1 · The thing that makes this economy different from a normal 4% take

Credits are **bought with cash and consumed as fees**. That makes three separate quantities that a naive
"we take 4%" hides:

| quantity | what it is | why it matters |
|---|---|---|
| **cash in** | GCash top-ups | the only real money that ever enters |
| **credits outstanding** | sold-but-unspent + cashback minted | a **liability** — services owed, not profit |
| **credits consumed** | commission debited on completion | the moment revenue is actually *earned* |

Cash arrives **before** revenue is earned. That is a float, and it is genuinely helpful for a bootstrapped
platform — but it means **the bank balance overstates the business**. Money sitting there is partly other
people's unspent credit.

**The discipline that follows:** never read the GCash balance as profit. Earned revenue is
`SUM(ledger WHERE entry_type='commission')`, and the liability is
`credits_sold − credits_consumed + cashback_minted`. Both are already derivable from `service_credit_ledger`,
which is exactly why cashback was built as a ledger entry rather than a balance column.

## §2 · The cashback is a discount on future credit sales — and that is fine

Follow one cashback peso through the loop:

1. Consumer completes a ₱2,000 job → **20 credits minted**, no cash behind them.
2. Consumer spends those 20 credits on a future service.
3. The provider receives them, and uses credits to pay **their** commission.
4. The platform's commission is paid in credits it minted itself.

So a cashback peso does not cost cash today — it **reduces future credit sales by up to one peso**. It is a
discount, not an expense, and it only lands if the consumer comes back. Three consequences:

- **Breakage is real revenue.** Credits never spent are a discount never taken. Retail gift-card breakage runs
  ~10–20%; assume conservatively and treat any breakage as upside, never as plan.
- **The 1% is cheap for what it buys.** It is the only reason a *consumer* holds a balance at all, which is
  the difference between a wallet that exists for billing and a wallet that creates return visits.
- **It must never become cash-outable.** The moment it can be withdrawn it stops being a discount and becomes
  stored value — a different business and a different regulator.

## §3 · Break-even, honestly

Net take is **4% of completed GMV** (5% in, 1% back out).

| monthly completed GMV | platform revenue |
|---:|---:|
| ₱100,000 | ₱4,000 |
| ₱500,000 | ₱20,000 |
| ₱1,000,000 | ₱40,000 |
| ₱2,500,000 | ₱100,000 |

At a ₱2,000 average job that is **50 · 250 · 500 · 1,250 completed jobs/month**.

**The uncomfortable truth: 4% of a small GMV is a small number.** 250 completed jobs a month is real traction
for a new marketplace, and it yields ₱20,000. So the model does not fail on rate — it fails or succeeds on
**volume and cost discipline**. Two implications worth taking seriously:

1. **Keep fixed costs near zero for a long time.** This is already the platform's instinct — free-tier AI,
   a self-hosted embedder, no paid infra — and that instinct is load-bearing, not thrift for its own sake.
2. **Do not discount the rate to buy growth.** 4% → 3% is a 25% revenue cut for a change no provider will
   even notice. Growth comes from more completed jobs, not a cheaper take.

## §4 · Where this model actually breaks — five failure modes worth watching

1. **Credits bought, jobs never completed.** Float grows, revenue does not. Looks like success in the bank
   account. *Watch:* `credits_outstanding / monthly_commission`. Rising sharply means providers are stocking
   up but not earning — a supply problem wearing a cash-flow disguise.
2. **The commission is unpayable exactly when it is owed.** A provider completes a job with an empty wallet.
   *Mitigation:* the **min-balance to list** knob (`min_list_balance`, already built, currently 0). Set it and
   the wallet is never empty at completion time.
3. **Cashback outruns commission in a promo.** Structurally impossible now — the solvency CHECK refuses
   `cashback_pct > commission_pct + listing_fee_pct` — but the same discipline must extend to *vouchers*,
   which mint credits with no fee behind them at all.
4. **Refunds and disputes.** A settled job that is later disputed has already minted cashback and debited
   commission. *Needs:* a compensating ledger entry (`adjustment`), never a delete — the ledger is the audit
   trail and a deleted row is a lie.
5. **The float is spent.** The most dangerous one, because it is invisible until it is fatal: credits
   outstanding are **services owed**. Spending that cash on operating costs works until providers spend their
   balances faster than new top-ups arrive.

## §5 · The four numbers to watch

All derivable from `service_credit_ledger` today, and worth a founder-console tile each:

| metric | formula | healthy signal |
|---|---|---|
| **earned revenue** | `SUM(amount) WHERE entry_type='commission'` | grows with GMV |
| **credit liability** | `topups − commission + cashback − spend` | grows *slower* than revenue |
| **liability cover** | `cash_on_hand / credit_liability` | **stays ≥ 1.0** |
| **cashback ROI** | repeat-purchase rate of consumers holding credits vs not | > 1, or the 1% is a gift |

**Liability cover ≥ 1.0 is the one that matters.** It says: if every credit were spent tomorrow, the platform
could honour it. That is the difference between a float and a hole.

## §6 · What to build next, in order

1. **Set `min_list_balance`** to a real number (₱100–200 in credits). The knob exists and is unread today —
   it is the single best protection against failure mode 2, and it delivers the float your original
   listing-fee instinct wanted.
2. **A commission-on-completion minter**, mirroring `mint_service_cashback`: debit `commission_pct` from the
   provider wallet on `settled`, idempotent by partial unique index, as a ledger entry.
3. **The four metrics as a founder-console tile**, computed from the ledger. Ship it *before* real money moves
   — a number you cannot see is a number you cannot manage.
4. **A dispute-adjustment path** (failure mode 4): compensating `adjustment` entries, never deletions.
5. **A liability-cover gate**: fails if cover drops below 1.0. The economics deserve the same standing
   enforcement as the schema.

## §7 · The one-line verdict

**The model is sound and the rate is right; the risk is not the 4%, it is treating the float as profit.**
Keep credits non-withdrawable, keep fixed costs near zero, set the min-balance, and watch liability cover
above 1.0 — and this funds a lean platform. The credit economy's real advantage is that money arrives before
revenue is earned; its real danger is forgetting that those are different things.

---

# Part II — the expansion

## §8 · The attack the 4% actually invites: buying reputation

Cashback cannot be farmed for profit, and the arithmetic is what protects it: a provider who fakes a job with
a sock-puppet consumer pays **5% commission** to receive **1% cashback** — a guaranteed **4% loss**.
Self-dealing for credits is unprofitable by construction, which is the right way to defend it.

**But the same 4% is a price list for something else.** Tier is derived from completed sales, so a scammer is
not buying credits — they are buying a **gold badge**:

| target | fake jobs | at ₱2,000 each | cost at 4% |
|---|---:|---:|---:|
| silver (11 sales) | 11 | ₱22,000 GMV | **₱880** |
| gold (51 sales) | 51 | ₱102,000 GMV | **₱4,080** |

> **⚠ CORRECTION, found by testing this section's own premise: it costs ₱0, not ₱4,080.**
> `total_sales` counts `marketplace_listings WHERE status='sold'` — and a seller may mark their OWN listing
> sold, while `marketplace_listings` records **no buyer at all**. Verified live as a real authenticated
> seller (not as the table owner): **12 self-marked listings → silver; 51 → gold. No buyer, no order, no
> payment, no commission.** `marketplace_orders`, the only table carrying `buyer_name`, is empty and
> vestigial since the Stripe removal. Banked as `TB-TRUST-tier-selfmint`.
>
> The economics below were sound but metered the **wrong event**: a self-declared STATUS, not a completed
> TRANSACTION. **An economic model is only as good as the event it meters.**
>
> **✅ CLOSED 2026-07-31 (mig `20260731000017`).** The counterparty this section said did not exist was
> *built*: a listing cannot reach `sold` without naming the **inquiry it sold through**, that inquiry must
> belong to **that** listing (so one inquiry cannot "sell" a whole catalogue), and
> `recompute_seller_sales_and_tier` now counts **DISTINCT counterparties instead of rows** — the half that
> actually stops farming, since 51 sales to one person are worth one. Thresholds were deliberately left
> alone: loosening them to compensate would have handed back exactly what the fix took. A second layer
> turned up unprompted during the proof — **RLS already refuses a seller creating their own buyer inquiry**,
> so the forgery now needs a real counterparty at two independent layers.
> `TB-TRUST-tier-selfmint` flipped from documenting the hole to guarding the fix (0 sales, bronze), exactly
> as its own last assertion predicted it would.
>
> **Residual, stated rather than papered over:** inquiries carry **free-text** identity, so farming via
> invented contacts is still possible. A nullable `buyer_auth_uid` is now preferred by the count, and
> contacts are normalised (one phone written three ways folds to one buyer), but the remainder is a
> **detection** problem and lives in the fraud model as `TB-FRAUD` A2 — not in this guard. A fix that claims
> to close a hole it only narrows is worse than the hole, because it stops anyone looking.

**₱4,080 for a gold badge would be cheap** if it wins one real ₱50,000 industrial contract — and until
2026-07-31 the real price was zero. With the counterparty requirement in place the price is no longer money
at all: it is **51 different people who will vouch for you**, which is the thing the badge was always
supposed to mean. The trust ladder no longer inverts the credit ladder — both now defend themselves.

What already blunts it, and it is not nothing: ratings recompute only over `verified_purchase = true` reviews
(confirmed in `update_seller_rating`); `guard_marketplace_order_status` refuses a client-side jump to
`released`/`refunded`; the D9 trust knobs are tighten-only. What remains is that **the cost of faking scales
linearly while the value of a badge is a step function** — gold is worth the same whether earned or bought.

**Suggestions, cheapest first:**

1. **Make tier require DISTINCT COUNTERPARTIES**, not just a sale count — gold needs ≥51 sales across ≥20
   distinct buyers. A sock-puppet ring must then scale its *identities*, which is far harder than scaling its
   pesos. One line in the tier query, and the highest-leverage fix here.
2. **Age the badge.** Require gold's sales to span ≥90 days. Reputation bought in a weekend is the signature
   of farming; real accumulation is slow.
3. **Watch a ratio, not a job:** `completed_jobs / distinct_counterparties` per seller. A real provider trends
   toward many buyers; a farm trends toward few.
4. **Never sell verification.** A paid KYB badge turns the one signal money *cannot* buy into one it can.

## §9 · Revenue lines beyond the 4%, ranked by whether they corrupt the marketplace

| line | verdict | why |
|---|---|---|
| **Featured placement** | **ADOPT, later** | a fee for *visibility*, chosen when it pays. Does not tax existence. |
| **Pro subscription** (₱X/mo: lower commission, analytics, more listings) | **ADOPT at scale** | turns lumpy commission into predictable MRR, and the providers who want predictability self-select. Only once volume makes the trade real. |
| **Lead fees on quotes** (Thumbtack) | **DEFER** | roadmap §5 keeps quotes free to protect thin supply. Charging for a lead that may not convert is a listing fee in another hat. |
| **Paid verification / badges** | **REJECT** | corrupts the trust signal, per §8. |
| **Payment processing margin** | **BLOCKED** | needs business registration; the platform is deliberately GCash-personal for now. |
| **Auxiliary services** (reports, AI briefs, parts sourcing) | **WATCH — strongest** | see below. |

**The strongest non-obvious line is the last.** The maintenance intelligence this platform already generates —
failure history, PM compliance, asset health, the now-99.97%-retrievable knowledge corpus — is worth money to
a hive *independently of any transaction*. That revenue does not depend on marketplace liquidity, which is
this model's single largest vulnerability. It is the natural hedge.

## §10 · Sizing the min-balance, concretely

`min_list_balance` is built and currently 0. Too low protects nothing; too high is the listing fee you
rejected, wearing a deposit's clothes. **Principle: cover one job's commission, not one month's.**

- A ₱2,000 job costs **₱100** in commission.
- **₱200** covers two average jobs, so a provider is never caught empty at completion.
- ₱500+ stops being a deposit and becomes an entry fee — the supply suppression you avoided.

**Suggestion: ₱200, per-hive tunable** (the knob already is), and say it plainly in the UI: *"₱200 keeps your
listings live. It is spent on your commission — it is not a fee."* Providers accept a deposit they can spend
far more readily than a fee they cannot.

## §11 · Philippine specifics that change the model's shape

1. **Payday cycles (15th & 30th).** Top-ups and demand will spike biweekly; monthly averages will mislead.
2. **13th-month pay (December).** A real annual demand spike — the best month to spend acquisition vouchers,
   because the cashback lands when people are already spending.
3. **Typhoon season (Jun–Nov).** Repair demand is *counter*-cyclical to comfort: storm damage drives urgent
   work. Then **capacity**, not demand, is the constraint — precisely when per-hive
   `broadcast_radius_start_m` earns its keep.
4. **GCash P2P limits.** Personal accounts have ceilings, so a large top-up may need splitting — friction
   exactly where money enters. **Cap credit packs comfortably under the limit** (₱1,000 / ₱2,500 / ₱5,000)
   rather than letting a provider discover the ceiling mid-transfer.
5. **Prepaid is culturally native** — load, e-wallets, prepaid everything. The credit model matches how people
   already pay, which is a genuine tailwind worth saying out loud in the copy.

## §12 · Credit packs: price the behaviour you want

A flat "buy N credits" wastes a lever. Bulk discounts denominated **in credits** are commission discounts for
committed providers that cost nothing when unredeemed:

| pack | credits | effective discount | what it buys |
|---:|---:|---:|---|
| ₱1,000 | 1,000 | — | low-friction entry |
| ₱2,500 | 2,600 | 4% | mild commitment |
| ₱5,000 | 5,300 | 6% | a provider who has pre-paid ~50 jobs of commission |

**Why this beats cutting the rate:** the discount is paid in *credits* (a liability that may never be spent)
rather than *cash* (gone immediately), and it is opt-in by your most committed providers. Headline stays 5%;
the committed provider effectively pays ~4.7%.

## §13 · Vouchers — the acquisition line already half-built

`service_vouchers` and `service_voucher_redemptions` exist, and roadmap §5 has them platform-funded with the
provider reimbursed in credits on verified completion. That makes a voucher a **real CAC**:

- **A ₱200 signup voucher is ₱200 of real liability.** At 4% of a ₱2,000 job you earn ₱80 per completion, so
  a ₱200 voucher needs **~2.5 completed jobs** to pay back. That is the bar to hold vouchers to.
- **Vouchers are the one place cashback's self-funding logic does NOT apply** — they mint with no fee behind
  them. The §4 solvency CHECK covers cashback but **not vouchers**: that is a live gap, and a per-period
  voucher budget closes it.
- **Completion-gate every voucher**, exactly as cashback is, or it becomes a free-credit faucet.

## §14 · When to raise the rate (and how not to)

4% net is thin and should eventually rise. The wrong way is changing it on everyone at once.

- **Grandfather by cohort.** Existing providers keep their rate; new ones join at the new one. The D9 knobs
  already make per-*hive* rates expressible, so per-*cohort* is a small extension.
- **Raise only after liquidity is proven** — when leaving would cost a provider real income. Before that, the
  rate is not what keeps them.
- **Prefer adding lines to raising the rate.** Featured placement and subscriptions are opt-in; a rate rise
  taxes everyone, including the providers you most want to keep.

## §15 · Free levers worth more than 1%

Tier benefits that cost nothing but are worth real money — and which make the ladder valuable enough that
faking it (§8) matters more:

- **Broadcast priority** for higher tiers — pure ordering, zero cost.
- **More concurrent listings** at higher tiers — the per-hive caps already express this.
- **A faster verification queue** for gold — your time, not your money.
- **Search prominence**, earned rather than bought.

Every peso of cashback is a peso of liability; a priority slot costs nothing and may retain better. **Spend
the free levers first.**

## §16 · The revised short list

1. **`min_list_balance` = ₱200**, framed as a spendable deposit, never a fee.
2. **Tier requires distinct counterparties** (≥20 buyers for gold) — highest-leverage anti-farming fix, one
   line of SQL.
3. **Voucher budget cap** — the solvency CHECK covers cashback but not vouchers. Live gap.
4. **Credit packs** with credit-denominated bulk discounts, capped under GCash P2P limits.
5. **The four ledger metrics on the founder console — before real money moves.**
6. **Paid maintenance-intelligence reports** — the one revenue line that does not depend on marketplace
   liquidity, and therefore the hedge against this model's main vulnerability.
