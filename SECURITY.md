# Security policy

Report a vulnerability privately through GitHub: https://github.com/Questboy23/predictive-loading/security/advisories/new (Security tab, "Report a vulnerability"). Do not open a public issue.

## Disclosure process
Reports are acknowledged within 7 days. A fix is released as a new version (Homebrew tap and GitHub release) and the advisory is published once users can update, normally within 30 days. Credit is given unless the reporter declines.

## Supported versions
Only the latest release receives fixes: https://github.com/Questboy23/predictive-loading/releases/latest

What is in scope: the macOS daemon and CLI (`mac/`), the Chrome extension (`extension/`), the setup guide (`guide/`, `install/`).

Checks on every push: CodeQL (security-extended queries; Python, JavaScript, GitHub Actions), OpenSSF Scorecard, GitHub secret scanning with push protection, Dependabot alerts. Before each release: `tests/security.sh` (manifest permissions, CSP, no network APIs in the extension, standard-library-only Python, Semgrep, Bandit, gitleaks), plus TruffleHog, ShellCheck, OSV-Scanner and Syft + Grype.
