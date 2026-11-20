// Shared predictor, JavaScript port. Mirrors predictor/predictor.py line for
// line; tests/parity.test.js checks both give identical output.
(function (root) {
  "use strict";
  const DECAYS = [0.9, 0.95, 0.98, 0.99, 0.995, 0.999];
  const DEFAULT_DECAY_INDEX = 3;
  const SEP = "\u0001";
  const NMODELS = 4;

  class Bank {
    constructor(d) {
      this.d = d;
      this.inv = 1.0 / d;
      this.scale = 1.0;
      this.tables = [new Map(), new Map(), new Map(), new Map()]; // ctx -> [N, E, Map(sym -> n)]
      this.logw = [0.0, 0.0, 0.0, 0.0];
    }

    prepare(ctxs, gsize) {
      const prep = [];
      for (let i = 0; i < NMODELS; i++) {
        const entry = this.tables[i].get(ctxs[i]);
        if (entry === undefined) {
          prep.push(null);
          continue;
        }
        const syms = entry[2];
        const e = entry[1] / this.scale;
        const denom = entry[0] / this.scale + e + 0.5 * (syms.size + 1);
        prep.push([syms, denom, (e + 0.5) / denom, 1.0]);
      }
      const p0 = prep[0];
      for (let i = 1; i < NMODELS; i++) {
        const pi = prep[i];
        if (pi === null || p0 === null) continue;
        let used = 0.0;
        for (const y of pi[0].keys()) used = used + (p0[0].get(y) / this.scale + 0.5) / p0[1];
        pi[3] = Math.max(1.0 - used, p0[2]);
      }
      return prep;
    }

    p0(prep, x, gsize) {
      const p0 = prep[0];
      if (p0 === null) return 1.0 / (gsize + 1);
      const n = p0[0].get(x);
      if (n === undefined) return p0[2];
      return (n / this.scale + 0.5) / p0[1];
    }

    modelProbs(prep, x, gsize) {
      const base = this.p0(prep, x, gsize);
      const out = [base];
      for (let i = 1; i < NMODELS; i++) {
        const pi = prep[i];
        if (pi === null) {
          out.push(base);
          continue;
        }
        const n = pi[0].get(x);
        if (n !== undefined) out.push((n / this.scale + 0.5) / pi[1]);
        else out.push((pi[2] * base) / pi[3]);
      }
      return out;
    }

    weights() {
      const m = Math.max(this.logw[0], this.logw[1], this.logw[2], this.logw[3]);
      const e = this.logw.map((v) => Math.exp(v - m));
      const s = e[0] + e[1] + e[2] + e[3];
      return e.map((v) => v / s);
    }

    update(ctxs, x, probs) {
      for (let i = 0; i < NMODELS; i++) this.logw[i] = this.d * this.logw[i] + Math.log(probs[i]);
      const m = Math.max(this.logw[0], this.logw[1], this.logw[2], this.logw[3]);
      this.logw = this.logw.map((v) => v - m);
      this.scale = this.scale * this.inv;
      for (let i = 0; i < NMODELS; i++) {
        const t = this.tables[i];
        let entry = t.get(ctxs[i]);
        if (entry === undefined) {
          entry = [0.0, 0.0, new Map()];
          t.set(ctxs[i], entry);
        }
        const syms = entry[2];
        if (syms.has(x)) {
          entry[0] = entry[0] + this.scale;
          syms.set(x, syms.get(x) + this.scale);
        } else {
          entry[1] = entry[1] + this.scale;
          syms.set(x, 0.0);
        }
      }
      if (this.scale > 1e100) {
        const s = this.scale;
        for (const t of this.tables) {
          for (const entry of t.values()) {
            entry[0] = entry[0] / s;
            entry[1] = entry[1] / s;
            const syms = entry[2];
            for (const [k, v] of syms) syms.set(k, v / s);
          }
        }
        this.scale = 1.0;
      }
    }
  }

  class Predictor {
    constructor(decays = DECAYS, defaultIndex = DEFAULT_DECAY_INDEX) {
      this.decays = decays.slice();
      this.banks = this.decays.map((d) => new Bank(d));
      this.choice = Math.min(defaultIndex, decays.length - 1);
      this.seen = new Map();
      this.prev1 = null;
      this.prev2 = null;
      this.day = null;
      this.dayLoss = this.decays.map(() => 0.0);
      this.history = [];
      this.events = 0;
      this.totalBits = 0.0;
    }

    ctxs(hour) {
      const p1 = this.prev1 === null ? "" : this.prev1;
      const p2 = this.prev2 === null ? "" : this.prev2;
      return ["", p1, p1 + SEP + p2, String(hour)];
    }

    mix(bank, prep, x, w) {
      const probs = bank.modelProbs(prep, x, this.seen.size);
      if (w === undefined) w = bank.weights();
      const p = w[0] * probs[0] + w[1] * probs[1] + w[2] * probs[2] + w[3] * probs[3];
      return [p, probs];
    }

    newDay(day) {
      if (this.day !== null && day !== this.day) {
        this.history.push(this.dayLoss);
        if (this.history.length > 7) this.history.shift();
        const sums = this.decays.map(() => 0.0);
        for (const dl of this.history) for (let j = 0; j < sums.length; j++) sums[j] = sums[j] + dl[j];
        let best = 0;
        for (let j = 1; j < sums.length; j++) if (sums[j] < sums[best]) best = j;
        this.choice = best;
        this.dayLoss = this.decays.map(() => 0.0);
      }
      this.day = day;
    }

    predict(hour, k = 1) {
      const bank = this.banks[this.choice];
      const ctxs = this.ctxs(hour);
      const w = bank.weights();
      const prep = bank.prepare(ctxs, this.seen.size);
      const scored = [];
      for (const s of this.seen.keys()) {
        if (s === this.prev1) continue; // a repeat is never the next event
        scored.push([this.mix(bank, prep, s, w)[0], s]);
      }
      scored.sort((a, b) => (a[0] !== b[0] ? b[0] - a[0] : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
      return scored.slice(0, k).map((r) => [r[1], r[0]]);
    }

    observe(x, hour = 0, day = 0) {
      if (x === this.prev1) return null;
      this.newDay(day);
      const ctxs = this.ctxs(hour);
      const top = this.predict(hour, 1);
      const top1 = top.length ? top[0][0] : "";
      let pChosen = 0.0;
      for (let j = 0; j < this.banks.length; j++) {
        const bank = this.banks[j];
        const [p, probs] = this.mix(bank, bank.prepare(ctxs, this.seen.size), x);
        this.dayLoss[j] = this.dayLoss[j] - Math.log2(p);
        if (j === this.choice) pChosen = p;
        bank.update(ctxs, x, probs);
      }
      this.totalBits = this.totalBits - Math.log2(pChosen);
      this.events = this.events + 1;
      this.seen.set(x, true);
      this.prev2 = this.prev1;
      this.prev1 = x;
      return [top1, pChosen];
    }

    bitsPerEvent() {
      return this.events ? this.totalBits / this.events : 0.0;
    }

    // Plain-object snapshot for chrome.storage.local (Maps are not JSON).
    toJSON() {
      return {
        v: 1, choice: this.choice, seen: [...this.seen.keys()], prev1: this.prev1, prev2: this.prev2,
        day: this.day, dayLoss: this.dayLoss, history: this.history, events: this.events, totalBits: this.totalBits,
        banks: this.banks.map((b) => ({
          scale: b.scale, logw: b.logw,
          tables: b.tables.map((t) => [...t].map(([c, e]) => [c, e[0], e[1], [...e[2]]])),
        })),
      };
    }

    static fromJSON(o) {
      const p = new Predictor();
      if (!o || o.v !== 1) return p;
      p.choice = o.choice; p.prev1 = o.prev1; p.prev2 = o.prev2; p.day = o.day;
      p.dayLoss = o.dayLoss; p.history = o.history; p.events = o.events; p.totalBits = o.totalBits;
      for (const s of o.seen) p.seen.set(s, true);
      o.banks.forEach((b, j) => {
        const bank = p.banks[j];
        bank.scale = b.scale; bank.logw = b.logw;
        bank.tables = b.tables.map((t) => new Map(t.map(([c, n, e, syms]) => [c, [n, e, new Map(syms)]])));
      });
      return p;
    }
  }

  function shouldAct(p, tSaved, cost) {
    return p * tSaved > cost;
  }

  function chooseAction(p, tLoad, prefetchCost, prerenderCost, prefetchGainFrac) {
    const gainPrerender = p * tLoad - prerenderCost;
    const gainPrefetch = p * tLoad * prefetchGainFrac - prefetchCost;
    const best = Math.max(gainPrerender, gainPrefetch);
    if (best <= 0) return null;
    return gainPrerender > gainPrefetch ? "prerender" : "prefetch";
  }

  const api = { Predictor, shouldAct, chooseAction, DECAYS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PLPredictor = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
