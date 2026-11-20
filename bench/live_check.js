// 10-minute live browsing check: Chrome for Testing with the extension,
// real sites, a person-like loop (open a site, follow 2-4 same-site links,
// return to sites it has seen before so history builds). Reports the popup
// numbers and any request from the extension origin. Usage: node bench/live_check.js [minutes]
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { chromium } = require("playwright");
const EXT = path.resolve(__dirname, "..", "extension");
const sites = JSON.parse(fs.readFileSync(path.join(__dirname, "sites.json"), "utf8")).slice(0, 12);
const minutes = Number(process.argv[2] || 10);
function extId(dir) { const h = crypto.createHash("sha256").update(fs.realpathSync(dir)).digest("hex").slice(0, 32); return [...h].map((c) => String.fromCharCode(97 + parseInt(c, 16))).join(""); }
(async () => {
  const ctx = await chromium.launchPersistentContext(fs.mkdtempSync(path.join(os.tmpdir(), "pl-live-")), {
    headless: true, channel: "chromium", args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`] });
  ctx.setDefaultTimeout(20000);
  let extReq = 0, loads = 0, preloaded = 0, errors = 0;
  ctx.on("request", (r) => { if (r.url().startsWith("chrome-extension://")) extReq++; });
  const page = ctx.pages()[0] || (await ctx.newPage());
  const end = Date.now() + minutes * 60000;
  let i = 0;
  while (Date.now() < end) {
    const s = sites[i++ % sites.length];
    try {
      await page.goto(s.home, { waitUntil: "load" }); loads++;
      for (let k = 0; k < 3 && Date.now() < end; k++) {
        await page.waitForTimeout(1500 + Math.random() * 2000);
        const target = k === 0 ? s.nextPath : await page.evaluate(() => { const a = [...document.links].filter((l) => l.origin === location.origin && !l.search && l.pathname.length > 1 && (l.offsetWidth || l.offsetHeight)); return a.length ? a[Math.floor(Math.random() * Math.min(a.length, 8))].pathname : null; });
        if (!target) break;
        const from = page.url();
        await page.evaluate((p) => { const a = [...document.links].find((l) => l.pathname === p); if (a) { a.removeAttribute("target"); a.click(); } else location.href = p; }, target);
        await page.waitForURL((u) => u.href !== from).catch(() => {});
        await page.waitForLoadState("load"); loads++;
        if (await page.evaluate(() => { const n = performance.getEntriesByType("navigation")[0]; return n.activationStart > 0 || n.deliveryType === "navigational-prefetch"; })) preloaded++;
      }
    } catch (e) { errors++; }
  }
  const extReqBrowsing = extReq; // popup files below are the extension's own page
  const popup = await ctx.newPage();
  await popup.goto(`chrome-extension://${extId(EXT)}/popup.html`);
  await popup.waitForTimeout(500);
  const out = { minutes, loads, preloaded, errors, extensionOriginRequestsDuringBrowsing: extReqBrowsing,
    popupSaved: await popup.textContent("#saved"), popupDetail: await popup.textContent("#detail") };
  await popup.screenshot({ path: path.join(__dirname, "..", "docs", "store", "popup-live.png") });
  fs.writeFileSync(path.join(__dirname, "..", "results", "live_check.json"), JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out));
  await ctx.close();
})();
