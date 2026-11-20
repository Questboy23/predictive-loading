"""Route 3: curl to 50 API hosts, Mac tool off/on. curl sends hostnames to the
bench SOCKS proxy (--socks5-hostname), which resolves with the system resolver
(off) or Unbound + predictor (on). R rounds; host order and mode order are
shuffled per round; W seconds between rounds. Real network, no added RTT.
Writes results/route3.json.
"""
import json
import os
import random
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import env  # noqa: E402
import socksproxy  # noqa: E402
from route1 import summarize  # noqa: E402

HOSTS = """api.github.com api.stripe.com api.openai.com api.anthropic.com api.twitter.com graph.facebook.com
api.spotify.com api.dropboxapi.com api.slack.com discord.com api.telegram.org api.twilio.com api.sendgrid.com
api.mailgun.net api.cloudflare.com api.digitalocean.com api.heroku.com api.vercel.com api.netlify.com
api.linear.app api.notion.com api.airtable.com api.trello.com api.atlassian.com api.zoom.us api.box.com
api.paypal.com api.squareup.com api.shopify.com api.coinbase.com api.kraken.com api.binance.com
api.coingecko.com api.frankfurter.dev api.open-meteo.com hacker-news.firebaseio.com en.wikipedia.org
restcountries.com pypi.org registry.npmjs.org api.nuget.org rubygems.org crates.io api.weather.gov
api.nasa.gov api.data.gov api.mapbox.com maps.googleapis.com www.googleapis.com api.reddit.com""".split()
ROUNDS = int(os.environ.get("R3_ROUNDS", "5"))
WAIT = int(os.environ.get("R3_WAIT", "120"))
PORT = 1090


def curl(host):
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "--max-time", "15", "--socks5-hostname",
                        "127.0.0.1:%d" % PORT, "-w", "%{http_code} %{time_connect} %{time_total}",
                        "https://%s/" % host], capture_output=True, text=True)
    code, tc, tt = (r.stdout.split() + ["0", "0", "0"])[:3]
    return int(code), float(tc) * 1000, float(tt) * 1000


def main():
    assert len(HOSTS) == 50, len(HOSTS)
    own_env = "--shared" not in sys.argv
    if own_env:
        env.start(with_daemon=True)
    proxy = subprocess.Popen([sys.executable, os.path.join(ROOT, "bench", "socksproxy.py"), str(PORT), str(env.UB_PORT)])
    time.sleep(1)
    rng = random.Random(5)
    rows = []
    try:
        for r in range(ROUNDS):
            hosts = HOSTS[:]
            rng.shuffle(hosts)
            for h in hosts:
                modes = ["off", "on"]
                rng.shuffle(modes)
                for m in modes:
                    socksproxy.send(PORT, "MODE " + m)
                    code, tc, tt = curl(h)
                    rows.append({"round": r + 1, "host": h, "mode": m, "code": code, "connect_ms": tc, "total_ms": tt})
            print("round", r + 1, "done", flush=True)
            if r < ROUNDS - 1:
                time.sleep(WAIT)
    finally:
        proxy.terminate()
        if own_env:
            env.stop()
    ok = [x for x in rows if x["code"] > 0]
    out = {"hosts": len(HOSTS), "rounds": ROUNDS, "wait_s": WAIT, "failed": len(rows) - len(ok)}
    for phase, sel in (("cold", lambda x: x["round"] == 1), ("warm", lambda x: x["round"] > 1)):
        out[phase] = {m: {k: summarize([x[k] for x in ok if x["mode"] == m and sel(x)]) for k in ("connect_ms", "total_ms")}
                      for m in ("off", "on")}
        # paired per host+round difference (off - on)
        pairs = {}
        for x in ok:
            if sel(x):
                pairs.setdefault((x["host"], x["round"]), {})[x["mode"]] = x["total_ms"]
        d = [p["off"] - p["on"] for p in pairs.values() if len(p) == 2]
        out[phase]["paired_total_off_minus_on"] = summarize(d)
    json.dump(out, open(os.path.join(ROOT, "results", "route3.json"), "w"), indent=1)
    json.dump(rows, open(os.path.join(ROOT, "results", "route3_rows.json"), "w"))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
