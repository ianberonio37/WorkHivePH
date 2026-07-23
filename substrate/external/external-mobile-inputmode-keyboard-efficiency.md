---
name: external-mobile-inputmode-keyboard-efficiency
type: reference
source: https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inputmode
source_sha: mdn-inputmode-2026
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: mobile input efficiency — a numeric/email/tel/url/search field must trigger the RIGHT on-screen keyboard via input type or inputmode, or the phone shows a full text keyboard (the measurable core of rubric dim Z1 · input efficiency per modality)
---

## reference · Mobile input efficiency — the right keyboard per field (inputmode / type)

The measurable core of UFAI **Z1 · Input efficiency per modality** (Phone side). A phone renders a virtual
keyboard from the field's `type` / `inputmode`; the wrong one forces the user to hunt on a full QWERTY.

* **Numeric fields MUST declare numeric intent.** A bare `<input type="text">` for a quantity/PIN/price
  shows the FULL text keyboard on mobile. Fix: `type="number"` (validated numeric), or `type="text"
  inputmode="numeric"` (integers, no minus), or `inputmode="decimal"` (fractional, locale separator).
* **Prefer the semantic `type` over `inputmode` alone** — `type` also gives validation + the right keyboard:
  `type="email"` (adds @), `type="tel"` (0-9 * #), `type="url"` (adds /), `type="search"` ("Search" return
  key). `inputmode` is a keyboard HINT only, not validation.
* **inputmode values → keyboard:** `numeric` (0-9), `decimal` (0-9 + . or ,), `tel` (phone pad), `email`,
  `url`, `search`, `text` (default), `none` (custom keypad, suppress virtual kbd).
* **Testable rule (Z1 phone):** every input whose expected value is numeric/email/tel/url MUST have a
  matching `type` OR `inputmode`. A `type="text"`/no-type field collecting a number = FAIL. Also pair
  `autocomplete="..."` (name/email/tel/street-address/one-time-code) so the phone/browser can autofill —
  every keystroke saved is a field a gloved field-tech doesn't fumble.

## PC side (same dim, keyboard-operability)
* Every interactive control reachable + operable by keyboard (Tab order logical, Enter/Space activate,
  visible focus — see C2/F2); frequent actions get a shortcut; frequent bulk work supports multi-select.

Sources: https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inputmode
