// penpot_tab.mjs - keep the WorkHive design file open and MCP-connected in a browser this tool owns (2026-11-04).
//
// The Penpot MCP acts through the plugin of an OPEN Penpot tab. That tab lived in the chrome-devtools MCP's browser, and
// on 2026-11-04 it was lost three times - every session restart restarts that browser, signed out - and a backgrounded
// window throttled it until the plugin's heartbeat lapsed ("the Penpot plugin tab appears to be suspended"). This holds
// the tab in a headless Chromium with a persistent profile instead: it signs in from .env (in-process, never printed),
// opens the file, waits for "MCP connected", and checks the connection every minute, reopening the file when it drops.
// Headless has no window to lose focus, so nothing throttles it.
//
//   node tools/penpot_tab.mjs            # run in the background for as long as comps are drawn; prints one line per change
//   node tools/penpot_tab.mjs --once     # sign in, connect, report, exit (a check)
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '@playwright/test';

const FILE_URL = 'https://design.penpot.app/?screen=workspace&team-id=c6f51e89-5d00-81ce-8008-e37031e66882'
  + '&file-id=542abcb8-15f9-80f7-8008-e3710bf0596e';
const PROFILE = path.join('.tmp', 'penpot_profile');
const ONCE = process.argv.includes('--once');

function env(key) {
  const text = fs.readFileSync('.env', 'utf8').replace(/^﻿/, '');
  const m = new RegExp('^\\s*' + key + '\\s*=\\s*(.+)$', 'm').exec(text);
  if (!m) throw new Error(key + ' is not in .env');
  return m[1].trim().replace(/^['"]|['"]$/g, '');
}
const log = (s) => console.log(`${new Date().toISOString().slice(11, 19)} ${s}`);

async function signInIfAsked(page) {
  const email = page.getByRole('textbox', { name: /work email/i });
  if (!(await email.isVisible({ timeout: 8000 }).catch(() => false))) return false;
  await page.getByRole('button', { name: /reject all/i }).click({ timeout: 3000 }).catch(() => {});
  await email.fill(env('PENPOT_EMAIL'));
  await page.getByRole('button', { name: /^continue$/i }).click();
  const pass = page.getByRole('textbox', { name: /password/i });
  await pass.waitFor({ state: 'visible', timeout: 30000 });
  await pass.fill(env('PENPOT_PASSWORD'));
  await page.getByRole('button', { name: /^continue$/i }).click();
  return true;
}

async function connected(page) {
  return /MCP connected/.test(await page.evaluate(() => document.body.innerText || '').catch(() => ''));
}

async function openAndConnect(page) {
  // 'commit', then wait for what matters: Penpot's app shell can take minutes to reach DOMContentLoaded on a loaded host
  await page.goto(FILE_URL, { waitUntil: 'commit', timeout: 180000 });
  await page.waitForFunction(() => /WORK EMAIL|MCP/.test(document.body ? document.body.innerText : ''), null, { timeout: 240000 })
    .catch(() => {});
  if (await signInIfAsked(page)) {
    log('signed in');
    await page.waitForURL(/screen=workspace/, { timeout: 120000 }).catch(() => {});
  }
  for (let i = 0; i < 60; i++) {
    if (await connected(page)) return true;
    // the plugin connects on its own once the file is open; the MCP menu shows its state and offers Connect
    if (i % 8 === 7) {
      await page.getByRole('button', { name: /^MCP$/ }).first().click({ timeout: 3000 }).catch(() => {});
      await page.getByText(/^connect$/i).first().click({ timeout: 3000 }).catch(() => {});
    }
    await page.waitForTimeout(2000);
  }
  return connected(page);
}

const ctx = await chromium.launchPersistentContext(PROFILE, { headless: true, viewport: { width: 1440, height: 900 } });
const page = ctx.pages()[0] || await ctx.newPage();
let ok = await openAndConnect(page).catch((e) => { log('open failed: ' + String(e.message || e).split('\n')[0]); return false; });
log(ok ? 'MCP connected' : 'NOT connected after 2 min');
if (ONCE) { await ctx.close(); process.exit(ok ? 0 : 1); }
for (;;) {
  await page.waitForTimeout(60000);
  const now = await connected(page);
  if (now !== ok) log(now ? 'MCP connected' : 'MCP connection lost - reopening the file');
  ok = now;
  if (!now) {
    ok = await openAndConnect(page).catch((e) => { log('reopen failed: ' + String(e.message || e).split('\n')[0]); return false; });
    log(ok ? 'MCP connected (after reopen)' : 'still NOT connected');
  }
}
