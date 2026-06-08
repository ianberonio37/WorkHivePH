/* ─────────────────────────────────────────────────────────────────────────
 * asset-qr.js — WorkHive asset QR TAG GENERATOR (the other half of the scan loop)
 *
 * qr-scanner.js lets a worker SCAN an equipment tag to find an asset. This is
 * the missing counterpart: it GENERATES a printable QR tag for an asset so the
 * tag physically exists to be scanned later. The QR encodes the asset TAG code
 * (e.g. "M-001") — the exact value the logbook scan handler matches against
 * (asset.asset_id), so generate -> print -> stick -> scan -> select is a closed
 * round-trip.
 *
 * Usage:
 *   await WHAssetQR.printTag('M-001', 'Siemens Simotics SD 200L', 'Pump Pit 1');
 *   const svg = await WHAssetQR.tagSvg('M-001');           // raw QR SVG string
 *   await WHAssetQR.render(containerEl, 'M-001');           // inject QR into a node
 *
 * The QR encoder (qrcode-generator, MIT) is lazy-loaded from jsdelivr (same CDN
 * the platform already trusts for supabase) on first use — zero cost until used.
 * ───────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';
  if (window.WHAssetQR) return;

  var LIB_URL = 'https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js';
  var _libPromise = null;

  function loadLib() {
    if (window.qrcode) return Promise.resolve(window.qrcode);
    if (_libPromise) return _libPromise;
    _libPromise = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = LIB_URL;
      s.onload = function () {
        if (typeof window.qrcode === 'function') resolve(window.qrcode);
        else reject(new Error('qrcode global missing after load'));
      };
      s.onerror = function () { reject(new Error('QR library failed to load (offline / CSP)')); };
      document.head.appendChild(s);
    });
    return _libPromise;
  }

  // Build the QR matrix and return an SVG string (crisp at any print size).
  function buildSvg(text, opts) {
    opts = opts || {};
    var px = opts.size || 220;       // target pixel size
    var margin = opts.margin == null ? 4 : opts.margin; // quiet-zone modules
    var qr = window.qrcode(0, opts.ecl || 'M');         // type 0 = auto-fit
    qr.addData(String(text));
    qr.make();
    var count = qr.getModuleCount();
    var total = count + margin * 2;
    var cell = px / total;
    var rects = '';
    for (var r = 0; r < count; r++) {
      for (var c = 0; c < count; c++) {
        if (qr.isDark(r, c)) {
          var x = (c + margin) * cell;
          var y = (r + margin) * cell;
          rects += '<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) +
            '" width="' + cell.toFixed(2) + '" height="' + cell.toFixed(2) + '"/>';
        }
      }
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + px + '" height="' + px +
      '" viewBox="0 0 ' + px + ' ' + px + '" shape-rendering="crispEdges" role="img" ' +
      'aria-label="QR code for ' + String(text).replace(/"/g, '') + '">' +
      '<rect width="100%" height="100%" fill="#fff"/><g fill="#000">' + rects + '</g></svg>';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  window.WHAssetQR = {
    /** Raw QR SVG string encoding `text` (the asset tag). */
    tagSvg: function (text, opts) { return loadLib().then(function () { return buildSvg(text, opts); }); },

    /** Inject a QR for `text` into `container`. */
    render: function (container, text, opts) {
      return loadLib().then(function () {
        if (container) container.innerHTML = buildSvg(text, opts);
        return container;
      });
    },

    /** Open a print window with a clean, stick-on QR tag for the asset. The QR
     *  encodes the TAG code so the in-app scanner resolves it back to the asset. */
    printTag: function (tag, name, location) {
      return loadLib().then(function () {
        var svg = buildSvg(tag, { size: 300, ecl: 'M' });
        var win = window.open('', '_blank', 'width=420,height=560');
        if (!win) throw new Error('Popup blocked — allow popups to print the tag.');
        win.document.write(
          '<!DOCTYPE html><html><head><meta charset="utf-8"><title>QR Tag ' + esc(tag) + '</title>' +
          '<style>@page{margin:8mm}body{font-family:-apple-system,Segoe UI,sans-serif;color:#111;' +
          'text-align:center;padding:10px;margin:0}.tag{border:2px solid #111;border-radius:10px;' +
          'padding:16px;display:inline-block;max-width:340px}.code{font-size:26px;font-weight:800;' +
          'letter-spacing:1px;margin:10px 0 2px}.name{font-size:13px;color:#333}.loc{font-size:11px;' +
          'color:#666;margin-top:2px}.qr{margin:6px auto}.brand{font-size:9px;color:#999;margin-top:8px;' +
          'text-transform:uppercase;letter-spacing:1px}</style></head><body><div class="tag">' +
          '<div class="qr">' + svg + '</div>' +
          '<div class="code">' + esc(tag) + '</div>' +
          (name ? '<div class="name">' + esc(name) + '</div>' : '') +
          (location ? '<div class="loc">' + esc(location) + '</div>' : '') +
          '<div class="brand">WorkHive asset tag</div></div>' +
          '<script>window.onload=function(){window.print();setTimeout(function(){window.close()},400)}<\/script>' +
          '</body></html>');
        win.document.close();
        return true;
      });
    },
  };
})();
