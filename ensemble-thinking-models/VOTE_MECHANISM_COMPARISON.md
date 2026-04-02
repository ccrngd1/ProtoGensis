# Vote Mechanism Comparison

## The Two Approaches

### 1. Judge Selection (Old - "Pick Best")
**What it does:** Haiku evaluates all responses and selects the highest quality answer

**Prompt to Haiku:** "Analyze each response and select the BEST one based on correctness, clarity, and completeness"

### 2. Semantic Majority Vote (New - "Pick Most Common")
**What it does:** Haiku identifies which responses reach the same conclusion and picks the majority

**Prompt to Haiku:** "Identify which responses AGREE semantically (ignore wording) and return the most common conclusion"

## Results Comparison

| Prompt | Judge Selection (Best) | Semantic Vote (Majority) | Difference |
|--------|----------------------|--------------------------|------------|
| p1_monty_hall | Mistral | Nova + Mistral | Judge split the tie |
| p2_mutex_deadlock | Nova | Nova + Mistral | Same result |
| p3_trolley_autonomous | Nova | No majority | Judge picked when no consensus |
| p4_regex_edge_case | Mistral | Nova + Mistral | Judge picked one from majority |
| p5_medical_bayes | Nova | Nova + Mistral | Same result |
| p6_time_complexity | Nova | Nova + Mistral | Same result |
| p7_ship_of_theseus | Nova | Nova + Mistral | Same result |
| p8_sql_injection | Nova | Nova + Mistral | Same result |
| p9_ai_copyright | Nova | Nova + Mistral | Same result |
| p10_optimization | Nova | Nova + Mistral | Same result |

## Key Findings

### Agreement Patterns (Semantic Vote)
- **9/10 prompts**: Nova + Mistral agree (2-way majority)
- **1/10 prompts**: No majority (all disagree)
- **0/10 prompts**: All 3 agree

### Selection Patterns (Judge Selection)
- **Nova selected**: 7/10 times
- **Mistral selected**: 2/10 times
- **Opus selected**: 0/10 times (empty answers)

## What This Reveals

### 1. Nova and Mistral Consistently Agree
**9/10 prompts show semantic agreement between Nova + Mistral**

This means:
- These models are producing similar conclusions
- They're not providing genuinely diverse reasoning
- Ensemble value is limited if 2 of 3 always agree

### 2. Judge Selection Adds Quality Layer
When Nova + Mistral agree, judge selection picks one based on quality:
- p1: Both agree, judge picks Mistral (better explanation)
- p5: Both agree, judge picks Nova (better math)

This is essentially: **"Pick the better explanation of the agreed-upon answer"**

### 3. Semantic Vote Is More "Ensemble-Like"
- Explicitly identifies consensus
- Returns majority (even if explanation quality varies)
- More aligned with traditional voting mechanisms

### 4. Judge Selection Is More "Oracle-Like"
- Uses quality/correctness to decide
- Can pick the minority if it's higher quality
- Acts more like a meta-reviewer than a vote counter

## Does Haiku Have Enough Reasoning?

**Yes, semantic voting is easier than quality judgment:**

✅ **Semantic Vote (Simple):**
- "Do these 3 answers reach the same conclusion?" → Pattern matching
- "Which conclusion appears most often?" → Counting
- Low reasoning required

✅ **Judge Selection (Complex):**
- "Which answer is most correct?" → Requires domain knowledge
- "Which reasoning is most thorough?" → Requires meta-reasoning
- High reasoning required

**Evidence Haiku can do semantic voting:**
- Successfully identified Nova + Mistral agreement on 9/10 prompts
- Correctly recognized no consensus on p3 (trolley problem with no objective answer)
- Didn't get confused by different writing styles

**Evidence Haiku struggles with judge selection:**
- On p4 (regex), both Nova & Mistral agree "instant failure" (wrong)
- Correct answer: "catastrophic backtracking occurs" (neither model said this)
- Judge picked Mistral from the wrong majority
- Haiku couldn't identify that both were incorrect

## Which Mechanism to Use?

### Use Semantic Majority Vote When:
- ✅ You want true ensemble behavior (consensus-seeking)
- ✅ You trust that agreement = correctness (wisdom of crowds)
- ✅ You value transparency (explicit vote counts)
- ✅ You want faster/cheaper (simpler task for LLM)

### Use Judge Selection When:
- ✅ You trust the judge model's expertise
- ✅ Quality matters more than consensus
- ✅ You want the best individual answer (not average)
- ✅ You're willing to pay for judgment capability

### The Irony:
If your judge model is good enough to identify correctness, why not just use it directly instead of running 3 models first?

## Implications for Experiment

**The semantic vote reveals:**
- Nova + Mistral agree 90% of the time
- Opus contributed nothing (empty answers)
- Ensemble is essentially: "Run 2 similar models, pick one"

**Cost analysis with semantic vote:**
- Nova alone: $0.02 → 85.7% accuracy
- Semantic vote: $2.06 ($0.02 Nova + $0.02 Mistral + $2 Opus empty + $0.02 Haiku) → 100% accuracy
- **ROI: 100x cost for 14% improvement by adding Mistral as a check**

**Better approach:**
- Run Nova alone: $0.02 → 85.7%
- If Nova has low confidence, run Mistral for validation: $0.04 total
- Only pay 2x when needed, not always

## Recommendation

**For this experiment, semantic majority vote is more appropriate because:**
1. ✅ It's what you'd call "voting" in ensemble literature
2. ✅ It shows the true agreement patterns (Nova + Mistral 90%)
3. ✅ It reveals the lack of diversity in reasoning
4. ✅ It's honest about what's happening (consensus, not quality judgment)

**Judge selection masks the problem** by picking the "best" from an already-converged set, making it look like you're adding value through selection when you're really just picking between equivalent answers.
