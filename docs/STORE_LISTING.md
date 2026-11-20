# Chrome Web Store listing

- Name: Predictive Loading
- Category: Productivity (alternative: Developer Tools)
- Language: English
- Short description (132 max): Loads the page you will open next on each site, learned only from your own history. No network calls, no tracking.
- Detailed description:
  Predictive Loading learns, on your own computer, which page you usually open next on each website. When the expected time saved is larger than the expected waste, it asks Chrome to load that page early with the Speculation Rules API, so the click feels instant.

  How it decides: a small Bayesian mixture of context models (previous page, two previous pages, overall frequency, hour of day) predicts the next page. A page is preloaded only if probability x measured load time > expected wasted bytes / measured throughput. Prerendering is used only when it beats a cheaper prefetch, and never for more than 2 pages.

  Safety: same-site links only. Never preloads logout, delete, cart, checkout, buy, pay, order, confirm, cancel, settings or unsubscribe links, downloads, or non-web links. Respects Data Saver. Off in Incognito.

  Privacy: page addresses are stored only as SHA-256 hashes, in Chrome's local storage, on your device. The extension has no network access of its own. "Delete all data" erases everything.

  The popup shows time saved against a random 20% holdout of predictions, with the number of measurements.
- Single purpose: preload the page the user is predicted to open next on the current site.
- Permission justification, `storage`: keeps the per-site prediction model (hashed page paths and counts), measured load times, the on/off switch and the time-saved statistics on the device.
- Host permissions: none requested. Content script on http/https pages is needed to read the current page path, find same-site links and add a Speculation Rules script.
- Remote code: no. All code ships in the package.
- Data usage disclosures: collects no user data (nothing leaves the device). Check "I do not sell or transfer user data", "not used for unrelated purposes", "not used for creditworthiness".
- Privacy policy URL: https://reedsmoneymaker23.com/predictive-loading/privacy.html
- Homepage URL: https://reedsmoneymaker23.com/predictive-loading/
- Support URL: https://github.com/Questboy23/predictive-loading/issues
- Screenshots: `docs/store/screenshot-1.png` (1280x800), `docs/store/screenshot-2.png`
- Icon: `extension/icons/128.png`
