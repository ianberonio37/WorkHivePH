// _shared/redactPII.ts
// Centralised PII redaction for AI prompts and outbound third-party
// payloads. Closes PRODUCTION_FIXES #44.
//
// The platform's privacy posture: model providers (OpenAI / Anthropic /
// Groq / etc.) and notification services (Resend) MUST NOT see raw worker
// identity (worker_name, display_name, email, phone) or tightly-scoped
// equipment IDs unless the call is explicitly opted-in (Stripe KYC,
// Resend digest with verified email).
//
// Two entry points:
//
//   redactPII(payload)
//     Recursively walk strings + objects + arrays, replacing PII tokens
//     with `<redacted>` placeholders. The KEY shape is preserved so the
//     model can still reason about "there is a worker here" without
//     learning who the worker is.
//
//   redactPIIWithMap(payload)
//     Same as redactPII but also returns a {token: original} map so the
//     caller can rehydrate the response after the model returns. Useful
//     when the model output references the worker by `<worker_1>`
//     and the UI needs to render the real name.

const PII_KEYS = new Set([
  "worker_name",
  "workerName",
  "display_name",
  "displayName",
  "fullName",
  "full_name",
  "first_name",
  "firstName",
  "last_name",
  "lastName",
  "email",
  "email_address",
  "emailAddress",
  "phone",
  "phone_number",
  "phoneNumber",
  "mobile",
]);

// Token patterns that signal raw PII text (used to scrub strings).
// Conservative -- only patterns we're confident are PII shaped.
const EMAIL_RE = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g;
const PHONE_RE = /\+?\d[\d\s().-]{8,}\d/g;

// ISO-8601 date / datetime (2026-06-13, 2026-06-13T01:29:44, optional
// fractional seconds + timezone). These are NOT phone numbers, but the
// loose PHONE_RE above happily eats the `YYYY-MM-DD` head and emits
// `<phone>T01:29:44` (seen once asset-brain answers routed through the
// gateway). We carve ISO timestamps out of the scrub pass entirely.
// Kept non-global; scrubExceptISO builds a fresh `g` instance so the
// shared lastIndex is never a cross-call hazard.
const ISO_DATETIME_RE =
  /\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b/;

export function redactPII<T>(payload: T): T {
  if (payload == null) return payload;
  if (typeof payload === "string") {
    return redactString(payload) as unknown as T;
  }
  if (Array.isArray(payload)) {
    return payload.map((item) => redactPII(item)) as unknown as T;
  }
  if (typeof payload === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(payload as Record<string, unknown>)) {
      if (PII_KEYS.has(k)) {
        out[k] = "<redacted>";
      } else {
        out[k] = redactPII(v);
      }
    }
    return out as unknown as T;
  }
  return payload;
}

// Run `scrub` over `s`, leaving any ISO date/datetime substrings verbatim so
// PHONE_RE can't misread `2026-06-13T01:29:44` as a phone number. The scrub
// callback only ever sees the gaps BETWEEN ISO timestamps.
function scrubExceptISO(s: string, scrub: (chunk: string) => string): string {
  const re = new RegExp(ISO_DATETIME_RE.source, "g");
  let out = "";
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    out += scrub(s.slice(last, m.index)); // scrub the text before the timestamp
    out += m[0];                          // keep the ISO timestamp verbatim
    last = m.index + m[0].length;
    if (m.index === re.lastIndex) re.lastIndex++; // guard against zero-width loops
  }
  out += scrub(s.slice(last));            // scrub the trailing text
  return out;
}

function redactString(s: string): string {
  return scrubExceptISO(s, (chunk) =>
    chunk.replace(EMAIL_RE, "<email>").replace(PHONE_RE, "<phone>"));
}

export interface RedactionMap {
  redacted: unknown;
  hydration: Record<string, string>;   // placeholder -> original
}

/**
 * redactPIIWithMap: produce a redacted payload AND a hydration map so the
 * caller can substitute placeholders back into the model response.
 *
 * Each PII-keyed value gets a stable placeholder like `<worker_1>`,
 * `<email_2>` etc. Arrays of workers preserve their indices so the
 * model can refer to "worker_1 said X, worker_2 said Y".
 */
export function redactPIIWithMap(payload: unknown): RedactionMap {
  const hydration: Record<string, string> = {};
  const counters: Record<string, number> = {};

  function alloc(kind: string, original: string): string {
    counters[kind] = (counters[kind] ?? 0) + 1;
    const ph = `<${kind}_${counters[kind]}>`;
    hydration[ph] = original;
    return ph;
  }

  function walk(v: unknown): unknown {
    if (v == null) return v;
    if (typeof v === "string") {
      return scrubExceptISO(v, (chunk) =>
        chunk
          .replace(EMAIL_RE, (m) => alloc("email", m))
          .replace(PHONE_RE, (m) => alloc("phone", m)));
    }
    if (Array.isArray(v)) {
      return v.map(walk);
    }
    if (typeof v === "object") {
      const out: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        if (PII_KEYS.has(k) && typeof val === "string" && val) {
          out[k] = alloc(piiKindFromKey(k), val);
        } else {
          out[k] = walk(val);
        }
      }
      return out;
    }
    return v;
  }

  return { redacted: walk(payload), hydration };
}

/**
 * redactKnownNames: replace each known worker FULL-NAME occurrence in a free-text block
 * (the forwarded memory_block, the summariser transcript) with a stable `<name_N>` placeholder
 * + a hydration map. redactPIIWithMap only scrubs email/phone in a plain string (a name in prose
 * has no PII KEY), so this closes the MULTI-TURN name leak the single-turn redaction misses: a
 * prior-turn answer ("Bryan Garcia is assigned to PB-001") or the worker's own name reaching the
 * model provider inside the memory_block, even though the current-turn worker_name is redacted.
 * Full-name + word-boundary only (never first-name-alone — too many false hits on common words).
 * CL11 live-caught 2026-07-08.
 */
export function redactKnownNames(
  text: string,
  names: string[],
): { redacted: string; hydration: Record<string, string> } {
  const hydration: Record<string, string> = {};
  if (!text || !names?.length) return { redacted: text, hydration };
  // Longest first so "Juan Dela Cruz" is matched before a shorter contained name.
  const uniq = [...new Set(names.filter((n) => n && n.trim().length >= 4))]
    .sort((a, b) => b.length - a.length);
  let out = text;
  let i = 0;
  for (const name of uniq) {
    const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`\\b${esc}\\b`, "gi");
    if (!re.test(out)) continue;               // don't burn a counter on an absent name
    const ph = `<name_${++i}>`;
    out = out.replace(re, ph);
    hydration[ph] = name;
  }
  return { redacted: out, hydration };
}

/**
 * redactMemoryText: full multi-turn PII scrub for a free-text memory block or
 * summariser transcript. `redactKnownNames` only scrubs known worker NAMES; a
 * worker who stated an EMAIL or PHONE in a prior turn ("my email is juan@plant.ph")
 * has that value carried verbatim in the agent_memory turn_text + the semantic
 * journal recall, so it reaches the model provider RAW inside the forwarded
 * memory_block / summariser transcript even though the current-turn redaction
 * scrubbed it. This closes that multi-turn egress leak (K2, live-caught 2026-07-12):
 * names -> <name_N> (via redactKnownNames) AND email/phone -> <mememail_N>/<memphone_N>.
 * The `<mem*_N>` namespace is DISTINCT from the current-turn map's <email_N>/<phone_N>
 * so a memory placeholder can never collide with (and overwrite) a current-turn one
 * when both hydration maps merge. Returns a hydration map so a placeholder the model
 * echoes in its answer is restored on egress (hydratePII); the summariser path can
 * discard it (server-side context, re-redacted on the next forward). ISO timestamps
 * are carved out exactly as the single-turn scrub does (scrubExceptISO).
 */
export function redactMemoryText(
  text: string,
  names: string[],
): { redacted: string; hydration: Record<string, string> } {
  if (!text) return { redacted: text, hydration: {} };
  // 1) known worker full-names -> <name_N> (+ hydration)
  const named = redactKnownNames(text, names);
  const hydration: Record<string, string> = { ...named.hydration };
  // 2) email / phone -> <mememail_N> / <memphone_N> (distinct namespace, own counters)
  const counters: Record<string, number> = {};
  const alloc = (kind: string, original: string): string => {
    counters[kind] = (counters[kind] ?? 0) + 1;
    const ph = `<mem${kind}_${counters[kind]}>`;
    hydration[ph] = original;
    return ph;
  };
  const redacted = scrubExceptISO(named.redacted, (chunk) =>
    chunk
      .replace(EMAIL_RE, (m) => alloc("email", m))
      .replace(PHONE_RE, (m) => alloc("phone", m)));
  return { redacted, hydration };
}

function piiKindFromKey(key: string): string {
  if (key.toLowerCase().includes("email")) return "email";
  if (key.toLowerCase().includes("phone") || key.toLowerCase().includes("mobile")) return "phone";
  return "worker";
}

/**
 * hydratePII: substitute placeholders in a model response with the
 * original PII values. Inverse of redactPIIWithMap.
 */
export function hydratePII(text: string, map: Record<string, string>): string {
  let out = text;
  for (const [placeholder, original] of Object.entries(map)) {
    // Use split/join to avoid regex special-character issues.
    out = out.split(placeholder).join(original);
  }
  return out;
}
