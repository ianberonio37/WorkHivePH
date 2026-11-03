// penpot_mcp.mjs - a minimal client for Penpot's hosted MCP server (2026-11-03).
//
// Penpot replaced Figma as WorkHive's design canvas (Ian, 2026-11-03: "instead of relying in figma ... open source"). The
// hosted server is https://design.penpot.app/mcp/stream?userToken=<PENPOT_MCP_KEY>; it acts through the MCP plugin of a
// Penpot tab, so the WorkHive design source file must be OPEN with MCP -> Connect clicked, or every call has nothing to
// act on. The key lives in .env (PENPOT_MCP_KEY) and never leaves this process.
//
// ★Cloudflare in front of the server refuses Python urllib's signature (error 1010); Node's fetch with a client
// User-Agent is what the MCP clients themselves use, so this is the one client every tool shares.
import fs from 'node:fs';
import path from 'node:path';

export function penpotKey(root = process.cwd()) {
  if (process.env.PENPOT_MCP_KEY) return process.env.PENPOT_MCP_KEY.trim();
  const env = fs.readFileSync(path.join(root, '.env'), 'utf8').replace(/^﻿/, '');
  const m = /^PENPOT_MCP_KEY=(.+)$/m.exec(env);
  if (!m) throw new Error('PENPOT_MCP_KEY is not in .env');
  return m[1].trim();
}

function parse(text) {
  const i = text.indexOf('{');
  try { return JSON.parse(text.slice(i, text.lastIndexOf('}') + 1)); } catch { return {}; }
}

export async function penpot(root = process.cwd()) {
  const url = 'https://design.penpot.app/mcp/stream?userToken=' + penpotKey(root);
  let id = 0;
  const post = async (body) => {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream',
                 'User-Agent': 'workhive-tools/1.0 (mcp)' },
      body: JSON.stringify(body),
    });
    if (r.status !== 200) throw new Error(`penpot mcp HTTP ${r.status}`);
    return parse(await r.text());
  };
  await post({ jsonrpc: '2.0', id: ++id, method: 'initialize',
               params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'workhive', version: '1' } } });
  return {
    // run plugin-context JavaScript (the body of a function; `penpot`, `penpotUtils`, `storage` in scope)
    async run(code) {
      const d = await post({ jsonrpc: '2.0', id: ++id, method: 'tools/call', params: { name: 'execute_code', arguments: { code } } });
      if (d.error) throw new Error(d.error.message || JSON.stringify(d.error));
      const text = ((d.result || {}).content || []).map((c) => c.text || '').join('');
      const out = parse(text);
      if (out.error || /no plugin|not connected/i.test(text)) throw new Error(out.error || text.slice(0, 200));
      return out.result;
    },
  };
}
