// Route 2 session runner (Playwright, Chrome for Testing). Replaced browsertime
// after two runs where parallel sessions shared browser state. One process =
// one session = one fresh profile + its own SOCKS proxy (own RTT, own DNS mode).
// Per site: one training pass per DNS mode (home, click link), then measured
// loads in shuffled mode order: clear cache, drop proxy connections, load home,
// wait 1.5 s (the extension decides), click the link, record timings.
// Usage: node bench/route2_pw.js <rtt> <ext on|off> <proxyPort> <seed> <n>
const fs = require("fs");
const os = require("os");
const path = require("path");
const net = require("net");
const { chromium } = require("playwright");

const [rtt, ext, port, seed0, n] = process.argv.slice(2);
const ROOT = path.resolve(__dirname, "..");
const EXT = path.join(ROOT, "extension");
const OUT = process.env.R2_OUT || path.join(ROOT, "results", "route2.jsonl");
const sites = JSON.parse(fs.readFileSync(path.join(__dirname, "sites.json"), "utf8")).slice(0, Number(n || 50));
const ctl = (cmd) => new Promise((res, rej) => {
  const s = net.connect(Number(port) + 1, "127.0.0.1", () => s.write(cmd + "\n"));
  let b = ""; s.on("data", (d) => (b += d)); s.on("end", () => res(b.trim())); s.on("error", rej);
});
let seed = Number(seed0);
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const TIMING = () => { const n = performance.getEntriesByType("navigation")[0] || {}; const a = Math.max(n.activationStart || 0, 0);
  return { url: location.origin + location.pathname, waited: Math.max(n.loadEventEnd - a, 0), ttfb: Math.max(n.responseStart - a, 0),
    activationStart: a, deliveryType: n.deliveryType || "", rules: document.querySelectorAll("script[type=speculationrules]").length }; };

async function clickTo(page, p) {
  const from = page.url();
  const ok = await page.evaluate((p) => { const a = [...document.querySelectorAll("a[href]")].find((x) => x.pathname === p);
    if (!a) return false; a.removeAttribute("target"); setTimeout(() => a.click(), 0); return true; }, p);
  if (!ok) throw new Error("link not found");
  await page.waitForURL((u) => u.href !== from, { timeout: 30000 });
  await page.waitForLoadState("load");
  await page.waitForTimeout(300);
}

(async () => {
  await ctl("RTT " + rtt);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pl-r2-"));
  const args = [`--proxy-server=socks5://127.0.0.1:${port}`, "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"];
  if (ext === "on") args.push(`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`);
  const ctx = await chromium.launchPersistentContext(dir, { headless: true, channel: "chromium", args, viewport: { width: 1280, height: 900 } });
  ctx.setDefaultTimeout(30000);
  const page = ctx.pages()[0] || (await ctx.newPage());
  const cdp = await ctx.newCDPSession(page);
  for (const s of sites) {
    try {
      for (const mode of ["off", "on"]) {
        await ctl("MODE " + mode);
        await page.goto(s.home, { waitUntil: "load" });
        await page.waitForTimeout(800);
        await clickTo(page, s.nextPath);
      }
      const modes = rnd() < 0.5 ? ["off", "on"] : ["on", "off"];
      for (const mode of modes) {
        await ctl("MODE " + mode);
        await ctl("DROP");
        await cdp.send("Network.clearBrowserCache");
        await page.goto("about:blank");
        await page.goto(s.home, { waitUntil: "load" });
        const home = await page.evaluate(TIMING);
        await page.waitForTimeout(1500);
        await clickTo(page, s.nextPath);
        const next = await page.evaluate(TIMING);
        fs.appendFileSync(OUT, JSON.stringify({ site: s.domain, rank: s.rank, mode, ext, rtt: Number(rtt), session: `${rtt}-${ext}`, home, next }) + "\n");
      }
    } catch (e) {
      fs.appendFileSync(OUT, JSON.stringify({ site: s.domain, error: String(e.message || e).slice(0, 200), ext, rtt: Number(rtt) }) + "\n");
    }
  }
  await ctx.close();
})();
