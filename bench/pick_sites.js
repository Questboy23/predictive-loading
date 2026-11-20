// Picks 50 Tranco sites (in rank order) whose home page loads over https and
// has a same-origin link that passes the extension's link-safety rules.
// Writes bench/sites.json: [{rank, domain, home, next}]
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { isSafeLink } = require("../extension/linksafety.js");
const names = fs.readFileSync(path.join(__dirname, "..", "data", "raw", "top-1m.csv"), "utf8").split("\n").slice(0, 400).map((l) => (l.split(",")[1] || "").trim()).filter(Boolean);
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const out = [];
  for (let i = 0; i < names.length && out.length < 50; i++) {
    const page = await ctx.newPage();
    try {
      const resp = await page.goto(`https://${names[i]}/`, { timeout: 15000, waitUntil: "load" });
      if (!resp || resp.status() >= 400) throw new Error("status " + (resp && resp.status()));
      const url = new URL(page.url());
      const links = await page.$$eval("a[href]", (as) => as.map((a) => ({ href: a.href, origin: a.origin, protocol: a.protocol,
        pathname: a.pathname, search: a.search, hash: a.hash, text: a.textContent.trim().slice(0, 80), download: a.hasAttribute("download") ? true : undefined,
        dataset: Object.assign({}, a.dataset), rel: a.rel, visible: !!(a.offsetWidth || a.offsetHeight) })));
      const loc = { origin: url.origin, protocol: url.protocol, pathname: url.pathname, search: url.search };
      const ok = links.filter((l) => l.visible && isSafeLink(l, loc) && l.pathname.length > 1);
      if (!ok.length) throw new Error("no safe link");
      // the link must land where it points (no redirect), or the extension cannot match it
      let chosen = null;
      for (const l of ok.slice(0, 5)) {
        const r2 = await page.goto(l.origin + l.pathname, { timeout: 15000, waitUntil: "load" }).catch(() => null);
        const u2 = new URL(page.url());
        if (r2 && r2.status() < 400 && u2.origin === l.origin && u2.pathname === l.pathname) { chosen = l; break; }
      }
      if (!chosen) throw new Error("links redirect");
      out.push({ rank: i + 1, domain: names[i], home: url.origin + url.pathname, homePath: url.pathname, next: chosen.origin + chosen.pathname, nextPath: chosen.pathname });
      console.log(out.length, names[i], chosen.pathname);
    } catch (e) {
      console.log("skip", names[i], String(e.message).slice(0, 60));
    }
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(__dirname, "sites.json"), JSON.stringify(out, null, 1));
})();
