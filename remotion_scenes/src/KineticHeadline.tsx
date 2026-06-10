import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ORANGE_LT, FONT} from './Ambient';

/**
 * KineticHeadline — the shared silent-first headline used by EVERY scene style.
 * Words spring in one by one (kinetic typography: word-by-word reveals hold
 * muted viewers — 85% of social video plays with the sound off), then hold for
 * the rest of the beat. Frame resets per <Series.Sequence>, so each beat's
 * headline replays its reveal exactly when the narration reaches that beat.
 *
 * position="static" renders in normal flow (inside a style's own layout
 * wrapper); default is absolute at (x, y).
 */
// Words that never deserve the orange accent (the accent must land on MEANING —
// "Ask like a colleague" had highlighted "like"; frame critique 2026-06-10).
const ACCENT_STOP = new Set([
  'the', 'a', 'an', 'your', 'like', 'with', 'and', 'for', 'from', 'this',
  'that', 'every', 'into', 'when', 'what', 'just', 'still', 'are', 'is',
]);

/** Index of the most meaningful word: the longest non-stopword (≥4 letters). */
export const accentIndex = (words: string[]): number => {
  let best = -1;
  let bestLen = 3;
  words.forEach((w, i) => {
    const letters = w.replace(/[^A-Za-z]/g, '');
    if (letters.length > bestLen && !ACCENT_STOP.has(letters.toLowerCase())) {
      best = i;
      bestLen = letters.length;
    }
  });
  return best;
};

export const KineticHeadline: React.FC<{
  text: string;
  x?: number;
  y?: number;
  size?: number;
  maxWidth?: number;
  delay?: number;
  position?: 'absolute' | 'static';
}> = ({text, x = 100, y = 158, size = 52, maxWidth = 640, delay = 8, position = 'absolute'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = (text || '').split(' ').filter(Boolean);
  const accentAt = accentIndex(words);

  const outer: React.CSSProperties =
    position === 'absolute'
      ? {position: 'absolute', left: x, top: y, maxWidth, display: 'flex', flexWrap: 'wrap', gap: '0 14px'}
      : {display: 'flex', flexWrap: 'wrap', gap: '0 14px', maxWidth};

  return (
    <div style={outer}>
      {words.map((w, i) => {
        const wIn = spring({frame: frame - delay - i * 5, fps, config: {damping: 16, mass: 0.55}});
        const accent = i === accentAt;
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              color: accent ? ORANGE_LT : '#fff',
              fontWeight: 800,
              fontSize: size,
              lineHeight: 1.08,
              fontFamily: FONT,
              opacity: wIn,
              transform: `translateY(${interpolate(wIn, [0, 1], [34, 0])}px)`,
              textShadow: '0 4px 26px rgba(0,0,0,.55)',
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};
