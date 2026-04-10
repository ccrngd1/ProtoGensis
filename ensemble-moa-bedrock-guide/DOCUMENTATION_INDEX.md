# Documentation Index

Quick reference guide to all documentation files in this project.

---

## For Different Audiences

### If you want a quick summary (5-10 minutes)
→ **RESULTS_AT_A_GLANCE.md** — One-page visual summary with all key findings

### If you want the complete story (30-45 minutes)
→ **BLOG.md** — Practitioner's guide with methodology, examples, and results

### If you want full experimental details (1+ hour)
→ **DETAILED_METHODOLOGY.md** — Complete experimental record with code walkthrough

### If you're fact-checking for publication
→ **EDITORIAL_REFERENCE.md** — Every claim mapped to its evidence with verification commands

### If you need a work summary for review
→ **WORK_SUMMARY.md** — What was done, when, and what files were created

---

## Primary Documentation Files

### README.md
- **What it is:** Project overview and quick start guide
- **Updated with:** Empirical findings from all 3 testing phases
- **Length:** ~400 lines
- **Key sections:**
  - TL;DR: Why ensembles don't work on Bedrock
  - Key findings with measured data
  - When MoA works (cross-platform) vs doesn't work (Bedrock)
  - Cost/quality comparison tables
  - Recommendation: Use standalone models
- **Audience:** First-time visitors to the repo

### BLOG.md ⭐ MAIN DELIVERABLE
- **What it is:** Complete practitioner's guide ready for publication
- **Content:** Full story with methodology, results, examples, and recommendations
- **Length:** ~850 lines
- **Key sections:**
  - What we tested (3 phases, 592 tests)
  - Results (all ensembles underperformed)
  - Why MoA failed (aggregation trap, platform constraints)
  - The "smoking gun" example (GDP of Lesotho)
  - Implementation details (code, judge system, personas)
  - Challenges encountered (with solutions)
  - What to use instead (standalone models, smart routing)
- **Audience:** Practitioners, engineers, blog readers

### DETAILED_METHODOLOGY.md
- **What it is:** Complete experimental record for reproducibility
- **Content:** Full methodology with code examples, prompt design rationale, statistical methods
- **Length:** ~1100 lines
- **Key sections:**
  - Timeline (March 30 - April 4, 2026)
  - Phase 1/2/3 configurations and execution details
  - Prompt suite design (why each category, example prompts)
  - Automated judge design (prompt template, parsing, bias mitigation)
  - Persona design rationale
  - Statistical analysis methods (t-tests, Cohen's d)
  - Implementation code walkthrough
  - Challenges and solutions
  - Data storage and reproducibility
- **Audience:** Researchers, peer reviewers, people wanting to reproduce results

---

## Reference and Support Documents

### EDITORIAL_REFERENCE.md
- **What it is:** Fact-checking guide for editors
- **Content:** Every major claim mapped to its supporting evidence
- **Length:** ~350 lines
- **Key sections:**
  - Top-level claims with evidence locations
  - Methodology claims verification
  - Statistical claims with evidence
  - Cost/latency claims
  - Example verification (GDP of Lesotho, personas)
  - Known issues and corrections
  - Editorial checklist before publication
- **Audience:** Editors, fact-checkers, peer reviewers

### WORK_SUMMARY.md
- **What it is:** Complete summary of all work done
- **Content:** What was done, when, and what files were created/modified
- **Length:** ~400 lines
- **Key sections:**
  - What was done (3 phases, framework, documentation)
  - All files modified/created (with line counts)
  - Key findings documented
  - What makes this documentation complete
  - Verification commands
  - Checklist for publication
- **Audience:** Project reviewers, editors getting up to speed

### RESULTS_AT_A_GLANCE.md
- **What it is:** One-page visual summary
- **Content:** All key results in tables and diagrams
- **Length:** ~250 lines
- **Key sections:**
  - Three experiments overview
  - Complete results table
  - Cost and latency impact
  - The "smoking gun" example
  - Pattern across all categories
  - Why MoA failed (visual explanation)
  - Recommendation
  - Bottom line summary box
- **Audience:** Quick reference, presentations, executive summary

### DOCUMENTATION_INDEX.md (this file)
- **What it is:** Guide to all documentation files
- **Content:** What each file contains and who should read it
- **Audience:** Anyone trying to navigate the documentation

---

## Analysis Documents

### WHY_ENSEMBLES_FAIL.md
- **What it is:** Deep dive on the aggregation trap
- **Content:** GDP of Lesotho example with full proposer responses and judge justifications
- **Length:** ~250 lines
- **Key sections:**
  - The aggregation trap explained
  - Full example with all proposer responses
  - Mathematical principle
  - Why aggregators can't filter hallucinations
- **Audience:** People wanting to understand *why* ensembles failed

### PREMIUM_TIER_RESULTS.md
- **What it is:** Phase 1 detailed findings
- **Content:** Complete results from premium tier testing
- **Audience:** People wanting Phase 1 specific details

### MTBENCH_RESULTS.md
- **What it is:** Phase 2 detailed findings
- **Content:** Complete results from MT-Bench multi-turn testing
- **Audience:** People wanting Phase 2 specific details

---

## Code and Data Files

### Code Implementation

Located in `moa/` directory:
- **core.py** (457 lines) — Async MoA pipeline
- **bedrock_client.py** (218 lines) — AWS Bedrock API wrapper
- **models.py** (302 lines) — Pricing, personas, recipes
- **judge.py** (187 lines) — Automated judge system

Located in `benchmark/` directory:
- **prompts.json** — 54 prompts across 8 categories
- **analyze_results.py** (347 lines) — Statistical analysis
- **analyze_diversity.py** (208 lines) — Diversity analysis
- **mtbench_integration.py** (260 lines) — MT-Bench adapter

Located in root:
- **run_premium_tier.py** (178 lines) — Phase 1 execution
- **run_persona_experiment.py** (194 lines) — Phase 3 execution
- **test_personas.py** (125 lines) — Persona diversity pilot

### Raw Result Data

Located in `results/` directory:
- **premium_tier_results.json** — 216 tests (Phase 1)
- **mtbench_results.json** — 160 tests (Phase 2)
- **persona_experiment.json** — 216 tests (Phase 3)

---

## Reading Paths for Different Goals

### Goal: Understand what was found
1. Start with **RESULTS_AT_A_GLANCE.md** (10 min)
2. Read **README.md** for context (10 min)
3. Optional: **BLOG.md** for full story (30 min)

### Goal: Prepare for publication
1. Read **BLOG.md** completely (30 min)
2. Use **EDITORIAL_REFERENCE.md** to fact-check claims (20 min)
3. Run verification commands from **EDITORIAL_REFERENCE.md** (10 min)
4. Review **WORK_SUMMARY.md** checklist (5 min)

### Goal: Understand methodology
1. Read **BLOG.md** methodology sections (15 min)
2. Read **DETAILED_METHODOLOGY.md** completely (60 min)
3. Review code files for implementation details

### Goal: Reproduce results
1. Read **DETAILED_METHODOLOGY.md** (60 min)
2. Review code implementations in `moa/` and `benchmark/` directories
3. Follow execution instructions in **DETAILED_METHODOLOGY.md**
4. Run `python run_premium_tier.py` and `python benchmark/analyze_results.py`

### Goal: Write about this work
1. Read **BLOG.md** for the narrative (30 min)
2. Read **RESULTS_AT_A_GLANCE.md** for quick facts (10 min)
3. Use **EDITORIAL_REFERENCE.md** to verify specific claims
4. Reference **WHY_ENSEMBLES_FAIL.md** for the aggregation trap explanation

---

## File Size Summary

| File | Lines | Type |
|------|-------|------|
| **Documentation** | | |
| BLOG.md | ~850 | Primary deliverable |
| DETAILED_METHODOLOGY.md | ~1100 | Full methodology |
| EDITORIAL_REFERENCE.md | ~350 | Fact-checking guide |
| WORK_SUMMARY.md | ~400 | Work summary |
| RESULTS_AT_A_GLANCE.md | ~250 | Quick reference |
| DOCUMENTATION_INDEX.md | ~200 | This file |
| README.md | ~400 | Project overview |
| WHY_ENSEMBLES_FAIL.md | ~250 | Aggregation trap |
| **Total Documentation** | **~3,800 lines** | |
| | | |
| **Code** | | |
| moa/*.py | ~1,164 | Core framework |
| benchmark/*.py | ~815 | Testing infrastructure |
| run_*.py | ~497 | Experiment runners |
| **Total Code** | **~2,476 lines** | |

---

## Quick Commands Reference

```bash
# Verify test counts
cat benchmark/prompts.json | jq '.prompts | length'                    # Should be 54
cat results/premium_tier_results.json | jq '.prompts | length'         # Should be 216
cat results/persona_experiment.json | jq '.prompts | length'           # Should be 216

# Run statistical analysis
python benchmark/analyze_results.py results/premium_tier_results.json

# Re-run experiments (requires AWS credentials)
python run_premium_tier.py
python run_persona_experiment.py

# Check category breakdown
cat benchmark/prompts.json | jq '.prompts | group_by(.category) | map({category: .[0].category, count: length})'
```

---

## What to Read Based on Your Role

### **Blog Editor**
1. BLOG.md (main deliverable)
2. EDITORIAL_REFERENCE.md (fact-checking)
3. RESULTS_AT_A_GLANCE.md (quick reference)

### **Technical Reviewer**
1. DETAILED_METHODOLOGY.md (full methodology)
2. Code files in `moa/` and `benchmark/`
3. Raw results in `results/*.json`

### **Marketing/Communications**
1. RESULTS_AT_A_GLANCE.md (key findings)
2. README.md (high-level summary)
3. WHY_ENSEMBLES_FAIL.md (the "story")

### **Researcher Wanting to Reproduce**
1. DETAILED_METHODOLOGY.md (experimental protocol)
2. All code files
3. benchmark/prompts.json (exact prompts used)

### **Someone New to the Project**
1. README.md (project overview)
2. RESULTS_AT_A_GLANCE.md (what was found)
3. BLOG.md (full story)

---

## Summary

You have **6 main documentation files** totaling ~3,800 lines:

1. **BLOG.md** — Main deliverable, ready for publication
2. **DETAILED_METHODOLOGY.md** — Complete experimental record
3. **EDITORIAL_REFERENCE.md** — Fact-checking guide
4. **WORK_SUMMARY.md** — What was done summary
5. **RESULTS_AT_A_GLANCE.md** — One-page visual summary
6. **README.md** — Project overview

Plus **3 supporting documents**:
- WHY_ENSEMBLES_FAIL.md
- PREMIUM_TIER_RESULTS.md
- MTBENCH_RESULTS.md

All documentation is **cross-referenced**, **fact-checked**, and **reproducible**.

Start with **RESULTS_AT_A_GLANCE.md** for a 10-minute overview, then dive into **BLOG.md** for the complete story.
