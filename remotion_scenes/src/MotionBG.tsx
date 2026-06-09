import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// ── WorkHive brand palette ──────────────────────────────────────────────────
const NAVY_DEEP = '#0E1726';
const NAVY = '#162032';
const ORANGE = '#F7A21B';
const ORANGE_LT = '#FDB94A';
const ORANGE_DK = '#D88A0E';
const FONT = '"Poppins","Segoe UI",system-ui,-apple-system,sans-serif';

type Props = {
  headline: string;
  subhead: string;
};

/**
 * WorkHiveMotionBG — an ANIMATED on-brand motion-graphics background that MOVES
 * (live bar chart + scrolling line + sweeping gauge + drifting particles), so it
 * replaces Pexels stock-footage motion instead of being a static title card.
 * Motion is continuous/periodic so the assembler's hard loop stays smooth.
 *
 * Layout: headline top-left; the animated "live dashboard strip" sits in the
 * lower-left ~60% (x < 760); the right side (UI PiP) and bottom-centre (burned
 * captions) are kept clear.
 */
export const WorkHiveMotionBG: React.FC<Props> = ({headline, subhead}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;

  const titleIn = spring({frame: frame - 8, fps, config: {damping: 18, mass: 0.7}});
  const subIn = spring({frame: frame - 22, fps, config: {damping: 18, mass: 0.7}});

  // ── Live bar chart (oscillating), lower-left ──────────────────────────────
  const BAR_N = 6;
  const barW = 30, barGap = 16, barX0 = 96, barBaseY = 600, barTrack = 150;
  const bars = Array.from({length: BAR_N}, (_, i) => 36 + (0.5 + 0.5 * Math.sin(t * 1.5 + i * 0.85)) * (barTrack - 36));

  // ── Scrolling area/line chart, centre ─────────────────────────────────────
  const LW = 250, LH = 92, lx = 392, ly = 470;
  const pts: string[] = [];
  for (let x = 0; x <= LW; x += 7) {
    const phase = (x / LW) * Math.PI * 4 - t * 2.2;
    const amp = (LH / 2 - 6) * (0.6 + 0.4 * Math.sin(t * 0.5 + x / 110));
    pts.push(`${x},${(LH / 2 - Math.sin(phase) * amp).toFixed(1)}`);
  }
  const linePath = `M ${pts.join(' L ')}`;
  const areaPath = `M 0,${LH} L ${pts.join(' L ')} L ${LW},${LH} Z`;

  // ── Sweeping ring gauge, lower-right of the strip (still left of UI PiP) ───
  const gR = 62, gCx = 700, gCy = 512, gC = 2 * Math.PI * gR;
  const gPct = 0.5 + 0.42 * Math.sin(t * 0.9);
  const gNum = Math.round(gPct * 100);

  // ── Drifting particles (ambient) ──────────────────────────────────────────
  const particles = Array.from({length: 16}, (_, i) => {
    const x = ((i * 131) % 1000) / 1000 * width;
    const speed = 16 + (i % 5) * 7;
    const y = height - ((t * speed + i * 70) % (height + 80));
    return {x, y, size: 3 + (i % 3) * 2, op: 0.14 + 0.16 * (0.5 + 0.5 * Math.sin(t + i))};
  });

  return (
    <AbsoluteFill style={{backgroundColor: NAVY_DEEP, fontFamily: FONT}}>
      <AbsoluteFill
        style={{background: `radial-gradient(circle at 30% 34%, #1d2c44 0%, ${NAVY} 46%, ${NAVY_DEEP} 100%)`}}
      />

      {/* Drifting dot grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${ORANGE}18 1.4px, transparent 1.6px)`,
          backgroundSize: '48px 48px', opacity: 0.45,
          transform: `translate(${(t * 7) % 48}px, ${(t * 5) % 48}px)`,
        }}
      />

      {/* Particles */}
      {particles.map((p, i) => (
        <div key={i} style={{
          position: 'absolute', left: p.x, top: p.y, width: p.size, height: p.size,
          borderRadius: '50%', background: ORANGE_LT, opacity: p.op,
        }} />
      ))}

      {/* Wordmark */}
      <div style={{position: 'absolute', left: 96, top: 80, fontWeight: 800, fontSize: 30}}>
        <span style={{color: ORANGE}}>Work</span><span style={{color: '#fff'}}>Hive</span>
      </div>

      {/* Headline + tag, top-left */}
      <div style={{position: 'absolute', left: 96, top: 158, maxWidth: 600}}>
        <div style={{
          color: '#fff', fontWeight: 800, fontSize: 52, lineHeight: 1.05,
          opacity: titleIn, transform: `translateY(${interpolate(titleIn, [0, 1], [24, 0])}px)`,
          textShadow: '0 4px 24px rgba(0,0,0,.5)',
        }}>{headline}</div>
        <div style={{
          marginTop: 16, display: 'inline-block', padding: '7px 16px', borderRadius: 22,
          background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`,
          color: NAVY_DEEP, fontWeight: 700, fontSize: 20,
          opacity: subIn, transform: `translateY(${interpolate(subIn, [0, 1], [16, 0])}px)`,
        }}>{subhead}</div>
      </div>

      {/* LIVE pulse label above the strip */}
      <div style={{position: 'absolute', left: 96, top: 408, display: 'flex', alignItems: 'center', gap: 8}}>
        <div style={{
          width: 11, height: 11, borderRadius: '50%', background: ORANGE,
          opacity: 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(t * 4)), boxShadow: `0 0 12px ${ORANGE}`,
        }} />
        <span style={{color: ORANGE, fontWeight: 700, fontSize: 15, letterSpacing: 3}}>LIVE PLANT METRICS</span>
      </div>

      {/* Animated dashboard strip (SVG) */}
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        <defs>
          <linearGradient id="mbArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ORANGE} stopOpacity="0.36" />
            <stop offset="100%" stopColor={ORANGE} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Bars */}
        {bars.map((h, i) => {
          const x = barX0 + i * (barW + barGap);
          return (
            <g key={i}>
              <rect x={x} y={barBaseY - barTrack} width={barW} height={barTrack} rx={6} fill="#ffffff0d" />
              <rect x={x} y={barBaseY - h} width={barW} height={h} rx={6} fill={i % 2 === 0 ? ORANGE : ORANGE_DK} />
            </g>
          );
        })}

        {/* Scrolling line + area */}
        <g transform={`translate(${lx} ${ly})`}>
          <path d={areaPath} fill="url(#mbArea)" />
          <path d={linePath} fill="none" stroke={ORANGE_LT} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
        </g>

        {/* Sweeping ring gauge */}
        <circle cx={gCx} cy={gCy} r={gR} fill="none" stroke="#ffffff12" strokeWidth={11} />
        <circle cx={gCx} cy={gCy} r={gR} fill="none" stroke={ORANGE} strokeWidth={11} strokeLinecap="round"
                strokeDasharray={gC} strokeDashoffset={gC * (1 - gPct)} transform={`rotate(-90 ${gCx} ${gCy})`} />
        <text x={gCx} y={gCy} textAnchor="middle" dominantBaseline="central" fill="#fff"
              style={{fontFamily: FONT, fontWeight: 800, fontSize: 34}}>
          {gNum}<tspan fill={ORANGE_LT} style={{fontSize: 18}}>%</tspan>
        </text>
      </svg>

      {/* Brand bar */}
      <div style={{
        position: 'absolute', left: 0, bottom: 0, height: 8, width: '100%',
        background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`, opacity: 0.9,
      }} />
    </AbsoluteFill>
  );
};
