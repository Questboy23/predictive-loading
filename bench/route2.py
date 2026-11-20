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


def session(rtt, ext, n, seed):
    socksproxy.send(env.PROXY_PORT, "RTT %d" % rtt)
    args = ["--proxy-server=socks5://127.0.0.1:%d" % env.PROXY_PORT,
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
             R2_RTT=str(rtt), R2_N=str(n), R2_SEED=str(seed), R2_CTL=str(env.PROXY_PORT + 1))
    r = subprocess.run(cmd, env=e, capture_output=True, text=True)
    print("session rtt=%d ext=%s exit=%d %s" % (rtt, ext, r.returncode, r.stdout[-300:].replace("\n", " ")), flush=True)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    if os.path.exists(OUT) and "--append" not in sys.argv:
        os.remove(OUT)
    env.start(with_daemon=True)
    sessions = [(rtt, ext) for rtt in PROFILES.values() for ext in ("off", "on")]
    random.Random(3).shuffle(sessions)
    try:
        for i, (rtt, ext) in enumerate(sessions):
            session(rtt, ext, n, seed=100 + i)
    finally:
        env.stop()


if __name__ == "__main__":
    main()
