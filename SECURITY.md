# Security policy

Report a vulnerability privately through GitHub: Security tab, "Report a vulnerability". Do not open a public issue.

What is in scope: the macOS daemon and CLI (`mac/`), the Chrome extension (`extension/`), the setup guide (`guide/`, `install/`).

Checks on every push: CodeQL (security-extended queries; Python, JavaScript, GitHub Actions), OpenSSF Scorecard, GitHub secret scanning with push protection, Dependabot alerts. Before each release: `tests/security.sh` (manifest permissions, CSP, no network APIs in the extension, standard-library-only Python, Semgrep, Bandit, gitleaks), plus TruffleHog, ShellCheck, OSV-Scanner and Syft + Grype.
