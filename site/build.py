"""Builds site/predictive-loading/{index,privacy}.html from RESULTS.md and
docs/PRIVACY.md. Usage: python3 site/build.py [WEB_STORE_URL]"""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "predictive-loading")
V = {}
block = open(os.path.join(ROOT, "RESULTS.md")).read().split("## Machine-readable values")[1].split("```")[1]
for line in block.strip().splitlines():
    k, v = line.split(" = ", 1)
    V[k] = v
store = sys.argv[1] if len(sys.argv) > 1 else ""
REL = "https://github.com/Questboy23/predictive-loading/releases/latest"


def g(k, d="n/a"):
    return html.escape(V.get(k, d))


def page(title, body):
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>%s</title><link rel=\"stylesheet\" href=\"style.css\"></head><body><main>%s</main></body></html>\n" % (html.escape(title), body))


store_html = ('<a href="%s">Chrome Web Store</a>' % html.escape(store)) if store else "Chrome Web Store: in review (install from the GitHub release meanwhile)"
rows = ""
for rtt, name in ((10, "Home Wi-Fi, 10 ms"), (60, "Busy campus Wi-Fi, 60 ms"), (150, "Poor Wi-Fi, 150 ms")):
    rows += "<tr><td>%s</td><td>%s ms</td><td>%s ms</td><td>%s ms [%s, %s], n=%s</td></tr>" % (
        name, g("r2.%d.off.off.next" % rtt), g("r2.%d.on.on.next" % rtt),
        g("r2.%d.eff.ext" % rtt), g("r2.%d.eff.ext.lo" % rtt), g("r2.%d.eff.ext.hi" % rtt), g("r2.%d.eff.ext.n" % rtt))
body = """
<h1>Predictive Loading</h1>
<p>Predicts the next thing you will load from your own history and does the waiting early: DNS lookups for every app on your Mac, and the next page on each site in Chrome. Nothing leaves your device.</p>
<p class="links"><a href="%(rel)s">Download (latest release)</a> <a href="plain.pdf">Plain-language explainer (PDF)</a> <a href="paper.pdf">Paper (PDF)</a> <a href="privacy.html">Privacy policy</a> <a href="https://github.com/Questboy23/predictive-loading">Source</a></p>
<p>%(store)s</p>
<h2>Install on macOS</h2>
<pre>brew install questboy23/tap/predictive-loading
predictive-loading enable
predictive-loading stats</pre>
<p><code>predictive-loading uninstall</code> restores your DNS settings exactly and deletes all data.</p>
<h2>Install in Chrome</h2>
<pre>git clone https://github.com/Questboy23/predictive-loading
predictive-loading/install/setup.sh chrome</pre>
<p>A guide window opens beside Chrome, points at each button, and can do the clicks for you (Extensions page, Developer mode, Load unpacked, pick the folder). Or by hand: download the extension zip from the <a href="%(rel)s">latest release</a>, unzip, open chrome://extensions, turn on Developer mode, and choose Load unpacked. Permission requested: storage only.</p>
<h2>Measured results</h2>
<p>Offline replay: the predictor's log-loss beat an order-1 Markov baseline on %(wins)s of %(nt)s traces. On recorded Chrome history it guessed the next domain correctly %(dom)s%% of the time.</p>
<p>In the 50-site Chrome test below, each site had one training visit; the extension rarely passed its own threshold and showed no page-load gain. API calls through the Mac tool were %(r3w)s ms faster per call after the first round and slower on the first call (paired difference %(r3c)s ms).</p>
<table><tr><th>Wi-Fi profile</th><th>Next page wait, both off (median)</th><th>Both on (median)</th><th>Extension effect, paired median [95%% CI]</th></tr>%(rows)s</table>
<p>DNS after TTLs expire (Tranco top 500): system resolver %(sys)s ms, Unbound alone %(ub)s ms, Unbound + predictor %(up)s ms (medians). Full numbers, losses included: <a href="https://github.com/Questboy23/predictive-loading/blob/main/RESULTS.md">RESULTS.md</a>.</p>
""" % {"rel": REL, "store": store_html, "wins": g("r0.wins_markov_bits"), "nt": g("r0.ntraces"),
       "dom": g("r0.recorded_chrome_domains.mixture.top1"), "rows": rows, "sys": g("r1.warm.system_default.median_ms"),
       "ub": g("r1.warm.unbound_alone.median_ms"), "r3w": g("r3.warm.paired"), "r3c": g("r3.cold.paired"), "up": g("r1.warm.unbound_plus_predictor.median_ms")}
open(os.path.join(OUT, "index.html"), "w").write(page("Predictive Loading", body))

md = open(os.path.join(ROOT, "docs", "PRIVACY.md")).read()
out = []
for line in md.splitlines():
    line = html.escape(line)
    line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
    line = re.sub(r"(https://\S+)", r'<a href="\1">\1</a>', line)
    if line.startswith("# "):
        out.append("<h1>%s</h1>" % line[2:])
    elif line.startswith("## "):
        out.append("<h2>%s</h2>" % line[3:])
    elif line.startswith("- "):
        out.append("<p>&bull; %s</p>" % line[2:])
    elif line.strip():
        out.append("<p>%s</p>" % line)
open(os.path.join(OUT, "privacy.html"), "w").write(page("Predictive Loading privacy policy", "\n".join(out)))
print("site built", "with store link" if store else "without store link")
