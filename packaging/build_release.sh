#!/bin/bash
# Builds dist/: extension zip, source tarball, paper.pdf, SHA256SUMS.
set -euo pipefail
cd "$(dirname "$0")/.."
V=$(python3 -c 'import json;print(json.load(open("extension/manifest.json"))["version"])')
rm -rf dist && mkdir -p dist
(cd extension && zip -q -X -r "../dist/predictive-loading-extension-$V.zip" manifest.json predictor.js sha256.js linksafety.js content.js popup.html popup.css popup.js icons)
git archive --format=tar.gz --prefix="predictive-loading-$V/" -o "dist/predictive-loading-$V.tar.gz" HEAD
cp paper/paper.pdf dist/paper.pdf
cp paper/plain.pdf dist/plain.pdf
(cd dist && shasum -a 256 * > SHA256SUMS)
cat dist/SHA256SUMS
