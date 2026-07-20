/* Honeycomb lattice generator. Any element with class "hivebg" gets a subtle
   flat-top hexagon grid. Options via data-attrs:
     data-hex="46"     hex radius (center->vertex)
     data-op="0.12"    stroke opacity
   Accent hexes are added per-poster as explicit markup (see posters). */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  function pts(cx, cy, R) {
    let a = [];
    for (let i = 0; i < 6; i++) {
      const t = Math.PI / 180 * (60 * i);
      a.push((cx + R * Math.cos(t)).toFixed(1) + ',' + (cy + R * Math.sin(t)).toFixed(1));
    }
    return a.join(' ');
  }
  function build(el) {
    const R = parseFloat(el.dataset.hex || 46);
    const op = el.dataset.op || 0.12;
    const W = el.clientWidth || 1600, H = el.clientHeight || 900;
    const dx = 1.5 * R, dy = Math.sqrt(3) * R;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W); svg.setAttribute('height', H);
    let col = 0;
    for (let x = -R; x < W + R; x += dx) {
      const yoff = (col % 2) ? dy / 2 : 0;
      for (let y = -R + yoff; y < H + R; y += dy) {
        const poly = document.createElementNS(NS, 'polygon');
        poly.setAttribute('points', pts(x, y, R));
        poly.setAttribute('fill', 'none');
        poly.setAttribute('stroke', `rgba(150,185,225,${op})`);
        poly.setAttribute('stroke-width', '1.3');
        svg.appendChild(poly);
      }
      col++;
    }
    el.insertBefore(svg, el.firstChild);
  }
  function run() { document.querySelectorAll('.hivebg').forEach(build); }
  if (document.readyState !== 'loading') run();
  else document.addEventListener('DOMContentLoaded', run);
})();
