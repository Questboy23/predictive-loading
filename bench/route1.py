"""Route 1: DNS lookup time on the Tranco top 500 with dnspyre.
Conditions: system default (network resolver, direct), Unbound alone (own
prefetch + serve-expired), Unbound + predictor daemon. R rounds, condition
order shuffled per round, W seconds between rounds so TTLs expire. Round 1 is
cold for every condition and reported apart.
Writes results/route1.json.
"""
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
sys.path.insert(0, os.path.join(ROOT, "mac", "lib"))
import env  # noqa: E402

ROUNDS = int(os.environ.get("R1_ROUNDS", "5"))
WAIT = int(os.environ.get("R1_WAIT", "180"))
DUR = re.compile(r"qname:\[(\S+?)\.?\] .*rcode:\[(\w*)\].*duration:\[([\d.]+)(µs|ms|s)\]")
UNIT = {"µs": 0.001, "ms": 1.0, "s": 1000.0}


def start_plain_unbound():
    """Second Unbound on 5301, same config, no predictor."""
    import daemon
    d2 = os.path.join(env.BASE, "data-plain")
    subprocess.run(["rm", "-rf", d2])  # nosec B603 B607: own cache dir
    os.makedirs(d2, mode=0o700)
    conf = open(os.path.join(env.DATA, "unbound.conf")).read()
    conf = conf.replace(env.DATA, d2).replace("@5300", "@5301").replace("port: 5300", "port: 5301")
    open(os.path.join(d2, "unbound.conf"), "w").write(conf)
    subprocess.run(["cp", os.path.join(env.DATA, "root.key"), d2])  # nosec B603 B607
    p = subprocess.Popen(["unbound", "-d", "-c", os.path.join(d2, "unbound.conf")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    return p, daemon


def run_dnspyre(server, names_file, log):
    if os.path.exists(log):
        os.remove(log)
    subprocess.run(["dnspyre", "--server", server, "-n", "1", "-c", "1", "--no-color", "--no-progress",
                    "--silent", "--log-requests", "--log-requests-path", log, "@" + names_file], check=False)
    out = []
    for line in open(log):
        m = DUR.search(line)
        if m:
            out.append([m.group(1), m.group(2), float(m.group(3)) * UNIT[m.group(4)]])
    return out


def boot_ci(xs, stat, iters=2000, seed=0):
    rng = random.Random(seed)
    vals = sorted(stat([xs[rng.randrange(len(xs))] for _ in xs]) for _ in range(iters))
    return [round(vals[int(0.025 * iters)], 2), round(vals[int(0.975 * iters)], 2)]


def p75(xs):
    s = sorted(xs)
    return s[int(0.75 * (len(s) - 1))]


def summarize(xs):
    return {"n": len(xs), "median_ms": round(statistics.median(xs), 2), "p75_ms": round(p75(xs), 2),
            "mean_ms": round(statistics.fmean(xs), 2),
            "median_ci95": boot_ci(xs, statistics.median), "p75_ci95": boot_ci(xs, p75)}


def main():
    names = [l.split(",")[1].strip() for l in open(os.path.join(ROOT, "data", "raw", "top-1m.csv"))][:500]
    nf = os.path.join(env.BASE, "tranco500.txt")
    env.start(with_daemon=True)
    plain, daemon = start_plain_unbound()
    system = daemon.network_resolvers()[0]
    conds = {"system_default": system, "unbound_alone": "127.0.0.1:5301", "unbound_plus_predictor": "127.0.0.1:5300"}
    raw = {c: [] for c in conds}
    rng = random.Random(1)
    try:
        for r in range(ROUNDS):
            order = list(conds)
            rng.shuffle(order)
            shuffled = names[:]
            rng.shuffle(shuffled)
            open(nf, "w").write("\n".join(shuffled) + "\n")
            for c in order:
                res = run_dnspyre(conds[c], nf, os.path.join(env.BASE, "req-%s.log" % c))
                raw[c].append(res)
                print("round", r + 1, c, "n=%d" % len(res), "median %.1f ms" % statistics.median(x[2] for x in res), flush=True)
            if r < ROUNDS - 1:
                time.sleep(WAIT)
    finally:
        plain.terminate()
        env.stop()
    out = {"names": len(names), "rounds": ROUNDS, "wait_s": WAIT, "system_resolver": "network DHCP resolver",
           "cold": {c: summarize([x[2] for x in raw[c][0]]) for c in conds},
           "warm": {c: summarize([x[2] for rr in raw[c][1:] for x in rr]) for c in conds}}
    st = json.load(open(os.path.join(env.DATA, "stats.json"))) if os.path.exists(os.path.join(env.DATA, "stats.json")) else {}
    out["daemon_stats"] = st
    json.dump(out, open(os.path.join(ROOT, "results", "route1.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
