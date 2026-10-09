# MemDoc Preregistration

Generated from `memdoc/prereg.py`. The sha256 of the canonical JSON of the
hypotheses, analysis plan, and cause taxonomy below is locked in `PREREG.lock`.
Hypothesis text is never edited after lock; amendments are appended under
`## Amendments` and are outside the hashed content.

**Prereg hash:** `2f22444b0d103c3b1aaadfa6299e631fabf03e4aee65760c0ef9ead0df2da118`

## Hypotheses (verbatim from research §8)

### H1

H1 (size crossover): A1 ≥ A4 at 5K; A1 < A2 ≈ A5 at 100K. A1's cost crosses A4's between 4K and 9K tokens (§5).

- metric: success rate; cached $ per session (memory overhead)
- arms: a1, a2, a4, a5
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 5000, 100000
- comparison: A1 vs A4 at 5K (>=); A1 vs A2 and A5 at 100K (<); cost crossover in [4000, 9000]
- threshold: '≈' preregistered as |diff| <= 5 pts
- test: exact McNemar on paired pass/fail; seeded bootstrap 95% CI for the cost crossover

### H2

H2 (rationale): on categories 2 and 6, doc arms (A1/A2/A5) beat A4 by ≥10 pts.

- metric: success rate
- arms: a1, a2, a5, a4
- categories: 2, 6
- sizes: 25000
- comparison: each of A1, A2, A5 vs A4
- threshold: >= 10 pts
- test: exact McNemar; seeded bootstrap 95% CI on the difference

### H3

H3 (supersession): the stale-answer rate is highest for A3/A6, lower for A4 (with supersession), and lowest for A1/A2 *if* write fidelity ≥ 90%.

- metric: stale-answer rate; write fidelity (condition)
- arms: a3, a6, a4, a1, a2
- categories: 3, 4
- sizes: 25000
- comparison: ordering A3/A6 > A4 > A1/A2, conditional on A1/A2 write fidelity >= 90%
- threshold: strict ordering; condition write fidelity >= 90% else condition-not-met
- test: exact McNemar on paired stale/not-stale; ordering reported descriptively

### H4

H4 (implicit conflict): no arm exceeds 60% on category 4 (STALE base rate).

- metric: success rate
- arms: a0, astar, a1, a2, a4, a5, a6
- categories: 4
- sizes: 25000
- comparison: max over arms (A* excluded as ceiling) vs 60%
- threshold: <= 60%
- test: seeded bootstrap 95% CI on each arm's category-4 success rate

### H5

H5 (hybrid): A5 has the best success rate overall, and costs ≤ 1.5× A2 per successful task.

- metric: overall success rate; $ per successful task
- arms: a5, a1, a2, a4, a6
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 25000
- comparison: A5 vs every other non-oracle arm; A5 cost vs 1.5x A2 cost
- threshold: best overall; cost ratio <= 1.5
- test: exact McNemar vs each arm; seeded bootstrap 95% CI on the cost ratio

### H6

H6 (silent failure): the silent-failure share is ≥2× higher for A3/A4 than for A1/A2.

- metric: silent-failure share of failed probes
- arms: a3, a4, a1, a2
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 25000
- comparison: pooled silent share A3/A4 vs 2x pooled silent share A1/A2
- threshold: >= 2x
- test: seeded bootstrap 95% CI on the ratio of shares

### H7

H7 (write policy): holding read policy constant (A5 core written in the foreground vs by background extraction, as an ablation), foreground writes beat background writes on categories 2 and 6. This is the testable form of the §4.3 production example.

- metric: success rate
- arms: a5, a5bg
- categories: 2, 6
- sizes: 25000
- comparison: A5 (core_writer=foreground) vs A5-bg (core_writer=background)
- threshold: A5 > A5-bg
- test: exact McNemar on paired pass/fail

## Analysis plan

- **alpha:** 0.05
- **bootstrap_seed:** 20261009
- **ci:** seeded bootstrap 95% CI, 10000 resamples
- **correction:** Holm across H1-H7
- **evaluation:** hypotheses are evaluated only on live run logs; mock logs print 'hypotheses not evaluated: mock run'
- **not_tested:** arms not built (A3, A5-bg) make dependent comparisons NOT_TESTED, never silently dropped
- **pairing:** paired by storyline x seed
- **pass_fail_test:** exact two-sided McNemar on discordant pairs (binomial)

## Cause-code taxonomy (AC #9)

- `write_miss` (visible): fact never stored
- `stale_in_store` (visible): superseded value still stored as current
- `retrieval_miss` (silent): stored, not delivered to context
- `catalog_miss` (silent): stored in a doc the agent never opened
- `rank_stale` (silent): both values delivered, stale one first or chosen
- `applied_wrong` (silent): correct fact in context, wrong answer

**Assignment rule:** For a failed probe, assign the first matching cause in this order: (1) gold != ABSTAIN and the gold canary is absent from the store snapshot -> write_miss; (2) the superseded canary is stored as current (present and not marked superseded), the answer equals the superseded canary, and the gold canary was not delivered to context -> stale_in_store; (3) gold stored but not delivered to context: read_policy == catalog -> catalog_miss, otherwise -> retrieval_miss; (4) gold and superseded canary both delivered and the answer equals the superseded canary -> rank_stale; (5) otherwise (gold delivered, wrong answer; includes answering instead of ABSTAIN) -> applied_wrong.

Each hypothesis is reported as SUPPORTED, NOT_SUPPORTED, or NOT_TESTED
(with the reason). Hypotheses are evaluated only on live run logs.

## Amendments` and are outside the hashed content.

**Prereg hash:** `c8cae0346ede13a83a2ecc721b7a0c4d56fd00cb7b38c22607d6600b62d85598`

## Hypotheses (verbatim from research §8)

### H1

H1 (size crossover): A1 ≥ A4 at 5K; A1 < A2 ≈ A5 at 100K. A1's cost crosses A4's between 4K and 9K tokens (§5).

- metric: success rate; cached $ per session (memory overhead)
- arms: a1, a2, a4, a5
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 5000, 100000
- comparison: A1 vs A4 at 5K (>=); A1 vs A2 and A5 at 100K (<); cost crossover in [4000, 9000]
- threshold: '≈' preregistered as |diff| <= 5 pts
- test: exact McNemar on paired pass/fail; seeded bootstrap 95% CI for the cost crossover

### H2

H2 (rationale): on categories 2 and 6, doc arms (A1/A2/A5) beat A4 by ≥10 pts.

- metric: success rate
- arms: a1, a2, a5, a4
- categories: 2, 6
- sizes: 25000
- comparison: each of A1, A2, A5 vs A4
- threshold: >= 10 pts
- test: exact McNemar; seeded bootstrap 95% CI on the difference

### H3

H3 (supersession): the stale-answer rate is highest for A3/A6, lower for A4 (with supersession), and lowest for A1/A2 *if* write fidelity ≥ 90%.

- metric: stale-answer rate; write fidelity (condition)
- arms: a3, a6, a4, a1, a2
- categories: 3, 4
- sizes: 25000
- comparison: ordering A3/A6 > A4 > A1/A2, conditional on A1/A2 write fidelity >= 90%
- threshold: strict ordering; condition write fidelity >= 90% else condition-not-met
- test: exact McNemar on paired stale/not-stale; ordering reported descriptively

### H4

H4 (implicit conflict): no arm exceeds 60% on category 4 (STALE base rate).

- metric: success rate
- arms: a0, astar, a1, a2, a4, a5, a6
- categories: 4
- sizes: 25000
- comparison: max over arms (A* excluded as ceiling) vs 60%
- threshold: <= 60%
- test: seeded bootstrap 95% CI on each arm's category-4 success rate

### H5

H5 (hybrid): A5 has the best success rate overall, and costs ≤ 1.5× A2 per successful task.

- metric: overall success rate; $ per successful task
- arms: a5, a1, a2, a4, a6
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 25000
- comparison: A5 vs every other non-oracle arm; A5 cost vs 1.5x A2 cost
- threshold: best overall; cost ratio <= 1.5
- test: exact McNemar vs each arm; seeded bootstrap 95% CI on the cost ratio

### H6

H6 (silent failure): the silent-failure share is ≥2× higher for A3/A4 than for A1/A2.

- metric: silent-failure share of failed probes
- arms: a3, a4, a1, a2
- categories: 1, 2, 3, 4, 5, 6, 7, 8
- sizes: 25000
- comparison: pooled silent share A3/A4 vs 2x pooled silent share A1/A2
- threshold: >= 2x
- test: seeded bootstrap 95% CI on the ratio of shares

### H7

H7 (write policy): holding read policy constant (A5 core written in the foreground vs by background extraction, as an ablation), foreground writes beat background writes on categories 2 and 6. This is the testable form of the §4.3 production example.

- metric: success rate
- arms: a5, a5bg
- categories: 2, 6
- sizes: 25000
- comparison: A5 (core_writer=foreground) vs A5-bg (core_writer=background)
- threshold: A5 > A5-bg
- test: exact McNemar on paired pass/fail

## Analysis plan

- **alpha:** 0.05
- **bootstrap_seed:** 20261009
- **ci:** seeded bootstrap 95% CI, 10000 resamples
- **correction:** Holm across H1-H7
- **evaluation:** hypotheses are evaluated only on live run logs; mock logs print 'hypotheses not evaluated: mock run'
- **not_tested:** arms not built (A3, A5-bg) make dependent comparisons NOT_TESTED, never silently dropped
- **pairing:** paired by storyline x seed
- **pass_fail_test:** exact two-sided McNemar on discordant pairs (binomial)

## Cause-code taxonomy (AC #9)

- `write_miss` (visible): fact never stored
- `stale_in_store` (visible): superseded value still stored as current
- `retrieval_miss` (silent): stored, not delivered to context
- `catalog_miss` (silent): stored in a doc the agent never opened
- `rank_stale` (silent): both values delivered, stale one first or chosen
- `applied_wrong` (silent): correct fact in context, wrong answer

Each hypothesis is reported as SUPPORTED, NOT_SUPPORTED, or NOT_TESTED
(with the reason). Hypotheses are evaluated only on live run logs.
