/**
 * ssrf-guard.ts — Arc R (Z-lens, OWASP A10): block Server-Side Request Forgery
 * on outbound fetches whose URL is user/tenant-controlled.
 *
 * Context: several edge fns fetch a URL that comes from tenant config
 * (`integration_configs.endpoint_url`) or the request body (`image_url`). Without
 * validation, a hive supervisor (or anon caller) can point the server at internal
 * hosts — cloud metadata (169.254.169.254), the Supabase/Kong gateway, RFC1918
 * services — and, for the CMMS calls, the outbound `Authorization: Bearer <token>`
 * leaks to the attacker-chosen host.
 *
 * Defenses (defense-in-depth):
 *   1. https only (http allowed only if explicitly opted-in).
 *   2. no credentials in the URL (user:pass@host).
 *   3. reject internal hostnames (localhost, *.internal, *.local, single-label).
 *   4. reject IP literals in private/loopback/link-local/metadata/reserved ranges
 *      (IPv4 + IPv6, incl. IPv4-mapped ::ffff:).
 *   5. resolve the hostname via DNS and re-check EVERY resolved IP (DNS-rebinding).
 *   6. follow redirects MANUALLY, re-validating each hop, and STRIP Authorization
 *      on a cross-origin redirect (so creds never leak across a 3xx).
 *
 * Pure helpers (isPrivateIPv4/isPrivateIPv6) are exported so a gate/test can prove
 * the classification has teeth without a network.
 */

const INTERNAL_HOSTNAMES = new Set([
  "localhost", "kong", "metadata", "metadata.google.internal",
  "host.docker.internal", "supabase_kong_workhive",
]);

function ip4ToInt(ip: string): number | null {
  const m = ip.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return null;
  const o = m.slice(1).map(Number);
  if (o.some((n) => n > 255)) return null;
  return ((o[0] << 24) >>> 0) + (o[1] << 16) + (o[2] << 8) + o[3];
}

/** True if an IPv4 literal is in any private/loopback/link-local/reserved range. */
export function isPrivateIPv4(ip: string): boolean {
  const n = ip4ToInt(ip);
  if (n === null) return false;
  const inRange = (base: string, bits: number): boolean => {
    const b = ip4ToInt(base)!;
    const mask = bits === 0 ? 0 : (~((1 << (32 - bits)) - 1)) >>> 0;
    return (n & mask) === (b & mask);
  };
  return (
    inRange("10.0.0.0", 8) ||        // private
    inRange("172.16.0.0", 12) ||     // private
    inRange("192.168.0.0", 16) ||    // private
    inRange("127.0.0.0", 8) ||       // loopback
    inRange("169.254.0.0", 16) ||    // link-local + cloud metadata
    inRange("100.64.0.0", 10) ||     // CGNAT
    inRange("0.0.0.0", 8) ||         // "this" network
    inRange("192.0.0.0", 24) ||      // IETF protocol assignments
    inRange("192.0.2.0", 24) ||      // TEST-NET-1
    inRange("198.18.0.0", 15) ||     // benchmarking
    inRange("198.51.100.0", 24) ||   // TEST-NET-2
    inRange("203.0.113.0", 24) ||    // TEST-NET-3
    inRange("224.0.0.0", 4) ||       // multicast
    inRange("240.0.0.0", 4)          // reserved
  );
}

/** True if an IPv6 literal is loopback/link-local/ULA/multicast/unspecified/mapped-private. */
export function isPrivateIPv6(ip: string): boolean {
  const s = ip.toLowerCase().replace(/^\[/, "").replace(/\]$/, "");
  if (s === "::1" || s === "::") return true;                 // loopback / unspecified
  if (s.startsWith("fe80")) return true;                      // link-local
  if (s.startsWith("fc") || s.startsWith("fd")) return true;  // unique-local fc00::/7
  if (s.startsWith("ff")) return true;                        // multicast
  const m = s.match(/::ffff:(\d+\.\d+\.\d+\.\d+)$/);          // IPv4-mapped
  if (m) return isPrivateIPv4(m[1]);
  return false;
}

function isIpLiteral(host: string): boolean {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(host) || host.includes(":");
}

export interface SsrfOpts {
  allowHosts?: string[];   // exact hostnames to allow (bypass checks)
  allowHttp?: boolean;     // permit http: (default false)
  maxRedirects?: number;   // default 2
}

/** Validate a URL is a public, non-internal target. Throws "SSRF: ..." otherwise. */
export async function assertPublicUrl(rawUrl: string, opts: SsrfOpts = {}): Promise<URL> {
  let u: URL;
  try { u = new URL(rawUrl); } catch { throw new Error("SSRF: invalid URL"); }

  const scheme = u.protocol.toLowerCase();
  if (scheme !== "https:" && !(opts.allowHttp && scheme === "http:")) {
    throw new Error(`SSRF: scheme '${scheme}' not allowed (https only)`);
  }
  if (u.username || u.password) throw new Error("SSRF: credentials in URL not allowed");

  const host = u.hostname.toLowerCase().replace(/\.$/, "");
  if (opts.allowHosts?.map((h) => h.toLowerCase()).includes(host)) return u;

  if (
    INTERNAL_HOSTNAMES.has(host) ||
    host.endsWith(".internal") || host.endsWith(".local") ||
    !host.includes(".")            // single-label name = internal
  ) {
    throw new Error(`SSRF: internal hostname '${host}' blocked`);
  }

  if (isIpLiteral(host)) {
    if (isPrivateIPv4(host) || isPrivateIPv6(host)) {
      throw new Error(`SSRF: private/reserved IP '${host}' blocked`);
    }
    return u;
  }

  // hostname → resolve + re-check every IP (DNS-rebinding defense)
  try {
    const v4 = await Deno.resolveDns(host, "A").catch(() => [] as string[]);
    const v6 = await Deno.resolveDns(host, "AAAA").catch(() => [] as string[]);
    const ips = [...v4, ...v6];
    if (ips.length === 0) throw new Error(`SSRF: '${host}' did not resolve`);
    for (const ip of ips) {
      if (isPrivateIPv4(ip) || isPrivateIPv6(ip)) {
        throw new Error(`SSRF: '${host}' resolves to private IP ${ip}`);
      }
    }
  } catch (e) {
    if (e instanceof Error && e.message.startsWith("SSRF:")) throw e;
    // resolveDns unavailable/permission — literal checks above already ran; allow.
  }
  return u;
}

/** fetch() with SSRF validation + manual redirect re-validation + cross-origin auth-strip. */
export async function safeFetch(rawUrl: string, init: RequestInit = {}, opts: SsrfOpts = {}): Promise<Response> {
  const maxRedirects = opts.maxRedirects ?? 2;
  let current = await assertPublicUrl(rawUrl, opts);
  const headers = new Headers(init.headers || {});
  for (let i = 0; i <= maxRedirects; i++) {
    const resp = await fetch(current.toString(), { ...init, headers, redirect: "manual" });
    const loc = resp.headers.get("location");
    if (resp.status >= 300 && resp.status < 400 && loc) {
      const next = await assertPublicUrl(new URL(loc, current).toString(), opts);
      if (next.origin !== current.origin) headers.delete("authorization"); // never leak creds cross-origin
      current = next;
      continue;
    }
    return resp;
  }
  throw new Error("SSRF: too many redirects");
}
