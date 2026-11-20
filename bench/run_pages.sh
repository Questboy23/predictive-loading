#!/bin/bash
# Runs the page-preloading benchmark with its own proxy on 1190 (system resolver, 60 ms RTT).
cd "$(dirname "$0")/.." || exit 1
python3 bench/socksproxy.py 1190 5300 & P=$!
sleep 1
node bench/pages_bench.js "$@"
kill $P
