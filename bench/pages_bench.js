// Page-preloading benchmark on the Route 2 sites, at 60 ms RTT through the
// bench SOCKS proxy (system resolver). Methods, order shuffled per site:
//   default     Chrome as shipped (its own preloading only)
//   instantpage instant.page 5.2.0 injected (preloads on hover)
//   quicklink   Quicklink 3.0.1 injected, listen() after load (in-viewport links on idle)
//   extension   this extension, after 3 training visits home -> next
// User model: load home, wait 1.5 s, hover the link 300 ms, click.
// Records the time the person waited for the next page (loadEventEnd minus
// activationStart) and how many speculative requests were made.
const fs = require("fs");
const os = require("os");
const path = require("path");
const net = require("net");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const EXT = path.join(ROOT, "extension");
const sites = JSON.parse(fs.readFileSync(path.join(__dirname, "sites.json"), "utf8")).slice(0, Number(process.env.PB_N || 50));
const PROXY = Number(process.env.PB_PROXY || 1190);
const OUT = path.join(ROOT, "results", "pages_bench.jsonl");
const INSTANT = fs.readFileSync(path.join(__dirname, "vendor", "instantpage.js"), "utf8");
const QUICKLINK = fs.readFileSync(path.join(__dirname, "vendor", "quicklink.umd.js"), "utf8");
const ctl = (cmd) => new Promise((res) => { const s = net.connect(PROXY + 1, "127.0.0.1", () => s.write(cmd + "\n")); s.on("data", () => {}); s.on("end", res); s.on("error", res); });
const ARGS = [`--proxy-server=socks5://127.0.0.1:${PROXY}`, "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"];
let seed = 11;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);

async function launch(method) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pl-pb-"));
  const args = method === "extension" ? [...ARGS, `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`] : ARGS;
  const ctx = await chromium.launchPersistentContext(dir, { headless: true, channel: "chromium", args, viewport: { width: 1280, height: 900 } });
  ctx.setDefaultTimeout(30000);
  if (method === "instantpage") await ctx.addInitScript(`document.addEventListener('DOMContentLoaded', () => { (function(){ ${INSTANT} })() });`);
  if (method === "quicklink") await ctx.addInitScript(`${QUICKLINK}; window.addEventListener('load', () => quicklink.listen());`);
  return ctx;
}

async function visit(page, s, measure) {
  await page.goto(s.home, { waitUntil: "load" });
  await page.waitForTimeout(1500);
  const handle = await page.evaluateHandle((p) => [...document.querySelectorAll("a[href]")].find((a) => a.pathname === p && (a.offsetWidth || a.offsetHeight)) || [...document.querySelectorAll("a[href]")].find((a) => a.pathname === p), s.nextPath);
  const el = handle.asElement();
  if (!el) throw new Error("link not found");
  await el.evaluate((a) => a.removeAttribute("target"));
  await el.scrollIntoViewIfNeeded().catch(() => {});
  await el.hover({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(300);
  const from = page.url();
  await el.evaluate((a) => a.click());
  await page.waitForURL((u) => u.href !== from, { timeout: 30000 });
  await page.waitForLoadState("load");
  if (!measure) return null;
  return page.evaluate(() => { const n = performance.getEntriesByType("navigation")[0]; const a = Math.max(n.activationStart || 0, 0);
    return { url: location.origin + location.pathname, waited: Math.max(n.loadEventEnd - a, 0), activationStart: a, deliveryType: n.deliveryType || "" }; });
}

(async () => {
  await ctl("RTT 60");
  await ctl("MODE off");
  if (!process.argv.includes("--append") && fs.existsSync(OUT)) fs.unlinkSync(OUT);
  for (const s of sites) {
    const methods = ["default", "instantpage", "quicklink", "extension"].sort(() => rnd() - 0.5);
    for (const m of methods) {
      let ctx;
      try {
        ctx = await launch(m);
        const page = ctx.pages()[0] || (await ctx.newPage());
        let spec = 0;
        page.on("request", (r) => { const h = r.headers(); if (h["sec-purpose"] || h["purpose"]) spec++; });
        if (m === "extension") for (let i = 0; i < 3; i++) await visit(page, s, false);
        const cdp = await ctx.newCDPSession(page);
        await cdp.send("Network.clearBrowserCache");
        await ctl("DROP");
        spec = 0;
        const r = await visit(page, s, true);
        fs.appendFileSync(OUT, JSON.stringify({ site: s.domain, method: m, speculativeRequests: spec, ...r }) + "\n");
      } catch (e) {
        fs.appendFileSync(OUT, JSON.stringify({ site: s.domain, method: m, error: String(e.message || e).slice(0, 160) }) + "\n");
      }
      if (ctx) await ctx.close().catch(() => {});
    }
    console.log("done", s.domain);
  }
})();
