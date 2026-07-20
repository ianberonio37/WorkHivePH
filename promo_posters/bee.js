/* WorkHive futuristic bee mascot — shared SVG symbol library.
   Injects a hidden <svg> with gradient/filter defs + <symbol> mascots.
   Posters use:  <svg class="bee"><use href="#bee-mascot"/></svg>
   Colours: Amber #F5A623 · Cyan #29B6F6 · Navy #0D1928  (WorkHive brand v1.0) */
(function () {
  const LIB = `
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"  stop-color="#FFD57E"/>
      <stop offset=".45" stop-color="#F7A825"/>
      <stop offset="1"  stop-color="#D8800E"/>
    </linearGradient>
    <linearGradient id="headGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"  stop-color="#FFD98C"/>
      <stop offset=".55" stop-color="#F8AB2A"/>
      <stop offset="1"  stop-color="#E58C12"/>
    </linearGradient>
    <linearGradient id="armGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#F9B53D"/>
      <stop offset="1" stop-color="#E08A12"/>
    </linearGradient>
    <radialGradient id="wingGrad" cx=".3" cy=".3" r=".9">
      <stop offset="0"  stop-color="#EAFBFF" stop-opacity=".95"/>
      <stop offset=".55" stop-color="#7FD9F7" stop-opacity=".55"/>
      <stop offset="1"  stop-color="#29B6F6" stop-opacity=".18"/>
    </radialGradient>
    <linearGradient id="helmetGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF"/>
      <stop offset="1" stop-color="#D2DEE8"/>
    </linearGradient>
    <radialGradient id="beeAura" cx=".5" cy=".5" r=".5">
      <stop offset="0"  stop-color="#F7A825" stop-opacity=".55"/>
      <stop offset=".55" stop-color="#F7A825" stop-opacity=".12"/>
      <stop offset="1"  stop-color="#F7A825" stop-opacity="0"/>
    </radialGradient>
    <filter id="beeGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDev="2.4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="14" stdDev="14" flood-color="#04070d" flood-opacity=".45"/>
    </filter>
    <pattern id="wingCells" width="16" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(6)">
      <polygon points="8,1 15,4.5 15,9.5 8,13 1,9.5 1,4.5" fill="none" stroke="#BEEDFF" stroke-width="1" stroke-opacity=".5"/>
    </pattern>
    <!-- volumetric depth: sphere form-shadow + gloss highlight (light from top-left) -->
    <radialGradient id="sphereShade" cx=".36" cy=".28" r=".78">
      <stop offset="0"  stop-color="#5a3402" stop-opacity="0"/>
      <stop offset=".58" stop-color="#5a3402" stop-opacity="0"/>
      <stop offset=".82" stop-color="#7a4a08" stop-opacity=".22"/>
      <stop offset="1"  stop-color="#3a2200" stop-opacity=".5"/>
    </radialGradient>
    <radialGradient id="glossGrad" cx=".32" cy=".24" r=".5">
      <stop offset="0"  stop-color="#FFFFFF" stop-opacity=".6"/>
      <stop offset=".55" stop-color="#FFFFFF" stop-opacity=".08"/>
      <stop offset="1"  stop-color="#FFFFFF" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="rimLight" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="#FFE39A" stop-opacity=".9"/>
      <stop offset="1" stop-color="#FFE39A" stop-opacity="0"/>
    </linearGradient>
    <filter id="beeDrop" x="-40%" y="-45%" width="180%" height="190%">
      <feDropShadow dx="0" dy="4"  stdDev="5"  flood-color="#05070c" flood-opacity=".35"/>
      <feDropShadow dx="0" dy="18" stdDev="22" flood-color="#05070c" flood-opacity=".5"/>
    </filter>
    <filter id="contactBlur" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDev="10"/>
    </filter>

    <!-- ===================== FULL MASCOT ===================== -->
    <symbol id="bee-mascot" viewBox="0 0 300 340">
      <!-- ambient contact shadow (grounds the float) -->
      <ellipse cx="150" cy="316" rx="86" ry="20" fill="#04070d" opacity=".34" filter="url(#contactBlur)"/>
      <!-- WINGS (behind) -->
      <g filter="url(#beeGlow)" opacity=".92">
        <g transform="rotate(-30 108 128)">
          <ellipse cx="108" cy="128" rx="64" ry="30" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.6" stroke-opacity=".8"/>
          <ellipse cx="108" cy="128" rx="64" ry="30" fill="url(#wingCells)"/>
        </g>
        <g transform="rotate(-16 96 172)">
          <ellipse cx="96" cy="172" rx="46" ry="22" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.4" stroke-opacity=".7"/>
          <ellipse cx="96" cy="172" rx="46" ry="22" fill="url(#wingCells)"/>
        </g>
        <g transform="rotate(30 192 128)">
          <ellipse cx="192" cy="128" rx="64" ry="30" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.6" stroke-opacity=".8"/>
          <ellipse cx="192" cy="128" rx="64" ry="30" fill="url(#wingCells)"/>
        </g>
        <g transform="rotate(16 204 172)">
          <ellipse cx="204" cy="172" rx="46" ry="22" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.4" stroke-opacity=".7"/>
          <ellipse cx="204" cy="172" rx="46" ry="22" fill="url(#wingCells)"/>
        </g>
      </g>

      <!-- LEGS -->
      <g stroke="#241a0c" stroke-width="7" stroke-linecap="round" opacity=".9">
        <path d="M132 288 L124 312" /><path d="M150 292 L150 316" /><path d="M168 288 L176 312" />
      </g>

      <!-- BODY -->
      <g filter="url(#beeDrop)">
        <!-- thorax -->
        <ellipse cx="150" cy="168" rx="44" ry="40" fill="url(#bodyGrad)"/>
        <!-- abdomen -->
        <ellipse cx="150" cy="236" rx="58" ry="64" fill="url(#bodyGrad)"/>
      </g>
      <clipPath id="abdClip"><ellipse cx="150" cy="236" rx="58" ry="64"/></clipPath>
      <g clip-path="url(#abdClip)">
        <rect x="88" y="206" width="124" height="24" rx="12" fill="#101a2b"/>
        <rect x="88" y="254" width="124" height="22" rx="11" fill="#101a2b"/>
        <!-- volumetric form shadow + gloss on the abdomen sphere -->
        <ellipse cx="150" cy="236" rx="58" ry="64" fill="url(#sphereShade)"/>
        <ellipse cx="126" cy="198" rx="22" ry="13" fill="url(#glossGrad)"/>
        <path d="M196 268 Q205 240 190 208" fill="none" stroke="url(#rimLight)" stroke-width="4" stroke-linecap="round" opacity=".7"/>
      </g>
      <ellipse cx="150" cy="168" rx="44" ry="40" fill="url(#sphereShade)"/>
      <!-- stinger -->
      <path d="M139 294 L161 294 L150 314 Z" fill="#101a2b"/>

      <!-- ARMS -->
      <!-- left arm relaxed -->
      <path d="M112 182 Q92 206 84 230" fill="none" stroke="url(#armGrad)" stroke-width="19" stroke-linecap="round"/>
      <circle cx="82" cy="234" r="13" fill="#FFCf6E" stroke="#E08A12" stroke-width="2"/>
      <!-- right arm waving -->
      <path d="M190 176 Q224 150 232 108" fill="none" stroke="url(#armGrad)" stroke-width="19" stroke-linecap="round"/>
      <g transform="translate(232 100) rotate(14)">
        <ellipse cx="0" cy="2" rx="15" ry="16" fill="#FFCf6E" stroke="#E08A12" stroke-width="2"/>
        <circle cx="-9" cy="-11" r="5" fill="#FFCf6E" stroke="#E08A12" stroke-width="1.6"/>
        <circle cx="-1" cy="-14" r="5.4" fill="#FFCf6E" stroke="#E08A12" stroke-width="1.6"/>
        <circle cx="7.5" cy="-12" r="5" fill="#FFCf6E" stroke="#E08A12" stroke-width="1.6"/>
        <circle cx="14" cy="-4" r="4.4" fill="#FFCf6E" stroke="#E08A12" stroke-width="1.6"/>
      </g>

      <!-- HEAD -->
      <circle cx="150" cy="110" r="58" fill="url(#headGrad)" filter="url(#beeDrop)"/>
      <circle cx="150" cy="110" r="58" fill="url(#sphereShade)"/>
      <ellipse cx="130" cy="90" rx="26" ry="18" fill="url(#glossGrad)"/>
      <path d="M198 128 Q206 108 196 88" fill="none" stroke="url(#rimLight)" stroke-width="3.5" stroke-linecap="round" opacity=".65"/>
      <!-- cheeks -->
      <ellipse cx="116" cy="126" rx="12" ry="8" fill="#FF7A2E" opacity=".32"/>
      <ellipse cx="184" cy="126" rx="12" ry="8" fill="#FF7A2E" opacity=".32"/>
      <!-- eyes -->
      <g>
        <ellipse cx="131" cy="108" rx="16" ry="19" fill="#FFFFFF"/>
        <ellipse cx="169" cy="108" rx="16" ry="19" fill="#FFFFFF"/>
        <circle cx="134" cy="112" r="9" fill="#101a2b"/>
        <circle cx="166" cy="112" r="9" fill="#101a2b"/>
        <circle cx="130.5" cy="108" r="3.2" fill="#FFFFFF"/>
        <circle cx="162.5" cy="108" r="3.2" fill="#FFFFFF"/>
        <ellipse cx="131" cy="108" rx="16" ry="19" fill="none" stroke="#29B6F6" stroke-width="1.5" stroke-opacity=".65"/>
        <ellipse cx="169" cy="108" rx="16" ry="19" fill="none" stroke="#29B6F6" stroke-width="1.5" stroke-opacity=".65"/>
      </g>
      <!-- smile -->
      <path d="M134 140 Q150 154 166 140" fill="none" stroke="#101a2b" stroke-width="4.5" stroke-linecap="round"/>

      <!-- SMART HELMET -->
      <ellipse cx="150" cy="94" rx="66" ry="13" fill="#C7D4DE"/>
      <path d="M92 96 Q96 50 150 48 Q204 50 208 96 Z" fill="url(#helmetGrad)" stroke="#B9C7D2" stroke-width="1.5"/>
      <path d="M150 49 Q150 72 150 95" stroke="#C9D4DD" stroke-width="3" fill="none" opacity=".8"/>
      <path d="M120 52 Q116 74 114 94" stroke="#D6E0E8" stroke-width="2.5" fill="none" opacity=".7"/>
      <path d="M180 52 Q184 74 186 94" stroke="#D6E0E8" stroke-width="2.5" fill="none" opacity=".7"/>
      <path d="M100 90 Q150 78 200 90" stroke="#F7A825" stroke-width="6" fill="none" stroke-linecap="round"/>
      <polygon points="150,74 159,79 159,89 150,94 141,89 141,79" fill="#F7A825" stroke="#fff" stroke-width="1.5"/>
      <!-- helmet sensor antennae -->
      <g filter="url(#beeGlow)">
        <path d="M138 54 Q132 34 130 26" stroke="#101a2b" stroke-width="4" fill="none" stroke-linecap="round"/>
        <path d="M162 54 Q168 34 170 26" stroke="#101a2b" stroke-width="4" fill="none" stroke-linecap="round"/>
        <polygon points="130,16 137,20 137,28 130,32 123,28 123,20" fill="#29B6F6"/>
        <polygon points="170,16 177,20 177,28 170,32 163,28 163,20" fill="#29B6F6"/>
      </g>
    </symbol>

    <!-- ===================== MINI (swarm) ===================== -->
    <symbol id="bee-mini" viewBox="0 0 120 100">
      <g transform="rotate(-14 60 50)">
        <ellipse cx="44" cy="34" rx="30" ry="15" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.2" stroke-opacity=".7"/>
        <ellipse cx="76" cy="34" rx="30" ry="15" fill="url(#wingGrad)" stroke="#8FE0FB" stroke-width="1.2" stroke-opacity=".7"/>
        <ellipse cx="60" cy="58" rx="34" ry="26" fill="url(#bodyGrad)"/>
        <clipPath id="miniClip"><ellipse cx="60" cy="58" rx="34" ry="26"/></clipPath>
        <g clip-path="url(#miniClip)">
          <rect x="28" y="44" width="64" height="11" rx="5.5" fill="#101a2b"/>
          <rect x="28" y="64" width="64" height="10" rx="5" fill="#101a2b"/>
        </g>
        <circle cx="52" cy="52" r="4" fill="#101a2b"/>
        <circle cx="70" cy="52" r="4" fill="#101a2b"/>
      </g>
    </symbol>
  </defs>
</svg>`;
  function inject() {
    if (document.getElementById('wh-bee-lib')) return;
    const wrap = document.createElement('div');
    wrap.id = 'wh-bee-lib';
    wrap.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
    wrap.innerHTML = LIB;
    document.body.insertBefore(wrap, document.body.firstChild);
  }
  if (document.body) inject();
  else document.addEventListener('DOMContentLoaded', inject);
})();
