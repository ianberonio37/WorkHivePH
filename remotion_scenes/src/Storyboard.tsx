import React from 'react';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {WorkHiveMotionBG} from './MotionBG';
import {WorkHiveKinetic} from './Kinetic';
import {WorkHiveInfographic} from './Infographic';
import {WorkHiveMindmap} from './Mindmap';
import {WorkHiveEndCard} from './EndCard';

/**
 * One background beat: the style to play, how long, and the content for that
 * style. Produced by tools/storyboard.py (one entry per narration beat).
 */
export type Segment = {
  style: 'dashboard' | 'kinetic' | 'infographic' | 'mindmap';
  frames: number;
  headline: string;
  subhead: string;
  section?: string;
  phrases?: string[];
  stats?: {value: string; label: string; dir?: 'up' | 'down' | 'flat'}[];
  nodes?: string[];
};

type Props = {segments: Segment[]};

const MIN_FRAMES = 30;
// Cross-fade length between beats (~0.4s). Soft cuts read as deliberate edits
// instead of jarring jumps (the hard-cut-to-empty-scene flaw caught by frame
// inspection 2026-06-10). Official @remotion/transitions package.
const T_FRAMES = 12;

/** Caption-safe band: a soft scrim over the bottom ~150px so the burned
 *  captions always sit on a clean darkened zone, never fighting the artwork
 *  (the caption × metrics-strip collision from the 2026-06-10 frame critique). */
const CaptionScrim: React.FC = () => (
  <div
    style={{
      position: 'absolute', left: 0, right: 0, bottom: 0, height: 150,
      background: 'linear-gradient(180deg, rgba(14,23,38,0) 0%, rgba(14,23,38,0.72) 62%, rgba(14,23,38,0.9) 100%)',
      pointerEvents: 'none',
    }}
  />
);

/** Render the right style component for a segment (frame resets per Sequence,
 *  so each style's intro animation replays — that's the visible variety). */
const StyleScene: React.FC<{seg: Segment}> = ({seg}) => {
  // CTA beats always close on the branded end card (the Direct in ABCD),
  // regardless of which background style the rotation assigned.
  if (seg.section === 'cta') {
    return <WorkHiveEndCard headline={seg.headline} subhead={seg.subhead} />;
  }
  switch (seg.style) {
    case 'kinetic':
      return (
        <WorkHiveKinetic
          headline={seg.headline}
          subhead={seg.subhead}
          phrases={seg.phrases && seg.phrases.length ? seg.phrases : [seg.headline]}
        />
      );
    case 'infographic':
      return (
        <WorkHiveInfographic
          headline={seg.headline}
          subhead={seg.subhead}
          stats={seg.stats && seg.stats.length ? seg.stats : [{value: '100%', label: 'Free', dir: 'up'}]}
        />
      );
    case 'mindmap':
      return (
        <WorkHiveMindmap
          headline={seg.headline}
          subhead={seg.subhead}
          nodes={seg.nodes && seg.nodes.length ? seg.nodes : ['Logbook', 'PM', 'Inventory', 'Alerts']}
        />
      );
    case 'dashboard':
    default:
      return <WorkHiveMotionBG headline={seg.headline} subhead={seg.subhead} />;
  }
};

/**
 * WorkHiveStoryboard — sequences the per-beat styles with CROSS-FADES so the
 * background tracks the narration like an edited film, never a slideshow of
 * hard cuts. Transitions overlap both scenes, which would shorten the timeline
 * — so every non-final sequence is EXTENDED by the transition length and the
 * NET total still equals the sum of segment frames (= the narration length,
 * the pipeline's master clock).
 */
export const WorkHiveStoryboard: React.FC<Props> = ({segments}) => {
  const segs = segments && segments.length
    ? segments
    : [{style: 'dashboard', frames: 600, headline: 'WorkHive', subhead: 'WorkHive'} as Segment];

  const items: React.ReactNode[] = [];
  segs.forEach((seg, i) => {
    const base = Math.max(MIN_FRAMES, Math.round(seg.frames));
    const dur = i < segs.length - 1 ? base + T_FRAMES : base; // compensate the overlap
    items.push(
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={dur}>
        <StyleScene seg={seg} />
        <CaptionScrim />
      </TransitionSeries.Sequence>
    );
    if (i < segs.length - 1) {
      items.push(
        <TransitionSeries.Transition
          key={`t${i}`}
          presentation={fade()}
          timing={linearTiming({durationInFrames: T_FRAMES})}
        />
      );
    }
  });

  return <TransitionSeries>{items}</TransitionSeries>;
};

/** Composition duration = sum of all segment frames (transition overlaps are
 *  exactly compensated by the per-sequence extension above). */
export const calculateStoryboardMetadata = ({props}: {props: Props}) => {
  const segs = props.segments || [];
  const total = segs.reduce((a, s) => a + Math.max(MIN_FRAMES, Math.round(s.frames || 0)), 0);
  return {durationInFrames: Math.max(MIN_FRAMES, total || 600)};
};
