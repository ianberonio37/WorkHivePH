/**
 * service_personas.mjs — the diverse humans who actually use this platform.
 *
 * Ian, 2026-07-31: "you have to consider the diversity of human beings — there are diverse simulations in
 * test banks."
 *
 * WHY THIS IS A JOURNEY AXIS AND NOT A PAGE PROPERTY. Every journey in the bank implicitly walks a
 * competent, sighted, literate, English-reading, fast-network, calm user. Almost none of this platform's
 * real users are all six at once: PH plant technicians in their fifties, first-time e-wallet users, someone
 * outdoors in glare wearing gloves, someone on 3G with ₱20 of load left. Diversity is not a property of a
 * page — it is WHO IS WALKING, so it belongs here.
 *
 * DIVISION OF LABOUR — do not re-measure what is already owned. The bank deliberately retired its
 * `viewport` and `lang` axes because other instruments own them: validate_service_ufai_deep.py measures
 * 390/1280 with real tap-target and overflow numbers, validate_i18n_coverage.py owns language,
 * validate_clickable_keyboard_a11y.py owns keyboard. **UFAI grades the PAGE; this walks the HUMAN** — it
 * asks whether a particular person can finish a particular task, which no per-page grader can answer.
 *
 * A PERSONA IS A RUNTIME CONDITION, NOT A COMMENT. Each entry carries the browser state the walk must
 * actually apply — viewport, zoom, colour filter, reduced motion, network throttle, locale, input delay —
 * so "we tested for low vision" means the page really was rendered at 200%, not that someone thought about
 * it. `pairedWith` binds each persona to the journeys where it is most likely to BREAK, with the reason
 * printed: 25 personas x 30 journeys is 750 walks nobody runs, and an unrunnable matrix silently becomes an
 * unrun one. Money screens (family E) take the full sweep, because that is where failure costs pesos.
 */

export const PERSONAS = [
  // ---- Sensory ------------------------------------------------------------------------------------
  { id: 'P-LOWVIS', group: 'sensory', label: 'Low vision, 200% zoom',
    conditions: { deviceScaleFactor: 2, zoom: 2.0, viewport: { width: 390, height: 844 } },
    pairedWith: ['B-map', 'E-money'],
    why: 'at 200% the page must REFLOW, not scroll sideways; money screens are where a clipped number costs money' },

  { id: 'P-COLORBLIND', group: 'sensory', label: 'Deuteranopia',
    conditions: { colorFilter: 'deuteranopia' },
    pairedWith: ['C-hail', 'B-map', 'E-money'],
    why: 'the 12 request states are signalled by CHIPS — if colour is the only difference, broadcasting, accepted and completed are one state to this person' },

  { id: 'P-SCREENREADER', group: 'sensory', label: 'Screen reader (NVDA)',
    conditions: { forcedColors: 'active', reducedMotion: 'reduce' },
    pairedWith: ['A-discovery', 'B-map'],
    why: 'A MAP IS UNUSABLE BY A SCREEN READER. If there is no text-equivalent "providers near you" list, discovery is entirely closed to blind users — and aria-label alone does not fix it' },

  { id: 'P-DEAF', group: 'sensory', label: 'Deaf / hard of hearing',
    conditions: { muteAudio: true },
    pairedWith: ['C-hail', 'G-unhappy'],
    why: 'a hail arriving must be VISIBLE; an audio-only alert is no alert at all' },

  // ---- Motor --------------------------------------------------------------------------------------
  { id: 'P-TREMOR', group: 'motor', label: 'Hand tremor',
    conditions: { inputDelayMs: 900, doubleTapRisk: true },
    pairedWith: ['C-hail', 'E-money'],
    why: 'time-boxed actions (TTL, the accept race) punish slow input, and a tremor double-taps — which must mint exactly one commission' },

  { id: 'P-ONEHANDED', group: 'motor', label: 'One-handed, phone in the other',
    conditions: { viewport: { width: 390, height: 844 }, reachZone: 'bottom-third' },
    pairedWith: ['C-hail', 'E-money'],
    why: 'a primary action stranded at the top of a 844px screen cannot be reached while holding a tool' },

  { id: 'P-GLOVED', group: 'motor', label: 'Wearing work gloves',
    conditions: { minTapTargetPx: 48 },
    pairedWith: ['C-hail', 'D-entrypoints'],
    why: 'a real industrial constraint: gloves make anything under ~48px unhittable, and this is a maintenance platform' },

  // ---- Language & literacy ------------------------------------------------------------------------
  { id: 'P-FILIPINO', group: 'language', label: 'Tagalog throughout',
    conditions: { locale: 'fil-PH', lang: 'fil' },
    pairedWith: ['E-money', 'A-discovery'],
    why: 'HARDEST on money. Commission, settle, release, cashback and escrow have no clean everyday Tagalog equivalents — an unresolved marker on a money screen is someone not understanding what they are agreeing to' },

  { id: 'P-TAGLISH', group: 'language', label: 'Code-switching Taglish',
    conditions: { locale: 'fil-PH', lang: 'en' },
    pairedWith: ['A-discovery'],
    why: 'how most PH users actually read: English UI, Tagalog search terms' },

  { id: 'P-LOWLITERACY', group: 'language', label: 'Low literacy / plain language',
    conditions: { maxReadingGrade: 6 },
    pairedWith: ['E-money'],
    why: 'jargon is a comprehension wall exactly where consent matters' },

  // ---- Device & network (the PH baseline, not an edge case) ---------------------------------------
  { id: 'P-LOWEND', group: 'device', label: 'Low-end Android, 360px',
    conditions: { viewport: { width: 360, height: 640 }, cpuThrottle: 4 },
    pairedWith: ['B-map', 'C-hail'],
    why: 'the map is the heaviest surface on the weakest device' },

  { id: 'P-SLOWNET', group: 'device', label: '3G',
    conditions: { network: { downloadKbps: 400, uploadKbps: 400, latencyMs: 400 } },
    pairedWith: ['B-map', 'C-hail', 'E-money'],
    why: 'a TTL that assumes fast tiles expires while this person is still waiting to see the hail' },

  { id: 'P-FLAKY', group: 'device', label: 'Connection drops mid-job',
    conditions: { network: 'intermittent', dropAfterMs: 3000 },
    pairedWith: ['G-unhappy', 'E-money'],
    why: 'the honest test of the offline queue — and adoption of an offline BANNER is not proof that writes are refused' },

  { id: 'P-BATTERY', group: 'device', label: 'Battery saver / reduced motion',
    conditions: { reducedMotion: 'reduce' },
    pairedWith: ['B-map', 'F-aftermath'],
    why: 'an animation-dependent affordance disappears entirely' },

  { id: 'P-DATACAP', group: 'device', label: 'Metered data, nearly out',
    conditions: { blockHeavyAssets: true },
    pairedWith: ['B-map'],
    why: 'payload weight is a cost this user pays in pesos' },

  // ---- Digital & financial literacy (the highest-stakes group here) --------------------------------
  { id: 'P-FIRSTTIME', group: 'literacy', label: 'First marketplace, first e-wallet',
    conditions: { clearStorage: true, noPriorSession: true },
    pairedWith: ['A-discovery', 'E-money'],
    why: 'nothing may depend on knowing a convention they have never met' },

  { id: 'P-SCAMWARY', group: 'literacy', label: 'Has been scammed before',
    conditions: { clearStorage: true, requireExplicitDisclosure: true },
    pairedWith: ['E-money'],
    why: 'THE PERSONA THAT DECIDES WHETHER THIS ECONOMY WORKS. If "Confirm payment & release" reads like a trick they abandon — and they are RIGHT to, unless the screen says plainly who gets what, that the platform never holds their money, and what happens if the job was bad' },

  { id: 'P-UNBANKED', group: 'literacy', label: 'GCash only, irregular income',
    conditions: { creditBalanceBelow: 200 },
    pairedWith: ['E-money'],
    why: 'who the ₱200 min-balance actually taxes; the refusal must be announced and must say how to fix it' },

  // ---- Age & environment --------------------------------------------------------------------------
  { id: 'P-OLDER', group: 'age', label: '55+, presbyopia',
    conditions: { zoom: 1.5, inputDelayMs: 600 },
    pairedWith: ['B-map', 'C-hail', 'F-aftermath'],
    why: 'the median experienced maintenance technician, not an edge case' },

  { id: 'P-SUNLIGHT', group: 'environment', label: 'Outdoors in glare',
    conditions: { contrastFloorAPCA: 60 },
    pairedWith: ['B-map', 'C-hail'],
    why: 'APCA already caught 25% perceptual contrast on dark where WCAG read 100%; glare is that failure outdoors' },

  { id: 'P-NIGHT', group: 'environment', label: 'Night shift, dark mode',
    conditions: { colorScheme: 'dark' },
    pairedWith: ['B-map', 'F-aftermath'],
    why: 'half of industrial maintenance happens at night' },

  { id: 'P-NOISY', group: 'environment', label: 'Plant floor, loud',
    conditions: { muteAudio: true },
    pairedWith: ['C-hail'],
    why: 'shares one rule with P-DEAF: no audio-only signal' },

  // ---- Behavioural --------------------------------------------------------------------------------
  { id: 'P-IMPULSIVE', group: 'behaviour', label: 'Double-taps everything',
    conditions: { doubleTapEveryAction: true },
    pairedWith: ['C-hail', 'E-money'],
    why: 'the human form of the idempotency tests — a double-tapped Release must mint exactly one commission' },

  { id: 'P-HAGGLER', group: 'behaviour', label: 'Negotiates every price',
    conditions: {},
    pairedWith: ['C-hail', 'E-money'],
    why: 'quote/counter-offer flows, and the gap between agreed and declared price the leakage gate watches' },

  { id: 'P-NOSHOW', group: 'behaviour', label: 'Abandons mid-flow',
    conditions: { abandonAfterStep: 2 },
    pairedWith: ['G-unhappy'],
    why: 'how `expired` and the cancel paths are actually reached by real people' },
];

/** Journey families the personas pair against (Tier 2 of the money test bank). */
export const FAMILIES = {
  'A-discovery':   'anon browses -> registers; provider onboarding; certified-skill gate; search',
  'B-map':         'markers, presence, radius widening, the marker following a provider',
  'C-hail':        'instant vs quote, broadcast/widen/TTL, the accept race',
  'D-entrypoints': 'asset-context hail, alert->hail, PM/recurring auto-hail',
  'E-money':       'confirm-and-release, min-balance block, GCash verify, dispute, founder metrics',
  'F-aftermath':   'bidirectional review, tier progress, logbook writeback, showcase',
  'G-unhappy':     'cancel from each state, expire, offline mid-job',
};

/** Every persona bound to the money family — failure there costs pesos, not a re-render. */
export const MONEY_SWEEP = PERSONAS.filter(p => p.pairedWith.includes('E-money')).map(p => p.id);

/** Pairings NOT walked are owed WITH A REASON, never quietly dropped. */
export function owedPairings() {
  const owed = [];
  for (const p of PERSONAS)
    for (const f of Object.keys(FAMILIES))
      if (!p.pairedWith.includes(f))
        owed.push({ persona: p.id, family: f,
                    reason: 'not paired: this persona is not the one most likely to break this family' });
  return owed;
}

export default PERSONAS;
