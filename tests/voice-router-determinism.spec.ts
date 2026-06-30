/**
 * voice-router-determinism.spec.ts — Arc H H2 routing/tool-selection ORACLE.
 * ==========================================================================
 * The Voice Action Router's intent classification is LLM-based (probabilistic,
 * needs a live model). But its routing/tool-selection CORRECTNESS lives in two
 * PURE deterministic functions in _shared/voice-router-core.ts:
 *   sanitiseIntents()      — kind allowlist, confidence clamp, slot-fill guard
 *   pickPrimaryCandidate() — asset disambiguation (context→exact→single→ambig)
 *
 * This is a VALUE oracle: it runs the REAL exported functions (the same module
 * the edge function imports — zero drift) against hand-derived input→output
 * pairs and asserts the exact result. No page, no model, no DB. It flips Arc H
 * H2/F from "attributed (not yet oracle-bound)" to oracle-bound.
 *
 * Run only this spec:
 *   npx playwright test voice-router-determinism --reporter=line
 *
 * Skills consulted: ai-engineer (router contract), qa (oracle = assert the
 * value not the shape), security (slot-fill guard = code-enforced, not model-
 * trusted), maintenance-expert (asset-required intents = logbook/pm/lookup).
 */
import { test, expect } from '@playwright/test';
import {
  sanitiseIntents,
  pickPrimaryCandidate,
  VALID_KINDS,
  ASSET_REQUIRED_KINDS,
  SLOT_FILL_CEILING,
  type AssetCandidate,
} from '../supabase/functions/_shared/voice-router-core';

// ─── sanitiseIntents: kind allowlist ───────────────────────────────────────────

test('sanitiseIntents: a valid kind passes through', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'query.ask', confidence: 0.7, params: { question: 'what is OEE?' } }],
  });
  expect(intents).toHaveLength(1);
  expect(intents[0].kind).toBe('query.ask');
  expect(intents[0].confidence).toBe(0.7);
});

test('sanitiseIntents: an invalid/invented kind is DROPPED (no arbitrary actions)', () => {
  const { intents } = sanitiseIntents({
    intents: [
      { kind: 'delete.everything', confidence: 0.99, params: {} },   // not in allowlist
      { kind: 'sql.exec', confidence: 0.99, params: {} },            // not in allowlist
      { kind: 'query.ask', confidence: 0.5, params: {} },            // valid
    ],
  });
  expect(intents).toHaveLength(1);
  expect(intents[0].kind).toBe('query.ask');
});

test('sanitiseIntents: every emitted kind is in the published allowlist', () => {
  const all = ['logbook.create', 'inventory.deduct', 'pm.complete', 'asset.lookup', 'query.ask', 'unknown'];
  const { intents } = sanitiseIntents({
    intents: all.map(k => ({ kind: k, confidence: 0.6, params: { machine: 'CHW-01' } })),
  });
  for (const it of intents) expect(VALID_KINDS.has(it.kind)).toBe(true);
});

// ─── sanitiseIntents: confidence clamp [0,1] ────────────────────────────────────

test('sanitiseIntents: confidence above 1 is clamped to 1', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'query.ask', confidence: 1.7, params: {} }],
  });
  expect(intents[0].confidence).toBe(1);
});

test('sanitiseIntents: negative confidence is clamped to 0', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'query.ask', confidence: -3, params: {} }],
  });
  expect(intents[0].confidence).toBe(0);
});

test('sanitiseIntents: non-numeric confidence defaults to 0', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'query.ask', confidence: 'high' as unknown as number, params: {} }],
  });
  expect(intents[0].confidence).toBe(0);
});

// ─── sanitiseIntents: slot-fill guard (the security-critical rule) ──────────────

test('slot-fill: logbook.create with NO machine is demoted below the 0.5 floor', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'logbook.create', confidence: 0.9, params: { problem: 'bearing noise' } }],
  });
  // model said 0.9 (confident write) — code forces it under the confirmation floor
  expect(intents[0].confidence).toBeLessThanOrEqual(SLOT_FILL_CEILING);
  expect(intents[0].confidence).toBeLessThan(0.5);
  expect(intents[0].params._needs_asset).toBe(true);
});

test('slot-fill: pm.complete with a BLANK machine is demoted (whitespace ≠ asset)', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'pm.complete', confidence: 0.8, params: { machine: '   ', task_summary: 'greased' } }],
  });
  expect(intents[0].confidence).toBeLessThanOrEqual(SLOT_FILL_CEILING);
  expect(intents[0].params._needs_asset).toBe(true);
});

test('slot-fill: asset.lookup with no machine is demoted', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'asset.lookup', confidence: 0.95, params: { question: 'last PM?' } }],
  });
  expect(intents[0].confidence).toBeLessThanOrEqual(SLOT_FILL_CEILING);
});

test('slot-fill: logbook.create WITH a machine keeps its confidence (no demotion)', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'logbook.create', confidence: 0.88, params: { machine: 'PUMP-204', problem: 'leak' } }],
  });
  expect(intents[0].confidence).toBe(0.88);
  expect(intents[0].params._needs_asset).toBeUndefined();
});

test('slot-fill: inventory.deduct with no machine is NOT demoted (its slot is the part)', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'inventory.deduct', confidence: 0.82, params: { parts: [{ part_name: 'seal', qty: 2 }] } }],
  });
  expect(intents[0].confidence).toBe(0.82);            // full confidence preserved
  expect(intents[0].params._needs_asset).toBeUndefined();
  expect(ASSET_REQUIRED_KINDS.has('inventory.deduct')).toBe(false);  // contract guard
});

test('slot-fill: query.ask with no machine is NOT demoted (not asset-required)', () => {
  const { intents } = sanitiseIntents({
    intents: [{ kind: 'query.ask', confidence: 0.75, params: { question: 'what is MTBF?' } }],
  });
  expect(intents[0].confidence).toBe(0.75);
});

// ─── sanitiseIntents: malformed input is contained ──────────────────────────────

test('sanitiseIntents: null / non-object input yields empty result, never throws', () => {
  for (const bad of [null, undefined, 42, 'oops', []]) {
    const out = sanitiseIntents(bad as unknown);
    expect(out.intents).toEqual([]);
    expect(out.mentioned).toEqual([]);
  }
});

test('sanitiseIntents: missing params defaults to {} and missing kind becomes "unknown"', () => {
  const { intents } = sanitiseIntents({ intents: [{ confidence: 0.3 }] });
  expect(intents).toHaveLength(1);
  expect(intents[0].kind).toBe('unknown');
  expect(intents[0].params).toEqual({});
});

test('sanitiseIntents: mentioned_assets is deduped and empties are dropped', () => {
  const { mentioned } = sanitiseIntents({
    intents: [],
    mentioned_assets: ['CHW-01', 'chw-01', 'CHW-01', '', '   ', 'PUMP-204'],
  });
  // dedup is exact-string (case-sensitive per source); blanks filtered
  expect(mentioned).toContain('CHW-01');
  expect(mentioned).toContain('PUMP-204');
  expect(mentioned).not.toContain('');
  expect(mentioned.filter(m => m === 'CHW-01')).toHaveLength(1);
});

// ─── pickPrimaryCandidate: deterministic asset disambiguation ───────────────────

const cand = (asset_id: string, tag: string, name = ''): AssetCandidate =>
  ({ asset_id, tag, name, hive_id: 'h1' });

test('pickPrimary: no candidates → no primary, not ambiguous', () => {
  const r = pickPrimaryCandidate([], null, []);
  expect(r.primary).toBeUndefined();
  expect(r.ambiguous).toBe(false);
});

test('pickPrimary: page context wins when its asset_id is among candidates', () => {
  const cs = [cand('a1', 'CHW-01'), cand('a2', 'CHW-02')];
  const r = pickPrimaryCandidate(cs, 'a2', ['chw']);
  expect(r.primary?.asset_id).toBe('a2');
  expect(r.ambiguous).toBe(false);
});

test('pickPrimary: exact case-insensitive tag match wins (no context)', () => {
  const cs = [cand('a1', 'CHW-01'), cand('a2', 'CHW-02')];
  const r = pickPrimaryCandidate(cs, null, ['chw-02']);
  expect(r.primary?.asset_id).toBe('a2');
  expect(r.ambiguous).toBe(false);
});

test('pickPrimary: exact name match wins too', () => {
  const cs = [cand('a1', 'CHW-01', 'Chiller One'), cand('a2', 'CHW-02', 'Chiller Two')];
  const r = pickPrimaryCandidate(cs, null, ['chiller two']);
  expect(r.primary?.asset_id).toBe('a2');
});

test('pickPrimary: a single candidate wins by default, not ambiguous', () => {
  const r = pickPrimaryCandidate([cand('a1', 'CHW-01')], null, ['nonsense']);
  expect(r.primary?.asset_id).toBe('a1');
  expect(r.ambiguous).toBe(false);
});

test('pickPrimary: multiple candidates with no clear winner → ambiguous (page asks)', () => {
  const cs = [cand('a1', 'CHW-01'), cand('a2', 'CHW-02')];
  const r = pickPrimaryCandidate(cs, null, ['chw']);  // partial, matches neither exactly
  expect(r.ambiguous).toBe(true);
  expect(r.primary?.asset_id).toBe('a1');             // first as a fallback handle
});

test('pickPrimary: page context takes PRECEDENCE over an exact mention match', () => {
  const cs = [cand('a1', 'CHW-01'), cand('a2', 'CHW-02')];
  // mention exactly matches a1's tag, but context points at a2 → context wins
  const r = pickPrimaryCandidate(cs, 'a2', ['chw-01']);
  expect(r.primary?.asset_id).toBe('a2');
  expect(r.ambiguous).toBe(false);
});
