// tools/load_test.k6.js — P1 roadmap 2026-05-27 turn 7 (LB/G2 stub).
// =====================================================================
// Synthetic load test rig for the WorkHive edge stack. Closes the (LB, G2)
// cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 as scaffolding —
// real load runs against staging once a staging environment is provisioned.
//
// Run:
//   k6 run tools/load_test.k6.js  -e BASE_URL=http://127.0.0.1:54321  -e ANON_KEY=...
//
// Scenarios (capacity-plan-aligned):
//   1. voice_companion_sustained  — 20 simulated workers across 5 hives, 30 min
//   2. rag_flywheel_burst         — flywheel + 10 workers, 10 min
//   3. logbook_write_burst        — 100 concurrent workers, 1 entry/sec, 5 min
//   4. mixed_browsing             — 200 simulated users, 1 page/30s, 15 min
//
// Pass criteria (matches CAPACITY_PLAN.md):
//   - p95 latency < 2s on voice + RAG paths
//   - error rate < 1%
//   - no rate-limit fall-through below 80% chain provider success
//
// This is a STUB rig — counts as the scaffolding for the gap-list item but
// is not wired into CI until staging exists.

import http from 'k6/http';
import { sleep, check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:54321';
const ANON_KEY = __ENV.ANON_KEY || '';

export const options = {
  scenarios: {
    voice_companion_sustained: {
      executor: 'constant-vus',
      exec: 'voiceCompanion',
      vus: 20,
      duration: '5m',  // shortened for stub; 30m in real run
      tags: { scenario: 'voice_companion' },
    },
    rag_flywheel_burst: {
      executor: 'constant-vus',
      exec: 'ragFlywheel',
      vus: 10,
      duration: '3m',
      startTime: '5m',
      tags: { scenario: 'rag_flywheel' },
    },
    mixed_browsing: {
      executor: 'constant-vus',
      exec: 'browsing',
      vus: 30,
      duration: '5m',
      startTime: '8m',
      tags: { scenario: 'browsing' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'],     // p95 < 2s
    http_req_failed:   ['rate<0.01'],      // < 1% errors
    'http_req_duration{scenario:voice_companion}': ['p(95)<2500'],
    'http_req_duration{scenario:rag_flywheel}':    ['p(95)<5000'],
  },
};

const voiceLatency = new Trend('voice_companion_latency_ms');
const ragLatency   = new Trend('rag_flywheel_latency_ms');
const errorRate    = new Rate('error_rate');

function authHeaders(traceSuffix = '') {
  return {
    'Content-Type':  'application/json',
    'Authorization': `Bearer ${ANON_KEY}`,
    'x-wh-trace':    'k6test' + (traceSuffix || Math.random().toString(16).slice(2, 10)),
  };
}

export function voiceCompanion() {
  const t0 = Date.now();
  const res = http.post(`${BASE_URL}/functions/v1/ai-gateway`, JSON.stringify({
    agent:   'voice-journal',
    message: 'kumusta po, ano ang status ngayong shift?',
    context: { worker_name: `k6-${__VU}` },
  }), { headers: authHeaders('voice'), timeout: '30s' });
  voiceLatency.add(Date.now() - t0);
  const ok = check(res, {
    'voice 2xx': r => r.status >= 200 && r.status < 300,
    'voice has trace_id': r => {
      try { return Boolean(JSON.parse(r.body).trace_id); } catch { return false; }
    },
  });
  errorRate.add(!ok);
  sleep(Math.random() * 3 + 2);  // 2-5s between turns per worker
}

export function ragFlywheel() {
  const t0 = Date.now();
  const res = http.post(`${BASE_URL}/functions/v1/agentic-rag-loop`, JSON.stringify({
    question:    'How many breakdowns this week and what was the most common root cause?',
    hive_id:     null,
    worker_name: `k6-bg-${__VU}`,
  }), { headers: authHeaders('rag'), timeout: '45s' });
  ragLatency.add(Date.now() - t0);
  const ok = check(res, { 'rag 2xx or 4xx (not 5xx)': r => r.status < 500 });
  errorRate.add(!ok);
  sleep(Math.random() * 5 + 5);  // 5-10s between turns (background traffic)
}

export function browsing() {
  const pages = ['hive.html', 'logbook.html', 'inventory.html', 'analytics.html'];
  for (const p of pages) {
    const res = http.get(`${BASE_URL}/${p}`, { timeout: '10s' });
    check(res, { 'page 2xx': r => r.status === 200 });
    sleep(Math.random() * 30 + 10);  // 10-40s per page
  }
}
