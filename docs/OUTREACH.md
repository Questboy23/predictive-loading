# Who to send Predictive Loading to

Status: draft. The ranking below is finalised from the confirmatory results (PREREG.md, results/confirm.json). Nothing here has been sent.

## Ranking rule
- E3 (Chrome habit) primary effect negative with the interval below 0 after Holm: lead with the Chrome preloading team.
- E2 (DNS, held-out history) P minus S negative with the interval below 0: lead with Unbound / NLnet Labs.
- Neither: publish the negative result (arXiv + blog post) and stop pitching implementers.

## Targets (lowest effort first)
| Target | Channel | Ask | Effort |
|---|---|---|---|
| Chrome preloading / Speculation Rules team | Public issue at github.com/WICG/nav-speculation | "Per-user learned next-page prediction as a built-in eagerness mode; data attached" | 1 post |
| NLnet Labs (Unbound) | unbound-users mailing list | "History-driven prefetch beyond prefetch: yes; simulation and code attached" | 1 email |
| arXiv (cs.NI) | arxiv.org submission; first-time submitters need an endorsement from an existing cs.NI author | Preprint of paper.pdf | 1 form + endorsement |
| PAM 2027 / ACM IMC short paper | Conference submission | Measurement paper with pre-registered negative or positive results | Formatting + deadline |
| Hacker News | "Show HN: Predictive Loading" | Outside testers; the popup and `stats` give real-world holdout data | 1 post |

## Message drafts
Numbers come from results/confirm.json. Each draft is ready to paste. Nothing has been sent.

### 1. unbound-users mailing list (NLnet Labs)
Subject: History-driven prefetch on top of prefetch: yes, a held-out replay

Hi all,

Unbound's `prefetch: yes` refreshes a cached name in the last 10% of its TTL, but only if it is queried in that window. I tested a per-user predictor that also re-fetches names the user is likely to need in the next hour, learned from their own history.

On 14 held-out days of one person's real history (13,934 lookups, trained only on earlier weeks), replayed through three policies:
- TTL cache only: hit rate 0.754
- plus Unbound prefetch: 0.768
- plus the predictor: 0.790

Per day, the predictor cut mean lookup time by 0.22 ms [0.20, 0.25] against the plain cache, and was faster on all 15 days (Wilcoxon, Holm-corrected, pre-registered). The cost is about 2.3x upstream queries per awake hour. On this campus network a miss costs about 6 ms, so the gain is small; it scales with resolver latency.

The analysis plan was committed before the analysis ran (PREREG.md). Code, raw outputs and paper: https://github.com/Questboy23/predictive-loading

Would a history-driven prefetch hook (a list of names to keep warm, fed by an outside process) fit Unbound, or is it better kept outside as it is now?

### 2. WICG nav-speculation (Chrome Speculation Rules)
E3_WICG

### 3. Hacker News
Title: Show HN: Predictive Loading, a per-user next-page and DNS predictor with pre-registered tests

Body: A Mac tool keeps a local DNS cache warm with names you are likely to need next hour, and a Chrome extension writes Speculation Rules for the link you are likely to click. Both learn only from your own history, kept on your machine as hashes. I pre-registered the tests: the DNS predictor gives a small, reliable gain on replayed history (hit rate 0.754 to 0.790, 0.22 ms per lookup), and loses to a fast campus resolver live. E3_HN Code, data, paper: https://reedsmoneymaker23.com/predictive-loading/

### 4. arXiv cs.NI
Upload paper/paper.pdf with source. A first-time cs.NI submitter needs an endorsement: email an author of a recent cs.NI DNS-measurement paper with the abstract and ask for endorsement through arxiv.org/auth/endorse.

### 5. PAM 2027 / IMC short paper
Reformat paper.tex to the venue template (PAM uses Springer LNCS, 12 pages). Frame it as a measurement paper: pre-registered, one user, negative live result and positive replay result.
