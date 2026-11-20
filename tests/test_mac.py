"""macOS safety tests. Runs the real Unbound and the real daemon code as the
current user on port 5300, with fake networksetup / scutil / launchctl on PATH
and a fake captive-portal server. Needs network access for upstream lookups.

Scenarios: start-up switch-over, simulated crash, fake captive portal, VPN
toggle, network switch, stale record, uninstall, file modes, LAN exposure,
DNSSEC failure, own-query filtering and holdout bookkeeping.
"""
import http.server
import json
import os
import re
import shutil
import socket
import socketserver
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="pl-mac-")
DATA = os.path.join(TMP, "data")
FAKE = os.path.join(TMP, "fake")
BIN = os.path.join(TMP, "bin")
PORT = 5300
os.makedirs(FAKE)
os.makedirs(BIN)

# Real upstream resolvers of this machine, read before PATH is faked.
REAL_DNS = subprocess.run(["scutil", "--dns"], capture_output=True, text=True).stdout
UPSTREAM = []
for chunk in REAL_DNS.split("DNS configuration (for scoped queries)")[0].split("resolver #"):
    if "domain   :" in chunk or "port     :" in chunk:
        continue
    for a in re.findall(r"nameserver\[\d+\] : (\S+)", chunk):
        if a not in ("127.0.0.1", "::1") and a not in UPSTREAM:
            UPSTREAM.append(a)
UPSTREAM = UPSTREAM or ["1.1.1.1"]


def scutil_dns(addrs):
    body = "".join("  nameserver[%d] : %s\n" % (i, a) for i, a in enumerate(addrs))
    return "DNS configuration\n\nresolver #1\n%s  if_index : 12 (en0)\n\nresolver #2\n  domain   : local\n  options  : mdns\n" % body


NWI_WIFI = "Network information\n\nIPv4 network interface information\n     en0 : flags      : 0x5 (IPv4,DNS)\n           address    : 10.0.0.%d\n"
NWI_VPN = NWI_WIFI + "   utun4 : flags      : 0x5 (IPv4,DNS)\n           address    : 10.8.0.2\n"


def fake(name, text):
    with open(os.path.join(FAKE, name), "w") as f:
        f.write(text)


FAKE_SCRIPTS = {
    "networksetup": r'''#!/bin/sh
D="%s"
case "$1" in
  -listallnetworkservices) echo "An asterisk (*) denotes that a network service is disabled."; cat "$D/services";;
  -getdnsservers) f="$D/dns_$(echo "$2" | tr ' ' _)"; if [ -s "$f" ]; then cat "$f"; else echo "There aren't any DNS Servers set on $2."; fi;;
  -setdnsservers) svc="$2"; shift 2; f="$D/dns_$(echo "$svc" | tr ' ' _)"; if [ "$1" = Empty ]; then : > "$f"; else printf '%%s\n' "$@" > "$f"; fi;;
esac
''' % FAKE,
    "scutil": r'''#!/bin/sh
D="%s"
case "$1" in --dns) cat "$D/scutil_dns";; --nwi) cat "$D/scutil_nwi";; esac
''' % FAKE,
    "launchctl": '#!/bin/sh\necho "$@" >> "%s/launchctl.log"\n' % FAKE,
}
for n, body in FAKE_SCRIPTS.items():
    p = os.path.join(BIN, n)
    with open(p, "w") as f:
        f.write(body)
    os.chmod(p, 0o755)


class Captive(http.server.BaseHTTPRequestHandler):
    portal = False

    def do_GET(self):
        body = b"<HTML><BODY>Sign in to Campus WiFi</BODY></HTML>" if Captive.portal else \
            b"<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class StaleDNS(threading.Thread):
    """Answers every A query with 192.0.2.10, TTL 1, until silenced."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.silent = False

    def run(self):
        while True:
            data, addr = self.sock.recvfrom(4096)
            if self.silent:
                continue
            qend = 12
            while data[qend] != 0:
                qend += data[qend] + 1
            q = data[12:qend + 5]
            is_a = struct.unpack(">H", data[qend + 1:qend + 3])[0] == 1
            hdr = data[:2] + struct.pack(">HHHHH", 0x8180, 1, int(is_a), 0, 0)
            ans = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 1, 4) + bytes([192, 0, 2, 10]) if is_a else b""
            self.sock.sendto(hdr + q + ans, addr)


STALE = StaleDNS()
STALE.start()
CAPTIVE = socketserver.TCPServer(("127.0.0.1", 0), Captive)
threading.Thread(target=CAPTIVE.serve_forever, daemon=True).start()

os.environ.update(PL_DATA=DATA, PL_PORT=str(PORT), PL_TICK="0.05", PL_CYCLE="3600",
                  PL_CAPTIVE_URL="http://127.0.0.1:%d/hotspot-detect.html" % CAPTIVE.server_address[1],
                  PL_LAUNCHD_DIR=FAKE, PATH=BIN + ":" + os.environ["PATH"])
sys.path.insert(0, os.path.join(ROOT, "mac", "lib"))
import daemon  # noqa: E402
import dnsq  # noqa: E402

TEMPLATE = os.path.join(ROOT, "mac", "lib", "unbound.conf.in")
_orig_render = daemon.render_config


def render_with_test_zone(forwarders):
    """Real template plus an insecure test zone served by the stale-record server."""
    _orig_render(forwarders)
    p = daemon.path("unbound.conf")
    text = open(p).read().replace("server:\n", 'server:\n    domain-insecure: "plstale.test."\n'
                                  '    local-zone: "test." nodefault\n    do-not-query-localhost: no\n', 1)
    text += '\nforward-zone:\n    name: "plstale.test."\n    forward-addr: 127.0.0.1@%d\n' % STALE.port
    with open(p, "w") as f:
        f.write(text)
    os.chmod(p, 0o600)


daemon.render_config = render_with_test_zone


class Unbound:
    proc = None

    @classmethod
    def start(cls):
        cls.proc = subprocess.Popen(["unbound", "-d", "-c", daemon.path("unbound.conf")],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if cls.proc.poll() is not None:
                raise RuntimeError("unbound exited (port %d busy?)" % PORT)
            if daemon.alive():
                return
            time.sleep(0.1)
        raise RuntimeError("unbound did not start")

    @classmethod
    def stop(cls):
        if cls.proc:
            cls.proc.kill()
            cls.proc.wait()
            cls.proc = None


def dns_of(service):
    p = os.path.join(FAKE, "dns_" + service.replace(" ", "_"))
    return open(p).read().split() if os.path.exists(p) else []


def tick(d, n=1):
    for _ in range(n):
        d.tick()


class MacSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake("services", "Wi-Fi\nUSB Ethernet\n")
        fake("dns_Wi-Fi", "")
        fake("dns_USB_Ethernet", "9.9.9.9\n149.112.112.112\n")
        fake("scutil_dns", scutil_dns(UPSTREAM))
        fake("scutil_nwi", NWI_WIFI % 5)
        os.makedirs(DATA, mode=0o700)
        daemon.snapshot_original()
        daemon.render_config(UPSTREAM)
        subprocess.run(["unbound-anchor", "-a", daemon.path("root.key")])
        fd = os.open(daemon.path("unbound.log"), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        Unbound.start()
        cls.d = daemon.Daemon()
        daemon.restore_original()

    @classmethod
    def tearDownClass(cls):
        Unbound.stop()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        Captive.portal = False
        fake("scutil_nwi", NWI_WIFI % 5)
        if not Unbound.proc:
            Unbound.start()
        tick(self.d, 20)
        self.assertEqual(self.d.mode, "active")

    def test_01_startup_switches_to_local(self):
        self.assertEqual(dns_of("Wi-Fi"), ["127.0.0.1", "::1"])
        self.assertEqual(dns_of("USB Ethernet"), ["127.0.0.1", "::1"])

    def test_02_crash_restores_dns_then_recovers(self):
        Unbound.stop()
        tick(self.d, 2)
        self.assertEqual(self.d.mode, "active")  # 2 failures: not yet
        tick(self.d, 1)
        self.assertEqual(self.d.mode, "fallback")
        self.assertEqual(dns_of("Wi-Fi"), [])
        self.assertEqual(dns_of("USB Ethernet"), ["9.9.9.9", "149.112.112.112"])
        Unbound.start()
        tick(self.d, 16)
        self.assertEqual(self.d.mode, "active")

    def test_03_captive_portal_passthrough(self):
        Captive.portal = True
        fake("scutil_nwi", NWI_WIFI % 77)  # joined another network
        tick(self.d, 10)
        self.assertEqual(self.d.mode, "passthrough")
        self.assertEqual(dns_of("Wi-Fi"), [])
        Captive.portal = False
        tick(self.d, 1)
        self.assertEqual(self.d.mode, "active")

    def test_04_vpn_full_bypass(self):
        fake("scutil_nwi", NWI_VPN % 5)
        tick(self.d, 3)
        self.assertEqual(self.d.mode, "bypass")
        self.assertEqual(dns_of("USB Ethernet"), ["9.9.9.9", "149.112.112.112"])
        before = self.d.st["pending"].copy()
        self.d.cycle()  # no prefetching while bypassed
        self.assertEqual(self.d.st["pending"], before)
        fake("scutil_nwi", NWI_WIFI % 5)
        tick(self.d, 2)
        self.assertEqual(self.d.mode, "active")

    def test_05_network_switch_updates_forwarders(self):
        new = list(reversed(UPSTREAM)) + ["1.1.1.1"]
        fake("scutil_dns", scutil_dns(new))
        fake("scutil_nwi", NWI_WIFI % 99)
        tick(self.d, 2)
        conf = open(daemon.path("unbound.conf")).read()
        self.assertIn("forward-addr: 1.1.1.1", conf)
        self.assertEqual(self.d.mode, "active")
        rc, an, _ = dnsq.query("example.com", "A", "127.0.0.1", PORT, timeout=5)
        self.assertEqual(rc, "NOERROR")
        fake("scutil_dns", scutil_dns(UPSTREAM))

    def test_06_stale_record_served_within_400ms(self):
        rc, an, _ = dnsq.query("www.plstale.test", "A", "127.0.0.1", PORT, timeout=3)
        self.assertEqual((rc, an), ("NOERROR", 1), "fresh answer")
        STALE.silent = True
        time.sleep(2.2)  # TTL 1 has expired
        rc, an, ms = dnsq.query("www.plstale.test", "A", "127.0.0.1", PORT, timeout=3)
        STALE.silent = False
        self.assertEqual((rc, an), ("NOERROR", 1))
        self.assertLess(ms, 700)

    def test_07_dnssec_failure_is_servfail(self):
        h = daemon.health_check()
        self.assertEqual(h, {"local": True, "resolve": True, "dnssec": True})

    def test_08_not_reachable_from_lan(self):
        conf = open(daemon.path("unbound.conf")).read()
        ifaces = re.findall(r"^\s*interface: (\S+)", conf, re.M)
        self.assertEqual(sorted(ifaces), sorted(["127.0.0.1@%d" % PORT, "::1@%d" % PORT]))
        self.assertIn("access-control: 0.0.0.0/0 refuse", conf)
        lan = subprocess.run(["/usr/sbin/ipconfig", "getifaddr", "en0"], capture_output=True, text=True).stdout.strip()
        if lan:
            rc, _, _ = dnsq.query("example.com", "A", lan, PORT, timeout=1)
            self.assertIsNone(rc)

    def test_09_learns_prefetches_and_filters_own_queries(self):
        names = ["example.com", "example.org", "example.net", "iana.org"] * 6
        for n in names:
            dnsq.query(n, "A", "127.0.0.1", PORT, timeout=5)
        dnsq.query("captive.apple.com", "A", "127.0.0.1", PORT, timeout=5)
        before = self.d.pred.events
        self.d.cycle()
        self.assertGreaterEqual(self.d.pred.events - before, len(names) - 1)
        self.assertNotIn("captive.apple.com", self.d.pred.seen)
        self.assertTrue(self.d.st["pending"])  # predictions were acted on or held out
        groups = {g for _, g in self.d.st["pending"].values()}
        self.assertTrue(groups <= {"treat", "hold"})
        # our own upper-case prefetch queries must not be learned as events
        events = self.d.pred.events
        self.d.cycle()
        self.assertEqual(self.d.pred.events, events)
        for n in names[:4]:
            dnsq.query(n, "A", "127.0.0.1", PORT, timeout=5)
        self.d.cycle()
        n = len(self.d.st["samples"]["treat"]) + len(self.d.st["samples"]["hold"])
        self.assertGreater(n, 0)

    def test_10_data_files_mode_600(self):
        self.d.cycle()
        for name in ("unbound.log", "state.json", "predictor.json", "original_dns.json", "unbound.conf", "cache.dump"):
            p = daemon.path(name)
            self.assertTrue(os.path.exists(p), name)
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600, name)
        self.assertEqual(stat.S_IMODE(os.stat(DATA).st_mode), 0o700)
        s = json.load(open(daemon.path("stats.json")))
        self.assertFalse(any(isinstance(v, str) and "." in v and v != s.get("mode") for v in s.values()))

    def test_11_cache_dump_reload(self):
        dnsq.query("example.com", "A", "127.0.0.1", PORT, timeout=5)
        self.d.cycle()
        self.assertIn("example.com", open(daemon.path("cache.dump")).read())
        Unbound.stop()
        Unbound.start()
        daemon.ctl("load_cache", stdin=open(daemon.path("cache.dump")).read())
        self.assertIn("example.com", daemon.ctl("dump_cache"))

    def test_99_uninstall_restores_exactly_and_deletes(self):
        import cli
        for label in cli.LABELS:
            open(cli.plist_path(label), "w").write("x")
        Unbound.stop()
        cli.root_main("uninstall")
        self.assertEqual(dns_of("Wi-Fi"), [])
        self.assertEqual(dns_of("USB Ethernet"), ["9.9.9.9", "149.112.112.112"])
        self.assertFalse(os.path.exists(DATA))
        for label in cli.LABELS:
            self.assertFalse(os.path.exists(cli.plist_path(label)))
        self.assertIn("bootout system/org.predictive-loading.daemon", open(os.path.join(FAKE, "launchctl.log")).read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
