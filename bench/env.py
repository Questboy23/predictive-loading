"""Start/stop the unprivileged benchmark environment:
  Unbound (real config) on 127.0.0.1:5300 as the current user,
  the real daemon (60 s cycle shortened to 10 s) with a fake networksetup so
  the Mac's DNS settings are never touched, and the SOCKS5 proxy on 1080.
Usage: python3 bench/env.py start|stop [--no-daemon]
"""
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser(os.environ.get("PL_BENCH_BASE", "~/.cache/pl-bench"))
DATA = os.path.join(BASE, "data")
BIN = os.path.join(BASE, "bin")
UB_PORT = int(os.environ.get("PL_BENCH_UB_PORT", "5300"))
PROXY_PORT = int(os.environ.get("PL_BENCH_PROXY_PORT", "1080"))
ENV = dict(os.environ, PL_DATA=DATA, PL_PORT=str(UB_PORT), PL_CYCLE="10", PL_TICK="2",
           PATH=BIN + ":" + os.environ["PATH"])


def pidfile(n):
    return os.path.join(BASE, n + ".pid")


def spawn(name, cmd):
    log = open(os.path.join(BASE, name + ".log"), "a")
    p = subprocess.Popen(cmd, env=ENV, stdout=log, stderr=log, start_new_session=True)
    open(pidfile(name), "w").write(str(p.pid))
    return p


def stop():
    for n in ("proxy", "daemon", "unbound"):
        try:
            os.kill(int(open(pidfile(n)).read()), signal.SIGTERM)
        except (OSError, ValueError):
            pass
    time.sleep(1)


def start(with_daemon=True, fresh=True):
    stop()
    os.makedirs(BIN, exist_ok=True)
    if fresh and os.path.exists(DATA):
        subprocess.run(["rm", "-r", DATA])  # nosec B603 B607: own cache dir
    os.makedirs(DATA, mode=0o700, exist_ok=True)
    fake = os.path.join(BIN, "networksetup")
    open(fake, "w").write('#!/bin/sh\ncase "$1" in -listallnetworkservices) echo x; echo Bench;; esac\n')
    os.chmod(fake, 0o700)  # nosemgrep: insecure-file-permissions  (owner-only fake tool)
    sys.path.insert(0, os.path.join(ROOT, "mac", "lib"))
    os.environ.update(PL_DATA=DATA, PL_PORT=str(UB_PORT))
    import daemon
    daemon.DATA, daemon.PORT = DATA, UB_PORT
    daemon.render_config(daemon.network_resolvers())
    subprocess.run(["unbound-anchor", "-a", os.path.join(DATA, "root.key")])
    fd = os.open(os.path.join(DATA, "unbound.log"), os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    spawn("unbound", ["unbound", "-d", "-c", os.path.join(DATA, "unbound.conf")])
    for _ in range(50):
        if daemon.alive():
            break
        time.sleep(0.1)
    if with_daemon:
        spawn("daemon", [sys.executable, os.path.join(ROOT, "mac", "lib", "daemon.py")])
    spawn("proxy", [sys.executable, os.path.join(ROOT, "bench", "socksproxy.py"), str(PROXY_PORT), str(UB_PORT)])
    time.sleep(1)
    print("bench env up: unbound :%d, proxy :%d, daemon %s" % (UB_PORT, PROXY_PORT, with_daemon))


if __name__ == "__main__":
    if sys.argv[1] == "stop":
        stop()
    else:
        start(with_daemon="--no-daemon" not in sys.argv)
