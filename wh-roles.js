/**
 * wh-roles.js — canonical CLIENT-side RBAC SSOT (PLATFORM_CENTRALIZATION_ROADMAP · +RBAC surface).
 * ─────────────────────────────────────────────────────────────────────────────
 * The role→capability truth was DRIFTED: `localStorage.getItem('wh_hive_role')` +
 * raw `role`-string equality checks were hand-repeated across pages (isSupervisor computed 25×,
 * the raw supervisor check 13×, 125 raw 'supervisor' literals), so a role-gating decision
 * lived in dozens of places instead of one. This is the ONE canonical reader + capability map.
 *
 * SECURITY NOTE (honoured): this is a CLIENT-side UX gate only — it decides what a worker
 * SEES, never what they may DO. Every privileged action is independently enforced server-side
 * by RLS + edge-fn entitlement checks (Layer D/AU). A client role hint is advisory; the
 * database is the authority. So a wrong/absent role here degrades to "shows less", never to
 * "does more than allowed".
 *
 * Loaded early by nav-hub.js so window.WHRoles is present platform-wide. Defensive throughout.
 */
(function () {
  'use strict';
  if (typeof window === 'undefined' || window.WHRoles) return;

  // The role vocabulary (mirrors nav-hub.js MODES + wh_hive_role writes).
  // 'all' is the permissive default when no role hint is stored (solo mode / new install).
  var ROLES = ['field', 'supervisor', 'engineer'];

  // Role → capability matrix, MIRRORING nav-hub.js TOOLS `roles` arrays (the existing
  // source of role→tool visibility) so the two never diverge. A capability with roles:'*'
  // is universal. Extend here — never re-hardcode a a raw role-string comparison on a page.
  var CAPABILITIES = {
    // field work
    logbook:            ['field', 'supervisor'],
    inventory:          ['field', 'supervisor'],
    day_planner:        ['field', 'supervisor'],
    pm_scheduler:       ['field', 'supervisor'],
    // team / supervisor
    manage_hive:        ['supervisor'],
    approve:            ['supervisor'],   // approve writes (logbook/inventory/FMEA/CO sign-offs)
    reset_password:     ['supervisor'],
    analytics:          ['supervisor', 'engineer'],
    reports:            ['supervisor', 'engineer'],
    alert_hub:          ['supervisor'],
    audit_log:          ['supervisor'],
    ai_quality:         ['supervisor'],
    asset_hub:          ['supervisor', 'engineer'],
    // engineering
    engineering_design: ['engineer'],
    project_manager:    ['supervisor', 'engineer'],
    connections:        ['supervisor'],
  };

  function whRole() {
    try {
      // storage-key-allow: wh_hive_role is the canonical role key (storage_key_registry.json)
      var r = (localStorage.getItem('wh_hive_role') || '').toLowerCase().trim();
      return ROLES.indexOf(r) !== -1 ? r : '';
    } catch (_) { return ''; }
  }

  // Direct role checks — the canonical replacements for the scattered a raw role-string comparison.
  function whIsSupervisor() { return whRole() === 'supervisor'; }
  function whIsEngineer()   { return whRole() === 'engineer'; }
  function whIsField()      { return whRole() === 'field'; }

  // Capability check — the preferred gate: whCan('approve') instead of a raw role-string check.
  // Fails OPEN to false only when a role IS stored and lacks the capability; an EMPTY role
  // (solo/new — the nav-hub 'all' default) is treated as permissive so a lone tech isn't locked out.
  function whCan(cap) {
    var role = whRole();
    if (!role) return true;                 // no role hint = solo/all mode = permissive UX
    var allowed = CAPABILITIES[cap];
    if (!allowed) return true;              // unknown capability = don't hide (fail-open UX)
    return allowed === '*' || allowed.indexOf(role) !== -1;
  }

  window.WHRoles = {
    role: whRole,
    isSupervisor: whIsSupervisor,
    isEngineer: whIsEngineer,
    isField: whIsField,
    can: whCan,
    CAPABILITIES: CAPABILITIES,
    ROLES: ROLES,
  };
})();
