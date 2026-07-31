# The credit economy — refining the listing-fee idea

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
