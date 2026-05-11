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

function redactString(s: string): string {
  return s
    .replace(EMAIL_RE, "<email>")
    .replace(PHONE_RE, "<phone>");
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
      return v
        .replace(EMAIL_RE, (m) => alloc("email", m))
        .replace(PHONE_RE, (m) => alloc("phone", m));
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
