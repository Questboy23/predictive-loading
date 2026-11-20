#!/bin/bash
# Builds the site and copies it plus the latest GitHub release files to the
# folder the reedsmoneymaker23.com/predictive-loading/ server reads.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="$HOME/predictive-loading-site/predictive-loading"
python3 site/build.py
T=$(mktemp -d)
gh release download -R Questboy23/predictive-loading -D "$T" -p '*.tar.gz' -p '*.zip' -p '*.pdf'
mkdir -p "$DEST/download"
cp "$T"/predictive-loading-extension-*.zip "$DEST/download/predictive-loading-extension.zip"
cp "$T"/predictive-loading-1*.tar.gz "$DEST/download/predictive-loading-source.tar.gz"
cp "$T"/plain.pdf "$T"/paper.pdf "$DEST/"
cp site/predictive-loading/*.html site/predictive-loading/style.css "$DEST/"
(cd "$DEST" && shasum -a 256 download/*.zip download/*.tar.gz plain.pdf paper.pdf > download/SHA256SUMS)
rm -rf "$T"
cat "$DEST/download/SHA256SUMS"
