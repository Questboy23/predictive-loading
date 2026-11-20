// predictive-loading content script. Learns this site's page sequence from
// SHA-256 hashes of same-origin paths, then writes Speculation Rules for the
// pages worth loading early. Makes no network requests of its own.
(function () {
  "use strict";
  if (window.top !== window) return;
  const { Predictor, chooseAction } = globalThis.PLPredictor;
  const sha256 = globalThis.PLsha256;
  const { isSafeLink } = globalThis.PLlinks;
  const store = chrome.storage.local;
  const HOLDOUT = 0.2;
  const MAX_PRERENDER = 2;
  const MAX_MODERATE = 100;
  const MAX_MODEL_BYTES = 400000;

  const loc = { origin: location.origin, protocol: location.protocol, pathname: location.pathname, search: location.search };
  const originKey = sha256(location.origin);
  const pathHash = sha256(location.pathname || "/");
  const K = { model: "m:" + originKey, meta: "t:" + originKey, pending: "p:" + originKey };

  function navTiming() {
    const nav = performance.getEntriesByType("navigation")[0];
    if (!nav || nav.loadEventEnd <= 0) return null;
    const start = Math.max(nav.activationStart || 0, 0);
    return {
      waited: Math.max(nav.loadEventEnd - start, 0), // what the person waited for
      full: nav.loadEventEnd, // full load time when not preloaded
      net: nav.responseEnd > 0 ? nav.responseEnd / nav.loadEventEnd : 0.3,
      bytes: nav.transferSize || nav.encodedBodySize || 0,
      xferMs: Math.max(nav.responseEnd - nav.responseStart, 1),
      preloaded: start > 0 || nav.deliveryType === "navigational-prefetch",
    };
  }

  const ema = (old, x, a) => (old === undefined || old === null ? x : (1 - a) * old + a * x);

  async function run() {
    const got = await store.get(["enabled", "stats", K.model, K.meta, K.pending]);
    if (got.enabled === false) return;
    const t = navTiming();
    if (!t) return;
    const meta = got[K.meta] || { load: {}, docBytes: {}, thr: null, net: null };
    const stats = got.stats || { treat: [], hold: [] };

    // 1. Score the previous page's decision against where the person went.
    const pend = got[K.pending];
    if (pend && Date.now() - pend.t < 30 * 60 * 1000 && pend.target === pathHash) {
      const list = stats[pend.group];
      list.push(Math.round(t.waited));
      if (list.length > 2000) list.shift();
    }

    // 2. Learn this page and its measured costs (full load only when not preloaded).
    let model = Predictor.fromJSON(got[K.model]);
    const now = new Date();
    const day = Math.floor((now.getTime() - now.getTimezoneOffset() * 60000) / 86400000);
    model.observe(pathHash, now.getHours(), day);
    if (!t.preloaded) {
      meta.load[pathHash] = Math.round(ema(meta.load[pathHash], t.full, 0.3));
      meta.docBytes[pathHash] = Math.round(ema(meta.docBytes[pathHash], t.bytes, 0.3));
      if (t.bytes > 0) meta.thr = ema(meta.thr, t.bytes / t.xferMs, 0.2); // bytes per ms
      meta.net = ema(meta.net, t.net, 0.2);
    }

    // 3. Decide what to load early.
    const save = {};
    save[K.pending] = null;
    const saveData = navigator.connection && navigator.connection.saveData;
    const rules = { prerender: [], prefetch: [] };
    if (!saveData && HTMLScriptElement.supports && HTMLScriptElement.supports("speculationrules")) {
      const links = new Map(); // path hash -> absolute URL
      for (const a of document.links) {
        const info = { href: a.href, origin: a.origin, protocol: a.protocol, pathname: a.pathname, search: a.search,
          hash: a.hash, text: a.textContent, download: a.hasAttribute("download") ? true : undefined,
          dataset: a.dataset, rel: a.rel };
        if (isSafeLink(info, loc)) {
          const h = sha256(a.pathname || "/");
          if (!links.has(h)) links.set(h, a.origin + a.pathname);
        }
      }
      const loads = Object.values(meta.load).sort((x, y) => x - y);
      const medLoad = loads.length ? loads[loads.length >> 1] : t.full;
      const thr = meta.thr || 1000; // 1 MB/s until measured
      const netFrac = meta.net || 0.3;
      const hour = now.getHours();
      const decided = [];
      for (const [h, p] of model.predict(hour, 10)) {
        if (!links.has(h)) continue;
        const tLoad = meta.load[h] || medLoad;
        const bytes = meta.docBytes[h] || t.bytes || 50000;
        const wasted = (1 - p) * bytes;
        // prerender also fetches subresources: about 4x the document bytes (estimate)
        const action = chooseAction(p, tLoad, wasted / thr, (4 * wasted) / thr, netFrac);
        if (action) decided.push({ h, p, action, gain: p * tLoad });
      }
      decided.sort((x, y) => y.gain - x.gain);
      const top = decided[0];
      if (top) {
        const group = Math.random() < HOLDOUT ? "hold" : "treat";
        save[K.pending] = { target: top.h, group, t: Date.now() };
        if (group === "hold") links.delete(top.h);
      }
      let prerenders = 0;
      for (const d of decided) {
        if (!links.has(d.h)) continue;
        if (d.action === "prerender" && prerenders < MAX_PRERENDER) {
          rules.prerender.push(links.get(d.h));
          prerenders++;
        } else {
          rules.prefetch.push(links.get(d.h));
        }
        links.delete(d.h);
      }
      const moderate = [...links.values()].slice(0, MAX_MODERATE);
      const spec = {};
      if (rules.prerender.length) spec.prerender = [{ source: "list", urls: rules.prerender, eagerness: "immediate" }];
      spec.prefetch = [];
      if (rules.prefetch.length) spec.prefetch.push({ source: "list", urls: rules.prefetch, eagerness: "immediate" });
      if (moderate.length) spec.prefetch.push({ source: "list", urls: moderate, eagerness: "moderate" });
      if (!spec.prefetch.length) delete spec.prefetch;
      if (Object.keys(spec).length) {
        const s = document.createElement("script");
        s.type = "speculationrules";
        s.textContent = JSON.stringify(spec);
        s.dataset.predictiveLoading = "1";
        document.head.appendChild(s);
      }
    }

    let json = model.toJSON();
    if (JSON.stringify(json).length > MAX_MODEL_BYTES) json = null; // shortcut: reset an oversized site model
    save[K.model] = json;
    save[K.meta] = meta;
    save.stats = stats;
    await store.set(save); // shortcut: two tabs on one site can race; last write wins
  }

  function start() {
    // wait until load timing is final
    if (document.readyState === "complete") setTimeout(run, 0);
    else window.addEventListener("load", () => setTimeout(run, 0), { once: true });
  }
  if (document.prerendering) document.addEventListener("prerenderingchange", start, { once: true });
  else start();
})();
