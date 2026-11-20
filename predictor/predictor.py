"""Shared predictor, Python port. Standard library only.

Spec (mirrored line for line in extension/predictor.js):
- Events are strings. A repeat of the previous event is ignored (counts once).
- Four context models: order 0, order 1, order 2, hour of day.
- Each model: Krichevsky-Trofimov estimate over the k_c symbols seen in
  context c plus an escape symbol whose count e_c is the (decayed) number
  of times a symbol was new to c:
    P(x|c)   = (n_x + 0.5) / (N + e_c + 0.5 (k_c + 1))
    P(esc|c) = (e_c + 0.5) / (N + e_c + 0.5 (k_c + 1))
  The escape mass goes to symbols not seen in c in proportion to the
  order-0 model's probabilities (the order-0 escape is the brand-new-event
  slot): P_i(x) = P(esc|c) * P0(x) / (1 - sum over y in c of P0(y)).
- Counts decay by d per event. Stored counts are scaled by S = d^-t so the
  update is one add; renormalised when S > 1e100.
- Mixture weights: log w_i <- d * log w_i + log P_i(x)  (decayed product).
- d is chosen at each new day from DECAYS by lowest log-loss over the
  last 7 days; all six decays run in parallel as shadow models.
"""
import math

DECAYS = (0.9, 0.95, 0.98, 0.99, 0.995, 0.999)
DEFAULT_DECAY_INDEX = 3  # 0.99 until a week of data says otherwise
SEP = "\u0001"
NMODELS = 4


class _Bank:
    """Four context models plus mixture weights for one decay value."""

    def __init__(self, d):
        self.d = d
        self.inv = 1.0 / d
        self.scale = 1.0
        self.tables = [{} for _ in range(NMODELS)]  # ctx -> [N, E, {sym: n}]
        self.logw = [0.0] * NMODELS

    def prepare(self, ctxs, gsize):
        """Per-step cache: for each model, (syms, denom, esc_mass, rest)."""
        prep = []
        for i in range(NMODELS):
            entry = self.tables[i].get(ctxs[i])
            if entry is None:
                prep.append(None)
                continue
            tot, esc, syms = entry
            e = esc / self.scale
            denom = tot / self.scale + e + 0.5 * (len(syms) + 1)
            prep.append([syms, denom, (e + 0.5) / denom, 1.0])
        p0 = prep[0]
        for i in range(1, NMODELS):
            pi = prep[i]
            if pi is None or p0 is None:
                continue
            used = 0.0
            for y in pi[0]:
                used = used + (p0[0][y] / self.scale + 0.5) / p0[1]
            pi[3] = max(1.0 - used, p0[2])
        return prep

    def p0(self, prep, x, gsize):
        p0 = prep[0]
        if p0 is None:
            return 1.0 / (gsize + 1)
        n = p0[0].get(x)
        if n is None:
            return p0[2]
        return (n / self.scale + 0.5) / p0[1]

    def model_probs(self, prep, x, gsize):
        """P_i(x) for each model; x may be unseen globally (novel slot)."""
        base = self.p0(prep, x, gsize)
        out = [base]
        for i in range(1, NMODELS):
            pi = prep[i]
            if pi is None:
                out.append(base)
                continue
            n = pi[0].get(x)
            if n is not None:
                out.append((n / self.scale + 0.5) / pi[1])
            else:
                out.append(pi[2] * base / pi[3])
        return out

    def weights(self):
        m = max(self.logw)
        e = [math.exp(v - m) for v in self.logw]
        s = e[0] + e[1] + e[2] + e[3]
        return [v / s for v in e]

    def update(self, ctxs, x, probs):
        for i in range(NMODELS):
            self.logw[i] = self.d * self.logw[i] + math.log(probs[i])
        m = max(self.logw)
        self.logw = [v - m for v in self.logw]
        self.scale = self.scale * self.inv
        for i in range(NMODELS):
            t = self.tables[i]
            entry = t.get(ctxs[i])
            if entry is None:
                entry = [0.0, 0.0, {}]
                t[ctxs[i]] = entry
            syms = entry[2]
            if x in syms:
                entry[0] = entry[0] + self.scale
                syms[x] = syms[x] + self.scale
            else:
                entry[1] = entry[1] + self.scale
                syms[x] = 0.0
        if self.scale > 1e100:
            s = self.scale
            for t in self.tables:
                for entry in t.values():
                    entry[0] = entry[0] / s
                    entry[1] = entry[1] / s
                    syms = entry[2]
                    for k in syms:
                        syms[k] = syms[k] / s
            self.scale = 1.0


class Predictor:
    def __init__(self, decays=DECAYS, default_index=DEFAULT_DECAY_INDEX):
        self.banks = [_Bank(d) for d in decays]
        self.decays = tuple(decays)
        self.choice = min(default_index, len(decays) - 1)
        self.seen = {}  # symbol -> True, insertion ordered
        self.prev1 = None
        self.prev2 = None
        self.day = None
        self.day_loss = [0.0] * len(decays)
        self.history = []  # list of per-day loss lists, last 7 days
        self.events = 0
        self.total_bits = 0.0

    def _ctxs(self, hour):
        p1 = "" if self.prev1 is None else self.prev1
        p2 = "" if self.prev2 is None else self.prev2
        return ("", p1, p1 + SEP + p2, str(hour))

    def _mix(self, bank, prep, x, w=None):
        probs = bank.model_probs(prep, x, len(self.seen))
        if w is None:
            w = bank.weights()
        p = w[0] * probs[0] + w[1] * probs[1] + w[2] * probs[2] + w[3] * probs[3]
        return p, probs

    def _new_day(self, day):
        if self.day is not None and day != self.day:
            self.history.append(self.day_loss)
            if len(self.history) > 7:
                self.history.pop(0)
            sums = [0.0] * len(self.decays)
            for dl in self.history:
                for j in range(len(sums)):
                    sums[j] = sums[j] + dl[j]
            best = 0
            for j in range(1, len(sums)):
                if sums[j] < sums[best]:
                    best = j
            self.choice = best
            self.day_loss = [0.0] * len(self.decays)
        self.day = day

    def predict(self, hour, k=1):
        """Top-k (symbol, probability) among seen symbols, chosen decay."""
        bank = self.banks[self.choice]
        ctxs = self._ctxs(hour)
        w = bank.weights()
        prep = bank.prepare(ctxs, len(self.seen))
        scored = []
        for s in self.seen:
            if s == self.prev1:
                continue  # a repeat is never the next event
            p, _ = self._mix(bank, prep, s, w)
            scored.append((-p, s))
        scored.sort()
        return [(s, -np) for np, s in scored[:k]]

    def observe(self, x, hour=0, day=0):
        """Score x against the current prediction, then learn it.
        Returns None for an ignored repeat, else (top1, p_of_x)."""
        if x == self.prev1:
            return None
        self._new_day(day)
        ctxs = self._ctxs(hour)
        top = self.predict(hour, 1)
        top1 = top[0][0] if top else ""
        p_chosen = 0.0
        for j, bank in enumerate(self.banks):
            p, probs = self._mix(bank, bank.prepare(ctxs, len(self.seen)), x)
            self.day_loss[j] = self.day_loss[j] - math.log2(p)
            if j == self.choice:
                p_chosen = p
            bank.update(ctxs, x, probs)
        self.total_bits = self.total_bits - math.log2(p_chosen)
        self.events = self.events + 1
        self.seen[x] = True
        self.prev2 = self.prev1
        self.prev1 = x
        return top1, p_chosen

    def bits_per_event(self):
        return self.total_bits / self.events if self.events else 0.0


def should_act(p, t_saved, cost):
    """Decision rule: act on B only if P(B) * T_saved(B) > C(B)."""
    return p * t_saved > cost


def choose_action(p, t_load, prefetch_cost, prerender_cost, prefetch_gain_frac):
    """Chrome: pick 'prerender', 'prefetch' or None by expected net gain.
    Prefetch saves only the network part of the load (prefetch_gain_frac)."""
    gain_prerender = p * t_load - prerender_cost
    gain_prefetch = p * t_load * prefetch_gain_frac - prefetch_cost
    best = max(gain_prerender, gain_prefetch)
    if best <= 0:
        return None
    return "prerender" if gain_prerender > gain_prefetch else "prefetch"
