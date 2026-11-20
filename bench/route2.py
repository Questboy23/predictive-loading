"""Route 2 driver: Playwright + Chrome for Testing (bench/route2_pw.js) through the bench SOCKS
proxy. 2x2 {Mac tool off/on (proxy resolver)} x {extension off/on}, at three
Wi-Fi RTT profiles. Session order (profile x extension) is shuffled; the DNS
mode order is shuffled per site inside each session.
Writes results/route2.jsonl.  Usage: python3 bench/route2.py [n_sites]
"""
import os
import random
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import env  # noqa: E402
import socksproxy  # noqa: E402

PROFILES = {"home_wifi": 10, "busy_campus_wifi": 60, "poor_wifi": 150}
EXT = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "results", "route2.jsonl")


def session(rtt, ext, n, seed, port):
    socksproxy.send(port, "RTT %d" % rtt)
    cmd = ["node", os.path.join(ROOT, "bench", "route2_pw.js"), str(rtt), ext, str(port), str(seed), str(n)]
    log = open(os.path.join(ROOT, "results", "route2-rtt%d-ext%s.log" % (rtt, ext)), "w")
    return subprocess.Popen(cmd, env=dict(os.environ, R2_OUT=OUT), stdout=log, stderr=subprocess.STDOUT)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    if os.path.exists(OUT) and "--append" not in sys.argv:
        os.remove(OUT)
    env.start(with_daemon=True)
    sessions = [(rtt, ext) for rtt in PROFILES.values() for ext in ("off", "on")]
    random.Random(3).shuffle(sessions)
    # All six sessions run at once, each through its own proxy (own RTT), sharing
    # one Unbound + daemon. Concurrency adds the same network load to every cell.
    proxies, procs = [], []
    try:
        for i, (rtt, ext) in enumerate(sessions):
            port = 1300 + 10 * i
            proxies.append(subprocess.Popen([sys.executable, os.path.join(ROOT, "bench", "socksproxy.py"), str(port), str(env.UB_PORT)]))
            for _ in range(50):
                try:
                    socksproxy.send(port, "STATS")
                    break
                except OSError:
                    time.sleep(0.2)
            procs.append((rtt, ext, session(rtt, ext, n, seed=100 + i, port=port)))
        for rtt, ext, p in procs:
            print("session rtt=%d ext=%s exit=%d" % (rtt, ext, p.wait()), flush=True)
    finally:
        for p in proxies:
            p.terminate()
        env.stop()


if __name__ == "__main__":
    main()
