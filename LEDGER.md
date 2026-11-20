# LEDGER: predictive-loading

## Update 2026-11-20 00:55 EST
- Extension installed privately in Reed's Chrome (Default profile, unpacked, id cgopchobemmbolhpnfdbhflkpohhicgn) via `install/setup.sh chrome` and the new on-screen guide (guide/Guide.swift). Verified on screen: card shows Predictive Loading 1.0.0, On, pinned.
- Web Store submission paused at Reed's request (test privately first). Daily store-check task disabled. When ready: `install/setup.sh store` (visibility Private).

## Update 2026-11-20 01:50 EST
- Mac tool enabled on Reed's Mac (v1.0.2 from the public tap): DNS 127.0.0.1, mode active, health local/resolve/dnssec all true, web loads.
- Fixed: status/stats could not read the root-owned data folder (now 711; files stay 600). v1.0.1, v1.0.2 (enable restarts services) released; tap updated.

## NEEDS A HUMAN (do these; everything else is done)
1. Chrome Web Store submission (route c; 1Password CLI has no account, so route a was impossible; route b needs your password and the $5 fee):
   1. Open https://chrome.google.com/webstore/devconsole and sign in with your Google account.
   2. If asked, pay the one-time $5 developer registration fee.
   3. Click "New item", upload `predictive-loading-extension-1.0.0.zip` from https://github.com/Questboy23/predictive-loading/releases/tag/v1.0
   4. Store listing tab: paste name, short and detailed description, category from `docs/STORE_LISTING.md`; upload `extension/icons/128.png`, `docs/store/screenshot-1280x800.png`, `docs/store/promo-440x280.png`.
   5. Privacy tab: single purpose, `storage` justification, "no remote code", data-use boxes, privacy URL https://reedsmoneymaker23.com/predictive-loading/privacy.html (all text in `docs/STORE_LISTING.md`).
   6. Click "Submit for review". The daily task "predictive-loading-webstore-check" (09:08 EST) puts the store link on the site and README once it is live.
2. DONE 2026-11-20. Mac install on your own Mac: `brew install questboy23/tap/predictive-loading` (verified from the public tap), then `predictive-loading enable` and type your admin password once. Check later with `predictive-loading stats`.
3. Chrome install: DONE 2026-11-20 (unpacked, via install/setup.sh chrome).
4. Safari arm of Route 2 (Mac tool on/off): needs the system DNS switched, so it can only run after step 2.
5. Optional: configure the 1Password CLI (`op account add`) and create vault "Predictive Loading" with Web Store API client id/secret/refresh token, so future releases can use chrome-webstore-upload-cli.

## Final report (2026-11-19 23:50 EST)
Done and verified:
- Kill test (Route 0) PASS: mixture log-loss below order-1 Markov on 6/6 traces (CI below 0), below PPM-C on 4/6.
- Full suite from a clean clone: 6/6 groups pass (unit, parity 10,000 events, link safety, 14 Mac safety tests, extension e2e 50 loads with 0 extension-origin requests and 0 action-link requests, security gate 9/9 incl. semgrep, bandit, gitleaks). gitleaks clean before every push.
- Route 1 (dnspyre, Tranco 500): later-round medians system 4.59, Unbound 5.01, Unbound+predictor 4.46 ms; p75 27.09 vs 20.92 ms for Unbound vs +predictor; campus resolver p75 6.64 ms stays fastest.
- Route 2 (Chrome, 50 sites x 2x2 x 3 profiles, 312 visit pairs): no page-load gain. Extension acted on 3 to 5 of ~25 visits per cell after one training visit; at 60 ms it was 76 ms slower [13, 432]. Reported as a loss.
- Route 3 (curl, 50 API hosts): later rounds 8.81 ms faster per call [4.56, 15.73], n=200; first calls slower, paired -9.96 ms [-37.62, -0.64], n=50.
- Page benchmark (60 ms, hovering user, n=7 to 8 sites): ours 575 ms median vs Chrome default 2375, instant.page 1622, Quicklink 1584 (Quicklink 87 speculative requests vs our 9). Small n.
- 10-minute live check (Chrome for Testing + extension): 58 loads, 0 extension-origin requests, popup shows n=3 early, holdout n=0.
- Paper: paper/paper.pdf, 8 pages, every number from RESULTS.md.
- Published: repo public; release v1.0 (zip, tarball, paper.pdf, SHA256SUMS); public tap Questboy23/homebrew-tap, `brew install` + `brew test` verified from it; site https://reedsmoneymaker23.com/predictive-loading/ (index, privacy, paper.pdf all 200).
Not done: Web Store submission, install on Reed's own Mac and Chrome, Safari arm (all need a human, see top). Route 2 deviates from the prompt: browsertime replaced by Playwright after two invalid browsertime runs.

## Decision: going public
The global rule forbids publishing unfiled inventions. The prompt for this project explicitly says PUBLISH_PUBLIC: yes, and the predecessor idea (per-user prefetch) is already public at reedsmoneymaker23.com/prefetch under MIT. Published on that basis.

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

## Status history (2026-11-19 22:58 EST)
- Done and tested: shared predictor (Py+JS, parity 10,000 events identical), 13 unit tests, Mac daemon + CLI + Unbound config (12 safety scenarios pass), extension (e2e 50 loads, 0 extension-origin requests, 0 action-link requests), security gate 9/9, Homebrew formula builds and `brew test` passes from a local tap.
- Route 0 done (PASS). Route 1 done. Route 3, Route 2 (6 parallel browsertime sessions), pages benchmark running.
- Route 2 design: no root available, so Chrome for Testing goes through a local SOCKS5 proxy that adds Wi-Fi RTT and resolves names with the system resolver (Mac tool off) or Unbound + predictor (on). Safari arm needs system DNS change: human step.

## Blockers / needs a human
- Web Store route (a) impossible: 1Password CLI has no account configured on this Mac (`op whoami`: "No accounts configured"). Route (b) blocked: Google asked for a password re-sign-in on the dashboard, and the $5 fee conflicts with the global never-spend rule. Route (c) taken.
- macOS live install needs Reed's admin password (`predictive-loading enable` shows one macOS prompt).
