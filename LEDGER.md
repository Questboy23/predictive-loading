# LEDGER: predictive-loading

## Goal
Predict the next load from a person's own history. Resolve it early at two layers: macOS DNS (Unbound + daemon) and Chrome page loads (Speculation Rules).

## Kill test (set before running, 2026-11-19 22:05 EST)
Assumption: the mixture predictor beats an order-1 Markov baseline on replayed per-user data.
Pass: mixture bits/event lower than order-1 Markov on at least 4 of 6 traces, with the 95% bootstrap CI of the difference below 0, and top-1 hit rate not more than 1 point below order-1 Markov on any of those 4.
Fail: stop building, report.

## Kill test result (2026-11-19 22:20 EST): PASS
1,000 users per public trace (fewer where fewer qualify), recorded Chrome history as 1 user (11,879 domain events) and 137 origins (36,075 path events).
Mixture bits/event minus order-1 Markov, 95% bootstrap CI, all below 0 on 6/6 traces: MSNBC [-0.03,-0.01], NASA [-1.62,-1.46], ClarkNet [-2.31,-2.03], Wikispeedia [-2.76,-2.59], Chrome domains [-0.62,-0.47], Chrome paths [-5.07,-2.20].
Top-1 hit minus Markov: above 0 on 5, CI spans 0 on Chrome domains [-0.3,+1.0] pts. Threshold met; building continues.
Loss reported: PPM-C beats the mixture on Chrome domains top-1 (35.7% vs 31.5%).
Design changes made before the full run (both found on a 30-user smoke run): escape symbol counted KT-style; escape mass routed by order-0 probabilities; previous event excluded from candidates.

## Decisions
- Repo private until every test passes (prompt says PUBLISH_PUBLIC: yes; this is not Computo and the ideas vault has no patent hold on it).
- Chrome Web Store $5 fee: not paid. Global rule says never spend money, and the agent may not type card data. Route (c).
- Recorded session = Reed's own Chrome history, read locally and hashed in memory, never written to disk or git.

## Status

## Blockers / needs a human
