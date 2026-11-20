// E3 (PREREG.md): the Chrome extension under a habit. One worker handles every
// nWorkers-th site. Per site and arm (extension on/off, random order), a fresh
// profile does 8 training visits (home, read 3 s, click the next link) and 6
// measured visits (proxy connections dropped first, HTTP cache kept).
// Usage: node bench/habit_pw.js <proxyPort> <worker> <nWorkers> <outFile>
const fs = require("fs");
const os = require("os");
const path = require("path");
const net = require("net");
const { chromium } = require("playwright");

const [port, worker, nWorkers, OUT] = process.argv.slice(2);
const ROOT = path.resolve(__dirname, "..");
const EXT = path.join(ROOT, "extension");
const TRAIN = Number(process.env.HABIT_TRAIN || 8), MEASURE = Number(process.env.HABIT_MEASURE || 6), READ_MS = 3000, RTT = 60; // env: smoke test only
const sites = JSON.parse(fs.readFileSync(path.join(__dirname, "sites.json"), "utf8"))
  .filter((_, i) => i % Number(nWorkers) === Number(worker)).slice(0, Number(process.env.HABIT_SITES || 50));
const ctl = (cmd) => new Promise((res, rej) => {
  const s = net.connect(Number(port) + 1, "127.0.0.1", () => s.write(cmd + "\n"));
  let b = ""; s.on("data", (d) => (b += d)); s.on("end", () => res(b.trim())); s.on("error", rej);
});
let seed = 7 + Number(worker);
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const TIMING = () => { const n = performance.getEntriesByType("navigation")[0] || {}; const a = Math.max(n.activationStart || 0, 0);
  return { waited: Math.max(n.loadEventEnd - a, 0), ttfb: Math.max(n.responseStart - a, 0), activationStart: a,
    deliveryType: n.deliveryType || "", rules: document.querySelectorAll("script[type=speculationrules]").length }; };

async function clickTo(page, p) {
  const from = page.url();
  const ok = await page.evaluate((p) => { const a = [...document.querySelectorAll("a[href]")].find((x) => x.pathname === p);
    if (!a) return false; a.removeAttribute("target"); setTimeout(() => a.click(), 0); return true; }, p);
  if (!ok) throw new Error("link not found");
  await page.waitForURL((u) => u.href !== from, { timeout: 30000 });
  await page.waitForLoadState("load");
}

async function arm(s, ext) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pl-habit-"));
  const args = [`--proxy-server=socks5://127.0.0.1:${port}`, "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"];
  if (ext === "on") args.push(`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`);
  const ctx = await chromium.launchPersistentContext(dir, { headless: true, channel: "chromium", args, viewport: { width: 1280, height: 900 } });
  ctx.setDefaultTimeout(30000);
  const rows = [];
  try {
    const page = ctx.pages()[0] || (await ctx.newPage());
    for (let i = 0; i < TRAIN; i++) {
      await page.goto(s.home, { waitUntil: "load" });
      await page.waitForTimeout(READ_MS);
      await clickTo(page, s.nextPath);
    }
    for (let i = 0; i < MEASURE; i++) {
      await ctl("DROP");
      await page.goto("about:blank");
      await page.goto(s.home, { waitUntil: "load" });
      const home = await page.evaluate(TIMING);
      await page.waitForTimeout(READ_MS);
      await clickTo(page, s.nextPath);
      const next = await page.evaluate(TIMING);
      rows.push({ site: s.domain, ext, rep: i, home, next });
    }
  } finally {
    await ctx.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
  return rows;
}

(async () => {
  await ctl("RTT " + RTT);
  await ctl("MODE off");
  for (const s of sites) {
    const order = rnd() < 0.5 ? ["off", "on"] : ["on", "off"];
    for (const ext of order) {
      try {
        for (const r of await arm(s, ext)) fs.appendFileSync(OUT, JSON.stringify(r) + "\n");
      } catch (e) {
        fs.appendFileSync(OUT, JSON.stringify({ site: s.domain, ext, error: String(e.message || e).slice(0, 200) }) + "\n");
      }
    }
  }
})();
