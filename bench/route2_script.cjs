// browsertime script for Route 2. For each site: one training pass per DNS
// mode (home, then click the chosen link), then measured loads in shuffled
// mode order: clear HTTP cache, drop proxy connections, load home, wait 1.5 s
// (the extension decides), click the link, record timings. Appends JSON lines
// to $R2_OUT.
const fs = require("fs");
const net = require("net");
const sites = JSON.parse(fs.readFileSync(process.env.R2_SITES, "utf8")).slice(0, Number(process.env.R2_N || 50));
const ctl = (cmd) => new Promise((res, rej) => {
  const s = net.connect(Number(process.env.R2_CTL || 1081), "127.0.0.1", () => s.write(cmd + "\n"));
  let buf = ""; s.on("data", (d) => (buf += d)); s.on("end", () => res(buf.trim())); s.on("error", rej);
});
const TIMING = `const n = performance.getEntriesByType('navigation')[0] || {};
  const a = Math.max(n.activationStart || 0, 0);
  const lcp = performance.getEntriesByType('largest-contentful-paint').slice(-1)[0];
  return { url: location.origin + location.pathname, load: n.loadEventEnd, waited: Math.max(n.loadEventEnd - a, 0),
    ttfb: Math.max(n.responseStart - a, 0), activationStart: a, deliveryType: n.deliveryType || '',
    fcp: (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime || null,
    rules: document.querySelectorAll('script[type=speculationrules]').length };`;

module.exports = async function (context, commands) {
  const rnd = (() => { let s = Number(process.env.R2_SEED || 7); return () => ((s = (s * 1103515245 + 12345) % 2147483648) / 2147483648); })();
  const clickTo = async (path) => {
    await commands.js.runAndWait(`const a=[...document.querySelectorAll('a[href]')].find(x=>x.pathname===${JSON.stringify(path)}); if(a){a.click()}else{location.href=${JSON.stringify(path)}}`);
  };
  for (const s of sites) {
    try {
      for (const mode of ["off", "on"]) { // history passes through each resolver
        await ctl("MODE " + mode);
        await commands.navigate(s.home);
        await commands.wait.byTime(800);
        await clickTo(s.nextPath);
      }
      const modes = rnd() < 0.5 ? ["off", "on"] : ["on", "off"];
      for (const mode of modes) {
        await ctl("MODE " + mode);
        await ctl("DROP");
        await commands.cdp.send("Network.clearBrowserCache");
        await commands.navigate("about:blank");
        await commands.navigate(s.home);
        const home = await commands.js.run(TIMING);
        await commands.wait.byTime(1500);
        await clickTo(s.nextPath);
        const next = await commands.js.run(TIMING);
        fs.appendFileSync(process.env.R2_OUT, JSON.stringify({ site: s.domain, rank: s.rank, mode, ext: process.env.R2_EXT,
          rtt: Number(process.env.R2_RTT), home, next }) + "\n");
      }
    } catch (e) {
      fs.appendFileSync(process.env.R2_OUT, JSON.stringify({ site: s.domain, error: String(e).slice(0, 200), ext: process.env.R2_EXT, rtt: Number(process.env.R2_RTT) }) + "\n");
    }
  }
};
