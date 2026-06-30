import React from 'react';
import {Composition} from 'remotion';
import {WorkHiveOEEScene} from './WorkHiveScene';
import {WorkHiveBrandedBG} from './BrandedBG';
import {WorkHiveMotionBG} from './MotionBG';
import {WorkHiveKinetic} from './Kinetic';
import {WorkHiveInfographic} from './Infographic';
import {WorkHiveMindmap} from './Mindmap';
import {WorkHiveStoryboard, calculateStoryboardMetadata} from './Storyboard';
import {FlagshipReel, FLAGSHIP_DURATION} from './FlagshipReel';

// 1280x720 matches what video_assembler.py normalises the scene clip to,
// so this renders straight into the existing scene_clip slot with no rescale.
export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="WorkHiveOEEScene"
      component={WorkHiveOEEScene}
      durationInFrames={360}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        kpiLabel: 'OEE',
        kpiValue: 87,
        kpiUnit: '%',
        caption: 'See your whole plant. Live.',
        // A real maintenance trend — this is the part stock footage can never do.
        spark: [62, 65, 61, 70, 74, 72, 80, 78, 85, 83, 87],
      }}
    />
    <Composition
      id="WorkHiveBrandedBG"
      component={WorkHiveBrandedBG}
      durationInFrames={600}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        headline: 'See your whole plant. Live.',
        subhead: 'WorkHive',
      }}
    />
    <Composition
      id="WorkHiveMotionBG"
      component={WorkHiveMotionBG}
      durationInFrames={600}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        headline: 'See your whole plant. Live.',
        subhead: 'WorkHive',
      }}
    />
    <Composition
      id="WorkHiveKinetic"
      component={WorkHiveKinetic}
      durationInFrames={600}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        headline: 'See your whole plant. Live.',
        subhead: 'WorkHive',
        phrases: ['Too much to track.', 'Too little time.', 'See it all at a glance.', 'Run your plant with pride.'],
      }}
    />
    <Composition
      id="WorkHiveInfographic"
      component={WorkHiveInfographic}
      durationInFrames={600}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        headline: 'The numbers that matter',
        subhead: 'WorkHive',
        stats: [
          {value: '87%', label: 'OEE visibility', dir: 'up'},
          {value: '40%', label: 'Less downtime', dir: 'down'},
          {value: '100%', label: 'Free to start', dir: 'up'},
        ],
      }}
    />
    <Composition
      id="WorkHiveMindmap"
      component={WorkHiveMindmap}
      durationInFrames={600}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        headline: 'It all connects',
        subhead: 'WorkHive · Hive Dashboard',
        nodes: ['Logbook', 'PM Checklist', 'Inventory', 'Alerts'],
      }}
    />
    {/* The narration-driven sequence: many beats, many styles, one render.
        durationInFrames is computed from the segments (see calculateMetadata),
        so the pipeline sizes it to the exact narration length — no looping. */}
    <Composition
      id="WorkHiveStoryboard"
      component={WorkHiveStoryboard}
      fps={30}
      width={1280}
      height={720}
      calculateMetadata={calculateStoryboardMetadata}
      defaultProps={{
        segments: [
          {style: 'kinetic', frames: 90, headline: '3am. Another breakdown.', subhead: 'WorkHive · Logbook',
            phrases: ['3am. Another breakdown.', 'Nobody knows.', 'Again.']},
          {style: 'dashboard', frames: 120, headline: 'No records. No answers.', subhead: 'WorkHive · Logbook'},
          {style: 'infographic', frames: 120, headline: 'Simple. Fast. Accurate.', subhead: 'WorkHive · Logbook',
            stats: [{value: '100%', label: 'Captured', dir: 'up'}, {value: '24/7', label: 'Searchable', dir: 'flat'}]},
          {style: 'mindmap', frames: 120, headline: 'It all connects', subhead: 'WorkHive · Logbook',
            nodes: ['Logbook', 'AI Assistant', 'Handover', 'PM']},
        ],
      }}
    />
    {/* NEW (2026): vertical-first flagship spot — poster DNA, product-as-hero,
        spring motion, mute-first kinetic captions. Native 1080x1920. */}
    <Composition
      id="WorkHiveFlagship"
      component={FlagshipReel}
      durationInFrames={FLAGSHIP_DURATION}
      fps={30}
      width={1080}
      height={1920}
    />
    <Composition
      id="WorkHiveFlagshipSquare"
      component={FlagshipReel}
      durationInFrames={FLAGSHIP_DURATION}
      fps={30}
      width={1080}
      height={1080}
    />
    <Composition
      id="WorkHiveFlagshipWide"
      component={FlagshipReel}
      durationInFrames={FLAGSHIP_DURATION}
      fps={30}
      width={1920}
      height={1080}
    />
    </>
  );
};
