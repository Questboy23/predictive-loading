"""Writes tests/fixtures/parity_events.json (10,000 events) and the Python
port's outputs to tests/fixtures/parity_py.txt. tests/parity.test.js runs the
JS port on the same events and requires byte-identical output."""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "predictor"))
from predictor import Predictor

def events(n=10000, seed=7):
    rng = random.Random(seed)
    vocab = ["e%03d" % i for i in range(120)]
    nxt = {v: rng.sample(vocab, 4) for v in vocab}
    out, cur, t = [], vocab[0], 0
    while len(out) < n:
        t += rng.randint(20, 3000)
        r = rng.random()
        cur = cur if r < 0.08 else rng.choice(nxt[cur]) if r < 0.8 else rng.choice(vocab)
        out.append([cur, (t // 3600) % 24, t // 86400])
    return out

def run(evs):
    p, lines = Predictor(), []
    for x, hr, d in evs:
        r = p.observe(x, hr, d)
        lines.append("skip" if r is None else "%s\t%.10f\t%d" % (r[0], r[1], p.choice))
    top = p.predict(evs[-1][1], 5)
    lines.append("final\t%.10f\t" % p.bits_per_event() + ",".join("%s:%.10f" % (s, q) for s, q in top))
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    evs = events()
    os.makedirs(os.path.join(HERE, "fixtures"), exist_ok=True)
    json.dump(evs, open(os.path.join(HERE, "fixtures", "parity_events.json"), "w"))
    open(os.path.join(HERE, "fixtures", "parity_py.txt"), "w").write(run(evs))
    print(len(evs), "events; days spanned:", evs[-1][2] - evs[0][2])
