const _PROD = "https://workhiveph.com";
// _EXTRA accepts a comma-separated list so a single env-var configures
// additional allowed origins for staging / preview deploys.
const _EXTRA_LIST = (Deno.env.get("ALLOWED_ORIGIN") || "")
  .split(",").map(s => s.trim()).filter(Boolean);

// Origins always allowed without env-var configuration:
//   - workhiveph.com    (apex production)
//   - www.workhiveph.com (www subdomain alias)
//   - http://localhost  (local dev server, any port)
//   - null              (file:// local testing -- browsers send Origin: null)
const _DEFAULT_ALLOWED = [
  _PROD,
  "https://www.workhiveph.com",
  "http://localhost",
  "null",
];

// Dynamic CORS: echoes the request origin back if it's allowed.
// Allows "null" origin so file:// local testing works without CORS errors.
// `Access-Control-Allow-Methods` covers all POST-based edge fns (the
// universal case in this codebase). Webhooks that need different methods
// or `*` origin (e.g., Stripe `marketplace-webhook`) keep their own
// inline helper -- documented exceptions, not drift.
export function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") || "";
  const allowed = [..._DEFAULT_ALLOWED, ..._EXTRA_LIST];
  // localhost match: any port and protocol scheme.
  const isLocalhost = origin.startsWith("http://localhost") || origin.startsWith("http://127.0.0.1");
  const effective = (allowed.includes(origin) || isLocalhost) ? (origin || _PROD) : _PROD;
  return {
    "Access-Control-Allow-Origin":  effective,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  };
}
