"""E3 driver (PREREG.md): 4 workers, each with its own SOCKS proxy in "off" DNS
mode (network resolver; set PL_BENCH_OFF_DNS when the Mac tool is live).
Writes results/habit.jsonl.  Usage: python3 bench/habit.py"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import socksproxy  # noqa: E402

OUT = os.path.join(ROOT, "results", "habit.jsonl")
WORKERS = 4


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    proxies, procs = [], []
    try:
        for w in range(WORKERS):
            port = 1500 + 10 * w
            proxies.append(subprocess.Popen([sys.executable, os.path.join(ROOT, "bench", "socksproxy.py"), str(port), "5300"]))
            for _ in range(50):
                try:
                    socksproxy.send(port, "STATS")
                    break
                except OSError:
                    time.sleep(0.2)
            log = open(os.path.join(ROOT, "results", "habit-w%d.log" % w), "w")
            procs.append(subprocess.Popen(["node", os.path.join(ROOT, "bench", "habit_pw.js"), str(port), str(w), str(WORKERS), OUT],
                                          stdout=log, stderr=subprocess.STDOUT))
        for w, p in enumerate(procs):
            print("worker %d exit %d" % (w, p.wait()), flush=True)
    finally:
        for p in proxies:
            p.terminate()


if __name__ == "__main__":
    main()
