"""Walkthrough 2026-05-13: seed Lucena ai_cost_log so ai-quality.html
renders a realistic Stair 3 dashboard.

Lucena is the walkthrough demo hive; without this seed the AI Quality
page shows $0.0000 spend and renders an empty/sad dashboard, which
defeats the purpose of the walkthrough.

Seeds ~100 rows across the last 30 days. Distribution mirrors a real
Stair 3 hive: AMC + voice-journal dominate volume, visual-defect is
mid, anomaly + gateway are infrequent but expensive.

Quality signal mix:
  status: 92% success, 5% fallback, 3% failed
  schema_compliance: 88% true, 10% false, 2% null
  user_feedback: 22% +1, 5% -1, 73% null

Idempotent: deletes Lucena's prior rows in the 30-day window first.
"""
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '.')
from lib.supabase_client import get_client


LUCENA_HIVE = '586fd158-42d1-4853-a406-64a4695e71c4'

# (fn, model, provider, base_cost, latency_range_ms, prompt_token_range, output_token_range, weight)
FN_PROFILES = [
    ('amc-orchestrator',       'claude-haiku-4-5',  'anthropic', 0.0040, (450, 1800),  (800, 2200), (180, 520),  18),
    ('voice-journal-agent',    'claude-haiku-4-5',  'anthropic', 0.0018, (380, 1200),  (320, 900),  (90, 280),   32),
    ('visual-defect-capture',  'claude-sonnet-4-6', 'anthropic', 0.0185, (1100, 4200), (1400, 3000),(220, 700),  16),
    ('ai-gateway',             'claude-haiku-4-5',  'anthropic', 0.0024, (320, 900),   (260, 720),  (60, 240),   10),
    ('anomaly-explainer',      'claude-sonnet-4-6', 'anthropic', 0.0095, (700, 2100),  (900, 2200), (160, 460),  6),
    ('failure-signature-scan', 'claude-haiku-4-5',  'anthropic', 0.0009, (180, 540),   (180, 480),  (40, 140),   12),
    ('knowledge-rerank',       'claude-haiku-4-5',  'anthropic', 0.0006, (140, 420),   (220, 540),  (30, 100),   6),
]


def pick_fn():
    total_weight = sum(p[7] for p in FN_PROFILES)
    r = random.uniform(0, total_weight)
    cum = 0
    for p in FN_PROFILES:
        cum += p[7]
        if r <= cum:
            return p
    return FN_PROFILES[-1]


def pick_status():
    r = random.random()
    if r < 0.92: return 'success'
    if r < 0.97: return 'fallback'
    return 'failed'


def pick_schema_compliance():
    r = random.random()
    if r < 0.88: return True
    if r < 0.98: return False
    return None


def pick_user_feedback():
    r = random.random()
    if r < 0.22: return 1
    if r < 0.27: return -1
    return None


def main():
    db = get_client()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    # Idempotent: clear walkthrough-seeded rows in the 30d window first
    delete_resp = db.table('ai_cost_log').delete() \
        .eq('hive_id', LUCENA_HIVE) \
        .gte('created_at', cutoff.isoformat()) \
        .execute()
    print(f"Cleared prior 30d rows: {len(delete_resp.data or [])}")

    workers = ['Pablo Aguilar', 'Maria Santos', 'Juan Reyes', 'Lola Cruz', 'Ramon Dela Cruz']
    rows = []
    target_count = 95
    for _ in range(target_count):
        fn, model, provider, base_cost, lat_r, ptr, otr, _w = pick_fn()
        prompt_tokens = random.randint(*ptr)
        output_tokens = random.randint(*otr)
        cost = round(base_cost * (0.7 + random.random() * 0.8), 6)
        latency = random.randint(*lat_r)
        status = pick_status()
        days_back = random.uniform(0, 30)
        ts = now - timedelta(days=days_back, hours=random.uniform(0, 24))
        rows.append({
            'fn': fn,
            'hive_id': LUCENA_HIVE,
            'worker_name': random.choice(workers),
            'model': model,
            'provider': provider,
            'prompt_tokens': prompt_tokens,
            'output_tokens': output_tokens,
            'cost_usd': cost,
            'latency_ms': latency,
            'status': status,
            'schema_compliance': pick_schema_compliance(),
            'user_feedback': pick_user_feedback(),
            'created_at': ts.isoformat(),
        })

    inserted = db.table('ai_cost_log').insert(rows).execute()
    print(f"Inserted {len(inserted.data)} ai_cost_log rows for Lucena")

    total_cost = sum(r['cost_usd'] for r in rows)
    ups = sum(1 for r in rows if r['user_feedback'] == 1)
    dns = sum(1 for r in rows if r['user_feedback'] == -1)
    sc_ok = sum(1 for r in rows if r['schema_compliance'] is True)
    sc_n = sum(1 for r in rows if r['schema_compliance'] is not None)
    fb = sum(1 for r in rows if r['status'] == 'fallback')
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Schema compliance: {sc_ok}/{sc_n} = {100*sc_ok/max(sc_n,1):.0f}%")
    print(f"  Thumbs: {ups} up / {dns} down  ({100*ups/max(ups+dns,1):.0f}% positive)")
    print(f"  Fallback rate: {fb}/{len(rows)} = {100*fb/len(rows):.0f}%")


if __name__ == '__main__':
    main()
