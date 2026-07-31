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
