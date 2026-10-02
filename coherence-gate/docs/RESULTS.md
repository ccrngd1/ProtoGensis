# CoherenceGate demo results (actual runs)

Every table below is pasted from a real run of the shipped demos on 2026-10-02.
All demos are deterministic and offline (scripted mock agents, fixed step clock,
pre-registered seeds). Paper-reference blocks are the paper's numbers, separately
labeled, never ours. Real-LLM behavior of this harness: not benchmarked.

## demo budget

```
=== CoherenceGate demo: budget — information is not ownership (Study IV analogue) ===
Paper: arXiv 2610.02036, Heng (2026), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong"
reproduction-style, not a replication of paper numbers
Scripted mock agents show the mechanism; they are not evidence.

Shared limit: 20 run calls across the team; seeds [0, 1, 2, 3, 4] (pre-registered).

arm                over budget (of 5)  calls (median, range)  refusals  progress (mean partial)
-----------------  ------------------  ---------------------  --------  -----------------------
ordinary           4/5                 23 (18-30)             0         1.000                  
visible_state      0/5                 19 (18-20)             0         0.890                  
ledger             0/5                 20 (18-20)             11        0.902                  
escrow             0/5                 19 (17-20)             17        0.759                  
wrong_unit_ledger  4/5                 23 (18-30)             0         1.000                  

The progress metric ignores the budget, so non-gate arms can score high progress by overspending.

Visible state stayed in budget only because every scripted agent obeyed a conservative stop rule. The ledger and escrow held with no such rule. That's the paper's 'information is not ownership' point, and their LLM teams overspent at 4/5 (paper result, not ours).

LINT: OWN001 guard counts tool_call:name=write_file, grader counts tool_call:name=run

Gate arms (ledger, escrow) are 0/N by construction; the informative rows are the non-gate arms and progress.

--- exploratory arm (exploratory, added after the pre-registered result) ---
Same seeds, demands, batch RNG, and superstep as visible_state, but each role spends its one batch per round whenever x < limit, skipping the x + batch <= limit check.
arm                over budget (of 5)  calls (median, range)  refusals  progress (mean partial)
-----------------  ------------------  ---------------------  --------  -----------------------
visible_state_lax  3/5                 21 (18-23)             0         0.937                  

--- paper reference (arXiv 2610.02036 Study IV, gpt-6-sol; not our numbers) ---
  ordinary 5/5 over (57-72 calls)
  visible_state 4/5 over (median 70 -> 29 calls)
  ledger 0/5, stopping at exactly 20 (1-32 surplus attempts rejected, mean 10.4)
  quota_escrow 0/5, mean partial 0.960 and 4/5 strict, vs ledger 0.874 and 2/5 strict (descriptive; confounded attestation gates)
  Paper limits: single author, one model family (gpt-6-sol), 5 seeds per cell, synthetic probes / injected failures.
```

Per-seed visible_state detail (seed: demands planner/executor/verifier; total calls; over?):
seed 0: 6/16/8 → 20, under; seed 1: 4/14/5 → 19, under; seed 2: 3/10/5 → 18, under;
seed 3: 4/14/9 → 19, under; seed 4: 4/12/5 → 20, under. 41 of 56 role decisions across the
5 seeds were made against a displayed count x > 0 (the arm is not degenerate), and every
decision's x came from the role's rendered `ContextAssembler` context.

Note: visible_state differs from ordinary here — fewer calls (18–20 vs 18–30), no run over
budget, and lower progress. AC #8's `visible_state ≥ 1/5` prediction was **falsified** for our
scripted agents: the literal pre-registered policy (one 1–3-call batch per role per round against
the shared round-start snapshot, with a conservative stop-for-good rule) lands at the limit
rather than past it on these seeds. The pre-registered result (0/5) is reported as-is and is
**final** per Amendment 1; the test suite asserts the recorded value as a determinism regression,
not as a claim that visible state is safe. Visible state stayed in budget only because every
scripted agent obeyed a conservative stop rule; the ledger and escrow held with no such rule.
That's the paper's "information is not ownership" point, and their LLM teams overspent at 4/5
(paper result, not ours). No seed search or tuning was performed (full record, including
Change 1 — reverted — Change 2, and Amendment 1, in
[`.mastercontrol/preregistration.md`](../.mastercontrol/preregistration.md)).

Exploratory arm `visible_state_lax` (**exploratory, added after the pre-registered result**,
Amendment 1): same seeds, demands, batch RNG, and superstep as visible_state, but each role
spends its one batch per round whenever x < limit, skipping the `x + batch <= limit` check.
Run once, reported as-is. Per-seed (seed: demands planner/executor/verifier; total calls; over?):
seed 0: 6/16/8 → 23, OVER; seed 1: 4/14/5 → 21, OVER; seed 2: 3/10/5 → 18, under;
seed 3: 4/14/9 → 23, OVER; seed 4: 4/12/5 → 20, under → **3/5 over**. Without the own-batch
stop rule, the same displayed count no longer keeps the team under the limit — safety under
visible state depended on every agent's own stop rule, while the ledger and escrow don't need
one (a gate-property test asserts both gates stay 0/5 under the lax rule).

## demo identifiability

```
=== CoherenceGate demo: identifiability — the aliasing probe (Study I analogue) ===
Paper: arXiv 2610.02036, Heng (2026), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong"
reproduction-style, not a replication of paper numbers
Scripted mock agents show the mechanism; they are not evidence.

40 tasks x 3 truths = 120 episodes per variant (all-truths evaluation; exact 1/k for deterministic policies).

arm               variant       score  
----------------  ------------  -------
competent         identifiable  120/120
competent         aliased       40/120 
planner_verifier  identifiable  120/120
planner_verifier  aliased       40/120 
majority5         identifiable  120/120
majority5         aliased       40/120 
blind_tool        identifiable  120/120
blind_tool        aliased       40/120 
reading_tool      aliased       120/120
competent         fact          120/120

Audit (aliased): identifiable=False, k=3, bound 1/k = 0.3333, aliased fibers 40
Audit (+fact):   identifiable=True, k=1, bound = 1.0000

The mock arms SHOW the theorem; the paper's arms MEASURED it on a model.

--- paper reference (arXiv 2610.02036 Study I, gpt-6-sol; not our numbers) ---
  identifiable 40/40 in every arm
  aliased: low/med/high effort 12/17/14; planner+verifier 13; 5-vote majority 13/39; blind tool 13
  reading tool 40/40; one authoritative sentence 40/40
  Paper limits: single author, one model family (gpt-6-sol), 5 seeds per cell, synthetic probes / injected failures.
```

## demo telecom

```
=== CoherenceGate demo: telecom — stale quote, silent revert, authority (tau^2-style) ===
Paper: arXiv 2610.02036, Heng (2026), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong"
reproduction-style, not a replication of paper numbers
Scripted mock agents show the mechanism; they are not evidence.

task     arm           ok   detail                                    
-------  ------------  ---  ------------------------------------------
S        unguarded     NO   final unit_price 100 (committed stale)    
P        unguarded     NO   roaming holds: False, notices 0           
A        unguarded     yes  not blocked                               
control  unguarded     yes  accepted                                  
S        conventional  NO   final unit_price 100 (committed stale)    
P        conventional  NO   roaming holds: False, notices 0           
A        conventional  yes  blocked                                   
control  conventional  yes  accepted                                  
S        coherence     yes  final unit_price 140 (repaired, re-quoted)
P        coherence     yes  roaming holds: True, notices 1            
A        coherence     yes  blocked                                   
control  coherence     yes  accepted                                  

Task A is a predicted TIE: conventional = coherence. Conventional authority checks already own this state; the gate adds nothing here, as predicted.
Controls: 0 false rejections across all arms.

--- paper reference (arXiv 2610.02036 Study V, tau^2-bench Telecom, gpt-6-sol; not our numbers) ---
  silent reverts: reward 0.00 / 0.07 / 1.00 (15/15) for unguarded / conventional / coherence
  conventional checks committed the stale quote 10/10
  predicted tie on policy-precondition cases: conventional = coherence
  no false rejections on controls
  Paper limits: single author, one model family (gpt-6-sol), 5 seeds per cell, synthetic probes / injected failures.
```

## demo single-agent

```
=== CoherenceGate demo: single-agent — the gate when you don't need it ===
Paper: arXiv 2610.02036, Heng (2026), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong"
reproduction-style, not a replication of paper numbers
Scripted mock agents show the mechanism; they are not evidence.

arm      final counter  final flag  rejections  notices
-------  -------------  ----------  ----------  -------
ungated  3              False       0           0      
gated    3              False       0           0      

Predicted TIE: with one agent and full state the gate changes no outcome and makes 0 rejections (Cor 4.2: needed only where its map can lose information). It tells you when you don't need it.
```

## demo warmup

```
=== CoherenceGate demo: warmup — lost update via version compare-and-swap (Prop 4.1, classical OCC) ===
Paper: arXiv 2610.02036, Heng (2026), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong"
reproduction-style, not a replication of paper numbers
Scripted mock agents show the mechanism; they are not evidence.

  ungated : Agent A clobbered Agent B's change (final = 'a_wins') — the lost update.
  gated   : stale read caught at commit; Repair returned with the fresh value (final = 'on').

`agent-coherence` already prevents this. Shown for completeness.
Credit: optimistic concurrency control, Kung & Robinson 1981.
```

## lint ownership

```
$ coherence-gate lint ownership --config coherencegate/demos/config/wrong_unit.json
OWN001 guard counts tool_call:name=write_file, grader counts tool_call:name=run
exit code: 1
$ coherence-gate lint ownership --config coherencegate/demos/config/aligned.json
ownership lint: aligned (guard unit == graded unit)
exit code: 0
```

## audit identifiability

```
$ coherence-gate audit identifiability --variant aliased
identifiability audit (aliased)
  aliased_fibers: 40
  bound: 0.333333
  identifiable: False
  max_k: 3
  n_worlds: 120
  variant: aliased
exit code: 1
```
