"""Builds RESULTS.md from results/*.json(l). Every number in the paper is read
back from RESULTS.md by paper/make_numbers.py, so this file is the single
source. Usage: python3 bench/make_results.py
"""
import json
import os
import random
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results")
LINES, KV = [], {}
TRACE_NAMES = {"msnbc": "MSNBC (UCI)", "nasa_jul95": "NASA-HTTP Jul 1995", "clarknet_aug28": "ClarkNet Aug 1995",
               "wikispeedia": "Wikispeedia (SNAP)", "recorded_chrome_domains": "Recorded: domains",
               "recorded_chrome_paths_per_origin": "Recorded: paths per site"}
METHOD_NAMES = {"mixture": "Mixture (ours)", "ppm_c": "PPM-C", "markov1": "Order-1 Markov",
                "last_successor": "Last successor", "most_popular": "Most popular"}
PROFILES = {10: "home Wi-Fi (10 ms)", 60: "busy campus Wi-Fi (60 ms)", 150: "poor Wi-Fi (150 ms)"}


def kv(key, value):
    KV[key] = value
    return value


def w(s=""):
    LINES.append(s)


def load(name):
    p = os.path.join(R, name)
    return json.load(open(p)) if os.path.exists(p) else None


def jsonl(name):
    p = os.path.join(R, name)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def p75(xs):
    s = sorted(xs)
    return s[int(0.75 * (len(s) - 1))]


def boot(xs, stat=statistics.median, iters=2000, seed=0):
    rng = random.Random(seed)
    v = sorted(stat([xs[rng.randrange(len(xs))] for _ in xs]) for _ in range(iters))
    return v[int(0.025 * iters)], v[int(0.975 * iters)]


def f(x, nd=1):
    return "%.*f" % (nd, x)


def route0():
    rows = [json.loads(l) for l in open(os.path.join(R, "route0.log")) if l.startswith("{")]
    w("## Route 0: offline replay (runs first)")
    w()
    w("Each user gets a fresh model that learns only from that user's own past events. "
      "Top-1 = share of events where the single best guess was right. Bits = log-loss per event (lower is better). "
      "CI = 95% bootstrap over users (over days for the single recorded user).")
    w()
    w("| Trace | Users | Events | " + " | ".join("%s top-1 / bits" % METHOD_NAMES[m] for m in METHOD_NAMES) + " |")
    w("|" + "---|" * (3 + len(METHOD_NAMES)))
    for r in rows:
        t = r["trace"]
        cells = []
        for m in METHOD_NAMES:
            v = r["methods"][m]
            kv("r0.%s.%s.top1" % (t, m), f(100 * v["top1"]))
            if v["bits"] is not None:
                kv("r0.%s.%s.bits" % (t, m), f(v["bits"], 2))
            cells.append("%s%% / %s" % (f(100 * v["top1"]), "n/a" if v["bits"] is None else f(v["bits"], 2)))
        kv("r0.%s.users" % t, str(r["users"]))
        kv("r0.%s.events" % t, "{:,}".format(r["events"]))
        w("| %s | %s | %s | %s |" % (TRACE_NAMES[t], r["users"], "{:,}".format(r["events"]), " | ".join(cells)))
    w()
    w("| Trace | Bits: mixture minus Markov-1 (CI) | Top-1 pts: mixture minus Markov-1 (CI) | Bits: mixture minus PPM-C (CI) | Top-1 pts: mixture minus PPM-C (CI) |")
    w("|---|---|---|---|---|")
    wins_m = wins_p = 0
    for r in rows:
        t = r["trace"]
        a, b = r["ci_bits_mix_minus_markov1"]
        c, d = r["ci_hit_mix_minus_markov1"]
        e, g = r["ci_bits_mix_minus_ppmc"]
        h, i = r["ci_hit_mix_minus_ppmc"]
        wins_m += b < 0
        wins_p += g < 0
        for k, (lo, hi) in {"bm": (a, b), "hm": (100 * c, 100 * d), "bp": (e, g), "hp": (100 * h, 100 * i)}.items():
            kv("r0.%s.ci.%s.lo" % (t, k), f(lo, 2))
            kv("r0.%s.ci.%s.hi" % (t, k), f(hi, 2))
        w("| %s | [%s, %s] | [%s, %s] | [%s, %s] | [%s, %s] |" % (TRACE_NAMES[t], f(a, 2), f(b, 2), f(100 * c, 1), f(100 * d, 1),
                                                                 f(e, 2), f(g, 2), f(100 * h, 1), f(100 * i, 1)))
    kv("r0.ntraces", str(len(rows)))
    kv("r0.wins_markov_bits", str(wins_m))
    kv("r0.wins_ppmc_bits", str(wins_p))
    w()
    w("Kill test: mixture bits below order-1 Markov with CI below 0 on %d of %d traces (threshold 4)." % (wins_m, len(rows)))
    w()


def route1():
    d = load("route1.json")
    if not d:
        return
    w("## Route 1: DNS lookup time, Tranco top %d (dnspyre)" % d["names"])
    w()
    w("%d rounds, condition order shuffled each round, %d s between rounds. Round 1 is cold for every condition." % (d["rounds"], d["wait_s"]))
    w()
    w("| Phase | Condition | n | Median ms (95% CI) | p75 ms (95% CI) | Mean ms |")
    w("|---|---|---|---|---|---|")
    names = {"system_default": "System default (network resolver)", "unbound_alone": "Unbound alone (own prefetch)",
             "unbound_plus_predictor": "Unbound + predictor"}
    for phase in ("cold", "warm"):
        for c, s in d[phase].items():
            for k in ("median_ms", "p75_ms", "mean_ms", "n"):
                kv("r1.%s.%s.%s" % (phase, c, k), str(s[k]))
            w("| %s | %s | %d | %s [%s, %s] | %s [%s, %s] | %s |" % (phase, names[c], s["n"], s["median_ms"], s["median_ci95"][0],
                                                                 s["median_ci95"][1], s["p75_ms"], s["p75_ci95"][0], s["p75_ci95"][1], s["mean_ms"]))
    kv("r1.rounds", str(d["rounds"]))
    kv("r1.wait", str(d["wait_s"]))
    st = d.get("daemon_stats", {})
    if "ms_saved_per_day" in st:
        w()
        w("Daemon holdout during Route 1: prefetched names %s ms (n=%d) vs random 10%% holdout %s ms (n=%d)." % (
            st["mean_ms_treat"], st["n_treat"], st["mean_ms_hold"], st["n_hold"]))
        kv("r1.hold.treat", str(st["mean_ms_treat"]))
        kv("r1.hold.hold", str(st["mean_ms_hold"]))
        kv("r1.hold.ntreat", str(st["n_treat"]))
        kv("r1.hold.nhold", str(st["n_hold"]))
    w()


def route2():
    rows = [r for r in jsonl("route2.jsonl") if "error" not in r and r.get("next")]
    errs = [r for r in jsonl("route2.jsonl") if "error" in r]
    if not rows:
        return
    w("## Route 2: page loads in Chrome (browsertime), 2x2 at three Wi-Fi profiles")
    w()
    w("Rows: Mac tool off/on x extension off/on. Home = home page load. Next = the person waits for the linked page "
      "(loadEventEnd minus activationStart). %d measured visit pairs, %d site errors excluded." % (len(rows), len(errs)))
    w()
    w("| Profile | Extension | Mac tool | n | Home median ms | Home p75 | Next median ms (95% CI) | Next p75 | Next served preloaded |")
    w("|---|---|---|---|---|---|---|---|---|")
    kv("r2.n", str(len(rows)))
    kv("r2.errors", str(len(errs)))
    for rtt in (10, 60, 150):
        for ext in ("off", "on"):
            for mode in ("off", "on"):
                cell = [r for r in rows if r["rtt"] == rtt and r["ext"] == ext and r["mode"] == mode]
                if not cell:
                    continue
                home = [r["home"]["waited"] for r in cell]
                nxt = [r["next"]["waited"] for r in cell]
                pre = sum(1 for r in cell if r["next"]["activationStart"] > 0 or r["next"]["deliveryType"] == "navigational-prefetch")
                lo, hi = boot(nxt)
                key = "r2.%d.%s.%s" % (rtt, ext, mode)
                kv(key + ".n", str(len(cell)))
                kv(key + ".home", f(statistics.median(home), 0))
                kv(key + ".next", f(statistics.median(nxt), 0))
                kv(key + ".pre", str(pre))
                w("| %s | %s | %s | %d | %s | %s | %s [%s, %s] | %s | %d |" % (PROFILES[rtt], ext, mode, len(cell), f(statistics.median(home), 0),
                                                                     f(p75(home), 0), f(statistics.median(nxt), 0), f(lo, 0), f(hi, 0), f(p75(nxt), 0), pre))
    w()
    w("Paired effects (same site): Mac tool on minus off on home load; extension on minus off on next-page wait. Negative = faster.")
    w()
    w("| Profile | Mac tool effect, home, median ms (95% CI), n | Extension effect, next page, median ms (95% CI), n |")
    w("|---|---|---|")
    for rtt in (10, 60, 150):
        mac = []
        for ext in ("off", "on"):
            by = {}
            for r in rows:
                if r["rtt"] == rtt and r["ext"] == ext:
                    by.setdefault(r["site"], {})[r["mode"]] = r["home"]["waited"]
            mac += [v["on"] - v["off"] for v in by.values() if len(v) == 2]
        ex = []
        for mode in ("off", "on"):
            by = {}
            for r in rows:
                if r["rtt"] == rtt and r["mode"] == mode:
                    by.setdefault(r["site"], {})[r["ext"]] = r["next"]["waited"]
            ex += [v["on"] - v["off"] for v in by.values() if len(v) == 2]
        cells = []
        for name, xs in (("mac", mac), ("ext", ex)):
            if xs:
                lo, hi = boot(xs)
                kv("r2.%d.eff.%s" % (rtt, name), f(statistics.median(xs), 0))
                kv("r2.%d.eff.%s.lo" % (rtt, name), f(lo, 0))
                kv("r2.%d.eff.%s.hi" % (rtt, name), f(hi, 0))
                kv("r2.%d.eff.%s.n" % (rtt, name), str(len(xs)))
                cells.append("%s [%s, %s], n=%d" % (f(statistics.median(xs), 0), f(lo, 0), f(hi, 0), len(xs)))
            else:
                cells.append("n/a")
        w("| %s | %s | %s |" % (PROFILES[rtt], cells[0], cells[1]))
    w()


def route3():
    d = load("route3.json")
    if not d:
        return
    w("## Route 3: curl to %d API hosts, Mac tool off/on" % d["hosts"])
    w()
    w("%d rounds, host and mode order shuffled, %d s between rounds; %d failed requests excluded." % (d["rounds"], d["wait_s"], d["failed"]))
    w()
    w("| Phase | Mac tool | n | Connect incl. DNS, median ms (95% CI) | Total median ms (95% CI) | Total p75 ms |")
    w("|---|---|---|---|---|---|")
    for phase in ("cold", "warm"):
        for m in ("off", "on"):
            c, t = d[phase][m]["connect_ms"], d[phase][m]["total_ms"]
            kv("r3.%s.%s.connect" % (phase, m), str(c["median_ms"]))
            kv("r3.%s.%s.total" % (phase, m), str(t["median_ms"]))
            kv("r3.%s.%s.n" % (phase, m), str(t["n"]))
            w("| %s | %s | %d | %s [%s, %s] | %s [%s, %s] | %s |" % (phase, m, t["n"], c["median_ms"], c["median_ci95"][0], c["median_ci95"][1],
                                                                 t["median_ms"], t["median_ci95"][0], t["median_ci95"][1], t["p75_ms"]))
        pd = d[phase]["paired_total_off_minus_on"]
        kv("r3.%s.paired" % phase, str(pd["median_ms"]))
        kv("r3.%s.paired.lo" % phase, str(pd["median_ci95"][0]))
        kv("r3.%s.paired.hi" % phase, str(pd["median_ci95"][1]))
        kv("r3.%s.paired.n" % phase, str(pd["n"]))
    w()
    w("Paired total time, off minus on (positive = Mac tool faster): cold median %s ms [%s, %s] (n=%s), warm median %s ms [%s, %s] (n=%s)." % (
        KV["r3.cold.paired"], KV["r3.cold.paired.lo"], KV["r3.cold.paired.hi"], KV["r3.cold.paired.n"],
        KV["r3.warm.paired"], KV["r3.warm.paired.lo"], KV["r3.warm.paired.hi"], KV["r3.warm.paired.n"]))
    w()


def pages():
    rows = [r for r in jsonl("pages_bench.jsonl") if "error" not in r]
    errs = [r for r in jsonl("pages_bench.jsonl") if "error" in r]
    if not rows:
        return
    w("## Benchmark: page preloading methods (60 ms RTT, user hovers 300 ms then clicks)")
    w()
    w("| Method | n | Next page wait, median ms (95% CI) | p75 ms | Served preloaded | Speculative requests seen |")
    w("|---|---|---|---|---|---|")
    names = {"default": "Chrome default", "instantpage": "instant.page 5.2.0", "quicklink": "Quicklink 3.0.1", "extension": "Predictive Loading (ours)"}
    for m in names:
        cell = [r for r in rows if r["method"] == m]
        if not cell:
            continue
        xs = [r["waited"] for r in cell]
        pre = sum(1 for r in cell if r["activationStart"] > 0 or r["deliveryType"] in ("navigational-prefetch", "cache"))
        lo, hi = boot(xs)
        kv("pb.%s.n" % m, str(len(cell)))
        kv("pb.%s.med" % m, f(statistics.median(xs), 0))
        kv("pb.%s.pre" % m, str(pre))
        kv("pb.%s.spec" % m, str(sum(r["speculativeRequests"] for r in cell)))
        w("| %s | %d | %s [%s, %s] | %s | %d | %d |" % (names[m], len(cell), f(statistics.median(xs), 0), f(lo, 0), f(hi, 0),
                                                    f(p75(xs), 0), pre, sum(r["speculativeRequests"] for r in cell)))
    w()
    w("%d runs failed (site errors, link not found) and are excluded." % len(errs))
    kv("pb.errors", str(len(errs)))
    w()


def tests():
    t = load("tests.json")
    if not t:
        return
    w("## Tests")
    w()
    for k, v in t.items():
        kv("t.%s" % k, str(v))
        w("- %s: %s" % (k, v))
    w()


def main():
    w("# RESULTS")
    w()
    w("Generated by `bench/make_results.py` from `results/`. Do not edit by hand.")
    w()
    for fn in (route0, route1, route2, route3, pages, tests):
        fn()
    w("## Machine-readable values")
    w()
    w("```")
    for k in sorted(KV):
        w("%s = %s" % (k, KV[k]))
    w("```")
    open(os.path.join(ROOT, "RESULTS.md"), "w").write("\n".join(LINES) + "\n")
    print("RESULTS.md: %d values" % len(KV))


if __name__ == "__main__":
    main()
