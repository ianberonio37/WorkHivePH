/**
 * drawing-symbols.js — Engineering Drawing SVG Symbol Library
 *
 * Standards reference:
 *   IEC 60617  — Electrical graphical symbols
 *   ISA-5.1    — Instrumentation symbols (P&ID)
 *   IEC 62305  — Lightning protection symbols
 *   ASHRAE     — HVAC / mechanical symbols (common Philippine practice)
 *
 * Each symbol:
 *   - Centered at (0,0), fits within a 60×60 bounding box (±30 each axis)
 *   - Uses `currentColor` for all strokes/fills — parent SVG or <g> sets color
 *   - render(x, y, opts) → full <g> SVG string positioned at (x, y)
 *   - ports: named connection points relative to (0,0) for wire/pipe routing
 *
 * Usage:
 *   const svg = drawSymbol('breaker', 100, 200);
 *   document.getElementById('canvas').innerHTML += svg;
 */

const DRAWING_SYMBOLS = {

  // ═══════════════════════════════════════════════════════════════════════════
  // ELECTRICAL  (IEC 60617 simplified for Philippine practice)
  // ═══════════════════════════════════════════════════════════════════════════

  utility_3ph: {
    label: '3-Phase Utility Source',
    discipline: 'electrical',
    ports: { bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-utility_3ph">
        <circle cx="0" cy="-8" r="20" fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="-12" text-anchor="middle" dominant-baseline="middle"
              font-size="9" font-family="sans-serif" font-weight="bold" fill="currentColor">3&#216;</text>
        <text x="0" y="-2" text-anchor="middle" dominant-baseline="middle"
              font-size="6.5" font-family="sans-serif" fill="currentColor">SOURCE</text>
        <line x1="0" y1="12" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  meter_kwh: {
    label: 'kWh Meter',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-meter_kwh">
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
        <rect x="-18" y="-22" width="36" height="44" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="-6" text-anchor="middle" dominant-baseline="middle"
              font-size="9" font-family="sans-serif" font-weight="bold" fill="currentColor">kWh</text>
        <text x="0" y="6" text-anchor="middle" dominant-baseline="middle"
              font-size="6.5" font-family="sans-serif" fill="currentColor">METER</text>
        <line x1="0" y1="22" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  breaker: {
    label: 'MCCB / Circuit Breaker',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-breaker">
        <line x1="0" y1="-30" x2="0" y2="-14" stroke="currentColor" stroke-width="2"/>
        <rect x="-14" y="-14" width="28" height="28" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="-8" y1="-8" x2="8" y2="8" stroke="currentColor" stroke-width="2.5"/>
        <line x1="0" y1="14" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  fuse: {
    label: 'Fuse',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-fuse">
        <line x1="0" y1="-30" x2="0" y2="-16" stroke="currentColor" stroke-width="2"/>
        <rect x="-9" y="-16" width="18" height="32" rx="2"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="-16" x2="0" y2="16" stroke="currentColor" stroke-width="1.5"/>
        <line x1="0" y1="16" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  transformer: {
    label: 'Step-Down Transformer',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-transformer">
        <line x1="0" y1="-30" x2="0" y2="-24" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="-12" r="12" fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="12"  r="12" fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="-6" cy="-16" r="2" fill="currentColor"/>
        <line x1="0" y1="24" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  panel: {
    label: 'Panel Board / MDB / SDB',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30], left: [-28, 0], right: [28, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-panel">
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
        <rect x="-28" y="-22" width="56" height="44" rx="4"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="-18" y1="-10" x2="18" y2="-10" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-18" y1="0"   x2="18" y2="0"   stroke="currentColor" stroke-width="1.5"/>
        <line x1="-18" y1="10"  x2="18" y2="10"  stroke="currentColor" stroke-width="1.5"/>
        <line x1="0" y1="22" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  motor: {
    label: 'Electric Motor',
    discipline: 'electrical',
    ports: { top: [0, -30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-motor">
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="0" r="22" fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="middle"
              font-size="16" font-family="sans-serif" font-weight="bold" fill="currentColor">M</text>
      </g>`;
    },
  },

  generator: {
    label: 'Generator / Genset',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-generator">
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="0" r="22" fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="middle"
              font-size="16" font-family="sans-serif" font-weight="bold" fill="currentColor">G</text>
        <line x1="0" y1="22" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  capacitor: {
    label: 'Capacitor Bank (PFC)',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-capacitor">
        <line x1="0" y1="-30" x2="0" y2="-8" stroke="currentColor" stroke-width="2"/>
        <line x1="-18" y1="-8" x2="18" y2="-8" stroke="currentColor" stroke-width="3"/>
        <line x1="-18" y1="8"  x2="18" y2="8"  stroke="currentColor" stroke-width="3"/>
        <line x1="0" y1="8" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  disconnect: {
    label: 'Disconnect Switch (Open)',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-disconnect">
        <line x1="0" y1="-30" x2="0" y2="-14" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="-14" r="3" fill="currentColor"/>
        <line x1="0" y1="-14" x2="20" y2="-2" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="14" r="3" fill="currentColor"/>
        <line x1="0" y1="14" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  ground: {
    label: 'Earth / Ground',
    discipline: 'electrical',
    ports: { top: [0, -30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-ground">
        <line x1="0" y1="-30" x2="0" y2="0" stroke="currentColor" stroke-width="2"/>
        <line x1="-20" y1="0"  x2="20" y2="0"  stroke="currentColor" stroke-width="2.5"/>
        <line x1="-13" y1="9"  x2="13" y2="9"  stroke="currentColor" stroke-width="2"/>
        <line x1="-6"  y1="18" x2="6"  y2="18" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  ups: {
    label: 'UPS (Uninterruptible Power Supply)',
    discipline: 'electrical',
    ports: { top: [0, -30], bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-ups">
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
        <rect x="-24" y="-22" width="48" height="44" rx="4"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="-5" text-anchor="middle" dominant-baseline="middle"
              font-size="11" font-family="sans-serif" font-weight="bold" fill="currentColor">UPS</text>
        <text x="0" y="8" text-anchor="middle" dominant-baseline="middle"
              font-size="6.5" font-family="sans-serif" fill="currentColor">ONLINE</text>
        <line x1="0" y1="22" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // MECHANICAL / HVAC  (ASHRAE + common Philippine practice)
  // ═══════════════════════════════════════════════════════════════════════════

  pump: {
    label: 'Centrifugal Pump',
    discipline: 'mechanical',
    ports: { left: [-30, 0], top: [0, -30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-pump">
        <circle cx="0" cy="0" r="22" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M -11,-11 L 11,0 L -11,11 Z"
              fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-30" y1="0" x2="-22" y2="0" stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="-30" x2="0" y2="-22" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  valve_gate: {
    label: 'Gate Valve (NO)',
    discipline: 'mechanical',
    ports: { left: [-30, 0], right: [30, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-valve_gate">
        <line x1="-30" y1="0" x2="30" y2="0" stroke="currentColor" stroke-width="2"/>
        <path d="M -12,-16 L 12,-16 L 0,0 Z"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M -12,16  L 12,16  L 0,0 Z"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="-16" x2="0" y2="-26" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-6" y1="-26" x2="6" y2="-26" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  valve_butterfly: {
    label: 'Butterfly Valve',
    discipline: 'mechanical',
    ports: { left: [-30, 0], right: [30, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-valve_butterfly">
        <line x1="-30" y1="0" x2="30" y2="0" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="0" r="12" fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="-9" y1="-9" x2="9" y2="9" stroke="currentColor" stroke-width="1.5"/>
        <line x1="0" y1="-12" x2="0" y2="-26" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-5" y1="-26" x2="5" y2="-26" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  valve_check: {
    label: 'Check Valve / NRV',
    discipline: 'mechanical',
    ports: { left: [-30, 0], right: [30, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-valve_check">
        <line x1="-30" y1="0" x2="30" y2="0" stroke="currentColor" stroke-width="2"/>
        <path d="M -10,-14 L 10,0 L -10,14 Z" fill="currentColor"/>
        <line x1="-10" y1="-14" x2="-10" y2="14"
              stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  valve_prv: {
    label: 'Pressure Relief Valve (PRV)',
    discipline: 'mechanical',
    ports: { left: [-30, 0], right: [30, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-valve_prv">
        <line x1="-30" y1="0" x2="30" y2="0" stroke="currentColor" stroke-width="2"/>
        <path d="M -10,0 L 0,-18 L 10,0 Z"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="-18" x2="0" y2="-26" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-6" y1="-26" x2="6" y2="-26" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  heat_exchanger: {
    label: 'Heat Exchanger / Coil',
    discipline: 'mechanical',
    ports: { left_top: [-30, -10], left_bottom: [-30, 10],
             right_top: [30, -10], right_bottom: [30, 10] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-heat_exchanger">
        <rect x="-24" y="-22" width="48" height="44" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M -14,-12 L 0,0 L -14,12"
              fill="none" stroke="currentColor" stroke-width="1.5"/>
        <path d="M 0,-12 L 14,0 L 0,12"
              fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-30" y1="-10" x2="-24" y2="-10" stroke="currentColor" stroke-width="2"/>
        <line x1="-30" y1="10"  x2="-24" y2="10"  stroke="currentColor" stroke-width="2"/>
        <line x1="24" y1="-10" x2="30" y2="-10" stroke="currentColor" stroke-width="2"/>
        <line x1="24" y1="10"  x2="30" y2="10"  stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  cooling_tower: {
    label: 'Cooling Tower',
    discipline: 'mechanical',
    ports: { bottom_left: [-14, 30], bottom_right: [14, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-cooling_tower">
        <path d="M -26,-28 L 26,-28 L 18,22 L -18,22 Z"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="-16" r="10" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <path d="M -7,-20 A 8,8 0 0,1 7,-20"
              fill="none" stroke="currentColor" stroke-width="1.5"/>
        <path d="M -7,-12 A 8,8 0 0,0 7,-12"
              fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-8" y1="2" x2="-8" y2="14"
              stroke="currentColor" stroke-width="1" stroke-dasharray="2,3"/>
        <line x1="0"  y1="0" x2="0"  y2="14"
              stroke="currentColor" stroke-width="1" stroke-dasharray="2,3"/>
        <line x1="8"  y1="2" x2="8"  y2="14"
              stroke="currentColor" stroke-width="1" stroke-dasharray="2,3"/>
        <line x1="-14" y1="22" x2="-14" y2="30" stroke="currentColor" stroke-width="2"/>
        <line x1="14"  y1="22" x2="14"  y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  ahu: {
    label: 'Air Handling Unit (AHU)',
    discipline: 'mechanical',
    ports: { left: [-38, 0], right: [38, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-ahu">
        <rect x="-28" y="-20" width="56" height="40" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="-10" cy="0" r="13" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-10" y1="-11" x2="-10" y2="11" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-21" y1="0"   x2="1"   y2="0"  stroke="currentColor" stroke-width="1.5"/>
        <line x1="-10" y1="-7"  x2="1"   y2="0"  stroke="currentColor" stroke-width="1"/>
        <line x1="-10" y1="7"   x2="1"   y2="0"  stroke="currentColor" stroke-width="1"/>
        <text x="13" y="1" text-anchor="middle" dominant-baseline="middle"
              font-size="10" font-family="sans-serif" fill="currentColor">&#8776;&#8776;</text>
        <line x1="-28" y1="0" x2="-38" y2="0" stroke="currentColor" stroke-width="2"/>
        <line x1="28"  y1="0" x2="38"  y2="0" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  fcu: {
    label: 'Fan Coil Unit (FCU)',
    discipline: 'mechanical',
    ports: { left: [-22, 0], right: [22, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-fcu">
        <rect x="-22" y="-18" width="44" height="36" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="0" cy="0" r="12" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="0" y1="-10" x2="0" y2="10" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-10" y1="0" x2="10" y2="0" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-7" y1="-7" x2="7"  y2="7" stroke="currentColor" stroke-width="1"/>
        <line x1="7"  y1="-7" x2="-7" y2="7" stroke="currentColor" stroke-width="1"/>
      </g>`;
    },
  },

  chiller: {
    label: 'Chiller Unit',
    discipline: 'mechanical',
    ports: { top_left: [-12, -28], top_right: [12, -28],
             bottom_left: [-12, 28], bottom_right: [12, 28] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-chiller">
        <rect x="-26" y="-24" width="52" height="48" rx="4"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <text x="0" y="-8" text-anchor="middle" dominant-baseline="middle"
              font-size="8" font-family="sans-serif" font-weight="bold" fill="currentColor">CHILLER</text>
        <line x1="-16" y1="4"  x2="16" y2="4"  stroke="currentColor" stroke-width="1.5"/>
        <line x1="-16" y1="11" x2="16" y2="11" stroke="currentColor" stroke-width="1.5"/>
        <line x1="-12" y1="-24" x2="-12" y2="-30" stroke="currentColor" stroke-width="2"/>
        <line x1="12"  y1="-24" x2="12"  y2="-30" stroke="currentColor" stroke-width="2"/>
        <line x1="-12" y1="24"  x2="-12" y2="30"  stroke="currentColor" stroke-width="2"/>
        <line x1="12"  y1="24"  x2="12"  y2="30"  stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  tank: {
    label: 'Tank / Vessel / Sump',
    discipline: 'mechanical',
    ports: { inlet: [-30, -8], outlet: [30, 8], drain: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-tank">
        <rect x="-20" y="-18" width="40" height="38" rx="3"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <ellipse cx="0" cy="-18" rx="20" ry="6"
                 fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="-20" y1="-8" x2="-30" y2="-8" stroke="currentColor" stroke-width="2"/>
        <line x1="20"  y1="8"  x2="30"  y2="8"  stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="20" x2="0" y2="30" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  fan: {
    label: 'Fan / Blower',
    discipline: 'mechanical',
    ports: { left: [-30, 0], right: [30, 0] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-fan">
        <circle cx="0" cy="0" r="20" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M 0,-15 A 8,8 0 0,1 13,8"
              fill="none" stroke="currentColor" stroke-width="2.5"/>
        <path d="M 13,8 A 8,8 0 0,1 -13,8"
              fill="none" stroke="currentColor" stroke-width="2.5"/>
        <path d="M -13,8 A 8,8 0 0,1 0,-15"
              fill="none" stroke="currentColor" stroke-width="2.5"/>
        <circle cx="0" cy="0" r="3" fill="currentColor"/>
        <line x1="-30" y1="0" x2="-20" y2="0" stroke="currentColor" stroke-width="2"/>
        <line x1="20"  y1="0" x2="30"  y2="0" stroke="currentColor" stroke-width="2"/>
      </g>`;
    },
  },

  diffuser: {
    label: 'Supply Air Diffuser',
    discipline: 'mechanical',
    ports: { top: [0, -22] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-diffuser">
        <line x1="0" y1="-22" x2="0" y2="-8" stroke="currentColor" stroke-width="2"/>
        <rect x="-24" y="-8" width="48" height="16" rx="2"
              fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="-16" y1="-8" x2="-16" y2="8" stroke="currentColor" stroke-width="1"/>
        <line x1="-8"  y1="-8" x2="-8"  y2="8" stroke="currentColor" stroke-width="1"/>
        <line x1="0"   y1="-8" x2="0"   y2="8" stroke="currentColor" stroke-width="1"/>
        <line x1="8"   y1="-8" x2="8"   y2="8" stroke="currentColor" stroke-width="1"/>
        <line x1="16"  y1="-8" x2="16"  y2="8" stroke="currentColor" stroke-width="1"/>
      </g>`;
    },
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // P&ID INSTRUMENTS  (ISA-5.1 simplified)
  // ═══════════════════════════════════════════════════════════════════════════

  instrument: {
    label: 'Instrument Bubble (P&ID)',
    discipline: 'pid',
    ports: { bottom: [0, 20] },
    render(x = 0, y = 0, opts = {}) {
      const tag  = opts.tag  || 'PIC';
      const loop = opts.loop || '101';
      return `<g transform="translate(${x},${y})" class="sym-instrument">
        <circle cx="0" cy="0" r="18" fill="white" stroke="currentColor" stroke-width="2"/>
        <line x1="-16" y1="0" x2="16" y2="0" stroke="currentColor" stroke-width="1"/>
        <text x="0" y="-5" text-anchor="middle" dominant-baseline="middle"
              font-size="7" font-family="sans-serif" font-weight="bold" fill="currentColor">${tag}</text>
        <text x="0" y="7" text-anchor="middle" dominant-baseline="middle"
              font-size="6" font-family="sans-serif" fill="currentColor">${loop}</text>
        <line x1="0" y1="18" x2="0" y2="28"
              stroke="currentColor" stroke-width="1.5" stroke-dasharray="4,3"/>
      </g>`;
    },
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // LIGHTNING PROTECTION  (IEC 62305 simplified)
  // ═══════════════════════════════════════════════════════════════════════════

  air_terminal: {
    label: 'Air Terminal / Lightning Rod',
    discipline: 'lps',
    ports: { bottom: [0, 30] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-air_terminal">
        <line x1="0" y1="30" x2="0" y2="-14" stroke="currentColor" stroke-width="2"/>
        <path d="M -4,-4 L 4,-18 L 0,-12 L 4,-28 L -4,-12 L 0,-18 Z" fill="currentColor"/>
        <line x1="-10" y1="30" x2="10" y2="30" stroke="currentColor" stroke-width="3"/>
      </g>`;
    },
  },

  earth_electrode: {
    label: 'Earth Electrode / Ground Rod',
    discipline: 'lps',
    ports: { top: [0, -28] },
    render(x = 0, y = 0, opts = {}) {
      return `<g transform="translate(${x},${y})" class="sym-earth_electrode">
        <line x1="0" y1="-28" x2="0" y2="2" stroke="currentColor" stroke-width="2"/>
        <line x1="-20" y1="2" x2="20" y2="2" stroke="currentColor" stroke-width="2"/>
        <line x1="0" y1="2" x2="0" y2="20"
              stroke="currentColor" stroke-width="2" stroke-dasharray="4,3"/>
        <rect x="-5" y="12" width="10" height="16" rx="3"
              fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="3,3"/>
      </g>`;
    },
  },

};

// ─── Utility: render a symbol at (cx, cy) ────────────────────────────────────
function drawSymbol(key, cx = 0, cy = 0, opts = {}) {
  const sym = DRAWING_SYMBOLS[key];
  if (!sym) return `<!-- drawing-symbols.js: unknown key "${key}" -->`;
  return sym.render(cx, cy, opts);
}

// ─── Utility: return all symbol metadata for gallery/picker ─────────────────
function getSymbolList() {
  return Object.entries(DRAWING_SYMBOLS).map(([key, sym]) => ({
    key,
    label:      sym.label,
    discipline: sym.discipline,
  }));
}
