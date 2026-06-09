import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Ambient, ORANGE, ORANGE_LT, NAVY_DEEP, FONT} from './Ambient';

type Props = {
  headline: string;
  subhead: string;
  phrases: string[];
};

/**
 * WorkHiveKinetic — kinetic-typography scene. Cycles the idea's key phrases,
 * animating each word in (slide + fade, staggered) with a sweeping orange
 * underline. Best for emotional / storytelling videos. Text is weighted
 * left/centre, clear of the UI PiP (bottom-right) and burned captions.
 */
export const WorkHiveKinetic: React.FC<Props> = ({headline, subhead, phrases}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const list = (phrases && phrases.length ? phrases : [headline]).slice(0, 6);
  const PER = 78;                                   // frames per phrase (~2.6s)
  const idx = Math.floor(frame / PER) % list.length;
  const local = frame % PER;
  const outStart = PER - 14;
  const words = list[idx].split(' ');

  // sweeping underline
  const ulIn = spring({frame: local - 6, fps, config: {damping: 16, mass: 0.7}});
  const ulOut = local > outStart ? interpolate(local, [outStart, PER], [1, 0]) : 1;

  return (
    <>
      <Ambient />
      {/* eyebrow */}
      <div style={{position: 'absolute', left: 100, top: 196, color: ORANGE, fontWeight: 700, fontSize: 16, letterSpacing: 4, fontFamily: FONT}}>
        {subhead.toUpperCase()}
      </div>

      {/* animated phrase */}
      <div style={{position: 'absolute', left: 100, top: 250, maxWidth: 720, display: 'flex', flexWrap: 'wrap', gap: '0 18px'}}>
        {words.map((w, i) => {
          const wIn = spring({frame: local - 4 - i * 4, fps, config: {damping: 16, mass: 0.55}});
          const wOut = local > outStart ? interpolate(local, [outStart, PER], [1, 0]) : 1;
          const accent = w.replace(/[^A-Za-z]/g, '').length > 3 && i % 3 === 1;
          return (
            <span key={i} style={{
              display: 'inline-block',
              color: accent ? ORANGE_LT : '#fff',
              fontWeight: 800, fontSize: 66, lineHeight: 1.1, fontFamily: FONT,
              opacity: wIn * wOut,
              transform: `translateY(${interpolate(wIn, [0, 1], [44, 0])}px)`,
              textShadow: '0 4px 26px rgba(0,0,0,.55)',
            }}>{w}</span>
          );
        })}
      </div>

      {/* sweeping underline */}
      <div style={{
        position: 'absolute', left: 102, top: 250 + 86 * Math.min(2, Math.ceil(words.length / 4)) + 8,
        height: 6, width: interpolate(ulIn, [0, 1], [0, 360]) * ulOut, maxWidth: 520,
        background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_LT} 100%)`, borderRadius: 4,
        opacity: ulOut,
      }} />

      {/* progress dots */}
      <div style={{position: 'absolute', left: 102, bottom: 120, display: 'flex', gap: 8}}>
        {list.map((_, i) => (
          <div key={i} style={{
            width: i === idx ? 22 : 8, height: 8, borderRadius: 4,
            background: i === idx ? ORANGE : '#ffffff33', transition: 'all .3s',
          }} />
        ))}
      </div>
    </>
  );
};
