# ASKED: every requirement from the prompt

## Process
- [ ] task-router at start; overseer active; kill-test-first Route 0 before other builds
- [ ] Stop building if predictor cannot beat order-1 Markov on replay
- [ ] Unattended; human-only steps at top of LEDGER.md
- [ ] Secrets only via 1Password CLI, vault "Predictive Loading"; gitleaks before every push
- [ ] Private repo Questboy23/predictive-loading from first commit; commit+push after each working step
- [ ] LEDGER.md and ASKED.md kept; re-read before reports
- [ ] Reuse existing tools (Unbound, Speculation Rules, quicklink/instant.page logic with credit, brew tap, browsertime, dnspyre, gitleaks/semgrep/bandit, chrome-webstore-upload-cli, tectonic/matplotlib/TikZ)
- [ ] Data: HF mirrors checked first, then originals (MSNBC, NASA-HTTP, ClarkNet, Wikispeedia)

## Shared predictor
- [ ] Python and JS ports; 10,000-event parity test identical
- [ ] Mac events = domains in lookup order; Chrome events = same-origin paths SHA-256, no query/fragment; no plain URLs on disk
- [ ] Repeat of same event counts once
- [ ] Mixture of order 0, 1, 2, hour-of-day; KT (n+0.5)/(N+0.5k) with escape
- [ ] Weights proportional to decayed product of past predicted probabilities
- [ ] Decay d chosen daily from {0.9,0.95,0.98,0.99,0.995,0.999} by 7-day log-loss
- [ ] Act only if P(B)*T_saved(B) > C(B), measured T_saved and C (Mac and Chrome definitions)
- [ ] Prerender only when its expected net gain beats prefetch
- [ ] Report bits/event

## Part 1 macOS
- [ ] Homebrew tap Questboy23/homebrew-tap
- [ ] Unbound on 127.0.0.1 and ::1 only; prefetch, serve-expired, serve-expired-client-timeout 400, DNSSEC, qname-minimisation, hide-identity, hide-version
- [ ] Forward to current network resolvers (scutil --dns)
- [ ] Dump cache on sleep/shutdown, reload on start
- [ ] Daemon stdlib only; reads query log (mode 600, truncated every 60 s); queries 127.0.0.1 only
- [ ] On wake/network change refresh domains predicted for next hour
- [ ] launchd KeepAlive; watchdog 2 s restores DNS after 3 failures
- [ ] Network change: pass-through until captive.apple.com succeeds
- [ ] VPN detected: full bypass
- [ ] Never interfere with Apple captive-portal domains
- [ ] Health check after macOS or Unbound updates
- [ ] Uninstall restores settings exactly, deletes all data
- [ ] brew install questboy23/tap/predictive-loading; predictive-loading enable (one admin prompt)
- [ ] predictive-loading stats: ms saved/day vs random 10% holdout, with n

## Part 2 Chrome
- [ ] MV3, permissions "storage" only, content script http/https, strict CSP
- [ ] No network calls, no eval/new Function/innerHTML, incognito not_allowed
- [ ] chrome.storage.local, hashed
- [ ] Popup: ms saved vs random 20% holdout with n, on/off, Delete all data; dark readable text, no grey
- [ ] Speculation Rules from decision rule; moderate eagerness for other same-origin links
- [ ] Same origin only; max 2 prerenders; respect saveData
- [ ] Never preload action, download, non-http(s) links
- [ ] quicklink / instant.page ignore logic copied with license credit

## Tests
- [ ] Manifest only "storage"; semgrep, bandit, gitleaks clean
- [ ] Source grep for forbidden APIs and non-stdlib imports
- [ ] Zero extension-origin requests in 50 page loads
- [ ] Port 53 unreachable from LAN; dnssec-failed.org SERVFAIL; data files mode 600
- [ ] Simulated crash, fake captive portal, VPN toggle, network switch, stale record, uninstall
- [ ] Action links never preloaded
- [ ] Unit tests: estimator, mixture, decay selection, decision rule; Py/JS parity
- [ ] Route 0 offline replay (hit rate, bits/event) first
- [ ] Route 1 dnspyre Tranco top 500: system vs Unbound vs Unbound+predictor
- [ ] Route 2 browsertime 2x2, Chrome, 50 Tranco sites, 3 throttle profiles (10/60/150 ms); Safari Mac tool on/off
- [ ] Route 3 curl 50 API domains on/off
- [ ] Randomized order, holdouts, median, p75, bootstrap 95% CI, n
- [ ] Benchmarks: most popular, last successor, order-1 Markov, PPM-C; Chrome default, instant.page, Quicklink; plain Unbound
- [ ] Final clean-checkout rerun until clean

## Paper
- [ ] tectonic article, one column, 6-8 pages, author "Reed Ostrov, Denison University"
- [ ] All listed sections; related work sources verified
- [ ] Grayscale system diagram, load timeline, results by Wi-Fi profile
- [ ] Every number generated from RESULTS.md; paper.pdf

## Publish
- [ ] Repo public, release v1.0 with zip, SHA-256, paper.pdf; public tap
- [ ] Web Store route a/b/c
- [ ] Website reedsmoneymaker23.com/predictive-loading with brew command, release, store link, paper, privacy page; live check
- [ ] Install on Reed's Mac and Chrome; 10-minute live browsing check
- [ ] Web Store review status every 24 h; update link when approved
- [ ] Final report top of LEDGER.md
