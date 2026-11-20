# ASKED: every requirement from the prompt

[x] done and verified, [~] partly done (the note says what is missing)

## Process
- [x] task-router at start; overseer active; kill-test-first Route 0 before other builds
- [x] Stop building if predictor cannot beat order-1 Markov on replay
- [x] Unattended; human-only steps at top of LEDGER.md
- [x] Secrets only via 1Password CLI, vault "Predictive Loading"; gitleaks before every push  <!-- No secrets were needed or used; op has no account configured; gitleaks clean before every push -->
- [x] Private repo Questboy23/predictive-loading from first commit; commit+push after each working step
- [x] LEDGER.md and ASKED.md kept; re-read before reports
- [x] Reuse existing tools (Unbound, Speculation Rules, quicklink/instant.page logic with credit, brew tap, browsertime, dnspyre, gitleaks/semgrep/bandit, chrome-webstore-upload-cli, tectonic/matplotlib/TikZ)
- [x] Data: HF mirrors checked first, then originals (MSNBC, NASA-HTTP, ClarkNet, Wikispeedia)

## Shared predictor
- [x] Python and JS ports; 10,000-event parity test identical
- [x] Mac events = domains in lookup order; Chrome events = same-origin paths SHA-256, no query/fragment; no plain URLs on disk
- [x] Repeat of same event counts once
- [x] Mixture of order 0, 1, 2, hour-of-day; KT (n+0.5)/(N+0.5k) with escape
- [x] Weights proportional to decayed product of past predicted probabilities
- [x] Decay d chosen daily from {0.9,0.95,0.98,0.99,0.995,0.999} by 7-day log-loss
- [x] Act only if P(B)*T_saved(B) > C(B), measured T_saved and C (Mac and Chrome definitions)
- [x] Prerender only when its expected net gain beats prefetch
- [x] Report bits/event

## Part 1 macOS
- [x] Homebrew tap Questboy23/homebrew-tap
- [x] Unbound on 127.0.0.1 and ::1 only; prefetch, serve-expired, serve-expired-client-timeout 400, DNSSEC, qname-minimisation, hide-identity, hide-version
- [x] Forward to current network resolvers (scutil --dns)
- [x] Dump cache on sleep/shutdown, reload on start
- [x] Daemon stdlib only; reads query log (mode 600, truncated every 60 s); queries 127.0.0.1 only
- [x] On wake/network change refresh domains predicted for next hour
- [x] launchd KeepAlive; watchdog 2 s restores DNS after 3 failures
- [x] Network change: pass-through until captive.apple.com succeeds
- [x] VPN detected: full bypass
- [x] Never interfere with Apple captive-portal domains
- [x] Health check after macOS or Unbound updates
- [x] Uninstall restores settings exactly, deletes all data
- [x] brew install questboy23/tap/predictive-loading; predictive-loading enable (one admin prompt)
- [x] predictive-loading stats: ms saved/day vs random 10% holdout, with n

## Part 2 Chrome
- [x] MV3, permissions "storage" only, content script http/https, strict CSP
- [x] No network calls, no eval/new Function/innerHTML, incognito not_allowed
- [x] chrome.storage.local, hashed
- [x] Popup: ms saved vs random 20% holdout with n, on/off, Delete all data; dark readable text, no grey
- [x] Speculation Rules from decision rule; moderate eagerness for other same-origin links
- [x] Same origin only; max 2 prerenders; respect saveData
- [x] Never preload action, download, non-http(s) links
- [x] quicklink / instant.page ignore logic copied with license credit

## Tests
- [x] Manifest only "storage"; semgrep, bandit, gitleaks clean
- [x] Source grep for forbidden APIs and non-stdlib imports
- [x] Zero extension-origin requests in 50 page loads
- [x] Port 53 unreachable from LAN; dnssec-failed.org SERVFAIL; data files mode 600
- [x] Simulated crash, fake captive portal, VPN toggle, network switch, stale record, uninstall
- [x] Action links never preloaded
- [x] Unit tests: estimator, mixture, decay selection, decision rule; Py/JS parity
- [x] Route 0 offline replay (hit rate, bits/event) first
- [x] Route 1 dnspyre Tranco top 500: system vs Unbound vs Unbound+predictor
- [~] Route 2 browsertime 2x2, Chrome, 50 Tranco sites, 3 throttle profiles (10/60/150 ms); Safari Mac tool on/off  <!-- Route 2 ran 2x2 x 3 profiles x 50 sites in Chrome (Playwright; browsertime twice gave shared-state data). Safari arm NOT run: needs system DNS change (admin) -->
- [x] Route 3 curl 50 API domains on/off
- [x] Randomized order, holdouts, median, p75, bootstrap 95% CI, n
- [x] Benchmarks: most popular, last successor, order-1 Markov, PPM-C; Chrome default, instant.page, Quicklink; plain Unbound
- [x] Final clean-checkout rerun until clean

## Paper
- [x] tectonic article, one column, 6-8 pages, author "Reed Ostrov, Denison University"
- [x] All listed sections; related work sources verified
- [x] Grayscale system diagram, load timeline, results by Wi-Fi profile
- [x] Every number generated from RESULTS.md; paper.pdf

## Publish
- [x] Repo public, release v1.0 with zip, SHA-256, paper.pdf; public tap
- [~] Web Store route a/b/c  <!-- Route (c): exact clicks at top of LEDGER.md -->
- [x] Website reedsmoneymaker23.com/predictive-loading with brew command, release, store link, paper, privacy page; live check
- [~] Install on Reed's Mac and Chrome; 10-minute live browsing check  <!-- Live check ran 10 min in Chrome for Testing with the extension. Install on Reed's own Mac/Chrome NOT done: admin password + unpacked load are human steps -->
- [~] Web Store review status every 24 h; update link when approved  <!-- Daily scheduled task predictive-loading-webstore-check created; submission itself is a human step -->
- [x] Final report top of LEDGER.md
