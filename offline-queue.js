// ─────────────────────────────────────────────────────────────────────────────
// offline-queue.js — Shared IndexedDB write queue (Phase 2.1 of STRATEGIC_ROADMAP)
//
// The Filipino industrial reality is brownouts, 2G cellular, intermittent
// Wi-Fi, and shared tablets. Any write that touches Supabase must survive
// a network blip: the worker must be able to save a logbook entry, an
// inventory transaction, a PM completion, an asset edit, or a defect
// photo draft while offline, and have it auto-drain when the connection
// returns. Without this, brownout writes are lost silently and the worker
// stops trusting the platform.
//
// Architecture:
//
//   const queue = whCreateQueue({
//     db: 'wh_pm_offline',          // IndexedDB database name (per concern)
//     store: 'pending',              // ObjectStore name (defaults to 'pending')
//     table: 'pm_completions',       // Supabase target table for drain
//     identityKey: 'worker_name',    // optional .eq() guard on drain
//     identityFn: () => WORKER_NAME, // identity resolver
//     onSyncedRow: (row) => {...},   // fire-and-forget hook per synced row
//     postSync: () => {...},         // post-drain hook (e.g. render refresh)
//   });
//
//   await queue.enqueue({ id, op: 'insert', payload: {...} });
//   await queue.enqueue({ id, op: 'update', match: { id, worker_name },
//                          payload: {...} });
//
//   queue.startAutoSync(supabaseClient);   // listens for online + initial drain
//   queue.getPending();                    // returns all pending rows
//   await queue.drain(supabaseClient);     // manual drain trigger
//
// The previous logbook-specific implementation in logbook.html stays in
// place; this helper is for NEW writer surfaces (inventory, pm-scheduler,
// asset edits, fmea, photo-defect drafts) so each one doesn't reinvent the
// wheel.
//
// Skills consulted:
//   devops (network resilience: never lose user writes, drain idempotently)
//   data-engineer (op-routing: insert vs update vs custom)
//   mobile-maestro (shared-tablet, brownout, 2G operating conditions)
//   security (per-identity enqueue + drain — one worker's queue cannot
//     surface another worker's pending writes)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window.whCreateQueue) return;

  function _openDB(dbName, storeName) {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(dbName, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(storeName)) {
          db.createObjectStore(storeName, { keyPath: 'id' });
        }
      };
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  function _idbReq(idb, storeName, mode, op) {
    return new Promise((resolve, reject) => {
      const tx = idb.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      const req = op(store);
      tx.oncomplete = () => resolve(req ? req.result : undefined);
      tx.onerror    = (e) => reject(e.target.error);
    });
  }

  // Cross-tab broadcast for queue-depth changes so the connectivity widget
  // updates without polling. Falls back silently when BroadcastChannel
  // isn't available (older browsers).
  function _broadcast(name) {
    try {
      if (typeof BroadcastChannel === 'undefined') return null;
      return new BroadcastChannel(name);
    } catch (_) { return null; }
  }

  function whCreateQueue(opts) {
    const cfg = Object.assign({
      db:           'wh_offline',
      store:        'pending',
      table:        null,
      identityKey:  null,
      identityFn:   null,
      onSyncedRow:  null,
      postSync:     null,
    }, opts || {});

    if (!cfg.table) throw new Error('whCreateQueue: opts.table is required');

    let _dbRef = null;
    let _draining = false;
    const channel = _broadcast('wh-offline-queue:' + cfg.db);

    // Arc S D-lens (D-002): retry/backoff/dead-letter so a failing item neither
    // wedges the queue nor retries forever. Exponential-ish backoff between attempts;
    // after MAX_RETRIES the item is flagged 'stalled' (kept for inspection, surfaced
    // as a warning by the connectivity widget, skipped by auto-drain).
    const MAX_RETRIES = 8;
    const BACKOFF_MS  = [1000, 5000, 30000, 120000, 600000, 3600000]; // 1s → 1h, then capped
    const _backoff = (rc) => BACKOFF_MS[Math.min(rc, BACKOFF_MS.length - 1)];
    const _due = (item) => {
      if (item.status === 'stalled') return false;            // dead-letter: no auto-retry
      if (!item.last_error_at) return true;                   // never attempted / last was clean
      return (Date.now() - item.last_error_at) >= _backoff(item.retry_count || 0);
    };

    async function _idb() {
      if (_dbRef) return _dbRef;
      _dbRef = await _openDB(cfg.db, cfg.store);
      return _dbRef;
    }

    async function enqueue(item) {
      if (!item || !item.id) throw new Error('enqueue: item.id required');
      const idb = await _idb();
      await _idbReq(idb, cfg.store, 'readwrite', (s) => s.put(item));
      try { channel && channel.postMessage({ type: 'enqueue' }); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } // empty-catch-allow: cross-tab broadcast best-effort
      return item;
    }

    async function getPending() {
      const idb = await _idb();
      return await _idbReq(idb, cfg.store, 'readonly', (s) => s.getAll());
    }

    async function remove(id) {
      const idb = await _idb();
      await _idbReq(idb, cfg.store, 'readwrite', (s) => s.delete(id));
      try { channel && channel.postMessage({ type: 'drain' }); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } // empty-catch-allow: cross-tab broadcast best-effort
    }

    async function clear() {
      const idb = await _idb();
      await _idbReq(idb, cfg.store, 'readwrite', (s) => s.clear());
      try { channel && channel.postMessage({ type: 'clear' }); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } // empty-catch-allow: cross-tab broadcast best-effort
    }

    async function drain(supabase) {
      if (_draining) return { drained: 0, errors: 0 };
      _draining = true;
      let drained = 0, errors = 0;
      try {
        const pending = await getPending();
        if (!pending.length) return { drained: 0, errors: 0 };
        const idb = await _idb();

        for (const item of pending) {
          if (!_due(item)) continue;   // Arc S D-002: stalled (dead-letter) or still in backoff
          const op = item.op || 'insert';
          let error = null;
          try {
            if (op === 'insert') {
              const r = await supabase.from(cfg.table).insert(item.payload);
              error = r.error;
            } else if (op === 'update') {
              let q = supabase.from(cfg.table).update(item.payload);
              const match = item.match || {};
              for (const [k, v] of Object.entries(match)) q = q.eq(k, v);
              if (cfg.identityKey && cfg.identityFn) {
                q = q.eq(cfg.identityKey, cfg.identityFn());
              }
              const r = await q;
              error = r.error;
            } else if (op === 'delete') {
              let q = supabase.from(cfg.table).delete();
              const match = item.match || {};
              for (const [k, v] of Object.entries(match)) q = q.eq(k, v);
              if (cfg.identityKey && cfg.identityFn) {
                q = q.eq(cfg.identityKey, cfg.identityFn());
              }
              const r = await q;
              error = r.error;
            } else {
              errors += 1; continue;
            }
          } catch (e) {
            error = e;
          }

          if (!error) {
            await remove(item.id);
            drained += 1;
            if (typeof cfg.onSyncedRow === 'function') {
              try { cfg.onSyncedRow(item); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } // empty-catch-allow: consumer hook isolation
            }
          } else {
            // Arc S D-002: record the failure with backoff + dead-letter so a
            // permanently-failing item doesn't wedge the queue or retry forever.
            const rc = (item.retry_count || 0) + 1;
            const upd = { ...item, retry_count: rc, last_error_at: Date.now(),
                          last_error: (error && error.message) ? String(error.message).slice(0, 200) : 'unknown' };
            if (rc >= MAX_RETRIES) upd.status = 'stalled';
            try { await _idbReq(idb, cfg.store, 'readwrite', (s) => s.put(upd)); }
            catch (_) { /* empty-catch-allow: best-effort persist of retry meta */ }
            errors += 1;
          }
        }
      } finally {
        _draining = false;
      }

      if (drained && typeof cfg.postSync === 'function') {
        try { await cfg.postSync({ drained, errors }); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } // empty-catch-allow: consumer hook isolation
      }
      return { drained, errors };
    }

    function startAutoSync(supabase, periodMs) {
      if (!supabase) return;
      const tick = () => {
        if (navigator.onLine) drain(supabase);
      };
      window.addEventListener('online', tick);
      // Initial drain on page load (covers the page-reload-after-brownout case)
      setTimeout(tick, 1500);
      // Arc S D-002: periodic retry so an item still in backoff — or a backend that
      // recovered while we never left 'online' — drains without needing an
      // offline→online flip. _due() gates per-item backoff so this isn't a hammer.
      const period = periodMs || 60000;
      // Lifetime auto-sync drain poll (Arc S D-002) — one per page, runs for the
      // page's entire life by design. Stored so it can be cleared on unload
      // (defence-in-depth against a leaked timer; the page usually unloads first).
      if (typeof setInterval === 'function') {
        const _syncTimer = setInterval(tick, period);
        if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
          window.addEventListener('beforeunload', () => clearInterval(_syncTimer));
        }
      }
    }

    return { enqueue, getPending, remove, clear, drain, startAutoSync, _cfg: cfg };
  }

  // ─── Aggregate queue depth across every registered queue ──────────────────
  // The connectivity widget reads this to render a single "5 pending across
  // 3 surfaces" badge. Queues opt-in by calling whRegisterQueue(name, q).
  const _registry = new Map();
  function whRegisterQueue(name, queue) {
    if (!name || !queue) return;
    _registry.set(name, queue);
  }
  async function whGetQueueDepth() {
    let total = 0, stalled = 0;
    const perSurface = {};
    for (const [name, q] of _registry.entries()) {
      try {
        const pending = await q.getPending();
        perSurface[name] = pending.length;
        total += pending.length;
        // Arc S D-002: surface dead-lettered items so the widget can warn "N stuck".
        stalled += pending.filter((it) => it && it.status === 'stalled').length;
      } catch (_) {
        perSurface[name] = -1;
      }
    }
    return { total, stalled, perSurface };
  }

  window.whCreateQueue     = whCreateQueue;
  window.whRegisterQueue   = whRegisterQueue;
  window.whGetQueueDepth   = whGetQueueDepth;
})();
