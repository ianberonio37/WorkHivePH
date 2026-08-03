# The credit economy - refining the listing-fee idea  **[SUPERSEDED 2026-08-03 - see the final design at the end]**

> **Ian, 2026-07-31:** *"when a service-provider lists a service they need to buy credits from me via GCash;
> the credits needed to list is 5% of the total listing price. A consumer who avails/buys a service gets 1%
> cashback in credits. Refine my thoughts and research sustainable economics."*
>
> **Method:** researched internally first. The platform **already has a locked monetization design** and the
> ledger machinery to run it, so the honest job is not to invent a model — it is to show where this idea
> agrees with it, where it diverges, and what the divergence costs.

## §1 · What we already decided (and already built)

`SERVICE_HAILING_ROADMAP.md` §5 locks the model:

> **Monetization = prepaid provider credit wallet + commission-in-credits ON VERIFIED COMPLETION + a
> min-balance to accept** (Grab PH ₱100 precedent). Opening rates: consumer ~10%, industrial B2B ~5%. Quotes
> FREE early to protect thin supply. **GCash-personal-only intake** → founder verification queue → ledger
> mint. Credits **non-withdrawable** prepaid fees, not stored value.

The tables exist and are guarded: `service_credit_topups` (with `guard_service_topup_status` refusing
self-verification — an admin cannot verify their own top-up), `service_credit_ledger`, and the trust/tier
machinery.

**Your idea agrees with the big things** — prepaid credits, GCash intake, non-withdrawable, ~5%. It differs on
exactly one axis, and that axis is the whole question:

| | roadmap §5 | your idea |
|---|---|---|
| **when the 5% is charged** | on **verified completion** | at **listing time** |
| what the provider pays for | an outcome they earned | permission to be visible |

## §2 · Why "when" is the entire economics

A listing fee is charged per listing; revenue only exists per *sale*. So what the provider actually feels is
not 5% — it is **5% ÷ sell-through**:

| sell-through | what a 5% listing fee really costs |
|---:|---:|
| 100% | 5% |
| 50% | **10%** |
| 20% | **25%** |
| 10% | **50%** |

A young marketplace has *low* sell-through — that is what "young" means. So a listing fee bites hardest
exactly when supply is most fragile, and it bites the honest provider hardest of all: the one who lists ten
real services and sells two subsidises everyone else. Their rational response is to list less, list only sure
things, or raise prices to cover dead listings — all of which shrink the catalogue a buyer sees, which lowers
sell-through further, which raises the effective rate again. That loop is why Craigslist and Etsy can charge
listing fees and a new entrant generally cannot: they already have the demand that makes a listing pay.

**Charging on completion inverts the loop.** The provider risks nothing to be visible, so the catalogue grows;
a bigger catalogue converts better; you earn on every conversion. You are paid out of value created rather
than out of hope.

## §3 · What you actually want from "charge at listing" — without the damage

Read generously, charging upfront buys three real things. All three are obtainable without a listing fee:

| what you want | listing fee gives it | better instrument |
|---|---|---|
| **cash in hand early** | yes | **min-balance to list** — the provider tops up via GCash and must *hold* it to publish. Your float arrives; credits are only DEBITED on a sale. |
| **skin in the game / anti-spam** | yes | the same held balance, plus the existing per-hive listing caps (`check_listing_rate`, 20/day) |
| **predictable revenue** | no — it scales with *listings*, which you do not control | commission scales with GMV, which is the thing you are growing |

**The min-balance is the key move.** It is already roadmap §5 (the Grab PH ₱100 precedent), it gets your money
in the door at exactly the moment your idea wanted it, and it costs a provider nothing to be listed — only to
*earn*. Float and commitment signal, without taxing an empty catalogue.

## §4 · The 1% cashback is the strongest part of the idea

Keep it, and understand why it is cheap:

- It is paid in **non-withdrawable credits**, so it is a **discount on a future purchase**, not cash out. Its
  true cost is well under 1% after breakage (credits never spent), and it only pays out if the customer
  returns — which is the behaviour you are buying.
- It makes the wallet **two-sided**. Today only providers hold credits, so the wallet is a cost centre with
  one reason to exist. Give consumers a balance and it becomes a reason to come back.
- Funded from the take, net platform revenue is **5% − 1% = 4%** of completed GMV.

Two guardrails it needs:

1. **Cashback is a liability the moment it is minted** — a `service_credit_ledger` entry with its own
   `ref_kind`, never a number on a profile. (This platform has already been bitten by trust numbers standing
   on nothing.)
2. **Only on VERIFIED completion**, never on order creation — otherwise self-dealing mints free credits, the
   exact shape `guard_marketplace_order_status` and the trust guards already refuse elsewhere.

## §5 · The refined model

> **Free to list. Pay when you earn. Come back for the cashback.**

1. **Listing: FREE**, gated by a **min credit balance** (suggest ₱100–200, per-hive tunable through the D9
   knobs that landed today) plus the existing daily listing caps.
2. **Completion: 5% commission in credits**, debited on *verified* completion — the event the guards already
   police. Consumer-segment jobs can carry the roadmap's ~10%; industrial B2B ~5%.
3. **Consumer: 1% cashback in credits** on verified completion, minted as a ledger entry.
4. **Net take: 4%** of completed GMV, effectively ~4.3–4.7% after breakage on the cashback.
5. **Later, and this is where a listing fee genuinely belongs:** paid **featured/boosted placement**. A fee for
   *visibility* is something a provider chooses when it pays for itself; a fee for *permission* is a tax they
   resent. Same revenue line, opposite incentive.

### What it takes at PH prices

At a ₱2,000 average job, 4% ≈ **₱80/job**. Covering a modest ₱20,000/month needs ~250 completed jobs — so
viability is a **volume** question, and every element above is chosen to grow volume rather than tax it. A
listing fee optimises in the opposite direction.

## §6 · Regulatory posture — keep it exactly as is

Credits stay **non-withdrawable prepaid fees**; GCash intake stays **personal P2P + 13-digit ref → founder
verification queue → ledger mint**. This is deliberate: non-withdrawable credits are a *prepayment for
services*, not stored value, which keeps the light regulatory posture until business registration. The
cashback does **not** change that, because it is also non-withdrawable. The moment credits become cash-outable
the posture changes entirely — so they must not.

## §7 · NEXT (all local, none of it started)

1. A **credit-policy knob set** on the D9 table: `commission_pct`, `cashback_pct`, `min_list_balance`. The knob
   machinery, tighten-only floors and integrity gate all shipped today, so this is a config row plus a
   consumer — and the gate will *fail* if any of them ships unread.
2. A **cashback `ref_kind`** in `service_credit_ledger`, minted only on verified completion.
3. A **min-balance predicate** on publish (the listing guard exists; it needs the balance check).
4. A **unit-economics probe**: given N completions at price P, assert net take == 4%, and that cashback can
   NEVER mint without a verified completion — the refusal-plus-non-vacuity shape the bank uses everywhere.

---

## §8 · Custody — deliberately deferred, and the number that should reopen it

> **Ian, 2026-07-31:** *"when the consumer user pays, they pay into my GCash, then I send the payment less
> the commission to the provider within 24 hours."*

The instinct is right about the thing that matters: **netting beats collecting.** A commission you subtract
from money already in your hands is collected 100% of the time; one you must ask a provider to pre-fund is
not. Marketplace leakage runs up to ~18% of transactions, and custody is the standard answer.

**It was declined on arithmetic, not principle.** Under custody every peso of GMV crosses a personal GCash
wallet, and a fully-verified personal wallet accepts **₱100,000 incoming per month**:

| | through the wallet | cap binds at | at ₱25,000/job | net revenue |
|---|---|---|---|---|
| **custody** | 100% of GMV | ₱100,000 GMV/mo | **~4 jobs/mo** | ~₱4,000/mo |
| **fee-only** (today) | ~5% of GMV | **₱2,000,000 GMV/mo** | ~80 jobs/mo | ~₱80,000/mo |

The multiplier is exactly `1 ÷ commission_pct` = **20×**. Custody would also make the founder an *Operator of
Payment System* under [RA 11127](https://www.bsp.gov.ph/PaymentAndSettlement/FAQ_OPS_Registration.pdf) —
which covers anyone providing *"clearing or settlement services"* — requiring the BSP registration D6 says is
not feasible yet, plus a 24-hour remittance funded personally before the money is irreversibly the platform's.

**What was built instead: confirm-to-release.** Money keeps moving consumer→provider directly; the platform
records it (`service_payments`, immutable), the **buyer confirms**, and only then does commission net from
the provider's prepaid wallet and cashback mint. This **upholds D13** ("payments stay OUTSIDE the platform,
record-only") rather than reversing it — it builds the record layer D13 always implied. It also produced the
proof-of-sale the tier ladder needed, which is how the self-mint in §8 of the sustainability study got closed.

### The landing pad, and when to use it

`marketplace_orders` already carries the full escrow state machine — `pending_payment → escrow_hold →
buyer_confirmed → released | refunded | disputed`, with `escrow_release_at` / `buyer_confirmed_at` /
`released_at`, policed by `guard_marketplace_order_status`. It has **0 rows**: a Stripe-era shape left
standing. Custody is therefore a **knob, not a rebuild**.

**The number that should reopen this: ~₱500k–1M GMV/month.** Below that, recovered leakage at 4% is smaller
than the compliance cost (BSP OPS registration + GCash for Business + BIR). Above it, custody starts paying
for itself — and the ₱100,000 personal-wallet ceiling will have been the binding constraint long before, so
the wallet upgrade comes first regardless.

**What custody would still need, none of which exists today and none of which is an accident:**
`escrow_in` / `payout` entry types on `service_credit_ledger` (the CHECK currently allows only topup,
commission, voucher_grant, voucher_reimburse, adjustment, cashback), a `platform` account type (the CHECK
allows only provider and consumer), a payout queue with a 24-hour SLA clock, and reconciliation against the
wallet statement. The ledger deliberately has **no representation for money the platform holds**, because the
platform holds none.

---

## §14 · SUPERSEDED - the design that actually shipped (2026-08-03)

Everything above is the July analysis of a **5% listing fee + 1% cashback**. Ian replaced it. The built
design is different in kind, not degree, and this section is what the code implements.

> **Ian, 2026-08-03:** *"the credits revolve that way. There is no revenue, there is no interest that will
> make credits appreciate. 1 peso is equal to 1 credit. Then the credit supply will be 10 million, then the
> credits in circulation are the credits bought."* Plus the mechanic: *"the provider wants to list an item,
> needs credits first to match the listing 10%, so that 10% will be passed on to the buyer."*

**Five rules, and everything else follows:** 1 credit = PHP1 fixed forever; supply capped at 10,000,000;
in-circulation = credits bought; listing requires a 10% RESERVATION that passes to the buyer on sale; **no
revenue** - the platform takes no commission and no spread.

**A reservation is not the fee this document argued against.** §2 above rejected a listing fee on
arithmetic: a 5% fee at 20% sell-through really costs 25%, because a fee is consumed whether or not the
item sells. A reservation is **returned in full** on delist, so it costs locked working capital rather than
revenue - which is precisely the "min-balance / skin in the game" instrument §2 recommended *instead* of a
fee, refined to be per-listing.

**Migrations 20260803000005-20260803000020.** Guards: supply cap (CHECK), listing reservation,
return-on-delist, earn-or-spend exclusivity, spend cap, non-transferable, holding fee, Sybil-gated starter
grant, new-seller listing cap. Gate: `tools/validate_credit_posture.py` (`credit-posture`).

### What building it found that designing it did not

Four defects, each invisible to the layer above it:

| defect | why every existing check missed it |
|---|---|
| **the spend half had no door** | `reward_spend` had two careful guards and **nothing ever wrote one**. Buyers could earn credits and never spend them. Guards that work perfectly prove nothing about whether anything reaches them. |
| **the spend destroyed the credits** | it wrote only the payer's leg. Each guard checks one side, so a *missing* counterparty violates none - and burnt credits leave the platform holding the cash that backed them, which is revenue arriving as an omission. Now two legs, with a per-job conservation assertion. |
| **the 10% cap never bound** | it capped against `service_requests.budget`, which is **NULL on 7 of 7** jobs with a matched provider. A missing cap *permits* silently, unlike a wrong one which raises. |
| **the guard messages never reached anyone** | `whWriteError` discarded the server's sentence, so a seller short PHP50 read "Save failed. Try again." - and retrying is exactly what cannot work. `whIsAuthFailure` also read any 42501 as a dead session, telling signed-in people to sign in. |

The third and fourth share a root worth stating plainly: **a rule derived twice will disagree**, and the
copy that drifts is always the one the user reads. `service_request_price()` now owns "what does this job
cost", and both the guard and the confirm sheet ask it.

### Open, and deliberately so

With no commission, no spread and no appreciation, the platform's only economic position is the float. That
is real but it is not revenue, so an income line will be needed eventually - paid featured placement is the
natural one, and it is a fee a provider *chooses* when it pays for itself. Nothing here forecloses it.

One thing for a PH lawyer before scale, not before building: credits are accepted by providers **other than
the issuer**, which is the line between a single-merchant card and a multi-merchant scheme. There is no cash
redemption, which is the prong that usually matters most, but it deserves a professional read once volume is
real.

### The claim, walked end to end

Every other credit gate checks one rule in isolation. `tools/validate_credit_loop_closes.py`
(`credit-loop-closes`) asks the question the design exists to answer, using the real triggers and the real
RPC at each step:

```
ONE cash entry  ->  seller A tops up PHP5,000
                    A drafts, an ADMIN publishes    -> PHP200 reserved
                    the listing SELLS               -> PHP200 passes to the BUYER
                    the buyer pays for a job in credits -> provider B RECEIVES PHP200
                    B publishes a PHP2,000 listing  -> funded entirely by what B was paid
                    circulation delta               -> 0.00
```

**Measured, not asserted in prose:** B listed on money nobody re-paid, and the ledger sum was identical at
the start and the end. That last number is the one that matters — every step is a transfer between two
wallets, so a non-zero delta means the circuit mints or burns. It is not a hypothetical failure: the spend
shipped writing only the payer's leg, which destroyed the credits and left the platform holding the cash
that backed them, while every per-side guard passed.

Teeth: `--inject spend` (the buyer pays in pesos, so B is never funded) and `--inject reward` (the sale
does not hand over its reservation, so the buyer has nothing to spend) each break the circuit.
