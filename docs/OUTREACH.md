# Who to send Predictive Loading to

Status: final. Nothing here has been sent.

## Result of the ranking rule (results/confirm.json, 2026-11-20)
- E2 passed (Holm p = 0.0002): lead with NLnet Labs / Unbound.
- E3 did not pass (Holm p = 0.69; estimate -98.6 ms, CI -258.7 to +106.9): send the Chrome team the data as an open question, and do not claim a gain.
- E1b did not pass (Holm p = 0.99).

## Order to send
1. unbound-users email (draft 1). One email, about 5 minutes.
2. arXiv cs.NI preprint (draft 4). Gives every other message a citable link.
3. WICG nav-speculation issue (draft 2), after the arXiv link exists.
4. Show HN (draft 3), to recruit real-world holdout data from outside testers.
5. PAM 2027 only after a larger E3 on a quiet machine.

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
Title: Data: per-user learned next-link prediction as a speculation-rules source

A Chrome extension learns, from one user's own history on a site, which link they click next. When the predicted time saved exceeds a measured cost, it writes a `prefetch` speculation rule for that link.

Pre-registered test, 50 popular sites (42 usable). Each site got a fresh profile, an 8-visit habit (home, then the same link), and 6 measured visits, with the extension on and off in random order.
- 163 of 252 measured next pages were served via navigational-prefetch.
- Per-site median next-page time: 1055 ms on, 1226 ms off.
- Paired Hodges-Lehmann estimate: -98.6 ms, 95% CI [-258.7, +106.9], Holm p = 0.69, so not confirmed.

Question for the team: is per-user habit prediction worth exposing as an eagerness signal (for example, a browser-side "learned" eagerness), given that site-authored rules cannot see per-user history? Code and raw data: https://github.com/Questboy23/predictive-loading

### 3. Hacker News
Title: Show HN: Predictive Loading, a per-user next-page and DNS predictor with pre-registered tests

Body: A Mac tool keeps a local DNS cache warm with names you are likely to need next hour, and a Chrome extension writes Speculation Rules for the link you are likely to click. Both learn only from your own history, kept on your machine as hashes. I pre-registered the tests: the DNS predictor gives a small, reliable gain on replayed history (hit rate 0.754 to 0.790, 0.22 ms per lookup), and loses to a fast campus resolver live. After an 8-visit habit, the extension prefetched 65% of next pages; the next-page estimate was about 100 ms faster, but its interval includes zero. Code, data, paper: https://reedsmoneymaker23.com/predictive-loading/

### 4. arXiv cs.NI
Upload `dist/arxiv-source.tar.gz` (built by packaging/build_release.sh; pdflatex-safe, ASCII only, compiles to the 11-page paper.pdf). Category cs.NI, cross-list cs.LG. License CC BY 4.0.

A first-time submitter needs an endorsement. Starting the submission makes arXiv show a 6-character endorsement code. Send it to one endorser below.

Endorser candidates (recent cs.NI DNS papers, found via the arXiv API on 2026-11-20):
1. Fabian E. Bustamante (Northwestern): "Who Resolves Your DNS?", arXiv:2608.29371. Closest topic: resolver performance and measurement.
2. Thomas C. Schmidt or Matthias Waehlisch: arXiv:2606.10097 and arXiv:2510.18572, DNS resolvers and forwarders.
3. Taejoong Chung (Virginia Tech): arXiv:2609.14210, DNS measurement.

Endorsement email (fill in CODE):
Subject: arXiv cs.NI endorsement request: pre-registered study of history-driven DNS prefetch

Dear Professor Bustamante,

I read "Who Resolves Your DNS?" and am submitting my first cs.NI paper, a pre-registered measurement of per-user DNS and page prefetching. On 14 held-out days of real history, a learned predictor raised a local resolver's hit rate from 0.754 to 0.790 (Holm p = 0.0002). A live test against a fast campus resolver found no gain, and the paper reports that too.

Paper and data: https://github.com/Questboy23/predictive-loading (paper/paper.pdf)
If it looks like a fit for cs.NI, could you endorse me with code CODE at https://arxiv.org/auth/endorse ? No is a fine answer.

Thank you,
Reed

### 5. PAM 2027 / IMC short paper
Reformat paper.tex to the venue template (PAM uses Springer LNCS, 12 pages). Frame it as a measurement paper: pre-registered, one user, negative live result and positive replay result.
