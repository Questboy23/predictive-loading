// End-to-end: real Chromium with the unpacked extension, local fixture site.
// Checks: 50 page loads make zero requests from the extension origin and none
// to other hosts; action/download links are never requested; after training
// the predicted page is speculated and served preloaded; popup works.
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const os = require("os");
const { chromium } = require("playwright");

const EXT = path.resolve(__dirname, "..", "extension");
const SITE = path.join(__dirname, "site");
const ACTION = /logout|cart|delete|settings|checkout|report\.pdf|\/d\/|mailto|javascript/;
const served = [];

const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  served.push({ path: u.pathname + u.search, purpose: req.headers["sec-purpose"] || "" });
  let p = path.join(SITE, decodeURIComponent(u.pathname));
  if (!p.startsWith(SITE)) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "index.html");
  if (!fs.existsSync(p)) { res.writeHead(404); return res.end("nf"); }
  setTimeout(() => { // 150 ms server think time so preloading is measurable
    res.writeHead(200, { "content-type": p.endsWith(".html") ? "text/html" : "application/octet-stream" });
    res.end(fs.readFileSync(p));
  }, 150);
});

function extId(dir) { // unpacked extension id = first 128 bits of sha256(path), hex digits mapped to a-p
  const h = crypto.createHash("sha256").update(fs.realpathSync(dir)).digest("hex").slice(0, 32);
  return [...h].map((c) => String.fromCharCode(97 + parseInt(c, 16))).join("");
}

(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "pl-e2e-"));
  const ctx = await chromium.launchPersistentContext(profile, {
    headless: false, channel: "chromium",
    args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`, "--no-first-run"],
  });
  const foreign = [];
  ctx.on("request", (r) => {
    const u = r.url();
    if (u.startsWith("chrome-extension://") || !u.startsWith(origin)) foreign.push(u);
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  ctx.setDefaultTimeout(10000);
  const fail = (m) => { console.error("E2E FAIL:", m); process.exitCode = 1; };

  // 50 loads: home -> a -> home -> a ... (clicking the link, as a person would)
  let speculatedA = 0, preloadedA = 0, rulesSeen = [];
  await page.goto(origin + "/");
  for (let i = 0; i < 49; i++) {
    if (process.env.PL_DEBUG) console.log("step", i, page.url());
    await page.waitForLoadState("load");
    await page.waitForTimeout(250); // content script runs after load
    const onHome = new URL(page.url()).pathname === "/";
    const rules = await page.$$eval('script[type="speculationrules"]', (s) => s.map((x) => x.textContent));
    rulesSeen.push(...rules);
    if (onHome && rules.some((r) => (JSON.parse(r).prerender || []).concat((JSON.parse(r).prefetch || []).filter((x) => x.eagerness === "immediate")).some((x) => x.urls.some((u) => u.endsWith("/a/"))))) speculatedA++;
    if (onHome) await page.waitForTimeout(600); // let the preload finish
    // same-document link click, renderer-initiated, so a prerender can activate
    const target = onHome ? "/a/" : "/";
    await page.evaluate((t) => document.querySelector(`a[href="${t}"]`).click(), target);
    await page.waitForURL(origin + target);
    if (onHome) {
      await page.waitForLoadState("load");
      const pre = await page.evaluate(() => { const n = performance.getEntriesByType("navigation")[0]; return n.activationStart > 0 || n.deliveryType === "navigational-prefetch"; });
      if (pre) preloadedA++;
    }
  }
  await page.waitForTimeout(500);

  const foreignDuringLoads = foreign.slice(); // popup files below are local extension pages, counted apart
  // Popup
  const id = extId(EXT);
  const popup = await ctx.newPage();
  await popup.goto(`chrome-extension://${id}/popup.html`);
  const saved = await popup.textContent("#saved");
  const detail = await popup.textContent("#detail");
  const colors = await popup.evaluate(() => [...document.querySelectorAll("body, h1, p, label")].map((e) => getComputedStyle(e).color));
  await popup.click("#delete");
  await popup.waitForTimeout(300);
  const afterDelete = await popup.evaluate(() => chrome.storage.local.get(null));
  await popup.uncheck("#enabled");
  const off = await popup.evaluate(() => chrome.storage.local.get("enabled"));
  await ctx.close();
  server.close();

  const actionHits = served.filter((s) => ACTION.test(s.path));
  const speculative = served.filter((s) => s.purpose);
  const prerenderCounts = rulesSeen.map((r) => (JSON.parse(r).prerender || []).reduce((n, x) => n + x.urls.length, 0));
  const ruleUrls = rulesSeen.flatMap((r) => Object.values(JSON.parse(r)).flat().flatMap((x) => x.urls));
  console.log(JSON.stringify({ loads: 50, foreign: foreignDuringLoads.length, actionRequests: actionHits.length,
    speculativeRequests: speculative.length, homeLoadsWithASpeculated: speculatedA, aLoadsServedPreloaded: preloadedA,
    maxPrerenders: Math.max(0, ...prerenderCounts), popup: { saved, detail }, keysAfterDelete: Object.keys(afterDelete), off }));
  if (foreignDuringLoads.length) fail("requests outside the fixture origin / from the extension: " + foreignDuringLoads.slice(0, 5));
  if (actionHits.length) fail("action/download links requested: " + JSON.stringify(actionHits));
  if (ruleUrls.some((u) => ACTION.test(u) || !u.startsWith(origin))) fail("unsafe URL in rules");
  if (Math.max(0, ...prerenderCounts) > 2) fail("more than 2 prerenders");
  if (speculatedA < 10) fail("predicted page /a/ speculated on only " + speculatedA + " home loads");
  if (preloadedA < 5) fail("/a/ served preloaded only " + preloadedA + " times");
  if (colors.some((c) => c !== "rgb(255, 255, 255)")) fail("popup text not white: " + colors);
  if (Object.keys(afterDelete).some((k) => k !== "enabled")) fail("delete left data: " + Object.keys(afterDelete));
  if (off.enabled !== false) fail("switch did not turn off");
  if (!process.exitCode) console.log("e2e OK");
})().catch((e) => { console.error(e); process.exit(1); });
