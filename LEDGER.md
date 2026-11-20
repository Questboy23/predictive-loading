# LEDGER: predictive-loading

## Goal
Predict the next load from a person's own history. Resolve it early at two layers: macOS DNS (Unbound + daemon) and Chrome page loads (Speculation Rules).

## Kill test (set before running, 2026-11-19 22:05 EST)
Assumption: the mixture predictor beats an order-1 Markov baseline on replayed per-user data.
Pass: mixture bits/event lower than order-1 Markov on at least 4 of 6 traces, with the 95% bootstrap CI of the difference below 0, and top-1 hit rate not more than 1 point below order-1 Markov on any of those 4.
Fail: stop building, report.

## Decisions
- Repo private until every test passes (prompt says PUBLISH_PUBLIC: yes; this is not Computo and the ideas vault has no patent hold on it).
- Chrome Web Store $5 fee: not paid. Global rule says never spend money, and the agent may not type card data. Route (c).
- Recorded session = Reed's own Chrome history, read locally and hashed in memory, never written to disk or git.

## Status

## Blockers / needs a human
