# Predictive Loading

Predicts the next thing you will load from your own history and does the waiting early, at two layers:

1. **macOS DNS** for every app: a local Unbound resolver plus a standard-library Python daemon that warms the names you are likely to look up next.
2. **Chrome page loads**: a Manifest V3 extension (permission `storage` only) that writes Speculation Rules for the same-site page you are likely to open next.

Both use one predictor (`predictor/predictor.py`, ported line for line to `extension/predictor.js`; a 10,000-event test requires identical output): a Bayesian mixture of order-0, order-1, order-2 and hour-of-day models, Krichevsky-Trofimov estimates with an escape symbol, recency decay chosen daily from six values by 7-day log-loss. It acts on a candidate only if `P(B) x T_saved(B) > C(B)`, with both sides measured on your machine.

Measured results, with n and confidence intervals: [RESULTS.md](RESULTS.md). Paper: [paper/paper.pdf](paper/paper.pdf).

## Install (macOS)

```bash
brew install questboy23/tap/predictive-loading
predictive-loading enable      # one admin prompt
predictive-loading stats       # ms saved per day vs a random 10% holdout, with n
predictive-loading uninstall   # restores your DNS settings exactly, deletes all data
```

Safety: Unbound answers only 127.0.0.1 and ::1, validates DNSSEC. A watchdog restores your original DNS after 3 failed checks 2 s apart. After a network change it passes through until captive.apple.com succeeds. It steps aside while a VPN is up and never touches Apple's captive-portal names.

## Install (Chrome)

Private install into your own Chrome (unpacked, nothing published), with an on-screen guide:

```bash
install/setup.sh chrome
```

It copies the extension to `~/Library/Application Support/PredictiveLoading/extension`, opens `chrome://extensions`, and starts a floating guide that reads the screen on this Mac (Vision text recognition), draws a red arrow to the next thing to click, and has Copy / Paste / "Open this folder for me" buttons. Chrome 137+ ignores `--load-extension`, so the two clicks (Load unpacked, Select) stay with you. `install/setup.sh store` walks through a private Chrome Web Store submission; `install/setup.sh mac` turns on the macOS tool. The guide asks once for Screen Recording (arrows) and Accessibility (paste for you); without them it still shows every step.

The popup shows ms saved against a random 20% holdout with n, an on/off switch and "Delete all data".

## Privacy

Nothing leaves your device. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Tests

```bash
npm install && tests/run_all.sh
```

Runs: predictor unit tests, Python/JS parity, link-safety cases, 14 macOS safety tests against a real Unbound with fake system tools, a 50-load end-to-end Chromium run of the extension, and the security gate (manifest, forbidden APIs, stdlib-only imports, semgrep, bandit, gitleaks).

## Credits

Link-safety checks adapted from instant.page (MIT) and Quicklink (Apache-2.0); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

MIT License. Reed Ostrov, Denison University.
