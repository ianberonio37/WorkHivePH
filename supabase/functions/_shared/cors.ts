const _PROD = "https://workhiveph.com";
const _EXTRA = Deno.env.get("ALLOWED_ORIGIN") || "";

// Dynamic CORS: echoes the request origin back if it's allowed.
// Allows "null" origin so file:// local testing works without CORS errors.
export function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") || "";
  const allowed = [_PROD, ...(_EXTRA ? [_EXTRA] : []), "null"];
  const effective = allowed.includes(origin) ? (origin || _PROD) : _PROD;
  return {
    "Access-Control-Allow-Origin": effective,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  };
}
