#!/bin/bash
# Private setup helper (nothing is published). Usage:
#   install/setup.sh chrome   load the extension into your own Chrome (like an unpacked dev extension)
#   install/setup.sh store    walk through a PRIVATE Chrome Web Store submission
#   install/setup.sh mac      install and turn on the macOS DNS tool (runs by itself; you type your Mac password once)
#   install/setup.sh all      chrome, then mac
# Copies the extension to ~/Library/Application Support/PredictiveLoading, opens
# the right page, and starts an on-screen guide with arrows and Copy/Paste buttons.
# Chrome 137+ ignores --load-extension, so two clicks in Chrome stay manual; the guide points at them.
set -euo pipefail
FLOW="${1:-chrome}"
if [ "$FLOW" = all ]; then "$0" chrome; exec "$0" mac; fi
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SUP="$HOME/Library/Application Support/PredictiveLoading"
APP="$SUP/PLGuide.app" # no space in the name: the guide looks for "Predictive Loading" on screen
mkdir -p "$SUP/store"
chmod 700 "$SUP"

rsync -a --delete --exclude '.*' "$REPO/extension/" "$SUP/extension/"
rm -f "$SUP/predictive-loading-extension.zip"
(cd "$SUP/extension" && zip -q -X -r "$SUP/predictive-loading-extension.zip" manifest.json predictor.js sha256.js linksafety.js content.js popup.html popup.css popup.js icons)
cp "$REPO/docs/store/screenshot-1280x800.png" "$REPO/docs/store/promo-440x280.png" "$SUP/store/"
cp "$REPO/extension/icons/128.png" "$SUP/store/icon-128.png"
python3 "$REPO/guide/make_flows.py" "$SUP" >/dev/null

# Build the guide app when missing or older than its source (needs Xcode command line tools).
BIN="$APP/Contents/MacOS/Guide"
if [ ! -x "$BIN" ] || [ "$REPO/guide/Guide.swift" -nt "$BIN" ]; then
  mkdir -p "$APP/Contents/MacOS"
  cp "$REPO/guide/Info.plist" "$APP/Contents/Info.plist"
  swiftc -O -swift-version 5 -o "$BIN" "$REPO/guide/Guide.swift" 2>/dev/null || { echo "Could not build the guide (install Xcode command line tools: xcode-select --install). Follow docs/INSTALL_CHROME.md instead."; BIN=""; }
  [ -n "$BIN" ] && codesign -s - --force "$APP" >/dev/null 2>&1 || true
  # A new build needs the macOS grants again: list the app in Accessibility and Screen Recording and open both prompts.
  [ -n "$BIN" ] && open -n "$APP" --args --ask-permissions
fi

open_in_chrome() {
  osascript >/dev/null 2>&1 <<OSA || open -a "Google Chrome" "$1"
tell application "Google Chrome"
  activate
  if (count of windows) = 0 then make new window
  tell front window to make new tab with properties {URL:"$1"}
end tell
OSA
}

case "$FLOW" in
  chrome)
    if grep -qs "PredictiveLoading/extension" "$HOME/Library/Application Support/Google/Chrome/"*/"Secure Preferences"; then
      echo "Already installed in Chrome (unpacked from $SUP/extension). To pick up a new version, click its reload arrow on chrome://extensions."
      exit 0
    fi
    printf '%s' "$SUP/extension" | pbcopy; open_in_chrome "chrome://extensions" ;;
  store)  open_in_chrome "https://chrome.google.com/webstore/devconsole" ;;
  mac)
    command -v predictive-loading >/dev/null || brew install questboy23/tap/predictive-loading
    if predictive-loading status 2>/dev/null | grep -q "mode: active"; then echo "Mac tool already on."; else
      echo "Turning on the Mac tool. macOS will ask for your Mac password once."
      predictive-loading enable
    fi
    predictive-loading status
    echo "Time saved shows here after a day or so:  predictive-loading stats"
    exit 0 ;;
  *) echo "usage: $0 chrome|store|mac"; exit 2 ;;
esac

pkill -f "PLGuide.app/Contents/MacOS/Guide" 2>/dev/null || true
[ -x "$APP/Contents/MacOS/Guide" ] && open -n "$APP" --args "$SUP/flows.json" "$FLOW"
echo "Guide started for: $FLOW. Extension folder: $SUP/extension"
