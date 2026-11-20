#!/bin/bash
# Full suite. Exit non-zero on any failure.
set -u
cd "$(dirname "$0")/.." || exit 99
rc=0
run() { echo "== $1"; if eval "$2"; then echo "ok: $1"; else echo "FAILED: $1"; rc=1; fi; }
run "python unit tests" "python3 -m unittest tests/test_predictor.py 2>&1 | tail -3"
run "parity python vs js (10,000 events)" "python3 tests/parity_gen.py && node tests/parity.test.js"
run "link safety" "node tests/links.test.js"
run "mac safety (real unbound, fake system tools)" "python3 -W ignore tests/test_mac.py 2>&1 | tail -3 | grep -q '^OK'"
run "extension e2e (50 loads in Chromium)" "node tests/extension_e2e.js | tail -2"
run "security gate" "tests/security.sh"
echo "== suite exit $rc"
exit $rc
