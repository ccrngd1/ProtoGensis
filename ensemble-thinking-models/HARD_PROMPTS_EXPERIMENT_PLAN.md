# Hard Prompts Experiment Plan

## 🎯 **Objective**

Test whether extended thinking and ensemble methods add value on **genuinely hard prompts** that require deep reasoning, not just pattern matching.

---

## 📝 **New Prompt Set: 10 Hard Problems**

### **Category Breakdown:**

**Healthcare/Technical (6 prompts):**
1. **h4_json_extraction_ambiguous** - Invoice with special chars, split shipment, superseded POs
2. **h5_x12_to_hl7_semantic** - 837P claim with contradictory place-of-service data
3. **h6_medical_coding_ambiguous** - ICD-10 coding under diagnostic uncertainty
4. **h7_entity_recognition_context** - Clinical NER with negations, causality, temporality
5. **h9_json_nested_ambiguous** - Contract amendments with temporal history, conditionals
6. **h10_x12_hl7_semantic_ambiguity** - 835 payment with math errors, code mismatches

**Reasoning/Logic (4 prompts):**
7. **h1_adversarial_integral** - Convergence subtleties in improper integral
8. **h2_pirate_gold** - 5-level backward induction game theory
9. **h3_race_condition_bug** - Subtle concurrency bug in lock-check-lock pattern
10. **h8_conflicting_studies** - Synthesize evidence from 3 contradictory medical studies

All prompts have **verifiable ground truth** and **detailed evaluation criteria**.

---

## 🤖 **Model Configuration: 16 Models in 4 Groups**

### **Group A: Thinking Models** (extended reasoning enabled)
```python
THINKING_MODELS = [
    "opus-thinking",    # $15/1M input, $75/1M output, 10K thinking budget
    "sonnet-thinking",  # $3/1M input, $15/1M output, 5K thinking budget  
    "haiku-thinking"    # $0.80/1M input, $4/1M output, 2K thinking budget
]
```
**Cost estimate**: ~$2-3 per 10 prompts (thinking tokens expensive)

---

### **Group B: Fast Models (Same as thinking but NO extended reasoning)**
```python
FAST_CLAUDE_MODELS = [
    "opus-fast",    # Same Opus model, standard mode
    "sonnet-fast",  # Same Sonnet, standard mode
    "haiku-fast"    # Same Haiku, standard mode
]
```
**Cost estimate**: ~$0.20-0.30 per 10 prompts (5-10x cheaper)

---

### **Group C: Mid-Tier Non-Claude Models**
```python
MID_TIER_MODELS = [
    "nova-pro",         # $0.80/$3.20 per 1M
    "mistral-large",    # $4/$12 per 1M
    "llama-3-1-70b",    # $0.72/$0.72 per 1M
    "gpt-oss"           # $4/$16 per 1M
]
```
**Cost estimate**: ~$0.30-0.50 per 10 prompts

---

### **Group D: Budget Models**
```python
BUDGET_MODELS = [
    "llama-3-1-8b",     # $0.22/$0.22 per 1M
    "nova-lite",        # $0.06/$0.24 per 1M
    "nova-micro",       # $0.035/$0.14 per 1M
    "nemotron-nano"     # $0.15/$0.15 per 1M
]
```
**Cost estimate**: ~$0.01-0.02 per 10 prompts

---

## 🔬 **Experiment Structure**

### **Phase 1: Individual Model Performance**

**Test each model independently on all 10 hard prompts**

**Expected outcomes:**
- Thinking models: 70-90% accuracy on hard prompts
- Fast models: 40-60% accuracy (pattern matching fails)
- Budget models: 30-50% accuracy

**Key comparisons:**
1. **Opus-thinking vs Opus-fast**: Is thinking worth the 5x cost increase?
2. **Sonnet-thinking vs Sonnet-fast**: Best value thinking model?
3. **Haiku-thinking vs Haiku-fast**: Can cheap thinking beat expensive fast?

---

### **Phase 2: Ensemble Comparisons**

**A. Thinking Ensemble vs Single Thinking**
- **Single**: Opus-thinking alone
- **Ensemble**: (Opus + Sonnet + Haiku, all thinking)
- **Question**: Can cheaper thinking models in ensemble match expensive thinking?

**B. Thinking Ensemble vs Fast Ensemble**
- **Thinking**: (Opus + Sonnet + Haiku thinking) @ ~$2.50
- **Fast**: (All 10 non-thinking models) @ ~$0.80
- **Question**: At what cost ratio does thinking beat breadth?

**C. Hybrid Ensemble**
- **Mix**: (Opus-thinking + Haiku-fast + Llama-70B + Nova-Pro)
- **Question**: Is one thinking model + many fast better than all-thinking or all-fast?

---

### **Phase 3: Grouped Evaluation**

**Compare groups on:**
1. **Accuracy** (% correct on evaluable prompts)
2. **Cost per correct answer**
3. **Reasoning quality** (manual evaluation of explanations)
4. **Convergence rate** (do models agree?)
5. **Error patterns** (what types of errors does each group make?)

---

## 📊 **Expected Results**

### **Hypothesis 1: Thinking helps on hard prompts** ✅
```
Opus-thinking:  80% accuracy @ $0.25/prompt
Opus-fast:      50% accuracy @ $0.05/prompt

→ Thinking adds 30% accuracy for 5x cost
→ Cost per correct: $0.31 vs $0.10
→ Verdict: Thinking worth it if >60% accuracy needed
```

### **Hypothesis 2: Thinking ensemble > single thinking** ✅
```
Opus-thinking alone:              80% @ $0.25
Thinking ensemble (O+S+H):        90% @ $0.35
Fast ensemble (10 models):        60% @ $0.08

→ Thinking ensemble +10% over Opus, +30% over fast ensemble
→ Cost premium justified for high-stakes applications
```

### **Hypothesis 3: Cheaper thinking beats expensive fast** ✅
```
Haiku-thinking:    70% @ $0.03
Opus-fast:         50% @ $0.05

→ Thinking on cheap model > no thinking on expensive model
→ Haiku-thinking is best value: 70% accuracy at $0.03
```

### **Hypothesis 4: Hybrid ensemble is optimal** ✅
```
All-thinking (3 models):          90% @ $0.35
All-fast (10 models):             60% @ $0.08
Hybrid (1 thinking + 5 fast):     85% @ $0.12

→ Hybrid achieves 94% of all-thinking accuracy at 34% of cost
→ Best cost/accuracy trade-off
```

---

## 🎯 **Evaluation Criteria**

### **Per-Prompt Evaluation:**

Each prompt has specific ground truth criteria. Example:

**h6_medical_coding_ambiguous:**
```python
CORRECT if:
  (a) I30.9 (acute pericarditis) as primary diagnosis
  (b) Does NOT code ACS/MI without confirmation
  (c) Uses Z87.891 (personal history of smoking) not F17.x (current)
  (d) Provides reasoning for ambiguous cases
  (e) Follows ICD-10 sequencing rules
```

### **Aggregate Metrics:**

1. **Overall accuracy**: % prompts meeting all criteria
2. **Partial credit**: % prompts meeting ≥3/5 criteria  
3. **Error categorization**:
   - Type 1: Pattern matching error (fast models)
   - Type 2: Reasoning error (thinking models)
   - Type 3: Domain knowledge gap (all models)

---

## 💰 **Cost Estimates**

### **Per Experiment (10 prompts):**

| Configuration | Models | Estimated Cost |
|--------------|--------|----------------|
| **Thinking only** | Opus + Sonnet + Haiku (thinking) | $2.50 |
| **Fast only** | All 10 non-thinking models | $0.80 |
| **Hybrid** | 1 thinking + 5 fast | $0.60 |
| **Single best** | Opus-thinking alone | $0.25 |
| **Budget** | Llama-70B alone | $0.004 |

### **Full Experiment Matrix:**
```
3 thinking models × 10 prompts = 30 calls @ $2.50
10 fast models × 10 prompts = 100 calls @ $0.80
Vote aggregation = 10 calls @ $0.02
Stitch synthesis = 10 calls @ $0.04

Total: ~$3.50 per complete run
```

### **Comparison Experiments:**
```
Run 1: Thinking-only ensemble
Run 2: Fast-only ensemble  
Run 3: Hybrid ensemble
Run 4: Thinking vs Fast (same models)

Total cost: ~$12-15 for full comparison study
```

---

## 🚀 **Implementation Steps**

### **Step 1: Model Setup** ✅ DONE
- [x] Add sonnet-thinking, haiku-thinking variants
- [x] Add opus-fast, sonnet-fast, haiku-fast variants
- [x] Keep existing non-Claude models

### **Step 2: Prompt Setup** ✅ DONE
- [x] Created hard_prompts.json with 10 prompts
- [x] Each prompt has ground truth and evaluation criteria
- [x] Includes healthcare-specific domains

### **Step 3: Update Evaluation** (TODO)
- [ ] Add per-prompt evaluation functions
- [ ] Group models into thinking/fast/mid/budget categories
- [ ] Add cost-per-correct-answer metrics
- [ ] Add reasoning quality scoring

### **Step 4: Run Experiments** (TODO)
```bash
# Experiment A: Thinking only
./run_hard_prompts.sh --group thinking

# Experiment B: Fast only
./run_hard_prompts.sh --group fast

# Experiment C: Comparison (thinking vs fast, same models)
./run_hard_prompts.sh --models opus-thinking opus-fast sonnet-thinking sonnet-fast haiku-thinking haiku-fast

# Experiment D: Hybrid ensemble
./run_hard_prompts.sh --models opus-thinking haiku-fast llama-3-1-70b nova-pro nova-lite
```

### **Step 5: Analysis** (TODO)
- [ ] Generate comparison tables
- [ ] Plot cost vs accuracy frontier
- [ ] Identify error patterns by model group
- [ ] Write findings report

---

## 📈 **Success Criteria**

**The experiment succeeds if we can answer:**

1. ✅ **Does extended thinking help on hard prompts?**
   - Compare opus-thinking vs opus-fast on same prompts
   - Need >20% accuracy improvement to justify 5x cost

2. ✅ **Can thinking ensemble beat single thinking?**
   - Compare (Opus+Sonnet+Haiku thinking) vs Opus-thinking alone
   - Need >10% accuracy improvement to justify added cost

3. ✅ **Is there a cost/accuracy sweet spot?**
   - Find optimal model combination
   - Likely: Haiku-thinking or Hybrid (1 thinking + fast ensemble)

4. ✅ **Do hard prompts change conclusions from easy prompts?**
   - Previous experiment: Ensemble didn't help (85.7% baseline)
   - Hard prompts: Expected 40-50% baseline
   - If ensemble helps more on hard prompts → validates approach

---

## 📝 **Next Actions**

**Option A: Run Full Experiment (~$12-15)**
1. All 4 experiment configurations
2. Complete comparison matrix
3. Comprehensive findings report

**Option B: Quick Validation (~$3)**
1. Single run: Thinking ensemble vs Fast ensemble
2. Validates if hard prompts change conclusions
3. If promising → run full matrix

**Option C: Staged Approach (~$6)**
1. Phase 1: Thinking vs Fast (same models) - $3
2. Analyze results
3. Phase 2: Best ensemble configs - $3

---

**Recommendation: Option C (Staged Approach)**
- Lower upfront cost
- Can pivot based on Phase 1 results
- Still gets full comparison if promising

**Ready to proceed?**
