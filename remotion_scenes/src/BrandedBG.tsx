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
 * WorkHiveBrandedBG — a REUSABLE, on-brand ambient background for ANY video idea.
 * Replaces generic Pexels stock. Motion is weighted to the left/top because the
 * video_assembler overlays the UI screen-recording at 38% in the bottom-right.
 * Headline fades in once then holds (so the assembler's hard loop is unobtrusive).
 */
export const WorkHiveBrandedBG: React.FC<Props> = ({headline, subhead}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;

  const titleIn = spring({frame: frame - 8, fps, config: {damping: 18, mass: 0.7}});
  const subIn = spring({frame: frame - 20, fps, config: {damping: 18, mass: 0.7}});

  return (
    <AbsoluteFill style={{backgroundColor: NAVY_DEEP, fontFamily: FONT}}>
      {/* Radial brand gradient */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 26% 30%, #1d2c44 0%, ${NAVY} 44%, ${NAVY_DEEP} 100%)`,
        }}
      />

      {/* Drifting dot grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${ORANGE}22 1.5px, transparent 1.6px)`,
          backgroundSize: '46px 46px',
          opacity: 0.5,
          transform: `translate(${(t * 6) % 46}px, ${(t * 4) % 46}px)`,
        }}
      />

      {/* Floating orange glow blobs */}
      {[0, 1, 2].map((i) => {
        const bx = width * (0.3 + i * 0.18) + Math.sin(t * 0.4 + i * 1.7) * 110;
        const by = height * (0.3 + i * 0.12) + Math.cos(t * 0.33 + i * 2.1) * 90;
        const size = 360 - i * 70;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: bx - size / 2,
              top: by - size / 2,
              width: size,
              height: size,
              borderRadius: '50%',
              background: `radial-gradient(circle, ${i === 1 ? ORANGE : ORANGE_DK}, transparent 68%)`,
              opacity: i === 2 ? 0.1 : 0.16,
              filter: 'blur(30px)',
            }}
          />
        );
      })}

      {/* Brand wordmark, top-left */}
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 84,
          fontWeight: 800,
          fontSize: 30,
          letterSpacing: 0.5,
        }}
      >
        <span style={{color: ORANGE}}>Work</span>
        <span style={{color: '#fff'}}>Hive</span>
      </div>

      {/* Headline (the idea), left-weighted, clear of bottom-right UI PiP */}
      <div style={{position: 'absolute', left: 96, top: 250, maxWidth: 640}}>
        <div
          style={{
            color: '#fff',
            fontWeight: 800,
            fontSize: 62,
            lineHeight: 1.05,
            opacity: titleIn,
            transform: `translateY(${interpolate(titleIn, [0, 1], [26, 0])}px)`,
          }}
        >
          {headline}
        </div>
        <div
          style={{
            marginTop: 22,
            display: 'inline-block',
            padding: '8px 18px',
            borderRadius: 24,
            background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`,
            color: NAVY_DEEP,
            fontWeight: 700,
            fontSize: 22,
            opacity: subIn,
            transform: `translateY(${interpolate(subIn, [0, 1], [18, 0])}px)`,
          }}
        >
          {subhead}
        </div>
      </div>

      {/* Brand bar, bottom */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          bottom: 0,
          height: 8,
          width: '100%',
          background: `linear-gradient(90deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`,
          opacity: 0.9,
        }}
      />
    </AbsoluteFill>
  );
};
