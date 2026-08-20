// session_signals.mjs — the ONE definition of "did the page tell the person?", shared by every prover that
// asks it.
//
// WHY THIS FILE EXISTS. The V1 prover (prove_session_died.mjs) and the V2/V3 prover
// (prove_dialog_session_died.mjs) each carried their OWN copy of these two patterns. Both copies were too
// narrow, and both reported `analytics` as presenting a dead session as data — when analytics actually
// renders "Authentication required" in #results-panel, "Analytics unavailable" as its verdict, and "Tap
// Refresh once the engine is ready." in its summary. It is arguably the most explicit page in the roster.
//
// Widening ONE copy withdrew ONE finding. For a while the bank therefore held TWO CONTRADICTORY READINGS OF
// THE SAME PAGE — one green with evidence, one red with evidence — and nothing in the data flagged the
// disagreement. That is worse than both being wrong, because the incoherence makes the bank look thorough.
//
// So the vocabulary lives here once. This platform already learned the lesson for the mirrored `PARENT` map,
// which is why that one is re-read out of wayfinding.js on every run rather than trusted; a duplicated
// VOCABULARY is the same hazard in different clothes.
//
// PATTERNS ARE EXPORTED AS SOURCE STRINGS, not as RegExp objects, because they are used inside
// `page.evaluate` — a callback serialised into the browser, where a Node-scope object does not exist.
// Referencing one there throws `ReferenceError` and every page comes back UNGRADED, which a summary can then
// report as a PASS (that exact failure happened once already). Pass these strings in as arguments and build
// `new RegExp(src, 'i')` inside the page.
//
// EXTENDING THEM: add the phrasing a REAL page uses, harvested from live text — never a wording invented at
// the desk. An oracle that only accepts the words its author thought of measures the author, not the product.

// "You are not signed in / you may not see this." An HONEST answer to a dead session.
// The last five alternatives were added 2026-08-13 from analytics' live text.
export const SIGNED_OUT_SRC =
  'sign in|signed out|log in|session (has )?expired|please (sign|log) in|not signed in'
  + '|create (a )?free account|get started free'
  + '|authenticat\\w* (required|needed)|requires? (sign|log|authenticat)|no access|not authoriz'
  + '|unauthoriz|permission';

// "There is nothing here, and here is why." Also honest — an empty state that states its reason.
// `unavailable`, `not available`, `warming up` and `try refresh` were added 2026-08-13 from analytics.
export const REASONED_EMPTY_SRC =
  'no (data|records|entries|items|results)|nothing (here|yet)|couldn.t load|failed to load'
  + '|unable to load|try (again|refresh)|something went wrong|unavailable|not available'
  + '|warming up|check (your )?connection';

// ── REFUSAL LEGIBILITY (CM `why_refused`) ──────────────────────────────────────────────────────────────
// "You are not allowed to do this, and here is the reason." A refusal a person can ACT on.
//
// THIS ORACLE HAS TEETH BECAUSE THE PLATFORM ALREADY SHIPPED ITS FAILURE, twice, in opposite directions:
//   · `feedback_42501_told_a_signed_in_buyer_to_sign_in` — a 42501 permission error rendered as "your
//     session expired", sending a signed-IN person to re-authenticate for a problem authentication cannot
//     fix.
//   · `feedback_401_and_403_are_not_the_same_event` — 401 (who are you?) and 403 (you may not) collapsed
//     into one message, so neither audience got a true statement.
// So a legible refusal must name PERMISSION, not identity. A page that answers an injected 403 with
// "please sign in" is not vague — it is WRONG, and it is wrong in the direction that wastes the person's
// time.
// ★ THE LAST TWO ALTERNATIVES ARE THE PLATFORM'S OWN CENTRAL WORDING, and adding them was a PRECONDITION
// for fixing anything. utils.js:1692-1694 (`whReadError`, the 403 branch) already answers a refused read
// with exactly the right sentence:
//     "You do not have access to <thing> with this account. Your session is fine. Ask a supervisor if you
//      need it."
// That sentence matched NOTHING in the list above. `no access` does not match "do not have access", and
// `contact (your )?(supervisor|admin)` does not match "Ask a supervisor". So the oracle would have failed
// the correct fix: adopt the central helper on 15 pages, re-run, and all 15 stay red — at which point the
// obvious-looking next move is to rewrite the PRODUCT's wording until the oracle is happy, i.e. to make
// the app say the words I happened to think of. That is precisely what the header rule above forbids, and
// it was caught by testing the helper's real output string against the pattern BEFORE editing any page.
// `community` passed only because its own inline copy says "No access to the community feed" — the one
// page whose wording happened to fall inside a desk-written vocabulary.
// `can.t` WAS A FALSE-POSITIVE GENERATOR: the `.` was written to stand for an apostrophe but matches ANY
// character, so "a quiz you can take now" and "can the user" both satisfied it. skillmatrix renders
// "1 discipline has a quiz you can take now" on the HEALTHY page, so the oracle saw refusal wording before
// any injection and returned UNGRADED — it declined to grade a page whose only sin was ordinary copy.
// UNGRADED is the safe direction, but the same match in the AFTER read would have been a false PASS, which
// is not safe at all. The class is escaping-by-wildcard; the apostrophe is now an explicit set covering
// the straight and curly forms, since the platform's copy uses both.
export const REFUSAL_SRC =
  'permission|not allowed|cannot|can[\'’]t|unable to|no access|not authoriz|unauthoriz|forbidden'
  + '|only (a |an )?(supervisor|admin|owner|member)|requires? (a |an )?(supervisor|admin|owner|role)'
  + '|read.only|restricted|your role|contact (your )?(supervisor|admin)'
  + '|n.t have access|not have access|ask (a |an |your )?(supervisor|admin|owner)';

// ── FAILURE vs EMPTINESS (CC failure-injection) ────────────────────────────────────────────────────────
// "We could not load this" versus "there is nothing here." The two are indistinguishable to a person and
// ONE OF THEM IS A LIE — this platform shipped exactly that: public-feed's Retry rendered "No public posts
// yet" over 15 existing posts, because the keyset cursor was never reset.
//
// LIFTED VERBATIM FROM tests/failure-injection.spec.ts, NOT RE-TYPED FROM MEMORY. That spec had already
// paid for this vocabulary: its first version listed only "could not LOAD" and missed the marketplace's
// own "…so the marketplace could not be READ", reporting five surfaces as silent while every one of them
// was speaking clearly. Its note is the rule this file exists to enforce — "an oracle that only recognises
// its author's phrasing measures vocabulary, not behaviour." A third copy is how two provers end up
// disagreeing about the same page, which is what created this module.
export const FAILURE_SRC =
  "couldn'?t (load|read|be)|could not (load|read|be)|failed to (load|read)|unable to (load|read)"
  + '|went wrong|try again|retry|session expired|expired,? so|not allowed to|does not have access'
  + '|no access to';

// The words that mean EMPTY. A pass for a failure-injection oracle needs the failed render to say
// something failure-shaped and the healthy render NOT to — and a page that answers a broken read with
// these words is the defect, stated in the product's own vocabulary.
export const EMPTY_SRC =
  'no listings|no posts|nothing here|no results|none found|no items|no public posts';

// A GENERIC error is NOT a reason — it tells the person something broke without telling them what to do.
// Matching these is how the oracle distinguishes "explained" from "merely acknowledged".
export const GENERIC_ERROR_SRC =
  'something went wrong|an error occurred|unexpected error|error occurred|oops|try again later'
  + '|failed|error(?![a-z])';
