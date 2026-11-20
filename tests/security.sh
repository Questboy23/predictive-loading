#!/bin/bash
# Security gate. Any failure blocks release. Exit code = number of failed checks.
cd "$(dirname "$0")/.." || exit 99
fails=0
check() { if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; fails=$((fails+1)); fi; }

check "manifest permissions are exactly [\"storage\"]" \
  "python3 -c 'import json,sys; m=json.load(open(\"extension/manifest.json\")); sys.exit(0 if m[\"permissions\"]==[\"storage\"] and \"host_permissions\" not in m and \"optional_permissions\" not in m and m.get(\"incognito\")==\"not_allowed\" else 1)'"
check "manifest CSP is strict (script-src self, no unsafe)" \
  "python3 -c 'import json,sys; c=json.load(open(\"extension/manifest.json\"))[\"content_security_policy\"][\"extension_pages\"]; sys.exit(0 if \"script-src '\\''self'\\''\" in c and \"unsafe\" not in c else 1)'"
check "extension: no fetch/XMLHttpRequest/WebSocket/sendBeacon/eval/Function(/innerHTML/EventSource/importScripts" \
  "! grep -nE '\\bfetch\\s*\\(|XMLHttpRequest|WebSocket|sendBeacon|\\beval\\s*\\(|Function\\s*\\(|innerHTML|outerHTML|insertAdjacentHTML|document\\.write|EventSource|importScripts|new Image' extension/*.js extension/*.html"
check "mac + predictor: Python imports are standard library only" \
  "python3 - <<'PY'
import ast, sys, pathlib
std = set(sys.stdlib_module_names) | {'dnsq', 'daemon', 'predictor', 'cli'}
bad = []
for f in list(pathlib.Path('mac/lib').glob('*.py')) + [pathlib.Path('predictor/predictor.py')]:
    for n in ast.walk(ast.parse(f.read_text())):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module] if isinstance(n, ast.ImportFrom) and n.module else []
        bad += ['%s:%s' % (f, m) for m in mods if m.split('.')[0] not in std]
print(*bad, sep='\n')
sys.exit(1 if bad else 0)
PY"
check "daemon queries 127.0.0.1 only" \
  "! grep -nE 'dnsq\\.query\\(' mac/lib/daemon.py | grep -v '\"127.0.0.1\"'"
check "no plain URLs stored by the extension (paths/origins hashed before storage)" \
  "grep -q 'sha256(location.pathname' extension/content.js && grep -q 'sha256(location.origin)' extension/content.js && ! grep -nE 'store\\.set\\([^)]*location' extension/content.js"
check "semgrep p/javascript p/python p/secrets clean" \
  "semgrep scan --quiet --error --metrics=off --config p/javascript --config p/python --config p/secrets extension mac predictor bench tests/*.py >/tmp/pl-semgrep.txt 2>&1 || { cat /tmp/pl-semgrep.txt | tail -20; false; }"
check "bandit clean (medium+)" \
  "bandit -q -r mac/lib predictor -ll >/tmp/pl-bandit.txt 2>&1 || { tail -20 /tmp/pl-bandit.txt; false; }"
check "gitleaks clean (git history + working tree)" \
  "gitleaks detect --no-banner --redact >/dev/null 2>&1 && gitleaks detect --no-git --no-banner --redact --source . >/dev/null 2>&1"
echo "security: $fails failed"
exit $fails
