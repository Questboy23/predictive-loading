"""Route 0: offline replay. Each user gets a fresh model that learns only from
that user's own past events (online, strictly causal). Compares the mixture
predictor to most-popular, last-successor, order-1 Markov and PPM-C.

Usage: python3 bench/replay.py [max_users_per_trace]
Writes results/route0.json.
"""
import gzip
import hashlib
import json
import math
import os
import random
import re
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "predictor"))
from predictor import Predictor  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
MIN_EVENTS = 10


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def dedupe(seq):
    out, last = [], None
    for e in seq:
        if e[0] != last:
            out.append(e)
            last = e[0]
    return out


# ---------- loaders: return {user: [(event, hour, day), ...]} ----------

def load_msnbc():
    users = {}
    with open(os.path.join(RAW, "msnbc990928.seq")) as f:
        lines = f.read().split("% Sequences:")[1].strip().splitlines()
    for i, line in enumerate(lines):
        toks = line.split()
        if toks:
            users[i] = [(t, 0, 0) for t in toks]
    return users


CLF = re.compile(r'^(\S+) \S+ \S+ \[(\d+)/(\w+)/(\d+):(\d+):(\d+):(\d+) ([-+]\d{4})\] "GET (\S+)[^"]*" (\d{3})')
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
NOT_PAGE = re.compile(r"\.(gif|jpe?g|png|xbm|ico|css|js|mpg|wav|au|zip|gz|tar|ps|pdf|txt|bmp|tif)$", re.I)


def load_clf(name):
    users = defaultdict(list)
    with gzip.open(os.path.join(RAW, name), "rt", errors="replace") as f:
        for line in f:
            m = CLF.match(line)
            if not m or m.group(10) not in ("200", "304"):
                continue
            path = m.group(9).split("?")[0].split("#")[0]
            if NOT_PAGE.search(path):
                continue
            day = int(m.group(2)) + 31 * MON.get(m.group(3), 0)
            users[m.group(1)].append((path, int(m.group(5)), day))
    return users


def load_wikispeedia():
    users = defaultdict(list)
    with tarfile.open(os.path.join(RAW, "wikispeedia_paths-and-graph.tar.gz")) as tf:
        for member in ("wikispeedia_paths-and-graph/paths_finished.tsv",
                       "wikispeedia_paths-and-graph/paths_unfinished.tsv"):
            f = tf.extractfile(member)
            for line in f.read().decode().splitlines():
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                ip, ts, path = parts[0], int(parts[1]), parts[3]
                dt = datetime.fromtimestamp(ts, timezone.utc)
                stack = []
                for a in path.split(";"):
                    if a == "<":
                        if len(stack) > 1:
                            stack.pop()
                        a = stack[-1]
                    else:
                        stack.append(a)
                    users[ip].append((ts, a, dt.hour, dt.toordinal()))
    return {u: [(a, hr, d) for _, a, hr, d in sorted(v, key=lambda r: r[0])] for u, v in users.items()}


def load_chrome():
    """Reed's own Chrome history, read locally, hashed in memory, never written."""
    src = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/History")
    if not os.path.exists(src):
        return {}, {}
    tmp = tempfile.mkdtemp()
    dst = os.path.join(tmp, "h.db")
    shutil.copy(src, dst)
    con = sqlite3.connect(dst)
    rows = con.execute("SELECT v.visit_time, u.url FROM visits v JOIN urls u ON u.id=v.url ORDER BY v.visit_time").fetchall()
    con.close()
    shutil.rmtree(tmp)
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    eastern = timezone(timedelta(hours=-5))  # shortcut: fixed EST offset, ignores DST
    domains, origins = [], defaultdict(list)
    for vt, url in rows:
        m = re.match(r"^(https?)://([^/?#]+)([^?#]*)", url)
        if not m:
            continue
        dt = (epoch + timedelta(microseconds=vt)).astimezone(eastern)
        domains.append((h(m.group(2)), dt.hour, dt.toordinal()))
        origins[h(m.group(1) + m.group(2))].append((h(m.group(3) or "/"), dt.hour, dt.toordinal()))
    return {"me": domains}, dict(origins)


# ---------- baselines: each returns (top1, p_of_x) then learns ----------

class MostPopular:
    def __init__(self):
        self.c, self.N = {}, 0

    def observe(self, x, hour, day):
        top = max(self.c, key=lambda s: (self.c[s], s)) if self.c else ""
        k = len(self.c)
        if x in self.c:
            p = (self.c[x] + 0.5) / (self.N + 0.5 * (k + 1))
        else:
            p = 0.5 / (self.N + 0.5 * (k + 1))
        self.c[x] = self.c.get(x, 0) + 1
        self.N += 1
        return top, p


class LastSuccessor:
    def __init__(self):
        self.nxt, self.prev = {}, None

    def observe(self, x, hour, day):
        top = self.nxt.get(self.prev, "")
        if self.prev is not None:
            self.nxt[self.prev] = x
        self.prev = x
        return top, None


class Markov1:
    """Order-1 Markov with the same KT-with-escape estimator as the mixture,
    no decay. Top-1 backs off to most popular in an unseen context."""

    def __init__(self):
        self.t, self.pop, self.prev, self.seen = {}, MostPopular(), None, set()

    def observe(self, x, hour, day):
        ctx = self.t.get(self.prev)
        g = len(self.seen)
        ptop, _ = self.pop.observe(x, hour, day)
        if ctx:
            syms = ctx["s"]
            N, e, k = ctx["N"], ctx["e"], len(syms)
            denom = N + e + 0.5 * (k + 1)
            top = max(syms, key=lambda s: (syms[s], s))
            if x in syms:
                p = (syms[x] + 0.5) / denom
            else:
                p = ((e + 0.5) / denom) / (g - k + 1)
        else:
            top, p = ptop, 1.0 / (g + 1)
        c = self.t.setdefault(self.prev, {"N": 0, "e": 0, "s": {}})
        if x in c["s"]:
            c["N"] += 1
            c["s"][x] += 1
        else:
            c["e"] += 1
            c["s"][x] = 0
        self.seen.add(x)
        self.prev = x
        return top, p


class PPMC:
    """PPM order 2, escape method C, with exclusion; order -1 uniform over seen+novel."""

    def __init__(self, order=2):
        self.order, self.t, self.hist, self.seen = order, {}, [], []

    def dist(self):
        probs, excl, mass = {}, set(), 1.0
        for o in range(min(self.order, len(self.hist)), -1, -1):
            ctx = tuple(self.hist[len(self.hist) - o:]) if o else ()
            c = self.t.get(ctx)
            if not c:
                continue
            items = {s: n for s, n in c.items() if s not in excl}
            if not items:
                continue
            N, q = sum(items.values()), len(items)
            for s, n in items.items():
                probs[s] = probs.get(s, 0.0) + mass * n / (N + q)
            excl.update(items)
            mass *= q / (N + q)
        rest = [s for s in self.seen if s not in excl]
        share = mass / (len(rest) + 1)
        for s in rest:
            probs[s] = probs.get(s, 0.0) + share
        return probs, share

    def observe(self, x, hour, day):
        probs, novel = self.dist()
        top = max(probs, key=lambda s: (probs[s], s)) if probs else ""
        p = probs.get(x, novel)
        for o in range(0, min(self.order, len(self.hist)) + 1):
            ctx = tuple(self.hist[len(self.hist) - o:]) if o else ()
            c = self.t.setdefault(ctx, {})
            c[x] = c.get(x, 0) + 1
        if x not in self.seen:
            self.seen.append(x)
        self.hist.append(x)
        return top, p


class Mixture:
    def __init__(self):
        self.p = Predictor()

    def observe(self, x, hour, day):
        return self.p.observe(x, hour, day)


METHODS = {"mixture": Mixture, "most_popular": MostPopular, "last_successor": LastSuccessor,
           "markov1": Markov1, "ppm_c": PPMC}


def run_user(seq):
    """Returns {day: {method: [hits, bits, n]}} so a single long trace can be
    bootstrapped over days instead of users."""
    res = defaultdict(lambda: {m: [0, 0.0, 0] for m in METHODS})
    for name, cls in METHODS.items():
        m = cls()
        for x, hr, d in seq:
            top, p = m.observe(x, hr, d)
            r = res[d][name]
            r[0] += top == x
            if p is not None:
                r[1] -= math.log2(p)
            r[2] += 1
    return dict(res)


def collapse(days):
    out = {m: [0, 0.0, 0] for m in METHODS}
    for d in days.values():
        for m in METHODS:
            for i in range(3):
                out[m][i] += d[m][i]
    return out


def bootstrap(per_user, a, b, key, iters=1000, seed=0):
    """95% CI over users of (a - b) for key in {'hit','bits'}; event weighted."""
    rng = random.Random(seed)
    idx = 0 if key == "hit" else 1
    diffs = []
    users = list(per_user)
    for _ in range(iters):
        s = [users[rng.randrange(len(users))] for _ in users]
        n = sum(u[a][2] for u in s)
        diffs.append((sum(u[a][idx] for u in s) - sum(u[b][idx] for u in s)) / n)
    diffs.sort()
    return diffs[int(0.025 * iters)], diffs[int(0.975 * iters)]


def evaluate(name, users, max_users):
    seqs = [dedupe(v) for v in users.values()]
    seqs = [s for s in seqs if len(s) >= MIN_EVENTS]
    rng = random.Random(42)
    rng.shuffle(seqs)
    # The first 30 shuffled users were the smoke-test sample used while fixing
    # the escape estimator; they are excluded so results come from untouched users.
    seqs = seqs[30:30 + max_users] if len(seqs) > 60 else seqs
    t0 = time.time()
    runs = [run_user(s) for s in seqs]
    if len(runs) == 1:
        per_user = list(runs[0].values())  # bootstrap units = days
    else:
        per_user = [collapse(r) for r in runs]
    out = {"trace": name, "users": len(runs), "boot_units": len(per_user), "events": sum(len(s) for s in seqs),
           "seconds": round(time.time() - t0, 1), "methods": {}}
    for mname in METHODS:
        H = sum(u[mname][0] for u in per_user)
        B = sum(u[mname][1] for u in per_user)
        N = sum(u[mname][2] for u in per_user)
        out["methods"][mname] = {"top1": H / N, "bits": None if mname == "last_successor" else B / N}
    out["ci_bits_mix_minus_markov1"] = bootstrap(per_user, "mixture", "markov1", "bits")
    out["ci_hit_mix_minus_markov1"] = bootstrap(per_user, "mixture", "markov1", "hit")
    out["ci_bits_mix_minus_ppmc"] = bootstrap(per_user, "mixture", "ppm_c", "bits")
    out["ci_hit_mix_minus_ppmc"] = bootstrap(per_user, "mixture", "ppm_c", "hit")
    print(json.dumps(out), flush=True)
    return out


def main():
    max_users = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    results = []
    chrome_domains, chrome_origins = load_chrome()
    traces = [("msnbc", load_msnbc), ("nasa_jul95", lambda: load_clf("NASA_access_log_Jul95.gz")),
              ("clarknet_aug28", lambda: load_clf("clarknet_access_log_Aug28.gz")),
              ("wikispeedia", load_wikispeedia),
              ("recorded_chrome_domains", lambda: chrome_domains),
              ("recorded_chrome_paths_per_origin", lambda: chrome_origins)]
    for name, loader in traces:
        users = loader()
        if users:
            results.append(evaluate(name, users, max_users))
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "route0.json"), "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
