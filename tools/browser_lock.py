"""browser_lock.py - take THE host's one browser slot from a shell, for MCP walks by the main session and its agents.

This host has one usable browser slot. tools/browser_slot.mjs (node provers, the suite's browser gates) and
tools/drive_journey_wave.sh already queue on `.tmp/jn_drive.lock`, which holds the PID of the live holder. An MCP
walk runs inside the Playwright MCP server, so it has no process of its own to put there: this tool starts a small
KEEPER process that writes its PID into that same lock and lives until the walk releases it. MCP walks, agents and
browser gates therefore all queue on ONE lock - two at once would sign each other out (every walker clears the
site's storage) and, on this 8 GB laptop, a second browser is how the 2026-10-08 11:11 low-memory crash happened.

  python tools/browser_lock.py acquire <owner> [--wait SECONDS]   # returns when the slot is <owner>'s
  python tools/browser_lock.py release <owner>
  python tools/browser_lock.py status

Rules every walker follows:
  - acquire immediately BEFORE a browser call, release immediately AFTER it - never across banking or gates;
  - restart the edge runtime or the test server ONLY while holding the slot (a restart mid-walk breaks that walk);
  - the slot is also a database courtesy: heavy psql suites and edge restarts wait for it (memory
    feedback_the_browser_slot_left_the_database_unguarded);
  - a keeper ends itself after STALE_S, so a crashed walker never blocks the host for long.
NOTE: never test a Windows PID with os.kill(pid, 0) - on Windows that TERMINATES the process. OpenProcess is used.
"""
import ctypes, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, '.tmp', 'jn_drive.lock')          # shared with browser_slot.mjs / drive_journey_wave.sh
META = os.path.join(ROOT, '.tmp', 'jn_drive.owner.json')    # who holds it (the lock itself holds only a PID)
QUEUE = os.path.join(ROOT, '.tmp', 'browser_queue')
STALE_S = 25 * 60


def alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000 | 0x00100000, False, int(pid))   # QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259                     # STILL_ACTIVE
    try:
        os.kill(int(pid), 0); return True
    except OSError:
        return False


def holder_pid():
    try:
        return int(open(LOCK, encoding='utf-8').read().strip() or 0)
    except Exception:
        return 0


def meta():
    try:
        return json.load(open(META, encoding='utf-8'))
    except Exception:
        return {}


def status():
    pid = holder_pid()
    m = meta()
    if pid and alive(pid):
        print('held by %s (pid %d) for %ds' % (m.get('owner', 'a node prover / journey drive'), pid, int(time.time() - m.get('at', time.time()))))
    else:
        print('free' + (' (stale lock of dead pid %d)' % pid if pid else ''))
    q = sorted(os.listdir(QUEUE)) if os.path.isdir(QUEUE) else []
    if q:
        print('waiting:', ', '.join(x.split('-', 1)[1] for x in q))


def keep(owner):
    """the keeper: holds the lock with its own PID until released or stale"""
    if holder_pid() and alive(holder_pid()) and holder_pid() != os.getpid():
        sys.exit(3)
    with open(LOCK, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    t0 = time.time()
    with open(META, 'w', encoding='utf-8') as f:
        json.dump({'owner': owner, 'at': t0, 'pid': os.getpid()}, f)
    while True:
        time.sleep(2)
        m = meta()
        if m.get('owner') != owner or m.get('pid') != os.getpid() or time.time() - t0 > STALE_S:
            break
    try:
        if holder_pid() == os.getpid():
            os.remove(LOCK)
    except OSError:
        pass
    try:
        if meta().get('pid') == os.getpid():
            os.remove(META)
    except OSError:
        pass


def acquire(owner, wait):
    os.makedirs(QUEUE, exist_ok=True)
    ticket = os.path.join(QUEUE, '%020d-%s' % (time.time_ns(), owner))
    open(ticket, 'w').close()
    t0 = time.time()
    try:
        while True:
            pid = holder_pid()
            if pid and alive(pid):
                if meta().get('owner') == owner and meta().get('pid') == pid:
                    print('already held by', owner); return 0
            else:
                first = sorted(os.listdir(QUEUE))[0] == os.path.basename(ticket)
                if first:
                    flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0   # DETACHED_PROCESS | NEW_PROCESS_GROUP
                    subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), '_keep', owner],
                                     creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
                    for _ in range(50):
                        time.sleep(0.2)
                        m = meta()
                        if m.get('owner') == owner and holder_pid() == m.get('pid') and alive(m.get('pid')):
                            print('acquired by %s after %ds' % (owner, int(time.time() - t0)))
                            return 0
            if time.time() - t0 > wait:
                print('TIMEOUT: %s waited %ds; holder %s' % (owner, int(time.time() - t0), meta().get('owner', pid)))
                return 2
            time.sleep(3)
    finally:
        try:
            os.remove(ticket)
        except OSError:
            pass


def release(owner):
    m = meta()
    if m.get('owner') != owner:
        print('REFUSED: held by %s, not %s' % (m.get('owner', 'nobody'), owner) if m else 'not held'); return 0 if not m else 2
    try:
        os.remove(META)                       # the keeper sees its claim gone and removes the lock itself
    except OSError:
        pass
    for _ in range(20):
        if not (holder_pid() and alive(holder_pid())):
            break
        time.sleep(0.3)
    print('released by', owner)
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'status':
        status(); raise SystemExit(0)
    if a[0] == '_keep':
        keep(a[1]); raise SystemExit(0)
    if a[0] == 'acquire':
        raise SystemExit(acquire(a[1], int(a[a.index('--wait') + 1]) if '--wait' in a else 3600))
    if a[0] == 'release':
        raise SystemExit(release(a[1]))
    print(__doc__); raise SystemExit(2)
