/**
 * plant-connections.html — UI smoke.
 * Phase 5 Track C of STRATEGIC_ROADMAP. Plant Connections Console.
 * Supervisor-only; non-supervisor sees the denied state. The smoke template
 * asserts no page errors regardless of the renderable branch.
 */
import { test, expect } from './_fixtures';
import { smokePage } from './_smoke-template';

test.describe('plant-connections.html smoke', () => {
  test('loads and renders without page errors', async ({ whPage }) => {
    await smokePage(whPage, '/workhive/plant-connections.html', { expectSourceChip: true });
  });
});
