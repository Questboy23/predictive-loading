"""Route 2 driver: browsertime + Chrome for Testing through the bench SOCKS
proxy. 2x2 {Mac tool off/on (proxy resolver)} x {extension off/on}, at three
Wi-Fi RTT profiles. Session order (profile x extension) is shuffled; the DNS
mode order is shuffled per site inside each session.
Writes results/route2.jsonl.  Usage: python3 bench/route2.py [n_sites]
"""
import glob
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
CFT = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1255/chrome-mac-arm64/"
                                   "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))[0]
CHROMEDRIVER = os.path.expanduser("~/.cache/pl-tools/chromedriver-mac-arm64/chromedriver")
EXT = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "results", "route2.jsonl")


def session(rtt, ext, n, seed, port=None):
    port = port or env.PROXY_PORT
    socksproxy.send(port, "RTT %d" % rtt)
    args = ["--proxy-server=socks5://127.0.0.1:%d" % port,
            "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1", "--no-first-run"]
    if ext == "on":
        args += ["--load-extension=" + EXT, "--disable-extensions-except=" + EXT]
    cmd = ["browsertime", "--browser", "chrome", "--chrome.binaryPath", CFT, "--chrome.chromedriverPath", CHROMEDRIVER,
           "-n", "1", "--headless", "--visualMetrics", "false", "--video", "false", "--screenshot", "false",
           "--timeouts.script", "3600000", "--timeouts.pageLoad", "60000",
           "--resultDir", os.path.join(ROOT, "results", "browsertime", "rtt%d-ext%s" % (rtt, ext))]
    for a in args:
        cmd.append("--chrome.args=" + a)
    cmd.append(os.path.join(ROOT, "bench", "route2_script.cjs"))
    e = dict(os.environ, R2_SITES=os.path.join(ROOT, "bench", "sites.json"), R2_OUT=OUT, R2_EXT=ext,
             R2_RTT=str(rtt), R2_N=str(n), R2_SEED=str(seed), R2_CTL=str(port + 1))
    return subprocess.Popen(cmd, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
