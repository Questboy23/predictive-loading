#!/bin/bash
# End-to-end test of the guide's "do the clicks for me" Chrome install, in a
# throwaway Chrome for Testing profile. Waits until the Mac has been idle 60 s
# (it moves the mouse), then checks the profile's Secure Preferences for the
# extension. Usage: guide/test_auto.sh [guide binary]
set -u
cd "$(dirname "$0")/.." || exit 99
BIN="${1:-/tmp/guide-test}"
SUP="$HOME/Library/Application Support/PredictiveLoading"
CFT=$(ls -d "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/"Google Chrome for Testing.app" | tail -1)
idle() { ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}'; }
for _ in $(seq 1 240); do [ "$(idle)" -ge 60 ] && break; sleep 5; done
[ "$(idle)" -ge 60 ] || { echo "SKIP: Mac never idle for 60 s"; exit 2; }
python3 guide/make_flows.py "$SUP" >/dev/null
P=$(mktemp -d /tmp/pl-cft.XXXX)
open -na "$CFT" --args --user-data-dir="$P" --no-first-run --window-position=0,30 --window-size=1100,800 chrome://extensions
sleep 5
front() { osascript -e 'tell application "System Events" to get name of first application process whose frontmost is true' 2>/dev/null; }
for _ in 1 2 3 4 5; do
  open -a "$CFT"; osascript -e 'tell application "Google Chrome for Testing" to activate' 2>/dev/null; sleep 2
  front | grep -q "Chrome for Testing" && break
done
front | grep -q "Chrome for Testing" || { echo "SKIP: test Chrome would not come to the front ($(front))"; osascript -e 'tell application "Google Chrome for Testing" to quit'; exit 2; }
"$BIN" "$SUP/flows.json" chrome >/dev/null 2>&1 &
G=$!
ok=0
for t in $(seq 1 30); do
  sleep 2
  screencapture -x "/tmp/pl-auto-$t.png"
  if grep -qs "PredictiveLoading/extension" "$P/Default/Secure Preferences" "$P/Default/Preferences"; then ok=1; break; fi
done
sleep 10
kill -0 $G 2>/dev/null && closed=no || closed=yes
kill $G 2>/dev/null
osascript -e 'tell application "Google Chrome for Testing" to quit' 2>/dev/null
echo "extension installed by guide: $([ $ok = 1 ] && echo yes || echo no); guide closed itself: $closed; screenshots /tmp/pl-auto-*.png"
[ $ok = 1 ] && [ $closed = yes ]
