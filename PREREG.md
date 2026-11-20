# Pre-registration: confirmatory experiments (written 2026-11-20 02:45 EST, before E2 and E3 ran)

Committed to git before any E2 or E3 data exists. Analysis scripts are committed with this file and run once on the final data. Anything not listed here is reported as exploratory.

## Disclosure
E1 was already running when this was written. Per-round medians from rounds 1 and 2 of E1a had been printed to the log and seen: network resolver 29.7 then 4.7 ms, Unbound alone 41.9 then 30.5 ms, Unbound + predictor 48.9 then 0.5 ms. E1's analysis plan below was fixed after seeing those, so E1 is labeled a replication with a fixed analysis, not a blind test.

The 0.5 ms figure exposes a flaw in the original Route 1 design. Name order is shuffled each round, but the same 500 names repeat every 180 s, which is shorter than many of their TTLs. "Warm" rounds therefore mostly measure how long each arm keeps answers cached, and the predictor's arm benefits from re-fetching a small fixed set. E1a is an upper bound for a highly repetitive workload. E2 removes this flaw with held-out real history and real TTLs.

The running E1a script keeps only per-arm summaries, not per-name rows, so E1a's primary analysis is the difference in medians with a bootstrap interval over lookups (unpaired). E1b keeps per-host rows and is analyzed paired.

## Common rules
- Effect = treatment minus control. Negative = faster.
- Paired designs: the pair is the unit (site, name, or host-round).
- Point estimate: Hodges-Lehmann (median of Walsh averages of the paired differences).
- Interval: 95% percentile bootstrap over pairs, 10,000 resamples, seed 0.
- Test: two-sided Wilcoxon signed-rank. Holm correction across the paired primary tests of E1b, E2 and E3 (3 tests).
- Exclusions: a unit with any failed measurement in either arm is dropped from both arms. Counts of dropped units are reported.
- No early stopping, no reruns of an arm. A crashed run is reported and rerun in full.

## E1: live DNS and API calls on the current network (Denison campus Wi-Fi, DHCP resolver 140.141.7.68)
- E1a (Route 1 rerun): Tranco top 500, 5 rounds, 180 s apart, condition and name order shuffled per round. Arms: network resolver direct, Unbound alone, Unbound + predictor. Primary: median lookup time over rounds 2 to 5, Unbound + predictor minus network resolver, 95% bootstrap interval from the script's own summary (not part of the Holm family, since it is unpaired).
- E1b (Route 3 rerun): 50 API hosts, 5 rounds, 120 s apart, Mac tool off/on. Primary: per host-round paired total request time, on minus off, rounds 2 to 5.

## E2: trace-driven DNS simulation on held-out real history
- Workload: Reed's own Chrome history (domains with visit timestamps), read in memory only; names never written to disk or logs.
- Split: chronological. Training = all days before the last 14 days. Test = last 14 days. The predictor learns online through the test period, as it would live.
- Per unique name, measured live before simulation: TTL (full TTL from a fresh query through a cold local Unbound) and network-resolver latency (median of 3 queries to the DHCP resolver).
- Policies, each with a TTL cache: (S) system cache only; (U) Unbound alone = S plus prefetch of a name queried in the last 10% of its TTL; (P) U plus the shipped predictor, run every 60 s of trace time on its top 25 candidates through the shipped cost rule with the shipped 10% holdout disabled.
- Hit costs 0.2 ms; a miss costs the name's measured network latency.
- Primary: per-test-day paired difference of mean lookup latency, P minus S. Secondary: hit rate, P minus U, and extra upstream queries per hour (cost).

## E3: Chrome extension under a habit (the condition it is built for)
- Sites: the 50 sites in bench/sites.json (home page plus one same-site next page each).
- Network: Chrome for Testing through the bench SOCKS proxy, 60 ms added round-trip time, DNS to the network resolver for both arms (Mac tool off).
- Per site and arm, a fresh browser profile: 8 training visits (load home, read 3 s, click the next link), then 6 measured visits. Before each measured visit, proxy connections are dropped. The HTTP cache is kept, as a habitual visitor's would be.
- Arms: extension on vs off, identical scripts. Arm order random per site (seed 7). 4 sites run in parallel, each worker with its own proxy.
- Primary: per-site paired difference of median next-page wait (loadEventEnd minus activationStart), on minus off.
- Secondary: share of measured next pages served from prerender; home-page load time difference (the extension's overhead).
- The extension's built-in 20% holdout stays on, so the estimate is intention-to-treat: what a user gets with the shipped extension.
- Power: with 50 pairs, Wilcoxon has 80% power at alpha 0.05 for a standardized paired effect of about 0.41.
