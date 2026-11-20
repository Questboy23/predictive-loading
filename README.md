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

Chrome Web Store: link on https://reedsmoneymaker23.com/predictive-loading/ once review finishes. Until then: download `predictive-loading-extension-1.0.0.zip` from the GitHub release, unzip, open `chrome://extensions`, turn on Developer mode, "Load unpacked".

The popup shows ms saved against a random 20% holdout with n, an on/off switch and "Delete all data".

## Privacy

Nothing leaves your device. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Tests

```bash
npm install && tests/run_all.sh
```

Runs: predictor unit tests, Python/JS parity, link-safety cases, 12 macOS safety scenarios against a real Unbound with fake system tools, a 50-load end-to-end Chromium run of the extension, and the security gate (manifest, forbidden APIs, stdlib-only imports, semgrep, bandit, gitleaks).

## Credits

Link-safety checks adapted from instant.page (MIT) and Quicklink (Apache-2.0); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

MIT License. Reed Ostrov, Denison University.
