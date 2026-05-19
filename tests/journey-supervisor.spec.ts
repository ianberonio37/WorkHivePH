/**
 * Tier 3 — Supervisor flows (7 scenarios, P0)
 *
 * Privileged actions: approve, reject, kick, acknowledge alerts, shift
 * handover. All must include internal HIVE_ROLE guards (skill: security).
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 3 — Supervisor flows', () => {

  test('C1_approve_inventory_handler: hive.html exposes Approve for inventory_items', async () => {
    // WHY: status='approved' is the gate for worker visibility; supervisor handler is `approveItem`
    const html = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(html, 'hive.html must define approveItem handler').toMatch(/function\s+approveItem\s*\(/);
    expect(html, 'must call approveItem on inventory_items').toMatch(/approveItem\(['"]inventory_items['"]/);
    // The approve flow writes status='approved'.
    expect(html, "must flip status to 'approved'").toMatch(/status\s*:\s*['"]approved['"]/);
  });

  test('C2_approve_asset_handler: hive.html surfaces Approve for assets', async () => {
    // WHY: asset_nodes.status flips pending → approved; same handler covers it
    const html = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(html, 'hive.html must call approveItem on assets').toMatch(/approveItem\(['"]assets['"]/);
  });

  test('C3_pm_template_approval_role_check: pm-scheduler reads HIVE_ROLE/supervisor for privileged edits', async () => {
    // WHY: privileged template actions require supervisor; the role gate must be present
    const html = readFileSync(resolve(ROOT, 'pm-scheduler.html'), 'utf-8');
    // Either explicit HIVE_ROLE check OR an isSupervisor helper.
    const hasRoleCheck =
      /HIVE_ROLE\s*===?\s*['"]supervisor['"]/.test(html) ||
      /isSupervisor\s*\(/.test(html);
    expect(hasRoleCheck, 'pm-scheduler must gate privileged actions by supervisor role').toBeTruthy();
  });

  test('C4_kick_member_handler: hive.html flips hive_members to kicked + writes audit log', async () => {
    // WHY: status='kicked' removes worker access; audit-log records kick_member action
    const html = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(html, "kick path must update hive_members to status='kicked'").toMatch(
      /hive_members[\s\S]{0,300}\.update\s*\(\s*\{\s*status\s*:\s*['"]kicked['"]/
    );
    expect(html, 'kick action must be audit-logged').toMatch(/writeAuditLog\s*\(\s*['"]kick_member['"]/);
  });

  test('C5_hive_feed_realtime: hive.html subscribes to postgres_changes on logbook', async () => {
    // WHY: realtime is the platform's live-board UX (skill: realtime-engineer)
    // STATIC: hive.html must declare a postgres_changes subscription covering INSERT (+ UPDATE/DELETE)
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    // JS object literal keys are unquoted: { event: 'INSERT', ... }
    expect(hive, 'hive.html must subscribe to postgres_changes').toMatch(/postgres_changes/);
    expect(hive, 'must cover INSERT event').toMatch(/event\s*:\s*['"]INSERT['"]/);
    expect(hive, 'must filter by hive_id').toMatch(/filter\s*:\s*['"]hive_id=eq\./);
    // DELETE handler must also exist (security skill: missing-realtime-DELETE-handler rule).
    expect(hive, 'must cover DELETE event (or deleted rows persist in UI)').toMatch(/event\s*:\s*['"]DELETE['"]/);
  });

  test('C6_acknowledge_amc_alert_handler: alert-hub flips status to acknowledged with metadata', async () => {
    // WHY: ack flips status open → acknowledged + stamps acknowledged_by/acknowledged_at
    const html = readFileSync(resolve(ROOT, 'alert-hub.html'), 'utf-8');
    expect(html, 'ack updates must set acknowledged_by + acknowledged_at + status').toMatch(
      /status\s*:\s*['"]acknowledged['"][\s\S]{0,200}acknowledged_by/
    );
    expect(html, 'ack must record acknowledged_at timestamp').toMatch(/acknowledged_at/);
    // UI button present
    expect(html, 'must surface Acknowledge button').toMatch(/data-action="acknowledge"|>Acknowledge</);
  });

  test('C7_shift_brain_orchestrator: shift-brain invokes shift-planner-orchestrator', async () => {
    // WHY: shift-planner-orchestrator is the canonical handover-plan generator
    const html = readFileSync(resolve(ROOT, 'shift-brain.html'), 'utf-8');
    expect(html, 'shift-brain must invoke shift-planner-orchestrator').toMatch(
      /invoke\s*\(\s*['"]shift-planner-orchestrator['"]/
    );
    // Plan reads from shift_plans-style structure (generated_at, briefing, payload)
    expect(html, 'must surface shift plan briefing field').toMatch(/briefing/);
  });
});
