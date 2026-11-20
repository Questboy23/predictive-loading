"""E2 (PREREG.md): trace-driven DNS simulation on held-out real history.

Workload: Reed's own Chrome history (host per page visit, real timestamps),
read in memory only. Names are never written to disk, logs or results.
Per unique name, measured live: full TTL (first answer from a cold, fully
recursive local Unbound) and network-resolver latency (median of 3 queries).
Policies: S system TTL cache; U = S + Unbound prefetch (refresh a name queried
in the last 10% of its TTL); P = U + the shipped predictor and cost rule every
60 s of awake trace time (the daemon's 1-hour pending rule, wake next-hour boost),
holdout off. Train on everything before the last 14 days, measure the last 14.
Writes results/dns_sim.json (aggregates only).
Usage: python3 bench/dns_sim.py   (needs PL_BENCH_OFF_DNS = network resolver IP)
"""
import json
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "predictor"))
sys.path.insert(0, os.path.join(ROOT, "mac", "lib"))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import dnsq  # noqa: E402
import paired  # noqa: E402
from predictor import Predictor, should_act  # noqa: E402

NET = os.environ["PL_BENCH_OFF_DNS"]
TEST_DAYS, CYCLE, AWAKE_GAP, PENDING_S = 14, 60, 1800, 3600
NEVER = re.compile(r"(^|\.)(local|localhost|internal|lan|home\.arpa)$")


def load_history():
    src = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/History")
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(src, os.path.join(tmp, "h"))
        con = sqlite3.connect(os.path.join(tmp, "h"))
        rows = con.execute("SELECT v.visit_time, u.url FROM visits v JOIN urls u ON u.id=v.url ORDER BY v.visit_time").fetchall()
        con.close()
    finally:
        shutil.rmtree(tmp)
    ev = []
    for vt, url in rows:
        m = re.match(r"^https?://([^/?#:]+)", url)
        if m and not NEVER.search(m.group(1).lower()) and "." in m.group(1):
            ev.append((vt / 1e6 - 11644473600, m.group(1).lower().rstrip(".")))
    return ev


def cold_unbound():
    d = tempfile.mkdtemp(prefix="pl-sim-")
    conf = os.path.join(d, "u.conf")
    open(conf, "w").write("server:\n  interface: 127.0.0.1\n  port: 5399\n  do-daemonize: no\n  chroot: \"\"\n"
                          "  username: \"\"\n  directory: \"%s\"\n  pidfile: \"\"\n  use-syslog: no\n"
                          "  module-config: \"iterator\"\n  cache-max-ttl: 86400\n  verbosity: 0\n" % d)
    p = subprocess.Popen(["/opt/homebrew/sbin/unbound", "-d", "-c", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    return p, d


def full_ttl(name):
    """Minimum TTL along the answer chain from a cold recursive resolver; None if no answer."""
    out = subprocess.run(["dig", "+noall", "+answer", "+time=3", "+tries=1", "@127.0.0.1", "-p", "5399", name, "A"],
                         capture_output=True, text=True).stdout
    ttls = [int(l.split()[1]) for l in out.splitlines() if len(l.split()) >= 5 and l.split()[1].isdigit()]
    return min(ttls) if ttls else None


def net_ms(name):
    xs = []
    for _ in range(3):
        rc, an, ms = dnsq.query(name, "A", NET, 53, timeout=3.0)
        if rc in ("NOERROR", "NXDOMAIN"):
            xs.append(ms)
    return statistics.median(xs) if xs else None


def local_hit_ms():
    dnsq.query("example.com", "A", "127.0.0.1", 53)
    return statistics.median(dnsq.query("example.com", "A", "127.0.0.1", 53)[2] for _ in range(50))


def day_of(t):
    lt = time.localtime(int(t))
    return int(time.mktime(lt[:3] + (0, 0, 0, 0, 0, -1))) // 86400


def simulate(ev, ttl, lat, hit_ms, test_start):
    cache = {k: {} for k in "SUP"}
    upstream = {k: 0 for k in "SUP"}
    pred, up_ms, pending = Predictor(), {}, {}
    per_day = {k: {} for k in "SUP"}
    hits = {k: 0 for k in "SUP"}
    n_test, last_cycle, last_event = 0, None, None
    default_up = statistics.median(lat.values())
    hours_awake_test = 0.0

    def cycle(t, next_hour):
        hour = time.localtime(int(t)).tm_hour
        cands = pred.predict(hour, 25)
        if next_hour:
            cands += pred.predict((hour + 1) % 24, 25)
        done = set()
        for d, p in cands:
            if d in done or d not in ttl:
                continue
            done.add(d)
            if next_hour:
                p = max(p, 0.05)
            if not should_act(p, up_ms.get(d, default_up), hit_ms) or (d in pending and t - pending[d] < PENDING_S):
                continue
            pending[d] = t
            if cache["P"].get(d, 0) <= t:  # the daemon's query goes upstream only on a local miss
                cache["P"][d] = t + ttl[d]
                if t >= test_start:
                    upstream["P"] += 1

    for t, name in ev:
        if name not in ttl:
            continue
        if last_event is not None and t - last_event > AWAKE_GAP:  # Mac asleep: no cycles; first cycle on wake looks ahead
            last_cycle = t
            cycle(t, True)
        elif last_cycle is None:
            last_cycle = t
        while t - last_cycle >= CYCLE:
            last_cycle += CYCLE
            cycle(last_cycle, False)
        if last_event is not None and t >= test_start and t - last_event <= AWAKE_GAP:
            hours_awake_test += (t - last_event) / 3600
        last_event = t
        measured = t >= test_start
        if measured:
            n_test += 1
        for k in "SUP":
            exp = cache[k].get(name, 0)
            hit = exp > t
            if hit and k in "UP" and exp - t < 0.1 * ttl[name]:  # Unbound prefetch on a query near expiry
                cache[k][name] = t + ttl[name]
                if measured:
                    upstream[k] += 1
            if not hit:
                cache[k][name] = t + ttl[name]
                if measured:
                    upstream[k] += 1
            if measured:
                hits[k] += hit
                per_day[k].setdefault(day_of(t), []).append(hit_ms if hit else lat[name])
        if cache["P"].get(name, 0) <= t or name not in up_ms:
            up_ms[name] = lat[name] if name not in up_ms else 0.7 * up_ms[name] + 0.3 * lat[name]
        pending.pop(name, None)
        lt = time.localtime(int(t))
        pred.observe(name, lt.tm_hour, day_of(t))
    return per_day, hits, upstream, n_test, hours_awake_test


def main():
    ev = load_history()
    test_start = ev[-1][0] - TEST_DAYS * 86400
    names = sorted({n for _, n in ev})
    p, d = cold_unbound()
    try:
        with ThreadPoolExecutor(16) as ex:
            ttls = dict(zip(names, ex.map(full_ttl, names)))
    finally:
        p.terminate()
        shutil.rmtree(d, ignore_errors=True)
    with ThreadPoolExecutor(8) as ex:
        lats = dict(zip(names, ex.map(net_ms, names)))
    ok = [n for n in names if ttls[n] is not None and lats[n] is not None]
    ttl = {n: max(ttls[n], 1) for n in ok}
    lat = {n: lats[n] for n in ok}
    hit_ms = local_hit_ms()
    per_day, hits, upstream, n_test, awake_h = simulate(ev, ttl, lat, hit_ms, test_start)
    days = sorted(per_day["S"])
    mean = {k: [statistics.fmean(per_day[k][dd]) for dd in days] for k in "SUP"}
    test_ev = [n for t, n in ev if t >= test_start]
    out = {
        "events_total": len(ev), "events_test": len(test_ev), "events_test_simulated": n_test,
        "names": len(names), "names_measured": len(ok), "test_days": len(days),
        "local_hit_ms": round(hit_ms, 3),
        "net_ms_median": round(statistics.median(lat.values()), 2), "net_ms_p90": round(sorted(lat.values())[int(0.9 * len(lat))], 2),
        "ttl_median_s": statistics.median(ttl.values()),
        "hit_rate": {k: round(hits[k] / n_test, 4) for k in "SUP"},
        "mean_ms": {k: round(statistics.fmean(x for dd in days for x in per_day[k][dd]), 3) for k in "SUP"},
        "upstream_per_awake_hour": {k: round(upstream[k] / awake_h, 1) for k in "SUP"}, "awake_hours_test": round(awake_h, 1),
        "primary_P_minus_S_per_day": paired.summary([a - b for a, b in zip(mean["P"], mean["S"])]),
        "P_minus_U_per_day": paired.summary([a - b for a, b in zip(mean["P"], mean["U"])]),
        "U_minus_S_per_day": paired.summary([a - b for a, b in zip(mean["U"], mean["S"])]),
    }
    json.dump(out, open(os.path.join(ROOT, "results", "dns_sim.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
