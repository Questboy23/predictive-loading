"""predictive-loading macOS daemon. Standard library only. Runs as root under
launchd (KeepAlive). Every 2 s: watchdog, network/VPN/wake check. Every 60 s:
read the Unbound reply log, learn, prefetch predicted domains, dump the cache.

Modes:
  active       system DNS -> 127.0.0.1 / ::1 (Unbound)
  passthrough  network changed; original DNS until captive.apple.com succeeds
  bypass       VPN up; original DNS, no prefetching
  fallback     Unbound failed 3 checks in a row; original DNS
"""
import hashlib
import json
import os
import random
import re
import signal
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "predictor"))
import dnsq  # noqa: E402
from predictor import Predictor, should_act  # noqa: E402

DATA = os.environ.get("PL_DATA", ("/opt/homebrew" if os.path.isdir("/opt/homebrew") else "/usr/local") + "/var/predictive-loading")
PORT = int(os.environ.get("PL_PORT", "53"))
CAPTIVE_URL = os.environ.get("PL_CAPTIVE_URL", "http://captive.apple.com/hotspot-detect.html")
TICK = float(os.environ.get("PL_TICK", "2"))
CYCLE = float(os.environ.get("PL_CYCLE", "60"))
HOLDOUT = 0.10
LOCAL = ("127.0.0.1", "::1")
NEVER = re.compile(r"(^|\.)(captive\.apple\.com|captive\.g\.aaplimg\.com|apple\.com\.edgekey\.net)\.?$|\.local\.?$|\.arpa\.?$")
LOGLINE = re.compile(r"^\[(\d+)\] unbound\[[^\]]*\] info: (\S+) (\S+) (\S+) IN (\S+) ([\d.]+) (\d) \d+")
VPN_IF = re.compile(r"^(utun\d+|ipsec\d+|ppp\d+|tun\d+|tap\d+)\b")


def path(name):
    return os.path.join(DATA, name)


def private_write(name, text):
    """Write a data file with mode 600, atomically."""
    tmp = path(name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path(name))


def sh(*cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


# ---------------- system DNS ----------------

def services():
    out = sh("networksetup", "-listallnetworkservices")
    return [s.lstrip("*") for s in out.splitlines()[1:] if s.strip()]


def get_dns(service):
    out = sh("networksetup", "-getdnsservers", service).split()
    return [] if "aren't" in " ".join(out) or not out else out


def set_dns(service, servers):
    sh("networksetup", "-setdnsservers", service, *(servers or ["Empty"]))


def snapshot_original():
    """Saved once at enable; uninstall restores exactly this."""
    if not os.path.exists(path("original_dns.json")):
        snap = {}
        for s in services():
            servers = get_dns(s)
            # never record our own local servers as "original"
            snap[s] = [] if set(servers) <= set(LOCAL) else servers
        private_write("original_dns.json", json.dumps(snap))
    return json.load(open(path("original_dns.json")))


def point_local():
    for s in snapshot_original():
        set_dns(s, list(LOCAL))


def restore_original():
    for s, servers in snapshot_original().items():
        set_dns(s, servers)


def network_resolvers():
    """Upstream resolvers of the current network (scutil --dns), local ones excluded."""
    out, addrs = sh("scutil", "--dns"), []
    block = out.split("DNS configuration (for scoped queries)")[0]
    for chunk in block.split("resolver #"):
        if "domain   :" in chunk or "port     :" in chunk:
            continue  # supplemental or non-53 resolvers
        for m in re.finditer(r"nameserver\[\d+\] : (\S+)", chunk):
            a = m.group(1)
            if a not in LOCAL and a not in addrs:
                addrs.append(a)
    return addrs


def network_fingerprint():
    nwi = sh("scutil", "--nwi")
    vpn = any(VPN_IF.match(l.strip()) for l in nwi.splitlines()) or bool(
        re.search(r"(utun|ipsec|ppp)\d+ : flags", nwi))
    return hashlib.sha256(nwi.encode()).hexdigest(), vpn


def captive_ok():
    try:
        with urllib.request.urlopen(CAPTIVE_URL, timeout=3) as r:  # nosec B310: fixed http URL by design
            return b"Success" in r.read(2048)
    except OSError:
        return False


# ---------------- Unbound ----------------

def ctl(*args, stdin=None):
    cmd = ["unbound-control", "-c", path("unbound.conf"), *args]
    try:
        # list form, no shell; PL_DATA only moves the data directory (tests use a temp dir)
        return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=30).stdout  # nosemgrep: dangerous-subprocess-use-tainted-env-args
    except (OSError, subprocess.TimeoutExpired):
        return ""


def render_config(forwarders):
    tpl = open(os.path.join(HERE, "unbound.conf.in")).read()
    fw = "\n".join("    forward-addr: %s" % a for a in forwarders) or "    forward-addr: 1.1.1.1"
    user = os.environ.get("PL_UNBOUND_USER", "")
    text = (tpl.replace("{PORT}", str(PORT)).replace("{DATA}", DATA)
            .replace("{USERNAME}", user).replace("{FORWARD_ADDRS}", fw))
    private_write("unbound.conf", text)


def alive():
    rc, _, _ = dnsq.query("localhost", "A", "127.0.0.1", PORT, timeout=1.0)
    return rc == "NOERROR"


def health_check():
    ok_local = alive()
    rc_ex, an, _ = dnsq.query("example.com", "A", "127.0.0.1", PORT, timeout=3.0)
    rc_bad, _, _ = dnsq.query("dnssec-failed.org", "A", "127.0.0.1", PORT, timeout=5.0)
    return {"local": ok_local, "resolve": rc_ex == "NOERROR" and an > 0, "dnssec": rc_bad == "SERVFAIL"}


def versions():
    return sh("sw_vers", "-productVersion").strip() + "|" + sh("unbound", "-V").split("\n")[0]


# ---------------- the daemon ----------------

class Daemon:
    def __init__(self):
        os.makedirs(DATA, mode=0o711, exist_ok=True)
        # 711: others may open stats.json (644, aggregate numbers only) by name, never list or read the 600 files.
        os.chmod(DATA, 0o711)  # nosec B103 nosemgrep: insecure-file-permissions
        self.mode = "passthrough"
        self.fails = 0
        self.oks = 0
        self.fp = None
        self.last_wall = time.time()
        self.last_cycle = 0.0
        self.refresh_due = True
        self.st = self.load_state()
        self.pred = self.st.pop("_pred")

    # -- state --
    def load_state(self):
        st = {"upstream_ms": {}, "types": {}, "pending": {}, "samples": {"treat": [], "hold": []},
              "local_ms": 0.3, "versions": "", "started": time.time(), "health": {}}
        try:
            st.update(json.load(open(path("state.json"))))
        except (OSError, ValueError):
            pass
        st["_pred"] = Predictor()
        try:
            st["_pred"] = restore_predictor(json.load(open(path("predictor.json"))))
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return st

    def save_state(self):
        private_write("state.json", json.dumps(self.st))
        private_write("predictor.json", json.dumps(dump_predictor(self.pred)))
        s = stats(self.st)
        s.update(mode=self.mode, events=self.pred.events, bits_per_event=round(self.pred.bits_per_event(), 3))
        # Aggregate numbers only (no names), readable by `predictive-loading stats`.
        fd = os.open(path("stats.json.tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        with os.fdopen(fd, "w") as f:
            json.dump(s, f)
        os.replace(path("stats.json.tmp"), path("stats.json"))

    # -- mode changes --
    def set_mode(self, mode):
        if mode == self.mode:
            return
        log("mode %s -> %s" % (self.mode, mode))
        if mode == "active":
            point_local()
            self.refresh_due = True
        else:
            restore_original()
        self.mode = mode

    # -- 2 s tick --
    def tick(self):
        now = time.time()
        woke = now - self.last_wall > TICK * 5 + 10
        self.last_wall = now
        if alive():
            self.fails, self.oks = 0, self.oks + 1
        else:
            self.fails, self.oks = self.fails + 1, 0
        if self.fails >= 3 and self.mode != "fallback":
            self.set_mode("fallback")
            return
        fp, vpn = network_fingerprint()
        if vpn:
            self.set_mode("bypass")
            self.fp = fp
            return
        if fp != self.fp or woke:
            self.fp = fp
            if self.mode == "active":
                self.set_mode("passthrough")
            elif self.mode != "fallback":
                self.mode = "passthrough"
        if self.mode in ("passthrough", "bypass") or (self.mode == "fallback" and self.oks >= 15):
            if self.mode == "bypass":
                self.mode = "passthrough"
                restore_original()
            if captive_ok():
                self.adopt_network()

    def adopt_network(self):
        fw = network_resolvers()
        if not fw:
            return
        if fw != self.st.get("forwarders"):
            self.st["forwarders"] = fw
            render_config(fw)
            ctl("reload")
            time.sleep(0.5)
        if alive():
            self.set_mode("active")
            self.refresh_due = True

    # -- 60 s cycle --
    def cycle(self):
        self.ingest()
        v = versions()
        if v != self.st.get("versions"):
            h = health_check()
            self.st["health"], self.st["versions"] = h, v
            log("health after version change %s: %s" % (v, h))
            if not all(h.values()):
                self.set_mode("fallback")
        if self.mode == "active":
            self.prefetch(next_hour=self.refresh_due)
            self.refresh_due = False
        dump = ctl("dump_cache")
        if dump.strip():
            private_write("cache.dump", dump)
        self.save_state()

    def ingest(self):
        lp = path("unbound.log")
        if not os.path.exists(lp):
            return
        os.chmod(lp, 0o600)
        with open(lp, "r+") as f:
            lines = f.read().splitlines()
            f.seek(0)
            f.truncate()  # Unbound appends (O_APPEND), so in-place truncation is safe
        st, now = self.st, time.time()
        for line in lines:
            m = LOGLINE.match(line)
            if not m:
                continue
            ts, client, name, qtype, rcode, secs, cached = m.groups()
            if client not in LOCAL or rcode not in ("NOERROR", "NXDOMAIN"):
                continue
            letters = re.sub(r"[^A-Za-z]", "", name)
            if letters and letters.isupper():
                continue  # our own prefetch queries are sent upper-case
            d = name.lower().rstrip(".")
            if not d or NEVER.search(d):
                continue
            ms = float(secs) * 1000
            if cached == "0":
                old = st["upstream_ms"].get(d)
                st["upstream_ms"][d] = ms if old is None else 0.7 * old + 0.3 * ms
            types = st["types"].setdefault(d, [])
            if qtype in dnsq.TYPES and qtype not in types:
                types.append(qtype)
            pend = st["pending"].pop(d, None)
            if pend and now - pend[0] < 3600:
                st["samples"][pend[1]].append([int(ts), round(ms, 3)])
            lt = time.localtime(int(ts))
            self.pred.observe(d, lt.tm_hour, int(time.mktime(lt[:3] + (0, 0, 0, 0, 0, -1))) // 86400)
        for k in ("treat", "hold"):
            st["samples"][k] = st["samples"][k][-20000:]
        st["pending"] = {d: v for d, v in st["pending"].items() if now - v[0] < 3600}
        if len(st["upstream_ms"]) > 20000:  # shortcut: drop arbitrary half when huge
            st["upstream_ms"] = dict(list(st["upstream_ms"].items())[-10000:])

    def prefetch(self, next_hour=False):
        hour = time.localtime().tm_hour
        cands = self.pred.predict(hour, 25)
        if next_hour:  # wake / network change: domains likely in the next hour
            cands += self.pred.predict((hour + 1) % 24, 25)
        ups = sorted(self.st["upstream_ms"].values())
        default_up = ups[len(ups) // 2] if ups else 30.0
        done = set()
        for d, p in cands:
            if d in done or NEVER.search(d):
                continue
            done.add(d)
            t_saved = self.st["upstream_ms"].get(d, default_up)
            if next_hour:
                p = max(p, 0.05)
            if not should_act(p, t_saved, self.st["local_ms"]):
                continue
            if d in self.st["pending"]:
                continue
            group = "hold" if random.random() < HOLDOUT else "treat"  # nosec B311: experiment split
            self.st["pending"][d] = [time.time(), group]
            if group == "hold":
                continue
            for qt in self.st["types"].get(d, ["A"]):
                _, _, ms = dnsq.query(d.upper(), qt, "127.0.0.1", PORT, timeout=2.0)
                self.st["local_ms"] = 0.9 * self.st["local_ms"] + 0.1 * min(ms, 50.0)

    def run(self):
        stop = {"flag": False}

        def on_term(*_):
            stop["flag"] = True

        signal.signal(signal.SIGTERM, on_term)
        signal.signal(signal.SIGINT, on_term)
        if os.path.exists(path("cache.dump")):
            ctl("load_cache", stdin=open(path("cache.dump")).read())
        restore_original()  # start in passthrough: original DNS until checks pass
        log("started, data=%s port=%d" % (DATA, PORT))
        while not stop["flag"]:
            try:
                self.tick()
                if time.time() - self.last_cycle >= CYCLE:
                    self.last_cycle = time.time()
                    self.cycle()
            except Exception as e:  # keep the watchdog alive whatever happens
                log("error: %r" % (e,))
            time.sleep(TICK)
        dump = ctl("dump_cache")  # shutdown: keep the cache for next start
        if dump.strip():
            private_write("cache.dump", dump)
        self.save_state()
        log("stopped")


def dump_predictor(p):
    return {"v": 1, "choice": p.choice, "seen": list(p.seen), "prev1": p.prev1, "prev2": p.prev2,
            "day": p.day, "dayLoss": p.day_loss, "history": p.history, "events": p.events,
            "totalBits": p.total_bits,
            "banks": [{"scale": b.scale, "logw": b.logw,
                       "tables": [[[c, e[0], e[1], list(e[2].items())] for c, e in t.items()] for t in b.tables]}
                      for b in p.banks]}


def restore_predictor(o):
    p = Predictor()
    if o.get("v") != 1:
        return p
    p.choice, p.prev1, p.prev2, p.day = o["choice"], o["prev1"], o["prev2"], o["day"]
    p.day_loss, p.history, p.events, p.total_bits = o["dayLoss"], o["history"], o["events"], o["totalBits"]
    p.seen = {s: True for s in o["seen"]}
    for bank, b in zip(p.banks, o["banks"]):
        bank.scale, bank.logw = b["scale"], b["logw"]
        bank.tables = [{c: [n, e, dict(syms)] for c, n, e, syms in t} for t in b["tables"]]
    return p


def stats(st):
    """ms saved per day: (holdout mean - treated mean) x treated hits per day."""
    t = [ms for _, ms in st["samples"]["treat"]]
    h = [ms for _, ms in st["samples"]["hold"]]
    out = {"n_treat": len(t), "n_hold": len(h)}
    if not t or not h:
        return out
    days = max((time.time() - st["started"]) / 86400, 1 / 24)
    mt, mh = sum(t) / len(t), sum(h) / len(h)
    rng = random.Random(0)  # nosec B311: bootstrap resampling
    boots = []
    for _ in range(1000):
        bt = [t[rng.randrange(len(t))] for _ in t]
        bh = [h[rng.randrange(len(h))] for _ in h]
        boots.append((sum(bh) / len(bh) - sum(bt) / len(bt)) * len(t) / days)
    boots.sort()
    out.update(mean_ms_treat=round(mt, 2), mean_ms_hold=round(mh, 2),
               ms_saved_per_day=round((mh - mt) * len(t) / days, 1),
               ci95=[round(boots[25], 1), round(boots[974], 1)], days=round(days, 2))
    return out


if __name__ == "__main__":
    Daemon().run()
