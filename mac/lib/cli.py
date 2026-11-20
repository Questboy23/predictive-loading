"""predictive-loading command line. Standard library only.

  predictive-loading enable      install launchd services, point DNS at Unbound (one admin prompt)
  predictive-loading disable     stop services, restore original DNS
  predictive-loading uninstall   disable, then delete every data file and plist
  predictive-loading stats       ms saved per day vs the 10% holdout, with n
  predictive-loading status      mode and health
"""
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import daemon  # noqa: E402

LABELS = ("org.predictive-loading.unbound", "org.predictive-loading.daemon")
LD = os.environ.get("PL_LAUNCHD_DIR", "/Library/LaunchDaemons")
BREW = "/opt/homebrew" if os.path.isdir("/opt/homebrew") else "/usr/local"


def plist_path(label):
    return os.path.join(LD, label + ".plist")


def as_root(sub):
    """Re-run this command as root through one macOS admin prompt."""
    if os.geteuid() == 0:
        return root_main(sub)
    cmd = " ".join(shlex.quote(a) for a in (sys.executable, os.path.abspath(__file__), "_root", sub))
    script = 'do shell script "%s" with administrator privileges' % cmd.replace("\\", "\\\\").replace('"', '\\"')
    r = subprocess.run(["osascript", "-e", script])  # nosec B603 B607: fixed system tool
    return r.returncode


def write_plists():
    env = {"PATH": "%s/bin:%s/sbin:/usr/bin:/bin:/usr/sbin:/sbin" % (BREW, BREW), "PL_DATA": daemon.DATA}
    unbound = {"Label": LABELS[0], "ProgramArguments": [BREW + "/sbin/unbound",
                                                         "-d", "-c", daemon.path("unbound.conf")],
               "RunAtLoad": True, "KeepAlive": True, "EnvironmentVariables": env}
    dmn = {"Label": LABELS[1], "ProgramArguments": [sys.executable, os.path.join(HERE, "daemon.py")],
           "RunAtLoad": True, "KeepAlive": True, "EnvironmentVariables": env,
           "StandardOutPath": daemon.path("daemon.out"), "StandardErrorPath": daemon.path("daemon.out")}
    for label, body in zip(LABELS, (unbound, dmn)):
        with open(plist_path(label), "wb") as f:
            plistlib.dump(body, f)
        os.chmod(plist_path(label), 0o644)


def root_main(sub):
    if sub == "enable":
        os.makedirs(daemon.DATA, mode=0o711, exist_ok=True)
        os.chmod(daemon.DATA, 0o711)  # nosec B103 nosemgrep: insecure-file-permissions  (traverse only: lets `stats` open stats.json; files stay 600)
        daemon.snapshot_original()
        daemon.render_config(daemon.network_resolvers())
        anchor = [BREW + "/sbin/unbound-anchor", "-a", daemon.path("root.key")]
        subprocess.run(anchor)  # nosemgrep: dangerous-subprocess-use-tainted-env-args  (exit 1 just means "created")
        for name in ("unbound.log", "daemon.out"):
            fd = os.open(daemon.path(name), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.close(fd)
            os.chmod(daemon.path(name), 0o600)
        write_plists()
        for label in reversed(LABELS):  # re-enable after an upgrade: restart with the new code
            subprocess.run(["launchctl", "bootout", "system/" + label], stderr=subprocess.DEVNULL)
        for label in LABELS:
            subprocess.run(["launchctl", "bootstrap", "system", plist_path(label)])
        print("enabled: Unbound on 127.0.0.1 and ::1; DNS switches over after the captive-portal check")
        return 0
    if sub in ("disable", "uninstall"):
        for label in reversed(LABELS):
            subprocess.run(["launchctl", "bootout", "system/" + label], stderr=subprocess.DEVNULL)
        if os.path.exists(daemon.path("original_dns.json")):
            daemon.restore_original()
        if sub == "uninstall":
            for label in LABELS:
                if os.path.exists(plist_path(label)):
                    os.remove(plist_path(label))
            shutil.rmtree(daemon.DATA, ignore_errors=True)
            print("uninstalled: original DNS restored, all data deleted")
        else:
            print("disabled: original DNS restored")
        return 0
    print("unknown root command", sub)
    return 2


def stats():
    try:
        s = json.load(open(daemon.path("stats.json")))
    except (OSError, ValueError):
        print("no stats yet (is it enabled? stats appear after the first 60 s cycle)")
        return 1
    print("mode: %s   events learned: %d   predictability: %.2f bits/event" % (
        s.get("mode"), s.get("events", 0), s.get("bits_per_event", 0)))
    if "ms_saved_per_day" not in s:
        print("ms saved per day: not enough data yet (treated n=%d, holdout n=%d)" % (s["n_treat"], s["n_hold"]))
        return 0
    print("ms saved per day: %.0f (95%% CI %.0f to %.0f) over %.2f days" % (
        s["ms_saved_per_day"], s["ci95"][0], s["ci95"][1], s["days"]))
    print("lookup time, predicted names: %.1f ms prefetched (n=%d) vs %.1f ms random 10%% holdout (n=%d)" % (
        s["mean_ms_treat"], s["n_treat"], s["mean_ms_hold"], s["n_hold"]))
    return 0


def status():
    try:
        mode = json.load(open(daemon.path("stats.json"))).get("mode")
    except (OSError, ValueError):
        mode = "not running"
    print("mode:", mode)
    print("health:", json.dumps(daemon.health_check()))
    return 0


def main(argv):
    if len(argv) >= 3 and argv[1] == "_root":
        return root_main(argv[2])
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd in ("enable", "disable", "uninstall"):
        return as_root(cmd)
    if cmd == "stats":
        return stats()
    if cmd in ("status", "health"):
        return status()
    print(__doc__)
    return 0 if cmd in ("help", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
