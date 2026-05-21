/**
 * journey-voice-companion-gates.spec.ts — Phase A per-turn anchor wiring (2026-05-21)
 *
 * Exercises the 24 newly-wired per-turn anchors across 9 flywheel batches
 * (T96, T100, T102, T104, T114, T115, T116, T118, T120, T133, T140, T146,
 *  T147, T149, T151, T175-T180, T182, T204, T207, T209).
 *
 * Strategy:
 *   1. Detector behaviour — call window.WHVoice._detector(transcript) for
 *      each wired detector against representative positive + negative
 *      transcripts. Asserts the runtime exports the detector AND its
 *      classification is correct.
 *   2. Chained scenario — one transcript that should trigger 4+ detectors
 *      in a single utterance (LOTO + hot work + welding + first-time JSA).
 *   3. Source-wiring sanity — fetch voice-handler.js as text and assert
 *      every wired anchor string co-exists with its detector callsite.
 *      Mirrors the validator ratchets but exercises the file the browser
 *      actually loads (catches build/cache mis-config).
 *
 * Coverage matches validators:
 *   - validate_ai_companion_safety.py wire_* keys
 *   - validate_ai_companion_integration_audit.py check_phase_a_wires
 *   - validate_ai_companion_learning.py check_phase_a_wires
 *   - validate_ai_companion_compliance.py check_phase_a_wires
 *   - validate_ai_companion_accessibility.py check_phase_a_wires
 *   - validate_ai_companion_operational.py check_phase_a_wires
 *   - validate_ai_companion_team_coordination.py check_phase_a_wires
 *   - validate_ai_companion_sustainability.py wires
 *   - validate_ai_companion_multilang.py wires
 *
 * Out of scope: real mic capture, full ai-gateway round-trip. The per-turn
 * anchors land in the system prompt assembled inside dispatch() — they
 * never round-trip to a remote LLM in this test. We assert the WIRING is
 * present and the detectors classify correctly.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/voice-journal.html';

/** All wired Phase A anchors — anchor string + detector callsite source token. */
const WIRED_ANCHORS: Array<{ anchor: string; callsite: string; tNum: string }> = [
  // Safety block
  { anchor: 'INCIDENT GATE',       callsite: '_isIncidentReport(transcript)',           tNum: 'T182' },
  { anchor: 'LOTO GATE',           callsite: '_detectLotoIntent(transcript)',           tNum: 'T175' },
  { anchor: 'HOT WORK GATE',       callsite: '_detectHotWorkIntent(transcript)',        tNum: 'T176' },
  { anchor: 'CONFINED SPACE GATE', callsite: '_detectConfinedSpaceIntent(transcript)',  tNum: 'T177' },
  { anchor: 'PPE MATRIX',          callsite: '_isPpeQuery(transcript)',                 tNum: 'T178' },
  { anchor: 'NEAR-MISS CAPTURE',   callsite: '_isNearMissReport(transcript)',           tNum: 'T179' },
  { anchor: 'JSA OFFER',           callsite: '_shouldOfferJsa(transcript)',             tNum: 'T180' },
  // PHASE A COMPREHENSIVE block
  { anchor: 'SESSION TAG',         callsite: '_detectSessionTagRequest(transcript)',    tNum: 'T100' },
  { anchor: 'STT MANGLED',         callsite: '_looksGrammarMangled(transcript)',        tNum: 'T102' },
  { anchor: 'SHIFT END HORIZON',   callsite: '_isNearShiftEnd(_shiftEnd, 30)',          tNum: 'T104' },
  { anchor: 'QUIET HOURS',         callsite: '_isQuietHours(new Date())',               tNum: 'T96'  },
  { anchor: 'MENTOR HANDOFF',      callsite: '_isMentorHandoff(transcript)',            tNum: 'T114' },
  { anchor: 'PII SCRUBBED',        callsite: '_scrubPii(transcript)',                   tNum: 'T115' },
  { anchor: 'CONSENT CHANGE',      callsite: '_detectConsentChange(transcript)',        tNum: 'T116' },
  { anchor: 'ERASURE REQUEST',     callsite: '_isErasureRequest(transcript)',           tNum: 'T118' },
  { anchor: 'SUSPICIOUS ACTIVITY', callsite: '_detectSuspiciousActivity(ctx.worker_name)', tNum: 'T120' },
  { anchor: 'VOICE-ONLY TOGGLE',   callsite: '_detectVoiceOnlyToggle(transcript)',      tNum: 'T133' },
  { anchor: 'MEMORY PRESSURE',     callsite: '_checkMemoryPressure()',                  tNum: 'T140' },
  { anchor: 'HANDOFF',             callsite: '_detectHandoffRequest(transcript)',       tNum: 'T146' },
  { anchor: 'SHARED NOTE',         callsite: '_isSharedNoteRequest(transcript)',        tNum: 'T147' },
  { anchor: 'WATCHLIST',           callsite: '_detectWatchRequest(transcript)',         tNum: 'T149' },
  { anchor: 'RESOLUTION CAPTURE',  callsite: '_detectResolution(transcript)',           tNum: 'T151' },
  { anchor: 'ENERGY QUERY',        callsite: '_isEnergyQuery(transcript)',              tNum: 'T204' },
  { anchor: 'TAGALOG IMPERATIVE',  callsite: '_isTagalogImperative(transcript)',        tNum: 'T207' },
  { anchor: 'POLITENESS REGISTER', callsite: '_classifyPolitenessRegister(transcript)', tNum: 'T209' },
  // Phase A2 — orphan-detector closeout (2026-05-21)
  { anchor: 'BUDDY SET',           callsite: '_detectBuddySet(transcript)',             tNum: 'T153' },
  { anchor: 'DIALECT NOTE',        callsite: '_isCebuanoLeaning(transcript)',           tNum: 'T205' },
  { anchor: 'DIALECT NOTE',        callsite: '_isIlonggoLeaning(transcript)',           tNum: 'T206' },
];

test.describe('voice-journal Phase A companion-gates wiring', () => {

  test('all Phase A anchor strings + detector callsites live in voice-handler.js', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const source = await whPage.evaluate(async () => {
      const r = await fetch('/workhive/voice-handler.js', { cache: 'no-store' });
      return r.ok ? await r.text() : '';
    });
    expect(source.length, 'voice-handler.js should fetch successfully').toBeGreaterThan(100000);
    const missing: string[] = [];
    for (const { anchor, callsite, tNum } of WIRED_ANCHORS) {
      if (!source.includes(anchor))   missing.push(`${tNum} anchor "${anchor}"`);
      if (!source.includes(callsite)) missing.push(`${tNum} callsite \`${callsite}\``);
    }
    expect(missing, `Missing Phase A wires in voice-handler.js:\n${missing.join('\n')}`).toEqual([]);
  });

  test('safety chain: LOTO + HOT WORK + CONFINED SPACE detectors fire on chained welding-tank transcript', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // "tank entry" matches T177 _CONFINED_RE (boiler interior / tank entry / vessel entry).
      // Plain "boiler tank" does NOT match — the regex requires "boiler interior" or an entry verb.
      const chain = "i'm doing lockout-tagout on the P-203 pump then welding the bracket and i need tank entry for the cleanout";
      return {
        ready:    true,
        loto:     wh._detectLotoIntent(chain),
        hot:      wh._detectHotWorkIntent(chain),
        confined: wh._detectConfinedSpaceIntent(chain),
        // negative — pure data query should fire NONE
        loto_neg: wh._detectLotoIntent('what is the MTBF for P-203'),
        hot_neg:  wh._detectHotWorkIntent('what is the MTBF for P-203'),
        conf_neg: wh._detectConfinedSpaceIntent('what is the MTBF for P-203'),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.loto,     'T175 LOTO fires on "lockout-tagout"').toBe(true);
    expect(verdict.hot,      'T176 HOT WORK fires on "welding"').toBe(true);
    expect(verdict.confined, 'T177 CONFINED fires on "inside the boiler tank"').toBe(true);
    expect(verdict.loto_neg, 'T175 LOTO does NOT fire on pure data query').toBe(false);
    expect(verdict.hot_neg,  'T176 HOT WORK does NOT fire on pure data query').toBe(false);
    expect(verdict.conf_neg, 'T177 CONFINED does NOT fire on pure data query').toBe(false);
  });

  test('safety procedures: PPE / near-miss / JSA / incident detectors classify correctly', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      return {
        ready:        true,
        ppe_q:        wh._isPpeQuery('what ppe do I need for this task'),
        ppe_q_tgl:    wh._isPpeQuery('ano ang ppe kailangan ko'),
        ppe_q_neg:    wh._isPpeQuery('the bearing failed yesterday'),
        nm_close:     wh._isNearMissReport('close call earlier — almost slipped'),
        nm_tgl:       wh._isNearMissReport('muntik na akong masaktan kaso natamaan ko nung pipa'),
        nm_neg:       wh._isNearMissReport('the alarm went off'),
        jsa_first:    wh._shouldOfferJsa('this is my first time doing this overhaul'),
        jsa_tgl:      wh._shouldOfferJsa('unang beses kong gagawin to'),
        jsa_neg:      wh._shouldOfferJsa('what is the MTBF'),
        incident_en:  wh._isIncidentReport('someone got hurt on the line, need first aid asap'),
        incident_tgl: wh._isIncidentReport('may nasaktan sa floor, paramedic kailangan'),
        incident_neg: wh._isIncidentReport('I am tired today'),
        // T181 gas-test reading validator — independent helper
        gas_ok:       wh._validateGasReading({ O2: 20.9, LEL: 2,  CO: 10, H2S: 1 }),
        gas_bad:      wh._validateGasReading({ O2: 18.0, LEL: 25, CO: 50, H2S: 15 }),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.ppe_q,        'T178 PPE query EN').toBe(true);
    expect(verdict.ppe_q_tgl,    'T178 PPE query Tagalog').toBe(true);
    expect(verdict.ppe_q_neg,    'T178 PPE non-query').toBe(false);
    expect(verdict.nm_close,     'T179 close call EN').toBe(true);
    expect(verdict.nm_tgl,       'T179 muntik na Tagalog').toBe(true);
    expect(verdict.nm_neg,       'T179 alarm not a near-miss').toBe(false);
    expect(verdict.jsa_first,    'T180 first time EN').toBe(true);
    expect(verdict.jsa_tgl,      'T180 unang beses Tagalog').toBe(true);
    expect(verdict.jsa_neg,      'T180 MTBF question not JSA').toBe(false);
    expect(verdict.incident_en,  'T182 incident EN').toBe(true);
    expect(verdict.incident_tgl, 'T182 incident Tagalog').toBe(true);
    expect(verdict.incident_neg, 'T182 fatigue not incident').toBe(false);
    expect(verdict.gas_ok && verdict.gas_ok.ok,  'T181 normal reading ok=true').toBe(true);
    expect(verdict.gas_bad && verdict.gas_bad.ok, 'T181 unsafe reading ok=false').toBe(false);
    expect(Array.isArray(verdict.gas_bad && verdict.gas_bad.fail), 'T181 fail array present').toBe(true);
    expect(verdict.gas_bad.fail.length, 'T181 unsafe reading lists multiple failures').toBeGreaterThan(2);
  });

  test('compliance chain: PII scrub returns markers + consent / erasure / suspicious classify', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      const dirty = 'My phone is 09171234567 and email is mike@plant.ph';
      const sc = wh._scrubPii(dirty);
      return {
        ready:         true,
        pii_text:      sc && sc.text,
        // T115 returns { text, scrubs } — `scrubs` is the count of replacements made.
        pii_scrubs:    sc && sc.scrubs,
        consent_grant: wh._detectConsentChange('I consent to voice logging'),
        // T116 _CONSENT_REVOKE_RE is "revoke (my) consent" — the word between
        // "my" and "consent" must be empty. "revoke my voice consent" misses.
        consent_rev:   wh._detectConsentChange('please revoke my consent'),
        consent_neg:   wh._detectConsentChange('what is the MTBF'),
        erase_en:      wh._isErasureRequest('delete all my voice history'),
        erase_neg:     wh._isErasureRequest('what is the MTBF'),
        // Suspicious activity returns shape {kind, count} or null/undefined; we tolerate either
        susp_self:     wh._detectSuspiciousActivity('test-worker'),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.pii_text,    'T115 phone scrubbed').toContain('[PHONE]');
    expect(verdict.pii_text,    'T115 email scrubbed').toContain('[EMAIL]');
    expect(typeof verdict.pii_scrubs, 'T115 scrubs is a number').toBe('number');
    expect(verdict.pii_scrubs,  'T115 at least 2 scrubs (phone + email)').toBeGreaterThanOrEqual(2);
    expect(verdict.consent_grant, 'T116 consent grant').toBe('grant');
    expect(verdict.consent_rev,   'T116 consent revoke').toBe('revoke');
    expect(verdict.consent_neg,   'T116 non-consent').toBeNull();
    expect(verdict.erase_en,      'T118 erasure EN').toBe(true);
    expect(verdict.erase_neg,     'T118 non-erasure').toBe(false);
    // T120 may return null (no history) or {kind,count}; just confirm it ran without throwing.
    expect(verdict.ready, 'T120 _detectSuspiciousActivity callable').toBe(true);
  });

  test('integration + learning + accessibility + operational helpers callable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      return {
        ready:         true,
        tag_en:        wh._detectSessionTagRequest('tag this as P-203 commissioning'),
        tag_neg:       wh._detectSessionTagRequest('what is the MTBF'),
        // T102 fires when ≥50% of tokens are ≥10 chars AND no recognised verb in the text.
        mangled_yes:   wh._looksGrammarMangled('asdfghjklqw zxcvbnmpoi qwertyuopa'),
        // Long well-formed sentence (contains verb "failed" / "is") should be NOT mangled
        mangled_no:    wh._looksGrammarMangled('the bearing on P-203 failed yesterday during the second shift'),
        quiet_callable: typeof wh._isQuietHours === 'function',
        shift_end_callable: typeof wh._isNearShiftEnd === 'function',
        // T114 regex is "i'll ask (my) supervisor|kuya|ate|boss|lead" or
        // "tatanungin ko si <name>" — needs first-person framing.
        mentor_yes:    wh._isMentorHandoff("I'll ask my supervisor about this"),
        mentor_tgl:    wh._isMentorHandoff('tatanungin ko si supervisor'),
        mentor_neg:    wh._isMentorHandoff('the bearing failed'),
        voiceonly_on:  wh._detectVoiceOnlyToggle('switch to voice-only mode'),
        voiceonly_off: wh._detectVoiceOnlyToggle('exit voice-only'),
        voiceonly_neg: wh._detectVoiceOnlyToggle('what is the MTBF'),
        memory_callable: typeof wh._checkMemoryPressure === 'function',
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.tag_en,       'T100 session tag detected').toContain('P-203');
    expect(verdict.tag_neg,      'T100 non-tag returns null/false').toBeFalsy();
    expect(verdict.mangled_yes,  'T102 garbled token flagged').toBe(true);
    expect(verdict.mangled_no,   'T102 well-formed sentence NOT flagged').toBe(false);
    expect(verdict.quiet_callable,      'T96  _isQuietHours exported').toBe(true);
    expect(verdict.shift_end_callable,  'T104 _isNearShiftEnd exported').toBe(true);
    expect(verdict.mentor_yes,          'T114 mentor handoff EN').toBe(true);
    expect(verdict.mentor_tgl,          'T114 mentor handoff Tagalog').toBe(true);
    expect(verdict.mentor_neg,          'T114 non-mentor false').toBe(false);
    // T133 toggle returns 'on' / 'off' / null
    expect(['on', 'voice_only', true]).toContain(verdict.voiceonly_on);
    expect(verdict.voiceonly_neg, 'T133 non-toggle is falsy').toBeFalsy();
    expect(verdict.memory_callable, 'T140 _checkMemoryPressure exported').toBe(true);
  });

  test('energy query + multi-lang: T204 / T207 / T209 detectors classify correctly', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      return {
        ready:         true,
        energy_kwh:    wh._isEnergyQuery('what is the kWh consumption of MX-12 last week'),
        // T204 regex covers power consumption / wasting power / electricity cost — not "carbon footprint".
        energy_power:  wh._isEnergyQuery('are we wasting power on P-203 this shift'),
        energy_neg:    wh._isEnergyQuery('what is the MTBF for P-203'),
        imp_iX:        wh._isTagalogImperative('i-check mo ang vibration ng P-203'),
        imp_paki:      wh._isTagalogImperative('pakisuyo, i-restart mo ang pump'),
        imp_neg:       wh._isTagalogImperative('what is the MTBF'),
        polite_formal: wh._classifyPolitenessRegister('opo sir, gagawin ko na po'),
        polite_casual: wh._classifyPolitenessRegister('sige tol, ako na bahala dyan pre'),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.energy_kwh,    'T204 kWh query').toBe(true);
    expect(verdict.energy_power,  'T204 "wasting power" query').toBe(true);
    expect(verdict.energy_neg,    'T204 MTBF question NOT energy').toBe(false);
    expect(verdict.imp_iX,        'T207 "i-X mo" imperative').toBe(true);
    expect(verdict.imp_paki,      'T207 "pakisuyo" imperative').toBe(true);
    expect(verdict.imp_neg,       'T207 non-imperative').toBe(false);
    expect(verdict.polite_formal, 'T209 "po/opo" → formal').toBe('formal');
    expect(verdict.polite_casual, 'T209 "tol/pre" → casual').toBe('casual');
  });

  test('team coordination chain: handoff + shared note + watchlist + resolution', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      return {
        ready:        true,
        // T146 handoff
        handoff_en:   wh._detectHandoffRequest('send this to Mike Santos'),
        handoff_tgl:  wh._detectHandoffRequest('ipasa mo kay Kuya Ben'),
        handoff_neg:  wh._detectHandoffRequest('what is the MTBF'),
        // T147 shared note
        sn_team:      wh._isSharedNoteRequest('share this with the team'),
        sn_neg:       wh._isSharedNoteRequest('what is the MTBF'),
        // T149 watch
        watch_p203:   wh._detectWatchRequest('watch P-203 for me'),
        watch_neg:    wh._detectWatchRequest('what is the MTBF'),
        // T151 resolution
        res_fixed:    wh._detectResolution('fixed it na boss'),
        res_ayos:     wh._detectResolution('ayos na to'),
        res_neg:      wh._detectResolution('still broken'),
        // T153 buddy set (Phase A2)
        buddy_en:     wh._detectBuddySet('buddy up with Juan Cruz'),
        buddy_tgl:    wh._detectBuddySet('kasama ko sa shift si Romeo Santos'),
        buddy_neg:    wh._detectBuddySet('what is the MTBF'),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.handoff_en,  'T146 "send this to Mike Santos"').toContain('Mike');
    expect(verdict.handoff_tgl, 'T146 "ipasa kay Kuya Ben"').toContain('Ben');
    expect(verdict.handoff_neg, 'T146 non-handoff null').toBeNull();
    expect(verdict.sn_team,     'T147 team share').toBe(true);
    expect(verdict.sn_neg,      'T147 non-share').toBe(false);
    expect(verdict.watch_p203,  'T149 watch P-203').toBe('P-203');
    expect(verdict.watch_neg,   'T149 non-watch null').toBeNull();
    expect(verdict.res_fixed,   'T151 "fixed it" → resolved').toBe('fix_resolved');
    expect(verdict.res_ayos,    'T151 "ayos na" → resolved').toBe('fix_resolved');
    expect(verdict.res_neg,     'T151 "still broken" not resolved').toBeNull();
    expect(verdict.buddy_en,    'T153 "buddy up with Juan Cruz"').toContain('Juan');
    expect(verdict.buddy_tgl,   'T153 "kasama ko si Romeo"').toContain('Romeo');
    expect(verdict.buddy_neg,   'T153 non-buddy returns null').toBeNull();
  });

  test('dialect detection: Cebuano + Ilonggo markers fire DIALECT NOTE (Phase A2)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      return {
        ready:       true,
        // T205 _isCebuanoLeaning needs ≥2 markers from the Cebuano set.
        ceb_yes:     wh._isCebuanoLeaning('unsa man na asa ang spare bearing kinsa nag-bitay'),
        ceb_neg:     wh._isCebuanoLeaning('the bearing failed yesterday'),
        // T206 _isIlonggoLeaning needs ≥2 Hiligaynon markers.
        ilo_yes:     wh._isIlonggoLeaning('manami gid bala ang reading damo gid na maintenance'),
        ilo_neg:     wh._isIlonggoLeaning('the bearing failed yesterday'),
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.ceb_yes, 'T205 Cebuano ≥2 markers').toBe(true);
    expect(verdict.ceb_neg, 'T205 EN sentence NOT Cebuano').toBe(false);
    expect(verdict.ilo_yes, 'T206 Ilonggo ≥2 markers').toBe(true);
    expect(verdict.ilo_neg, 'T206 EN sentence NOT Ilonggo').toBe(false);
  });

});
