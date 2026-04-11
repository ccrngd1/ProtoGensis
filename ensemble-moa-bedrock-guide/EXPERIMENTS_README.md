# MOA Experiments - All Scripts Ready

All experiment scripts created and ready to run.

## Status Summary

✅ **E1: Cross-Judge Validation** - **COMPLETE** ($0.97, rankings match, no Opus bias)

**Ready to run:** 11 experiments, ~$241 total

---

## Quick Start Commands

### Priority 1: Critical Validation (~$141)

```bash
# Cheapest first
python3 run_e14_baseline_stability.py --yes          # $3, 15 min
python3 run_e2_repeated_runs.py --yes                 # $135, 4-6 hours ⚠️ LONGEST

# Optional: MT-Bench premium (closes gap)
python3 run_e3_mtbench_premium.py --yes              # $25, 2-3 hours
```

### Priority 2: Theory Testing (~$54)

```bash
# Test if MoA helps weaker models
python3 run_e7_e8_low_baseline.py --yes              # $6, 1-2 hours

# Test if strong judge fixes vote ensemble
python3 run_e10_strong_judge_vote.py --yes           # $20, 1-2 hours

# Quantify adversarial brittleness
python3 run_e13_adversarial_only.py --yes            # $10, 1-2 hours

# Test different aggregator tiers
python3 run_e6_aggregator_tiers.py --yes             # $8, 30-60 min

# Validate smart routing recommendation
python3 run_e5_smart_routing.py --yes                # $15, 1-2 hours
```

### Priority 3: Literature Comparison (~$20)

```bash
python3 run_e4_alpacaeval.py --yes                   # $20, 1-2 hours
```

### Analysis Only ($0)

```bash
python3 run_e12_cost_matched_analysis.py --yes       # $0, instant
```

---

## Detailed Experiment List

| ID | Experiment | Cost | Time | Status | Priority |
|----|-----------|------|------|--------|----------|
| E1 | Cross-judge validation (Sonnet) | $0.97 | 20 min | ✅ COMPLETE | Critical |
| E2 | Phase 1 repeated runs (3×) | $135 | 4-6 hrs | ⬜ Ready | Critical |
| E3 | Premium on MT-Bench | $25 | 2-3 hrs | ⬜ Ready | High |
| E4 | AlpacaEval comparison | $20 | 1-2 hrs | ⬜ Ready | Medium |
| E5 | Smart routing validation | $15 | 1-2 hrs | ⬜ Ready | High |
| E6 | Aggregator tiers | $8 | 30-60 min | ⬜ Ready | Medium |
| E7/E8 | Low-baseline ensembles | $6 | 1-2 hrs | ⬜ Ready | High |
| E10 | Strong-judge vote | $20 | 1-2 hrs | ⬜ Ready | High |
| E12 | Cost-matched analysis | $0 | instant | ⬜ Ready | Medium |
| E13 | Adversarial-only | $10 | 1-2 hrs | ⬜ Ready | High |
| E14 | Baseline stability | $3 | 15 min | ⬜ Ready | Critical |

**Total remaining: $242** (E1 already done at $0.97)

---

## Recommended Execution Order

### Conservative Budget (~$25)

```bash
python3 run_e14_baseline_stability.py --yes          # $3
python3 run_e12_cost_matched_analysis.py --yes       # $0
python3 run_e7_e8_low_baseline.py --yes              # $6
python3 run_e13_adversarial_only.py --yes            # $10
python3 run_e6_aggregator_tiers.py --yes             # $8
```

### Moderate Budget (~$75)

Add to conservative:
```bash
python3 run_e10_strong_judge_vote.py --yes           # $20
python3 run_e5_smart_routing.py --yes                # $15
python3 run_e4_alpacaeval.py --yes                   # $20
python3 run_e3_mtbench_premium.py --yes              # $25
```

### Full Budget (~$242)

Add E2 (longest/most expensive):
```bash
python3 run_e2_repeated_runs.py --yes                # $135, 4-6 hours
```

---

## What Each Experiment Tests

**E1** ✅ - Opus self-bias → **No bias found, rankings match**

**E2** - Variance/confidence intervals → Adds statistical rigor

**E3** - MT-Bench premium configs → Closes "only tested weakest" gap

**E4** - AlpacaEval benchmark → Direct comparison to Wang et al.

**E5** - Smart routing → Validates recommended alternative

**E6** - Aggregator capability → Tests if stronger aggregator helps

**E7/E8** - Weak proposers → Tests if MoA helps below capability limit

**E10** - Strong judge → Fixes Haiku bottleneck, tests architecture

**E12** - Cost fairness → Best-of-N vs ensemble at equal cost

**E13** - Adversarial focus → Quantifies brittleness discovery

**E14** - Baseline drift → Verifies measurement stability

---

## Dependencies

All scripts require:
- `moa/` module (config, ensemble, judge)
- `benchmark/prompts.json` (54 prompts)
- AWS Bedrock credentials configured
- `boto3` library installed

**Optional data files:**
- `benchmark/mtbench_prompts.json` (for E3, falls back to existing data)
- `benchmark/alpacaeval_prompts.json` (for E4, generates if missing)

---

## Output Files

All scripts create timestamped JSON files in `results/`:
- `cross_judge_validation_YYYYMMDD_HHMMSS.json`
- `e2_repeated_runs_YYYYMMDD_HHMMSS.json`
- `e3_mtbench_premium_YYYYMMDD_HHMMSS.json`
- etc.

Each file includes:
- Metadata (timestamp, costs, configs)
- Full results (responses, scores, costs)
- Summary statistics

---

## Tips

1. **Run cheap experiments first** to validate before spending on E2
2. **Use `--yes` flag** to skip confirmation prompts
3. **E2 takes 4-6 hours** - run overnight or in tmux/screen
4. **Check costs** - actual may differ from estimates
5. **E12 is free** - run it first for quick insights

---

## After Running

Update documentation with results:
- BLOG.md (add new findings)
- RESULTS_AT_A_GLANCE.md (update tables)
- DETAILED_METHODOLOGY.md (add experiment notes)

---

**All 12 experiment scripts created and ready to execute.**
