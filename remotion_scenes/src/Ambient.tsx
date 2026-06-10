import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Poppins';

// Brand font GUARANTEED at render time (previously relied on Poppins being
// installed on the render box -- silent Segoe UI fallback otherwise).
const {fontFamily: POPPINS} = loadFont('normal', {weights: ['400', '600', '700', '800', '900']});

// ── WorkHive brand palette (shared) ─────────────────────────────────────────
export const NAVY_DEEP = '#0E1726';
export const NAVY = '#162032';
export const ORANGE = '#F7A21B';
export const ORANGE_LT = '#FDB94A';
export const ORANGE_DK = '#D88A0E';
export const FONT = `"${POPPINS}","Segoe UI",system-ui,-apple-system,sans-serif`;

/**
 * Ambient — the shared WorkHive backdrop for every animated scene style:
 * navy radial gradient + drifting dot grid + rising particles + wordmark +
 * brand bar. Continuous/periodic motion so the assembler's loop stays smooth.
 */
export const Ambient: React.FC<{wordmark?: boolean}> = ({wordmark = false}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const t = frame / fps;

  const particles = Array.from({length: 16}, (_, i) => {
    const x = ((i * 131) % 1000) / 1000 * width;
    const speed = 16 + (i % 5) * 7;
    const y = height - ((t * speed + i * 70) % (height + 80));
    return {x, y, size: 3 + (i % 3) * 2, op: 0.12 + 0.16 * (0.5 + 0.5 * Math.sin(t + i))};
  });

  return (
    <AbsoluteFill style={{backgroundColor: NAVY_DEEP, fontFamily: FONT}}>
      <AbsoluteFill
        style={{background: `radial-gradient(circle at 30% 34%, #1d2c44 0%, ${NAVY} 46%, ${NAVY_DEEP} 100%)`}}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${ORANGE}18 1.4px, transparent 1.6px)`,
          backgroundSize: '48px 48px', opacity: 0.42,
          transform: `translate(${(t * 7) % 48}px, ${(t * 5) % 48}px)`,
        }}
      />
      {particles.map((p, i) => (
        <div key={i} style={{
          position: 'absolute', left: p.x, top: p.y, width: p.size, height: p.size,
          borderRadius: '50%', background: ORANGE_LT, opacity: p.op,
        }} />
      ))}
      {wordmark && (
        <div style={{position: 'absolute', left: 96, top: 80, fontWeight: 800, fontSize: 28, zIndex: 5}}>
          <span style={{color: ORANGE}}>Work</span><span style={{color: '#fff'}}>Hive</span>
        </div>
      )}
      <div style={{
        position: 'absolute', left: 0, bottom: 0, height: 8, width: '100%',
        background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`, opacity: 0.9, zIndex: 5,
      }} />
    </AbsoluteFill>
  );
};
