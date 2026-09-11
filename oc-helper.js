// oc-helper.js — optimistic-concurrency helpers for Supabase updates.
//
// Closes PRODUCTION_FIXES #43 by providing the canonical OC pattern as
// a single helper. Pages adopt incrementally on save flows where two
// workers could plausibly edit the same row (logbook notes,
// inventory_items qty_on_hand, marketplace_listings).
//
// Usage:
//   const { error, conflict } = await updateWithOC(db, 'logbook', row.id, {
//     notes: newNotes,
//   }, row.updated_at);
//   if (conflict) {
//     showToast('Row was modified by someone else. Refresh and try again.');
//     return;
//   }
//   if (error) showToast('Save failed: ' + error.message);

(function () {
  'use strict';
  if (typeof window === 'undefined') return;

  /**
   * Optimistic update: include the row's last-known `updated_at` in the
   * filter. If the row was modified between read + write, no rows are
   * updated and we report a conflict.
   *
   * @param {SupabaseClient} db
   * @param {string} table
   * @param {string|number} id
   * @param {Record<string, unknown>} patch  fields to update
   * @param {string} expectedStamp  ISO timestamp of last-known updated_at
   * @returns {Promise<{ error, conflict, data }>}
   */
  /* W3-LC (2026-09-09): `filters` was added because its absence is the most likely reason this helper
     sat unused. FOUR pages loaded oc-helper.js and NONE ever called updateWithOC - 22 unguarded write
     sites - and the reason is visible the moment you try to adopt it: every real update on this
     platform is scoped by TENANCY as well as id. inventory.html's edit path is
     `.update(patch).eq('id', editingItemId).eq('worker_name', role === 'supervisor' ? prev.worker_name
     : WORKER_NAME)` - a filter that deliberately varies by role. Swapping that for the old id-only
     helper would have silently widened which rows the update could touch, so the safe move was to not
     adopt it at all, and that is what four pages did. A shared helper that cannot express the shape its
     callers actually use will be included and ignored; extending it is what makes adoption possible
     without trading a concurrency bug for an authorization one. Optional and last, so every existing
     call keeps its behaviour exactly. */
  window.updateWithOC = async function (db, table, id, patch, expectedStamp, filters) {
    if (!db || !table || !id) {
      return { error: new Error('updateWithOC: missing db/table/id'), conflict: false, data: null };
    }
    const q = db.from(table)
      .update(patch)
      .eq('id', id);
    if (filters && typeof filters === 'object') {
      for (const [col, val] of Object.entries(filters)) {
        if (val !== undefined && val !== null) q.eq(col, val);
      }
    }
    if (expectedStamp) q.eq('updated_at', expectedStamp);
    q.select();
    const { data, error } = await q;
    if (error) return { error, conflict: false, data: null };
    if (!data || data.length === 0) {
      // No row matched -- either id is bad OR updated_at didn't match
      return { error: null, conflict: true, data: null };
    }
    return { error: null, conflict: false, data: data[0] };
  };

  /**
   * Read-then-update with built-in OC. Snapshots the row's updated_at
   * before calling the mutator, then writes the patch with the guard.
   * Convenient for save handlers that don't already have the stamp.
   */
  window.readAndUpdateWithOC = async function (db, table, id, patchFn) {
    const { data: row, error: readErr } = await db.from(table)
      .select('id, updated_at').eq('id', id).maybeSingle();
    if (readErr || !row) {
      return { error: readErr || new Error('Row not found'), conflict: false, data: null };
    }
    const patch = await patchFn(row);
    return window.updateWithOC(db, table, id, patch, row.updated_at);
  };
})();
