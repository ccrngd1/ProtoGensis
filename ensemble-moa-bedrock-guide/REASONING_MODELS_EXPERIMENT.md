# Experiment: Reasoning Models + Persona Diversity

**Goal:** Replicate Wang et al.'s success on AWS Bedrock using:
1. Models with reasoning capabilities
2. Persona-based diversity to simulate different model families

---

## Part 1: Bedrock Models with Reasoning Capabilities

### Available Models with Reasoning

| Model | Reasoning Level | Cost/1K | Context | Status |
|-------|----------------|---------|---------|--------|
| **Claude Opus 4.6** | ⭐⭐⭐⭐⭐ Excellent | $0.015/$0.075 | 200K | ✅ Available |
| **Claude Sonnet 4.6** | ⭐⭐⭐⭐ Strong | $0.003/$0.015 | 200K | ✅ Available |
| **Claude Haiku 4.5** | ⭐⭐⭐ Moderate | $0.0008/$0.004 | 200K | ✅ Available |
| Nova Premier | ⭐⭐ Basic | $0.002/$0.008 | 300K | ❌ Access denied |
| Mistral Large | ⭐⭐⭐ Moderate | $0.004/$0.012 | 32K | ✅ Available |

**Key Insight:** We have 4 reasoning-capable models available (Claude family + Mistral Large).

### Reasoning Capabilities

**Claude Models (Anthropic):**
- Constitutional AI training
- Chain-of-thought reasoning
- Self-reflection and verification
- Meta-cognitive abilities
- Strong at evaluation tasks

**Mistral Large:**
- Instruction following
- Multi-step reasoning
- Code understanding
- Some meta-evaluation

---

## Part 2: Persona-Based Diversity Strategy

### The Hypothesis

**Can different personas create "virtual model diversity"?**

Instead of:
- GPT-4 (OpenAI culture/training)
- Claude (Anthropic culture/training)  
- Gemini (Google culture/training)

Use:
- Opus + "You are a critical analyst focusing on logical flaws"
- Opus + "You are a creative generalist emphasizing completeness"
- Opus + "You are a domain expert focusing on technical accuracy"

**Theoretical Benefit:**
- Same base model (consistent quality floor)
- Different perspectives/biases induced by personas
- Potentially uncorrelated errors
- Aggregator can reconcile different "viewpoints"

### Research Precedent

**Persona prompting has been shown to:**
- Alter model behavior and outputs
- Reduce certain biases while introducing others
- Change response style and emphasis
- Affect reasoning paths taken

**Examples from literature:**
- "Think like a [expert]" → changes problem-solving approach
- Role-playing prompts → different evaluation criteria
- Perspective-taking → diverse viewpoints on same question

---

## Part 3: Proposed Experiment Design

### Recipe 1: Reasoning-Capable Ensemble (Cross-Vendor)

**Goal:** Use best available reasoning models from different vendors

```python
"reasoning-cross-vendor": {
    "name": "Cross-Vendor Reasoning Ensemble",
    "description": "Best reasoning models from different vendors",
    "proposers": [
        "opus",           # Anthropic - strongest reasoner
        "sonnet",         # Anthropic - strong reasoner (different tuning)
        "mistral-large"   # Mistral - different architecture
    ],
    "aggregator": "opus",  # Most capable aggregator
    "layers": 2,
    "use_case": "Test if vendor diversity + reasoning helps"
}
```

**Cost per prompt:** ~$0.25
**Expected:** Better than single Opus? (Hypothesis: No, but let's test)

---

### Recipe 2: Persona-Based Diversity (Same Model)

**Goal:** Test if personas can substitute for model diversity

```python
"persona-diverse": {
    "name": "Persona-Diverse Ensemble",
    "description": "Same model (Opus) with different personas",
    "proposers": [
        ("opus", "critical-analyst"),
        ("opus", "creative-generalist"),
        ("opus", "domain-expert")
    ],
    "aggregator": ("opus", "neutral-synthesizer"),
    "layers": 2,
    "use_case": "Test if persona diversity helps"
}
```

**Persona Definitions:**

```python
PERSONAS = {
    "critical-analyst": """You are a critical analyst. Focus on:
- Identifying logical flaws and inconsistencies
- Questioning assumptions
- Pointing out missing information
- Being precise and rigorous
- Favoring cautious, well-justified answers""",

    "creative-generalist": """You are a creative generalist. Focus on:
- Providing comprehensive, complete answers
- Considering multiple perspectives
- Making connections between concepts
- Being expansive and thorough
- Favoring breadth over depth""",

    "domain-expert": """You are a domain expert. Focus on:
- Technical accuracy and precision
- Deep domain knowledge
- Best practices and standards
- Practical implementation details
- Favoring depth over breadth""",

    "neutral-synthesizer": """You are a neutral synthesizer. Your task is to:
- Read multiple responses objectively
- Identify the most accurate information
- Recognize and filter hallucinations
- Synthesize a balanced, accurate answer
- Justify your reasoning for the final answer"""
}
```

**Cost per prompt:** ~$0.38 (4x Opus)
**Expected:** Might create meaningful diversity

---

### Recipe 3: Hybrid Approach

**Goal:** Combine reasoning models + personas

```python
"reasoning-with-personas": {
    "name": "Reasoning Models with Persona Diversity",
    "description": "Different reasoning models, each with a specific persona",
    "proposers": [
        ("opus", "critical-analyst"),
        ("sonnet", "creative-generalist"),
        ("mistral-large", "domain-expert")
    ],
    "aggregator": ("opus", "neutral-synthesizer"),
    "layers": 2,
    "use_case": "Test if model + persona diversity compounds"
}
```

**Cost per prompt:** ~$0.25
**Expected:** Best shot at replicating Wang et al.

---

## Part 4: Implementation Plan

### Phase 3A: Add Persona Support

**Modify `moa/core.py` to support personas:**

```python
class MoA:
    def __init__(
        self,
        proposers: List[Union[str, Tuple[str, str]]],  # model or (model, persona)
        aggregator: Union[str, Tuple[str, str]],
        layers: int = 2,
        refiners: List[Union[str, Tuple[str, str]]] | None = None
    ):
        self.proposers = self._parse_models_with_personas(proposers)
        self.aggregator = self._parse_model_with_persona(aggregator)
        # ...

    def _parse_model_with_persona(self, model_spec):
        if isinstance(model_spec, tuple):
            model_key, persona_key = model_spec
            return (model_key, PERSONAS[persona_key])
        return (model_spec, None)

    async def _invoke_with_persona(self, model_key, prompt, persona):
        if persona:
            full_prompt = f"{persona}\n\n{prompt}"
        else:
            full_prompt = prompt
        # Call model with full_prompt
        # ...
```

### Phase 3B: Create New Recipes

Add to `moa/models.py`:

```python
PERSONAS = {
    "critical-analyst": "...",
    "creative-generalist": "...",
    "domain-expert": "...",
    "neutral-synthesizer": "..."
}

RECIPES = {
    # ... existing recipes ...
    
    "reasoning-cross-vendor": {
        "name": "Cross-Vendor Reasoning Ensemble",
        "proposers": ["opus", "sonnet", "mistral-large"],
        "aggregator": "opus",
        "layers": 2,
        "use_case": "Test vendor + reasoning diversity"
    },
    
    "persona-diverse": {
        "name": "Persona-Diverse Ensemble",
        "proposers": [
            ("opus", "critical-analyst"),
            ("opus", "creative-generalist"),
            ("opus", "domain-expert")
        ],
        "aggregator": ("opus", "neutral-synthesizer"),
        "layers": 2,
        "use_case": "Test persona-based diversity"
    },
    
    "reasoning-with-personas": {
        "name": "Reasoning + Persona Hybrid",
        "proposers": [
            ("opus", "critical-analyst"),
            ("sonnet", "creative-generalist"),
            ("mistral-large", "domain-expert")
        ],
        "aggregator": ("opus", "neutral-synthesizer"),
        "layers": 2,
        "use_case": "Test combined diversity"
    }
}
```

### Phase 3C: Run Experiment

```bash
# Test on 54 custom prompts
python benchmark/run.py \
  --recipes reasoning-cross-vendor persona-diverse reasoning-with-personas \
  --output results/reasoning_experiment.json

# Analyze results
python benchmark/analyze_diversity.py results/reasoning_experiment.json
```

**Cost estimate:**
- 3 new recipes × 54 prompts × ~$0.30 avg = **~$49**
- Judge scoring: 3 × 54 × $0.005 = **$0.81**
- **Total: ~$50**

---

## Part 5: Expected Outcomes

### Hypothesis 1: Reasoning-Cross-Vendor

**Prediction:** Still won't beat standalone Opus

**Reasoning:**
- ✅ Has reasoning capability (meets 1 condition)
- ⚠️ Limited vendor diversity (Claude + Mistral only)
- ❌ Aggregator NOT stronger than proposers (Opus = Opus)
- ❌ Same AWS platform (possibly correlated errors)

**Expected result:** Similar to same-model-premium (92-93 quality)

---

### Hypothesis 2: Persona-Diverse

**Prediction:** MIGHT create meaningful diversity

**Reasoning:**
- ✅ All proposers high-quality (Opus = 95%)
- ✅ Aggregator same quality as proposers
- ✅ Personas could induce different error patterns
- ⚠️ But still same base model (shared weaknesses)

**Expected result:**
- **Optimistic:** 95-96 quality (beats standalone by 0.5-1 points)
- **Realistic:** 93-94 quality (matches standalone)
- **Pessimistic:** 92-93 quality (loses like other ensembles)

**Key question:** Do personas create enough diversity to offset aggregation overhead?

---

### Hypothesis 3: Reasoning-With-Personas

**Prediction:** Best chance of success

**Reasoning:**
- ✅ Multiple reasoning models
- ✅ Persona diversity within each model
- ✅ Some vendor diversity (Anthropic vs Mistral)
- ✅ Strong aggregator with explicit instructions

**Expected result:**
- **Optimistic:** 96-97 quality (beats Opus by 1-2 points) ✨
- **Realistic:** 94-95 quality (matches Opus)
- **Pessimistic:** 93-94 quality (slightly worse)

**Success criteria:** Beat Opus by ≥1 point with p<0.05

---

## Part 6: Analysis Plan

### Primary Question

**Does persona diversity + reasoning models enable MoA success on AWS Bedrock?**

Compare:
1. `reasoning-with-personas` vs `opus` baseline
2. `persona-diverse` vs `same-model-premium`
3. All three new recipes vs existing best

### Secondary Questions

1. **Do personas actually create diversity?**
   - Measure response similarity between personas
   - Check if personas disagree on answers
   - Look for systematic biases per persona

2. **Which persona is most accurate?**
   - Score each persona individually
   - Compare to non-persona baseline
   - Identify if one persona is clearly best

3. **Does aggregator benefit from persona labels?**
   - With labels: "Response from critical-analyst: ..."
   - Without labels: Just 3 anonymous responses
   - Does knowing the persona help evaluation?

4. **Cost efficiency?**
   - Quality/$ for each recipe
   - Compare to Wang et al.'s approach
   - Find break-even point

---

## Part 7: Implementation Effort

### Code Changes Required

1. **Add persona support to MoA core** (~30 min)
   - Modify `__init__` to accept (model, persona) tuples
   - Add persona prompt injection
   - Update invocation logic

2. **Define personas** (~15 min)
   - Write 4 persona prompts
   - Store in models.py
   - Test that they alter behavior

3. **Add new recipes** (~5 min)
   - 3 new recipe definitions
   - Update documentation

4. **Testing** (~2 hours)
   - Run on 54 prompts
   - Judge scoring
   - Statistical analysis

**Total effort:** ~3 hours
**Total cost:** ~$50

---

## Part 8: Success Criteria

### Minimum Success (Validates approach)

- Any recipe beats Opus baseline by ≥1 point (p<0.05)
- Persona responses show measurable diversity
- Cost efficiency competitive with standalone

### Strong Success (Replicates Wang et al.)

- Recipe beats Opus by ≥2 points (p<0.01)
- Works across multiple categories
- Cost/quality ratio acceptable for production

### Expected (Realistic)

- Recipes match Opus baseline (±0.5 points)
- Personas create some diversity but not enough
- Still not worth the cost/complexity overhead

---

## Part 9: Alternative: Just Test Personas First

**Cheaper validation:** Test if personas work before full experiment

```bash
# Quick test: 3 prompts, compare personas
python test_personas.py --prompts 3

# For each prompt:
#   - Run opus with no persona
#   - Run opus with critical-analyst persona
#   - Run opus with creative-generalist persona
#   - Run opus with domain-expert persona
#   - Compare responses

# Cost: 3 prompts × 4 variations × $0.08 = $0.96
```

**If personas don't create diversity, skip full experiment.**

---

## Recommendation

### Option A: Quick Persona Test ($1, 15 minutes)

Test if personas actually work before investing $50:

1. Run 3-5 test prompts with different personas
2. Manually inspect if responses differ meaningfully
3. If YES → proceed to full experiment
4. If NO → conclude personas don't help

### Option B: Full Reasoning Experiment ($50, 3 hours)

If confident in approach:

1. Implement persona support
2. Add 3 new recipes
3. Run 54-prompt benchmark
4. Analyze results thoroughly

### Option C: Document and Stop ($0, now)

Accept that AWS Bedrock can't replicate Wang et al.:
- Platform limitations (no true cross-vendor diversity)
- Aggregation overhead outweighs benefits
- Use standalone models instead

---

## My Recommendation

**Start with Option A (quick persona test).**

**Reasoning:**
- Low cost ($1 vs $50)
- Fast validation (15 min vs 3 hours)
- If personas don't work, saves time/money
- If personas DO work, proceed to full experiment

**Test plan:**
```bash
# Create simple test script
python test_personas.py \
  --prompts "adversarial-2,reasoning-1,code-3" \
  --personas critical-analyst,creative-generalist,domain-expert \
  --output results/persona_test.json
```

**Decision criteria:**
- If responses are 70%+ similar → personas don't help, stop
- If responses are <70% similar → meaningful diversity, proceed to Option B

---

Would you like me to:
1. **Implement the quick persona test** (Option A)?
2. **Go straight to full experiment** (Option B)?
3. **Just document findings and conclude** (Option C)?
