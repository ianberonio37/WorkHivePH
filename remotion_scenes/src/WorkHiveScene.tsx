import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// ── WorkHive brand palette (from video_marketing_app/templates/index.html) ──────
const NAVY_DEEP = '#0E1726';
const NAVY = '#162032';
const ORANGE = '#F7A21B';
const ORANGE_LT = '#FDB94A';
const ORANGE_DK = '#D88A0E';
const FONT =
  '"Poppins", "Segoe UI", system-ui, -apple-system, sans-serif';

type Props = {
  kpiLabel: string;
  kpiValue: number;
  kpiUnit: string;
  caption: string;
  spark: number[];
};

/**
 * WorkHiveOEEScene — an on-brand, data-driven ambient background.
 *
 * Designed to sit BEHIND the UI screen-recording (which video_assembler.py
 * overlays at 38% in the bottom-right), so all the motion is weighted to the
 * left / centre and the bottom-right stays calm.
 *
 * Everything here is the opposite of generic stock footage: WorkHive navy +
 * orange, a real OEE number counting up, a live maintenance trend drawing in.
 */
export const WorkHiveOEEScene: React.FC<Props> = ({
  kpiLabel,
  kpiValue,
  kpiUnit,
  caption,
  spark,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps; // seconds, for smooth drift

  // ── Count-up + gauge fill ─────────────────────────────────────────────────
  const countUp = Math.round(
    interpolate(frame, [18, 78], [0, kpiValue], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    })
  );
  const gauge = spring({frame: frame - 18, fps, config: {damping: 200}});
  const ringPct = gauge * (kpiValue / 100);

  // ── Sparkline draw-on (normalised pathLength makes this resolution-free) ────
  const drawProgress = interpolate(frame, [34, 124], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // ── KPI panel entrance ────────────────────────────────────────────────────
  const panelIn = spring({frame: frame - 6, fps, config: {damping: 18, mass: 0.7}});
  const panelX = interpolate(panelIn, [0, 1], [-60, 0]);

  // ── Gauge geometry ────────────────────────────────────────────────────────
  const R = 92;
  const CIRC = 2 * Math.PI * R;

  // ── Sparkline geometry (drawn into a 360x120 box) ─────────────────────────
  const SW = 360;
  const SH = 120;
  const min = Math.min(...spark);
  const max = Math.max(...spark);
  const pts = spark
    .map((v, i) => {
      const x = (i / (spark.length - 1)) * SW;
      const y = SH - ((v - min) / (max - min || 1)) * SH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // ── Kinetic caption (word-by-word) ────────────────────────────────────────
  const words = caption.split(' ');

  return (
    <AbsoluteFill style={{backgroundColor: NAVY_DEEP, fontFamily: FONT}}>
      {/* Radial brand gradient base */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 28% 32%, #1d2c44 0%, ${NAVY} 42%, ${NAVY_DEEP} 100%)`,
        }}
      />

      {/* Drifting dot grid (slow parallax) */}
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${ORANGE}22 1.5px, transparent 1.6px)`,
          backgroundSize: '46px 46px',
          opacity: 0.5,
          transform: `translate(${(t * 6) % 46}px, ${(t * 4) % 46}px)`,
        }}
      />

      {/* Floating orange glow blobs — ambient motion, no hard loop seams */}
      {[0, 1, 2].map((i) => {
        const bx = width * (0.34 + i * 0.16) + Math.sin(t * 0.4 + i * 1.7) * 110;
        const by = height * (0.32 + i * 0.12) + Math.cos(t * 0.33 + i * 2.1) * 90;
        const size = 360 - i * 60;
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
              opacity: 0.16,
              filter: 'blur(28px)',
              // keep the bottom-right (UI overlay) calmer
              ...(i === 2 ? {opacity: 0.1} : {}),
            }}
          />
        );
      })}

      {/* ── KPI cluster (left) ─────────────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          left: 96,
          top: 150,
          transform: `translateX(${panelX}px)`,
          opacity: panelIn,
          display: 'flex',
          alignItems: 'center',
          gap: 36,
        }}
      >
        {/* Ring gauge */}
        <svg width={R * 2 + 24} height={R * 2 + 24}>
          <circle
            cx={R + 12}
            cy={R + 12}
            r={R}
            fill="none"
            stroke="#ffffff14"
            strokeWidth={14}
          />
          <circle
            cx={R + 12}
            cy={R + 12}
            r={R}
            fill="none"
            stroke={ORANGE}
            strokeWidth={14}
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC * (1 - ringPct)}
            transform={`rotate(-90 ${R + 12} ${R + 12})`}
          />
          <text
            x={R + 12}
            y={R + 12}
            textAnchor="middle"
            dominantBaseline="central"
            fill="#fff"
            style={{fontFamily: FONT, fontWeight: 800, fontSize: 54}}
          >
            {countUp}
            <tspan fill={ORANGE_LT} style={{fontSize: 30}}>
              {kpiUnit}
            </tspan>
          </text>
        </svg>

        {/* Label + sublabel */}
        <div>
          <div
            style={{
              color: ORANGE,
              fontWeight: 700,
              fontSize: 22,
              letterSpacing: 4,
            }}
          >
            {kpiLabel.toUpperCase()}
          </div>
          <div style={{color: '#fff', fontWeight: 800, fontSize: 40, marginTop: 4}}>
            Overall Equipment
          </div>
          <div style={{color: '#fff', fontWeight: 800, fontSize: 40, lineHeight: 1}}>
            Effectiveness
          </div>
          <div style={{color: '#9fb0c8', fontSize: 20, marginTop: 10}}>
            ↑ live across every shift
          </div>
        </div>
      </div>

      {/* ── Sparkline (mid-left) ───────────────────────────────────────────── */}
      <svg
        width={SW}
        height={SH}
        style={{position: 'absolute', left: 100, top: 420, overflow: 'visible'}}
      >
        <defs>
          <linearGradient id="sparkStroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={ORANGE_DK} />
            <stop offset="100%" stopColor={ORANGE_LT} />
          </linearGradient>
        </defs>
        <polyline
          points={pts}
          fill="none"
          stroke="url(#sparkStroke)"
          strokeWidth={5}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - drawProgress}
        />
      </svg>

      {/* ── Kinetic caption (bottom-left) ──────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          left: 100,
          bottom: 70,
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0 16px',
          maxWidth: 620,
        }}
      >
        {words.map((w, i) => {
          const wIn = spring({
            frame: frame - (60 + i * 7),
            fps,
            config: {damping: 16, mass: 0.6},
          });
          return (
            <span
              key={i}
              style={{
                color: '#fff',
                fontWeight: 800,
                fontSize: 46,
                opacity: wIn,
                transform: `translateY(${interpolate(wIn, [0, 1], [22, 0])}px)`,
                display: 'inline-block',
              }}
            >
              {w}
            </span>
          );
        })}
      </div>

      {/* Thin brand bar, bottom edge */}
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
