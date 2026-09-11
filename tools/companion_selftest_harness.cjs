// companion_selftest_harness — runs voice-handler.js's own _runSelfTest() OUTSIDE a browser.
//
// ★THE COMPANION CARRIED EIGHTEEN SELF-TEST CASES THAT NO GATE EVER RAN. _runSelfTest() is exported on
// the module surface and invoked only by a badge somebody has to open in a browser, so every case in it
// was a lock nothing turns: they could rot for months and the suite would stay green. The checks are
// good - they pin the affirmation and negation regexes, the PII scrub, the symptom normaliser and now
// the six input-normalisation capabilities - so the repair is to RUN them, not to rewrite them.
//
// voice-handler.js is a browser IIFE, so the page's globals are stubbed to the minimum it touches on
// load. Nothing here fakes a RESULT: the stubs only let the file finish loading, and the assertions are
// the module's own.
//
//   node tools/companion_selftest_harness.cjs
const fs = require('fs');
const store = {};
const el = () => ({ style:{}, classList:{add(){},remove(){},contains(){return false}}, setAttribute(){}, getAttribute(){return null}, appendChild(){}, addEventListener(){}, removeEventListener(){}, querySelector(){return null}, querySelectorAll(){return []}, textContent:'', innerHTML:'', dataset:{}, focus(){}, click(){}, remove(){} });
global.window = global;
global.localStorage = { getItem:(k)=>Object.prototype.hasOwnProperty.call(store,k)?store[k]:null, setItem:(k,v)=>{store[k]=String(v)}, removeItem:(k)=>{delete store[k]}, clear:()=>{for(const k in store)delete store[k]} };
global.sessionStorage = global.localStorage;
global.document = { createElement: el, body: el(), head: el(), documentElement: el(), getElementById(){return null}, querySelector(){return null}, querySelectorAll(){return []}, addEventListener(){}, removeEventListener(){}, hidden:false, visibilityState:'visible', cookie:'' };
global.navigator = { userAgent:'node', language:'en-PH', onLine:true, mediaDevices:{}, serviceWorker:{ addEventListener(){}, register(){return Promise.reject(new Error('no sw'))} } };
global.location = { href:'http://127.0.0.1:5000/workhive/logbook.html', pathname:'/workhive/logbook.html', origin:'http://127.0.0.1:5000', search:'' };
global.fetch = () => Promise.reject(new Error('offline in the harness'));
global.speechSynthesis = { speak(){}, cancel(){}, getVoices(){return []} };
global.addEventListener = () => {}; global.removeEventListener = () => {};
global.matchMedia = () => ({ matches:false, addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} });
global.requestAnimationFrame = (f) => setTimeout(f, 0);
try { eval(fs.readFileSync(process.env.WH_SELFTEST_SUBJECT || require('path').join(__dirname, '..', 'voice-handler.js'), 'utf8')); } catch (e) { console.log('LOAD FAILED: ' + e.message); process.exit(1); }
const V = global.WHVoice || global.window.WHVoice;
if (!V || typeof V._runSelfTest !== 'function') { console.log('no _runSelfTest on the module surface'); process.exit(1); }
const r = V._runSelfTest();
console.log(`  ${r.passed}/${r.total} self-test checks pass`);
if (r.failures && r.failures.length) { console.log('  failures:'); for (const f of r.failures) console.log('    - ' + f); }
process.exit(r.failures && r.failures.length ? 1 : 0);
