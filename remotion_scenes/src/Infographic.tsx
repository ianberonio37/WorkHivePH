import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Ambient, ORANGE, ORANGE_LT, ORANGE_DK, NAVY, NAVY_DEEP, FONT} from './Ambient';

type Stat = {value: string; label: string; dir?: 'up' | 'down' | 'flat'};
type Props = {
  headline: string;
  subhead: string;
  stats: Stat[];
};

const splitNum = (v: string) => {
  const m = (v || '').match(/^([^\d-]*)(-?\d+(?:\.\d+)?)(.*)$/);
  if (!m) return {pre: '', num: null as number | null, suf: v || ''};
  return {pre: m[1], num: parseFloat(m[2]), suf: m[3]};
};

/**
 * WorkHiveInfographic — animated stat callout cards (count-up numbers + trend
 * arrows) that fly in staggered, then breathe. Best for educational / comparison
 * videos. Cards live in the left ~55% (x < 740), clear of the UI PiP.
 */
export const WorkHiveInfographic: React.FC<Props> = ({headline, subhead, stats}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cards = (stats && stats.length ? stats : [{value: '100%', label: 'Free', dir: 'up' as const}]).slice(0, 4);

  const titleIn = spring({frame: frame - 8, fps, config: {damping: 18, mass: 0.7}});

  const CARD_W = 150, GAP = 18, X0 = 96, Y0 = 320;

  return (
    <>
      <Ambient />
      {/* eyebrow + headline */}
      <div style={{position: 'absolute', left: 100, top: 150, maxWidth: 660}}>
        <div style={{color: ORANGE, fontWeight: 700, fontSize: 15, letterSpacing: 4, fontFamily: FONT}}>
          {subhead.toUpperCase()}
        </div>
        <div style={{
          marginTop: 8, color: '#fff', fontWeight: 800, fontSize: 46, lineHeight: 1.06, fontFamily: FONT,
          opacity: titleIn, transform: `translateY(${interpolate(titleIn, [0, 1], [22, 0])}px)`,
          textShadow: '0 4px 24px rgba(0,0,0,.5)',
        }}>{headline}</div>
      </div>

      {/* stat cards */}
      {cards.map((s, i) => {
        const start = 18 + i * 10;
        const inP = spring({frame: frame - start, fps, config: {damping: 15, mass: 0.6}});
        const float = Math.sin((frame / fps) * 1.2 + i) * 5;
        const {pre, num, suf} = splitNum(s.value);
        const shown = num == null ? s.value
          : pre + Math.round(interpolate(frame, [start, start + 28], [0, num], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})).toString() + suf;
        const arrow = s.dir === 'down' ? '↓' : s.dir === 'flat' ? '→' : '↑';
        const x = X0 + i * (CARD_W + GAP);
        return (
          <div key={i} style={{
            position: 'absolute', left: x, top: Y0 + float, width: CARD_W, height: 168,
            background: `linear-gradient(160deg, ${NAVY} 0%, ${NAVY_DEEP} 100%)`,
            border: '1px solid #ffffff14', borderRadius: 16, padding: '18px 16px',
            boxShadow: '0 14px 38px rgba(0,0,0,.45)', fontFamily: FONT,
            opacity: inP, transform: `translateY(${interpolate(inP, [0, 1], [40, 0])}px)`,
          }}>
            <div style={{display: 'flex', alignItems: 'baseline', gap: 6}}>
              <span style={{color: ORANGE, fontWeight: 800, fontSize: 40, lineHeight: 1}}>{shown}</span>
              <span style={{color: ORANGE_LT, fontWeight: 800, fontSize: 22}}>{arrow}</span>
            </div>
            <div style={{marginTop: 12, color: '#cdd7e6', fontWeight: 600, fontSize: 15, lineHeight: 1.25}}>
              {s.label}
            </div>
            <div style={{position: 'absolute', left: 16, right: 16, bottom: 16, height: 4, borderRadius: 2,
              background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`, opacity: 0.85,
              transform: `scaleX(${inP})`, transformOrigin: 'left'}} />
          </div>
        );
      })}
    </>
  );
};
