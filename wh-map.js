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
