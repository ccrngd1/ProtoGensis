# Documentation Updates: Softening Claims and Adding Caveats

**Date:** April 9, 2026  
**Purpose:** Address REVIEW.md Issue #1 (methodology critique) by reframing findings with appropriate caveats

## Changes Made

### Key Principle
Changed from **definitive rejection** to **exploratory/preliminary findings** with explicit limitations.

---

## README.md Updates

### 1. Major Findings Section (Lines 6-18)
**Before:**
```markdown
**Both hypotheses REJECTED:**
1. ❌ Extended thinking does NOT improve accuracy
2. ❌ Ensembles provide ZERO value (0/40 times)
```

**After:**
```markdown
## Preliminary Findings (Updated April 2026)
> Note: Exploratory findings based on limited sample sizes (n=10 custom, n=20 per benchmark) 
> with single runs and no statistical testing. Consider preliminary pending replication.

**Key observations:**
1. Extended thinking showed no accuracy advantage on our test sets
2. Naive ensembles (Haiku as judge) did not improve accuracy (0/40 wins)
```

**Changes:**
- Removed "REJECTED ❌" language
- Added prominent caveat box about sample size limitations
- Changed "ZERO value" to "did not improve accuracy"
- Specified "Haiku as judge" (naive ensemble architecture)

### 2. Hypothesis 1 Section (Lines 26-33)
**Before:**
```markdown
### Hypothesis 1: Extended Thinking Helps ❌ REJECTED
**Result:** Extended thinking provided ZERO accuracy improvement
```

**After:**
```markdown
### Hypothesis 1: Extended Thinking Helps
**Preliminary result (n=10 custom, n=20 per benchmark):** Extended thinking showed 
no accuracy improvement on our test sets. However, thinking mode helped on math 
benchmarks (GSM8K: thinking 100% vs fast 85%), suggesting context-dependency.

**Caveat:** Opus-thinking had 2 timeouts (360s limit) that may have penalized it. 
Results based on keyword matching, which may bias against verbose answers.
```

**Changes:**
- Removed "❌ REJECTED"
- Added sample sizes
- Acknowledged GSM8K contradiction
- Added timeout and evaluation caveats

### 3. Hypothesis 2 Section (Lines 31-39)
**Before:**
```markdown
### Hypothesis 2: Ensembles Beat Best Individual ❌ REJECTED
**Result:** 0/40 times (0% win rate). Ensembles just add cost without adding accuracy.
```

**After:**
```markdown
### Hypothesis 2: Ensembles Beat Best Individual
**Preliminary result (0/40 custom, 0/4 benchmarks):** Naive ensembles using Haiku 
as judge/orchestrator did not beat best individual models. This may reflect the 
specific ensemble architecture (weak judge) rather than ensembles being inherently useless.

**Caveat:** Only tested one ensemble design (Haiku judge). Literature includes 
self-consistency, weighted voting, strong verifiers not yet tested.
```

**Changes:**
- Removed "❌ REJECTED"
- Specified "naive ensembles" and "Haiku judge"
- Acknowledged architectural flaw
- Listed untested ensemble methods

### 4. Key Findings Section (Lines 96-148)
**Before:**
```markdown
### 1. Extended Thinking Failed Its Test
### 2. Nova-lite is the Value Champion
### 3. Opus-thinking is the Worst Option
### 4. Ensembles Provide No Value
### 5. Fast Mode > Thinking Mode
```

**After:**
```markdown
### 1. Extended Thinking Showed No Advantage on Custom Prompts (Exploratory, n=10)
### 2. Nova-lite Had Strong Value on Custom Prompts
### 3. Opus-thinking Had Challenges on Custom Prompts
### 4. Naive Ensembles (Haiku Judge) Did Not Improve Accuracy
### 5. Fast Mode Matched or Beat Thinking Mode (Custom Prompts Only)
```

**Changes:**
- Softened all titles (Failed → Showed No Advantage, Worst → Had Challenges)
- Added "(Exploratory, n=10)" tags
- Added caveats in each section about timeouts, sample size, evaluation methods
- Changed "Never use ensembles" to "For this ensemble architecture, just use best individual"

---

## BLOG.md Updates

### 1. Title and Subtitle (Lines 1-3)
**Before:**
```markdown
# Do Thinking Models Think Better? (Spoiler: No)
```

**After:**
```markdown
# Do Thinking Models Think Better? An Exploratory Study

*Important: These are preliminary findings based on limited sample sizes, single runs, 
and no statistical testing. Treat as hypothesis-generating rather than conclusive.*
```

**Changes:**
- Removed snarky "Spoiler: No" from title
- Added explicit warning about preliminary nature

### 2. Introduction (Line 17)
**Before:**
```markdown
I ran a comprehensive study. Both hypotheses failed spectacularly.
```

**After:**
```markdown
I ran an exploratory study. The preliminary results challenge both hypotheses, 
though with important caveats about sample size and methodology.
```

**Changes:**
- "comprehensive" → "exploratory"
- "failed spectacularly" → "challenge... with caveats"

### 3. Finding 1 (Lines 67-86)
**Before:**
```markdown
### Finding 1: Extended Thinking Provides ZERO Accuracy Benefit
**Result:** ❌ REJECTED
Fast mode never worse, sometimes better, always cheaper.
```

**After:**
```markdown
### Finding 1: Extended Thinking Showed No Advantage on Custom Prompts (n=10)
**Preliminary Result (n=10, single run each):**
On these 10 prompts, fast mode was never worse, sometimes better, always cheaper.

**Important caveats:**
- Opus-thinking had 2 timeouts (may reflect infrastructure not capability)
- Keyword matching may penalize verbose answers
- GSM8K showed opposite pattern (thinking 100% vs fast 85%)
- One prompt = 10% accuracy change
- No statistical significance testing
```

**Changes:**
- Removed "❌ REJECTED"
- Added sample size and run count
- Listed 5 important caveats
- Acknowledged GSM8K contradiction

### 4. Finding 4 (Lines 131-147)
**Before:**
```markdown
### Finding 4: Ensembles Beat Best Individual 0/40 Times
**Result:** ❌ REJECTED
Not once. Ensembles just pick existing answers. They add cost without adding value.
```

**After:**
```markdown
### Finding 4: Naive Ensembles (Haiku Judge) Beat Best Individual 0/40 Times
**Preliminary Result (testing one specific ensemble architecture):**

**What was tested:** Vote (Haiku as judge) and Stitch (Haiku as synthesizer). 
Not once did this ensemble architecture beat best individual.

**Important limitations:**
- Only tested one design: weak model (Haiku) as judge
- Literature includes: self-consistency, weighted voting, strong verifiers, debate
- Architectural flaw (Haiku judging stronger models) may explain failure
- Sample size: n=10 per experiment, no statistical testing
```

**Changes:**
- Added "Naive" and "(Haiku Judge)" to title
- Specified what was tested vs what wasn't
- Listed alternative ensemble methods
- Acknowledged architectural flaw

### 5. "Why These Results Matter" (Lines 196-228)
**Before:**
```markdown
## Why These Results Matter
### The Cost of Being Wrong About Thinking
If you deployed Opus-thinking... Wasted budget: $2,207,000
### The Judge Model Irony (Resolved)
You don't need a judge. Just use the cheapest model.
### When Fast Mode > Thinking Mode
Every single tier... Thinking mode just burned money.
```

**After:**
```markdown
## Why These Preliminary Results Matter
### The Cost of Extended Thinking
If our 10-prompt findings generalize... Potential cost difference: ~$2,207,000
**But:** Nova-lite not yet validated on benchmarks. Task-specific performance may vary.

### The Haiku Judge Bottleneck
Our ensemble architecture: Haiku judges stronger models
The problem: Like having an intern grade senior engineer work
The insight: This specific architecture is flawed. Doesn't prove ensembles useless.

### When Fast Mode Matched/Beat Thinking Mode (Custom Prompts)
On our 10 custom prompts... 
**Context matters:** GSM8K showed opposite. Thinking appears task-dependent.
```

**Changes:**
- Added "Preliminary" to section title
- Changed "Wasted budget" to "Potential cost difference"
- Added "But" caveat about Nova-lite
- Acknowledged Haiku bottleneck explicitly
- Changed "burned money" to "task-dependent"

### 6. "The Bigger Picture" (Lines 500-517)
**Before:**
```markdown
This study challenges three pieces of conventional wisdom:
1. Extended reasoning - Not demonstrated
2. Ensembles - Not demonstrated
3. Expensive models - Not demonstrated

These aren't small claims. They contradict marketing materials.
Science progresses by proving each other wrong.
```

**After:**
```markdown
This exploratory study raises questions about three pieces of conventional wisdom:
1. Extended reasoning - Mixed evidence, appears task-dependent, needs larger samples
2. Ensembles - Weak-judge ensembles failed, other methods not yet tested
3. Expensive models - Nova-lite matched Opus on 10 prompts, not validated on benchmarks

These are preliminary, exploratory findings with significant limitations (n=10-20, 
single runs, keyword evaluation). They suggest directions for further investigation 
rather than definitive conclusions.

Science progresses by careful replication and critique.
```

**Changes:**
- "challenges" → "raises questions"
- Added nuance to each claim (mixed evidence, architectural flaw, not validated)
- Explicit limitations paragraph
- "proving each other wrong" → "careful replication and critique"

---

## Summary of Changes

### Language Changes
| Before | After |
|--------|-------|
| "REJECTED ❌" | "Preliminary result" |
| "ZERO value" | "did not improve accuracy" |
| "Failed spectacularly" | "challenge with caveats" |
| "Never use ensembles" | "For this architecture, use best individual" |
| "Comprehensive study" | "Exploratory study" |
| "Proves" | "Suggests" |

### Added Caveats
1. **Sample size:** Prominent notes about n=10 custom, n=20 benchmarks
2. **Single runs:** No statistical significance testing
3. **Timeout issue:** Opus-thinking penalized by 360s limit
4. **Evaluation bias:** Keyword matching may penalize verbose answers
5. **Architecture specificity:** Haiku judge is one specific (flawed) design
6. **Task dependency:** GSM8K contradicts custom prompts (thinking helps on math)
7. **Domain skew:** 60% healthcare prompts, not validated on standard benchmarks (Nova-lite)

### Structural Additions
- Prominent caveat box in README.md
- Explicit warning in BLOG.md subtitle
- "Important caveats" bullets in each findings section
- "Preliminary" / "Exploratory" qualifiers throughout
- Acknowledgment of untested ensemble methods
- Context about GSM8K contradicting findings

---

## Addresses REVIEW.md Concerns

✅ **Issue #1: N=10 Is Not a Study, It's an Anecdote**
- Now explicitly labeled "exploratory" and "preliminary"
- Sample sizes noted prominently
- Removed definitive "REJECTED" language

✅ **Issue #2: Evaluation Is Subjective**
- Acknowledged keyword matching limitations
- Noted LLM-as-judge now available
- Added caveat about verbose answer bias

✅ **Issue #3: Timeouts Are Configuration Problem**
- Acknowledged timeout issue in multiple places
- Noted infrastructure vs capability distinction
- Added caveat about 360s limit being potentially too aggressive

✅ **Issue #4: Naive Ensemble Design**
- Changed "ensembles" to "naive ensembles (Haiku judge)"
- Listed untested ensemble methods
- Acknowledged architectural flaw explicitly

✅ **Issue #8: Honest Framing**
- No longer claiming hypothesis rejection
- All findings labeled preliminary/exploratory
- Explicit limitations sections added

---

## Files Modified
- `README.md` - 12 sections updated
- `BLOG.md` - 8 sections updated
- `DOCUMENTATION_UPDATES.md` - This file created

## Next Steps from Review
1. ✅ **Update documentation framing** - COMPLETE
2. ⬜ Fix timeout issue (increase to 600s or remove)
3. ⬜ Add self-consistency ensemble (no judge needed)
4. ⬜ Test Nova-lite on benchmarks

---

*Updated: April 9, 2026*
