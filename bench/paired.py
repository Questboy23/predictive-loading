"""Paired-difference statistics fixed in PREREG.md: Hodges-Lehmann estimate,
95% percentile bootstrap (10,000 resamples, seed 0), two-sided Wilcoxon
signed-rank, Holm correction."""
import random

from scipy.stats import wilcoxon


def hodges_lehmann(d):
    w = sorted((d[i] + d[j]) / 2 for i in range(len(d)) for j in range(i, len(d)))
    n = len(w)
    return w[n // 2] if n % 2 else (w[n // 2 - 1] + w[n // 2]) / 2


def boot_ci(d, stat=hodges_lehmann, iters=10000, seed=0):
    rng = random.Random(seed)
    n = len(d)
    bs = sorted(stat([d[rng.randrange(n)] for _ in range(n)]) for _ in range(iters))
    return bs[int(0.025 * iters)], bs[int(0.975 * iters) - 1]


def wilcoxon_p(d):
    nz = [x for x in d if x != 0]
    return float(wilcoxon(nz).pvalue) if len(nz) >= 2 else 1.0


def holm(ps):
    """Holm-adjusted p-values, same order as given."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def summary(d, iters=10000):
    lo, hi = boot_ci(d, iters=iters)
    return {"n": len(d), "hl": round(hodges_lehmann(d), 2), "ci": [round(lo, 2), round(hi, 2)],
            "p": wilcoxon_p(d), "faster_share": round(sum(x < 0 for x in d) / len(d), 3)}


if __name__ == "__main__":  # self-check
    import statistics
    d = [1.0, 2.0, 3.0, 4.0, 100.0]
    assert hodges_lehmann(d) == 3.0, hodges_lehmann(d)
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    rng = random.Random(1)
    z = [rng.gauss(-5, 2) for _ in range(60)]
    s = summary(z, iters=2000)
    assert s["ci"][0] < -5 < s["ci"][1] and s["p"] < 1e-6, s
    assert abs(s["hl"] - statistics.median(z)) < 1.0
    print("paired.py self-check ok")
