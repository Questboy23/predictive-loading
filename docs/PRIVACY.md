# Predictive Loading privacy policy

Effective 2026-11-20.

Predictive Loading collects nothing and sends nothing anywhere.

## Chrome extension
- Permission: `storage` only. No host permissions, no network permissions.
- What it stores, on your computer only, in `chrome.storage.local`: SHA-256 hashes of each site's origin and of the page paths you visit on that site (query strings and fragments are dropped before hashing), counts used for prediction, measured page load times and sizes, and the time-saved numbers shown in the popup.
- It never stores a plain URL. It does not run in Incognito windows.
- It makes no network requests. Pages it predicts are loaded early by Chrome itself through the Speculation Rules API, from the same site you are on.
- "Delete all data" in the popup erases everything it stored. Removing the extension erases it too.

## macOS tool
- Runs a local DNS resolver (Unbound) that answers only this Mac (127.0.0.1 and ::1).
- Stores, on your Mac only, with file mode 600: the domain names your Mac looked up recently (the query log is read and emptied every 60 s), prediction counts, lookup timings, and a resolver cache file.
- Lookups go to the same DNS servers your network already gives you. Nothing is sent to the author or any third party.
- `predictive-loading uninstall` restores your original DNS settings and deletes all of its files.

## Contact
Open an issue at https://github.com/Questboy23/predictive-loading/issues.
