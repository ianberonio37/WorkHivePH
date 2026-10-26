/* wh-map.js — the platform's ONE map module (SERVICE_HAILING_ROADMAP.md P5 / C10 / G2).
 *
 * Vendored MapLibre GL (maplibre-gl.js + maplibre-gl.css, BSD-3) + OpenFreeMap vector
 * styles (public instance, no usage limits, no API key — D12; the OSMF raster endpoint
 * is best-effort/revocable for commercial use, and OpenFreeMap serves VECTOR tiles,
 * which is why the lib is MapLibre and not Leaflet). Prod CSP needs
 * connect-src https://tiles.openfreemap.org + worker-src blob: (edge-gated, D12).
 *
 * Pages load: <link rel="stylesheet" href="maplibre-gl.css">
 *             <script src="maplibre-gl.js"></script><script src="wh-map.js"></script>
 * Everything degrades honestly: if maplibregl is absent (offline PWA without the cached
 * lib), whMap.available() is false and callers show their text fallback instead.
 */
(function () {
  'use strict';

  var STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';

  function available() { return typeof window.maplibregl !== 'undefined'; }

  /* OWN dependency lens (2026-10-26): when the tile service was slow, rate-limited or answered a style the library
     could not read, MapLibre drew a blank grey box and said nothing - to the person pinning a job site and to the
     founder alike. The map now says what happened inside its own frame (the rest of the page still works) and logs
     the failure as dependency:tiles.openfreemap.org:<kind>, which the operator console groups. */
  var HOST = 'tiles.openfreemap.org';

  function say(map, text) {
    var box = map.getContainer();
    var note = box.querySelector('.wh-map-note');
    if (!text) { if (note) note.remove(); return; }
    if (!note) {
      note = document.createElement('p');
      note.className = 'wh-map-note';
      note.setAttribute('role', 'status');
      note.style.cssText = 'position:absolute;left:8px;right:8px;bottom:8px;margin:0;z-index:2;padding:8px 10px;border-radius:8px;'
        + 'background:rgba(15,23,42,0.88);color:#f8fafc;font-size:13px;line-height:1.4;';
      box.appendChild(note);
    }
    note.textContent = text;
  }

  function kindOf(err) {
    var status = err && (err.status || (err.error && err.error.status));
    var msg = String((err && (err.message || (err.error && err.error.message))) || '');
    if (status === 429 || /\b429\b|too many/i.test(msg)) return 'quota or 429';
    if (status >= 500 || status === 0 || /failed to fetch|network/i.test(msg)) return 'down';
    if (status >= 400) return 'changed API';
    return /unexpected|invalid|parse|expected|validat/i.test(msg) ? 'changed API' : 'down';
  }

  function logged(kind, detail) {
    if (typeof window.whDependency === 'function') {
      window.whDependency(HOST, kind, String(detail).slice(0, 200));
    } else if (typeof window.whLogError === 'function') {
      window.whLogError('dependency:' + HOST + ':' + kind, new Error(String(detail).slice(0, 200)));
    }
  }

  /* Create a map in `container` (id or element). PH-centric default view. */
  function create(container, opts) {
    if (!available()) return null;
    opts = opts || {};
    var map = new window.maplibregl.Map({
      container: container,
      style: opts.style || STYLE_URL,
      center: opts.center || [121.0, 14.6], // [lng, lat] — Metro Manila default
      zoom: (opts.zoom != null) ? opts.zoom : 11,
      attributionControl: { compact: true }
    });
    map.addControl(new window.maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    var t0 = Date.now(), failed = false;
    var slow = setTimeout(function () {
      if (!map.loaded() && !failed) say(map, 'The map is taking longer than usual to load. The rest of this page works without it.');
    }, 8000);
    map.on('load', function () {
      clearTimeout(slow);
      if (!failed) say(map, '');
      var secs = Math.round((Date.now() - t0) / 1000);
      if (secs > 10) logged('slow', 'map style and first tiles took ' + secs + ' s');
    });
    map.on('error', function (e) {
      if (failed) return;   // one sentence and one record per map, not one per tile
      var err = (e && e.error) || e;
      var kind = kindOf(err);
      failed = true;
      clearTimeout(slow);
      say(map, opts.failText || 'The map could not load right now, so it may be blank or incomplete. Everything else on this page still works.');
      var detail = (e && e.sourceId ? e.sourceId + ': ' : '') + String((err && (err.message || err.status)) || 'map error');
      // a device that cannot draw (no WebGL) is not the tile service failing: the same sentence, a different record
      if (/webgl/i.test(detail)) { if (typeof window.whLogError === 'function') window.whLogError('map-webgl', new Error(detail.slice(0, 200))); return; }
      logged(kind, detail);
    });
    return map;
  }

  /* A colored dot marker. kind: 'provider' (orange) | 'site' (blue). */
  function marker(map, lngLat, kind, label) {
    if (!available() || !map || !lngLat) return null;
    var el = document.createElement('div');
    el.style.cssText = 'width:16px;height:16px;border-radius:999px;border:2.5px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.45);'
      + (kind === 'provider' ? 'background:#F7A21B;' : 'background:#29B6D9;');
    if (label) { el.setAttribute('role', 'img'); el.setAttribute('aria-label', label); }
    return new window.maplibregl.Marker({ element: el }).setLngLat(lngLat).addTo(map);
  }

  /* Move a marker + glide the camera to keep both points in view. */
  function follow(map, mk, lngLat, otherLngLat) {
    if (!available() || !map || !mk || !lngLat) return;
    mk.setLngLat(lngLat);
    if (otherLngLat) {
      var b = new window.maplibregl.LngLatBounds(lngLat, lngLat);
      b.extend(otherLngLat);
      map.fitBounds(b, { padding: 56, maxZoom: 15, duration: 900 });
    } else {
      map.easeTo({ center: lngLat, duration: 900 });
    }
  }

  window.whMap = { available: available, create: create, marker: marker, follow: follow, STYLE_URL: STYLE_URL };
})();
