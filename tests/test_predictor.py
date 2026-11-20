import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "predictor"))
from predictor import DECAYS, Predictor, _Bank, choose_action, should_act  # noqa: E402


def full_dist(p, hour=0):
    """Mixture probability of every seen symbol plus the novel slot."""
    bank = p.banks[p.choice]
    prep = bank.prepare(p._ctxs(hour), len(p.seen))
    w = bank.weights()
    total = sum(p._mix(bank, prep, s, w)[0] for s in p.seen)
    novel = p._mix(bank, prep, "\x00never-seen", w)[0]
    return total, novel


class Estimator(unittest.TestCase):
    def test_kt_with_escape_values(self):
        # Context seen: a (new), a, b (new). N=1 repeat, e=2 escapes, k=2.
        b = _Bank(0.999999999)
        b.scale = 1.0
        b.inv = 1.0  # no decay: exact counts
        ctx = ("", "", "\u0001", "0")
        for x in ("a", "a", "b"):
            prep = b.prepare(ctx, 2)
            b.update(ctx, x, b.model_probs(prep, x, 2))
        prep = b.prepare(ctx, 2)
        denom = 1 + 2 + 0.5 * 3
        self.assertAlmostEqual(b.p0(prep, "a", 2), 1.5 / denom)
        self.assertAlmostEqual(b.p0(prep, "b", 2), 0.5 / denom)
        self.assertAlmostEqual(b.p0(prep, "zzz", 2), 2.5 / denom)

    def test_distribution_sums_to_one(self):
        p = Predictor()
        seq = "a b c a b d a b c e f a b".split()
        for i, x in enumerate(seq):
            p.observe(x, hour=i % 3, day=0)
            total, novel = full_dist(p, hour=(i + 1) % 3)
            self.assertAlmostEqual(total + novel, 1.0, places=9)

    def test_repeat_counts_once(self):
        p = Predictor()
        self.assertIsNotNone(p.observe("a"))
        self.assertIsNone(p.observe("a"))
        self.assertEqual(p.events, 1)

    def test_decay_renormalisation_keeps_probs(self):
        p = Predictor(decays=(0.9,), default_index=0)
        for i in range(5000):  # 0.9^-5000 overflows without renormalisation
            p.observe("ab"[i % 2] + str(i % 3))
        self.assertLess(p.banks[0].scale, 1e101)
        total, novel = full_dist(p)
        self.assertAlmostEqual(total + novel, 1.0, places=9)


class Mixture(unittest.TestCase):
    def test_learns_deterministic_cycle(self):
        p = Predictor()
        for _ in range(60):
            for x in "abc":
                p.observe(x)
        self.assertEqual(p.predict(0, 1)[0][0], "a")
        self.assertGreater(p.predict(0, 1)[0][1], 0.9)

    def test_order2_beats_order1_where_needed(self):
        # After 'a' comes x if preceded by 'p', y if preceded by 'q'.
        p = Predictor()
        for _ in range(80):
            for x in ("p", "a", "x", "q", "a", "y"):
                p.observe(x)
        w = p.banks[p.choice].weights()
        self.assertEqual(max(range(4), key=lambda i: w[i]), 2)
        p.observe("p")
        p.observe("a")
        self.assertEqual(p.predict(0, 1)[0][0], "x")

    def test_hour_model_used(self):
        # Hour fully determines the event; order 1/2 see a 50/50 choice.
        import random
        rng = random.Random(3)
        slots = {8: "work", 14: "lunch", 20: "home"}
        p = Predictor()
        for i in range(300):
            hour = rng.choice([h for h in slots if slots[h] != p.prev1])
            p.observe(slots[hour], hour=hour, day=i // 10)
        w = p.banks[p.choice].weights()
        self.assertEqual(max(range(4), key=lambda i: w[i]), 3)
        for hour, x in slots.items():
            if x != p.prev1:
                self.assertEqual(p.predict(hour, 1)[0][0], x)


class DecaySelection(unittest.TestCase):
    def test_choice_changes_only_at_day_boundary_and_picks_min_loss(self):
        p = Predictor()
        p.observe("a", day=0)
        p.observe("b", day=0)
        self.assertEqual(p.choice, 3)
        p.day_loss = [5.0, 4.0, 3.0, 2.0, 1.0, 9.0]
        p.observe("c", day=1)
        self.assertEqual(p.choice, 4)

    def test_window_is_seven_days(self):
        p = Predictor()
        p.day = 0
        for d in range(1, 12):
            p.day_loss = [float(d == 1) * 100] + [1.0] * 5
            p._new_day(d)
        self.assertEqual(len(p.history), 7)
        self.assertEqual(p.choice, 0)  # the big day-1 loss on decay 0 left the window

    def test_nonstationary_prefers_fast_decay(self):
        p = Predictor()
        for day in range(30):
            sym = "s%d" % (day // 2)
            for i in range(40):
                p.observe(sym if i % 2 else "hub", day=day)
        self.assertLess(DECAYS[p.choice], 0.995)


class DecisionRule(unittest.TestCase):
    def test_should_act(self):
        self.assertTrue(should_act(0.5, 40.0, 1.0))
        self.assertFalse(should_act(0.01, 40.0, 1.0))
        self.assertFalse(should_act(0.5, 2.0, 1.0))

    def test_choose_action(self):
        self.assertIsNone(choose_action(0.01, 1000, 50, 200, 0.3))
        self.assertEqual(choose_action(0.9, 1000, 5, 100, 0.3), "prerender")
        self.assertEqual(choose_action(0.3, 1000, 5, 400, 0.3), "prefetch")

    def test_bits_reported(self):
        p = Predictor()
        for x in "abcabcabc":
            p.observe(x)
        self.assertTrue(math.isfinite(p.bits_per_event()))
        self.assertGreater(p.bits_per_event(), 0)


if __name__ == "__main__":
    unittest.main()
