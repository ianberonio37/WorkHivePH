"""validate_federated_consent.py - anything published ACROSS hives is built only from hives that consented (2026-10-08).

hives.federated_benchmark_opted_in (Phase 6D) is the per-hive consent to contribute anonymised figures to the shared
PH benchmarks. Until 2026-10-08 no page could set it and no reader checked it: benchmark-compute, intelligence-report
and intelligence-api aggregated every hive (and a synthetic eval hive) while every hive was false. This gate holds:

  C1  _shared/federated-consent.ts exists, reads the flag, and FAILS CLOSED (an unreadable consent throws, it is never
      "everyone"; an empty consent filters to no hive, never to an absent filter)
  C2  in the cross-hive readers - benchmark-compute computeNetwork, intelligence-report gatherData, intelligence-api -
      every read of a hive-owned table is limited to named hives (.in("hive_id", ...) or a per-hive .eq("hive_id", ...))
      and each of those files takes its contributors from consentedHiveIds()
  C3  benchmark-compute WITHDRAWS network rows it could not republish under consent (upsert-only kept them forever)
  C4  the switch exists: set_federated_benchmark_opt_in (supervisor-only, audited) in a migration, called from hive.html

  python tools/validate_federated_consent.py              # the gate
  python tools/validate_federated_consent.py --selftest   # each rule must catch its fixture
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FN = os.path.join(ROOT, 'supabase', 'functions')
HIVE_OWNED = ('v_logbook_truth', 'logbook', 'fault_knowledge', 'v_inventory_items_truth', 'inventory_items',
              'hive_benchmarks', 'v_pm_scope_items_truth', 'pm_completions')
READERS = {
    'benchmark-compute': 'computeNetwork',
    'intelligence-report': 'gatherData',
    'intelligence-api': None,   # the whole file serves the external data product
}


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def fn_body(src, name):
    m = re.search(r'async function ' + re.escape(name) + r'\s*\(', src)
    if not m:
        return ''
    i = src.index('{', m.end())
    depth = 0
    for j in range(i, len(src)):
        c = src[j]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


def unscoped_reads(body):
    """every .from("<hive-owned>") chain (to the next ';') with no hive limit"""
    bad = []
    for m in re.finditer(r'\.from\(\s*["\']([a-z_]+)["\']\s*\)', body):
        if m.group(1) not in HIVE_OWNED:
            continue
        end = body.find(';', m.end())
        chain = body[m.end(): end if end != -1 else len(body)]
        if not re.search(r'\.(in|eq)\(\s*["\']hive_id["\']', chain):
            line = body.count('\n', 0, m.start()) + 1
            bad.append('%s (body line %d)' % (m.group(1), line))
    return bad


def check(files):
    problems = []
    helper = files.get('_shared/federated-consent.ts', '')
    if not helper:
        problems.append('C1 _shared/federated-consent.ts is missing')
    else:
        if 'federated_benchmark_opted_in' not in helper:
            problems.append('C1 the consent helper does not read hives.federated_benchmark_opted_in')
        if not re.search(r'if\s*\(\s*error\s*\)\s*throw', helper):
            problems.append('C1 the consent helper does not FAIL CLOSED (a read error must throw)')
        if not re.search(r'ids\.length\s*\?\s*ids\s*:\s*\[', helper):
            problems.append('C1 an empty consent must filter to no hive (hiveFilter), never to an absent filter')
    for fn, scope in READERS.items():
        src = files.get(fn, '')
        if not src:
            problems.append('C2 %s/index.ts is missing' % fn); continue
        if 'consentedHiveIds' not in src:
            problems.append('C2 %s does not take its contributors from consentedHiveIds()' % fn)
        body = fn_body(src, scope) if scope else src
        if scope and not body:
            problems.append('C2 %s has no %s() to check' % (fn, scope)); continue
        for b in unscoped_reads(body):
            problems.append('C2 %s%s reads %s across ALL hives (no .in/.eq hive_id)' % (fn, ' ' + scope + '()' if scope else '', b))
    bc = fn_body(files.get('benchmark-compute', ''), 'computeNetwork')
    if not re.search(r'from\(\s*["\']network_benchmarks["\']\s*\)\s*\.delete\(\)', bc):
        problems.append('C3 benchmark-compute computeNetwork never withdraws network rows it could not republish')
    mig = files.get('_migrations', '')
    if not re.search(r'FUNCTION public\.set_federated_benchmark_opt_in\(', mig) or "role = 'supervisor'" not in mig:
        problems.append('C4 no supervisor-only set_federated_benchmark_opt_in in the migrations')
    if "rpc('set_federated_benchmark_opt_in'" not in files.get('hive.html', ''):
        problems.append('C4 hive.html offers no switch (no call to set_federated_benchmark_opt_in)')
    return problems


def load():
    files = {fn: read(os.path.join(FN, fn, 'index.ts')) for fn in READERS}
    files['_shared/federated-consent.ts'] = read(os.path.join(FN, '_shared', 'federated-consent.ts'))
    mdir = os.path.join(ROOT, 'supabase', 'migrations')
    files['_migrations'] = '\n'.join(read(os.path.join(mdir, f)) for f in sorted(os.listdir(mdir))
                                     if 'federated' in f or 'national_benchmark' in f or 'benchmark' in f)
    files['hive.html'] = read(os.path.join(ROOT, 'hive.html'))
    return files


def selftest():
    base = load()
    assert not check(base), 'the real tree must pass before the fixtures mean anything: %s' % check(base)
    cases = [
        ('helper fails open', '_shared/federated-consent.ts', lambda s: re.sub(r'if\s*\(\s*error\s*\)\s*throw[^;]*;', '', s, count=1), 'FAIL CLOSED'),
        ('empty consent drops the filter', '_shared/federated-consent.ts', lambda s: s.replace('ids.length ? ids : [NO_HIVE]', 'ids'), 'absent filter'),
        ('report reads all hives', 'intelligence-report', lambda s: s.replace('.in("hive_id", inHives)\n    .gte("created_at", since);', '.gte("created_at", since);', 1), 'across ALL hives'),
        ('api sells without consent', 'intelligence-api', lambda s: s.replace('.in("hive_id", hiveFilter(consented))', '', 1), 'across ALL hives'),
        ('network reads all hives', 'benchmark-compute', lambda s: s.replace('.in("hive_id", hiveFilter(consented))', '', 1), 'across ALL hives'),
        ('no withdrawal', 'benchmark-compute', lambda s: s.replace('.from("network_benchmarks").delete()', '.from("network_benchmarks").select()', 1), 'withdraws'),
        ('no switch', 'hive.html', lambda s: s.replace("rpc('set_federated_benchmark_opt_in'", "rpc('x'"), 'offers no switch'),
    ]
    bad = 0
    for name, key, mut, want in cases:
        f = dict(base); f[key] = mut(base[key])
        if f[key] == base[key]:
            print('  FIXTURE DID NOT APPLY  %s' % name); bad += 1; continue
        got = check(f)
        hit = any(want in g for g in got)
        print('  %s  %s' % ('caught' if hit else 'MISSED', name))
        bad += 0 if hit else 1
    print('selftest: %d/%d caught' % (len(cases) - bad, len(cases)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    if '--selftest' in sys.argv:
        raise SystemExit(selftest())
    probs = check(load())
    for p in probs:
        print('  FAIL ' + p)
    print('PASS federated-consent - cross-hive figures come only from consenting hives; the switch exists' if not probs
          else 'FAIL (%d): federated consent' % len(probs))
    raise SystemExit(1 if probs else 0)
