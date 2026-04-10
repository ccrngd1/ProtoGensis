# MoA Benchmark Expansion Plan

**Date:** April 9, 2026  
**Status:** Planning phase  
**Estimated Cost:** $75.52  
**Estimated Time:** 4.5 hours  

---

## Context

Current implementation uses 54 custom prompts across 8 categories (adversarial, analysis, code, creative, edge-cases, factual, multistep, reasoning) with budget and mid-tier models.

**Wang et al.'s MoA paper** used three academic benchmarks:
1. **AlpacaEval 2.0** - 805 instruction-following prompts (achieved 65.1% win rate)
2. **MT-Bench** - 80 multi-turn conversations (8 categories)
3. **FLASK** - 1,800 prompts across 12 fine-grained skills

Their key claim: **Diversity improves quality** (tested with GPT-4, Claude, Gemini).

**Our finding (54 prompts):** Diversity does NOT significantly improve quality (p=0.36) with budget models.

**Question:** Does diversity matter on their benchmarks? Does it matter with premium models?

---

## Expansion Goals

1. **Test on Wang et al.'s benchmarks** - Direct comparison to paper's methodology
2. **Add thinking/reasoning models** - Test premium tier (Opus, Sonnet, Nova Premier)
3. **Validate diversity hypothesis** - Does diversity help on instruction-following vs. practical tasks?
4. **Cost/quality frontier** - Map full spectrum from ultra-cheap to premium

---

## Phase 1: High-End Models on Current Benchmark

**Goal:** Test if diversity matters at premium tier using our existing 54 prompts.

### New Model Recipes

Add to `moa/models.py`:

```python
"high-end-reasoning": {
    "name": "High-End Reasoning Ensemble",
    "description": "Premium models with extended thinking capability",
    "proposers": ["opus", "sonnet", "nova-premier"],
    "refiners": ["opus", "sonnet"],
    "aggregator": "opus",
    "layers": 3,
    "use_case": "Complex reasoning requiring deep analysis",
}

"mixed-capability": {
    "name": "Mixed Capability Ensemble", 
    "description": "Cheap proposers + premium aggregator (Wang et al. pattern)",
    "proposers": ["nova-lite", "haiku", "llama-3.1-8b"],
    "aggregator": "opus",
    "layers": 2,
    "use_case": "Budget proposers with strong synthesis",
}

"same-model-premium": {
    "name": "Same-Model Premium Ensemble",
    "description": "3x Opus proposers + Opus aggregator (ablation for premium tier)",
    "proposers": ["opus", "opus", "opus"],
    "aggregator": "opus",
    "layers": 2,
    "use_case": "Ablation - tests if diversity matters at premium tier",
}
```

### New Baselines

Add to baseline testing in `benchmark/run.py`:

```python
baseline_models = [
    "nova-lite",      # Existing
    "haiku",          # Existing
    "sonnet",         # Existing
    "opus",           # NEW
    "nova-premier",   # NEW
]
```

### Implementation Steps

1. Add recipes to `moa/models.py`
2. Update `benchmark/run.py` to include new baselines
3. Run benchmark:
   ```bash
   python benchmark/run.py \
     --output results/premium_tier.json \
     --recipes high-end-reasoning mixed-capability same-model-premium
   ```
4. Analyze diversity at premium tier:
   ```bash
   python benchmark/analyze_diversity.py results/premium_tier.json
   ```

### Cost Estimate

| Configuration | Cost/Prompt | Total (54 prompts) |
|--------------|-------------|-------------------|
| high-end-reasoning (3 layers) | ~$0.80 | $43.20 |
| mixed-capability | ~$0.10 | $5.40 |
| same-model-premium | ~$0.08 | $4.32 |
| opus baseline | ~$0.02 | $1.08 |
| nova-premier baseline | ~$0.005 | $0.27 |
| Judge scoring (5 configs × 54) | $0.005 | $1.35 |
| **TOTAL** | - | **$55.62** |

**Time:** ~90 minutes (premium models are slower)

### Expected Learnings

- Does diversity matter when all models are strong?
- Can 3x Opus beat standalone Opus via ensemble?
- Is mixed-capability (cheap+premium) a sweet spot?
- Cost/quality curve at premium tier

---

## Phase 2: MT-Bench Integration

**Goal:** Test multi-turn conversation ability (80 questions, 2 turns each).

### What is MT-Bench?

- 80 multi-turn questions across 8 categories
- Tests conversation coherence and context tracking
- Turn 2 depends on Turn 1 answer
- Categories: writing, roleplay, reasoning, math, coding, extraction, STEM, humanities
- Scored 1-10 by GPT-4 judge (we'll use Opus)

### Implementation

**New file:** `benchmark/mtbench_integration.py`

```python
#!/usr/bin/env python3
"""
MT-Bench integration for multi-turn conversation testing.
"""

import json
import requests
import asyncio
from pathlib import Path
from moa.core import run_ensemble
from moa.judge import QualityJudge

MTBENCH_URL = "https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/llm_judge/data/mt_bench/question.jsonl"

def fetch_mtbench_questions():
    """Download MT-Bench questions from FastChat repo."""
    response = requests.get(MTBENCH_URL)
    questions = []
    for line in response.text.strip().split('\n'):
        questions.append(json.loads(line))
    return questions  # 80 questions

async def run_mtbench_conversation(ensemble_config, question):
    """
    Run multi-turn conversation.
    
    Args:
        ensemble_config: Recipe name or config dict
        question: MT-Bench question with 'turns' array
    
    Returns:
        Dict with turn_1 and turn_2 responses
    """
    # Turn 1
    response_1 = await run_ensemble(
        ensemble_config, 
        question['turns'][0]
    )
    
    # Turn 2 (with context from Turn 1)
    context = f"""Previous conversation:

User: {question['turns'][0]}
Assistant: {response_1}

User: {question['turns'][1]}"""
    
    response_2 = await run_ensemble(
        ensemble_config,
        context
    )
    
    return {
        'question_id': question['question_id'],
        'category': question['category'],
        'turn_1': {
            'prompt': question['turns'][0],
            'response': response_1
        },
        'turn_2': {
            'prompt': question['turns'][1],
            'response': response_2,
            'context': response_1
        }
    }

async def run_mtbench_suite(configs, output_file):
    """Run all configs on MT-Bench."""
    questions = fetch_mtbench_questions()
    
    results = {
        'metadata': {
            'benchmark': 'MT-Bench',
            'total_questions': len(questions),
            'configs_tested': configs
        },
        'results': {}
    }
    
    for config_name in configs:
        print(f"\nTesting {config_name} on MT-Bench...")
        config_results = []
        
        for question in questions:
            result = await run_mtbench_conversation(config_name, question)
            config_results.append(result)
            print(f"  Completed {question['question_id']} ({question['category']})")
        
        results['results'][config_name] = config_results
    
    # Score with judge
    print("\nScoring with Opus judge...")
    judge = QualityJudge(judge_model="opus")
    
    for config_name, config_results in results['results'].items():
        for result in config_results:
            # Score both turns
            for turn in ['turn_1', 'turn_2']:
                score = await judge.score_response(
                    prompt=result[turn]['prompt'],
                    response=result[turn]['response'],
                    expected_answer=None  # MT-Bench has no reference answers
                )
                result[turn]['judge_score'] = score
    
    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python benchmark/mtbench_integration.py <config1> <config2> ...")
        print("\nExample:")
        print("  python benchmark/mtbench_integration.py ultra-cheap high-end-reasoning")
        sys.exit(1)
    
    configs = sys.argv[1:]
    
    asyncio.run(run_mtbench_suite(
        configs=configs,
        output_file="results/mtbench_results.json"
    ))
```

### Usage

```bash
# Test selected configs on MT-Bench
python benchmark/mtbench_integration.py \
  ultra-cheap \
  high-end-reasoning \
  same-model-baseline

# Analyze results
python benchmark/analyze_mtbench.py results/mtbench_results.json
```

### Cost Estimate

| Item | Calculation | Cost |
|------|-------------|------|
| Benchmark (3 configs) | 80 questions × 2 turns × $0.0007 × 3 | $0.34 |
| Judge scoring | 80 × 2 × 3 × $0.005 | $2.40 |
| **TOTAL** | - | **$2.74** |

**Time:** ~30 minutes

### Expected Learnings

- Multi-turn coherence of ensembles
- Does MoA maintain context across turns?
- Comparison to Wang et al.'s MT-Bench scores
- Category breakdown (which types benefit from ensemble?)

---

## Phase 3: AlpacaEval 2.0 Integration (Sample)

**Goal:** Test on instruction-following benchmark (Wang et al.'s primary evaluation).

### What is AlpacaEval 2.0?

- 805 instruction-following prompts
- Evaluated by GPT-4 judge (pairwise comparison vs. GPT-4 Turbo)
- Win rate metric (% of times model beats baseline)
- Wang et al. achieved 65.1% with MoA-GPT-4

### Implementation

**New file:** `benchmark/alpacaeval_integration.py`

```python
#!/usr/bin/env python3
"""
AlpacaEval 2.0 integration for instruction-following evaluation.
"""

import json
import requests
import asyncio
import random
from pathlib import Path
from moa.core import run_ensemble
from moa.judge import QualityJudge

ALPACAEVAL_URL = "https://raw.githubusercontent.com/tatsu-lab/alpaca_eval/main/src/alpaca_eval/evaluators_configs/alpaca_eval_gpt4_turbo_fn/alpaca_eval.json"

def fetch_alpacaeval_prompts(sample_size=None):
    """
    Download AlpacaEval 2.0 dataset.
    
    Args:
        sample_size: If provided, randomly sample this many prompts
    
    Returns:
        List of prompts with instructions and references
    """
    response = requests.get(ALPACAEVAL_URL)
    prompts = response.json()  # 805 prompts
    
    if sample_size:
        # Stratified sampling by category if available
        prompts = random.sample(prompts, sample_size)
    
    return prompts

async def run_alpacaeval_benchmark(configs, sample_size=100, output_file=None):
    """
    Run configs on AlpacaEval (or sample).
    
    Args:
        configs: List of ensemble config names
        sample_size: Number of prompts to test (default 100, use None for all 805)
        output_file: Where to save results
    """
    prompts = fetch_alpacaeval_prompts(sample_size=sample_size)
    
    print(f"\nRunning AlpacaEval with {len(prompts)} prompts...")
    print(f"Configs: {', '.join(configs)}\n")
    
    results = {
        'metadata': {
            'benchmark': 'AlpacaEval 2.0',
            'total_prompts': len(prompts),
            'sample_size': sample_size,
            'configs_tested': configs
        },
        'results': {}
    }
    
    for config_name in configs:
        print(f"\nTesting {config_name}...")
        config_results = []
        
        for i, prompt_data in enumerate(prompts, 1):
            instruction = prompt_data['instruction']
            reference = prompt_data.get('output', '')  # GPT-4 Turbo baseline
            
            response = await run_ensemble(config_name, instruction)
            
            config_results.append({
                'instruction': instruction,
                'response': response,
                'reference': reference,
                'dataset': prompt_data.get('dataset', 'unknown')
            })
            
            if i % 10 == 0:
                print(f"  Completed {i}/{len(prompts)}")
        
        results['results'][config_name] = config_results
    
    # Score with Opus judge
    print("\nScoring with Opus judge...")
    judge = QualityJudge(judge_model="opus")
    
    for config_name, config_results in results['results'].items():
        print(f"  Scoring {config_name}...")
        
        for result in config_results:
            score = await judge.score_response(
                prompt=result['instruction'],
                response=result['response'],
                expected_answer=result['reference']
            )
            result['judge_score'] = score
    
    # Calculate win rates (responses scoring >70 considered "wins")
    for config_name, config_results in results['results'].items():
        scores = [r['judge_score']['total'] for r in config_results]
        win_rate = sum(1 for s in scores if s >= 70) / len(scores) * 100
        
        results['results'][config_name]['summary'] = {
            'mean_score': sum(scores) / len(scores),
            'win_rate': win_rate,
            'total_prompts': len(scores)
        }
    
    # Save results
    output_file = output_file or "results/alpacaeval_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("ALPACAEVAL SUMMARY")
    print("="*60)
    
    for config_name, config_data in results['results'].items():
        if isinstance(config_data, list):
            continue
        summary = config_data.get('summary', {})
        print(f"\n{config_name}:")
        print(f"  Mean Score: {summary['mean_score']:.1f}/100")
        print(f"  Win Rate: {summary['win_rate']:.1f}%")
    
    print("="*60 + "\n")
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python benchmark/alpacaeval_integration.py <config1> <config2> ...")
        print("\nOptions:")
        print("  --sample N    Test on N random prompts (default: 100)")
        print("  --full        Test on all 805 prompts")
        print("\nExample:")
        print("  python benchmark/alpacaeval_integration.py ultra-cheap high-end-reasoning --sample 100")
        sys.exit(1)
    
    # Parse args
    configs = []
    sample_size = 100
    
    for arg in sys.argv[1:]:
        if arg == '--full':
            sample_size = None
        elif arg == '--sample':
            continue
        elif sys.argv[sys.argv.index(arg) - 1] == '--sample':
            sample_size = int(arg)
        else:
            configs.append(arg)
    
    if not configs:
        print("Error: No configs specified")
        sys.exit(1)
    
    asyncio.run(run_alpacaeval_benchmark(
        configs=configs,
        sample_size=sample_size
    ))
```

### Usage

```bash
# Sample test (100 prompts)
python benchmark/alpacaeval_integration.py \
  ultra-cheap high-end-reasoning same-model-baseline \
  --sample 100

# Full test (805 prompts, expensive!)
python benchmark/alpacaeval_integration.py \
  ultra-cheap \
  --full
```

### Cost Estimate

**Sample (100 prompts, 3 configs):**

| Item | Calculation | Cost |
|------|-------------|------|
| Benchmark | 100 × $0.0007 × 3 | $0.21 |
| Judge scoring | 100 × 3 × $0.005 | $1.50 |
| **TOTAL** | - | **$1.71** |

**Full (805 prompts, 3 configs):**

| Item | Calculation | Cost |
|------|-------------|------|
| Benchmark | 805 × $0.0007 × 3 | $1.69 |
| Judge scoring | 805 × 3 × $0.005 | $12.08 |
| **TOTAL** | - | **$13.77** |

**Time:** 60 min (sample), 8 hours (full)

### Expected Learnings

- Direct comparison to Wang et al.'s 65.1% win rate
- Does diversity help on instruction-following?
- How do budget ensembles compare to GPT-4 Turbo?
- Which instruction types benefit from ensemble?

---

## Phase 4: FLASK Integration (Sample)

**Goal:** Fine-grained skill evaluation across 12 dimensions.

### What is FLASK?

- 1,800+ prompts across 12 skills
- Skills: Logic, Background Knowledge, Problem Solving, Creativity, Factuality, Commonsense, Comprehension, Insightfulness, Completeness, Metacognition, Readability, Conciseness
- Each response scored 1-5 on relevant skills
- Human-annotated reference answers

### Implementation

**New file:** `benchmark/flask_integration.py`

```python
#!/usr/bin/env python3
"""
FLASK integration for fine-grained skill evaluation.
"""

import json
import requests
import asyncio
import random
from pathlib import Path
from moa.core import run_ensemble
from moa.judge import QualityJudge

FLASK_SKILLS = [
    'logical_reasoning',
    'background_knowledge',
    'problem_solving',
    'creativity',
    'factuality',
    'commonsense',
    'comprehension',
    'insightfulness',
    'completeness',
    'metacognition',
    'readability',
    'conciseness'
]

def fetch_flask_dataset(sample_per_skill=None):
    """
    Download FLASK dataset from GitHub.
    
    Args:
        sample_per_skill: If provided, sample N prompts per skill
    
    Returns:
        List of prompts with skill annotations
    """
    # NOTE: FLASK dataset location - need to verify actual URL
    # https://github.com/kaistAI/FLASK
    
    url = "https://raw.githubusercontent.com/kaistAI/FLASK/main/evaluation_set/flask_evaluation.json"
    response = requests.get(url)
    dataset = response.json()
    
    if sample_per_skill:
        # Stratified sampling by skill
        sampled = []
        for skill in FLASK_SKILLS:
            skill_prompts = [p for p in dataset if skill in p.get('skills', [])]
            sampled.extend(random.sample(skill_prompts, min(sample_per_skill, len(skill_prompts))))
        dataset = sampled
    
    return dataset

async def run_flask_benchmark(configs, sample_per_skill=20, output_file=None):
    """
    Run configs on FLASK benchmark.
    
    Args:
        configs: List of ensemble config names
        sample_per_skill: Number of prompts per skill (default 20)
        output_file: Where to save results
    """
    dataset = fetch_flask_dataset(sample_per_skill=sample_per_skill)
    
    print(f"\nRunning FLASK with {len(dataset)} prompts...")
    print(f"Configs: {', '.join(configs)}\n")
    
    results = {
        'metadata': {
            'benchmark': 'FLASK',
            'total_prompts': len(dataset),
            'sample_per_skill': sample_per_skill,
            'configs_tested': configs
        },
        'results': {}
    }
    
    for config_name in configs:
        print(f"\nTesting {config_name}...")
        config_results = []
        
        for i, prompt_data in enumerate(dataset, 1):
            instruction = prompt_data['instruction']
            reference = prompt_data.get('reference', '')
            skills = prompt_data.get('skills', [])
            
            response = await run_ensemble(config_name, instruction)
            
            config_results.append({
                'instruction': instruction,
                'response': response,
                'reference': reference,
                'skills': skills
            })
            
            if i % 10 == 0:
                print(f"  Completed {i}/{len(dataset)}")
        
        results['results'][config_name] = config_results
    
    # Score with Opus judge
    print("\nScoring with Opus judge...")
    judge = QualityJudge(judge_model="opus")
    
    for config_name, config_results in results['results'].items():
        print(f"  Scoring {config_name}...")
        
        for result in config_results:
            score = await judge.score_response(
                prompt=result['instruction'],
                response=result['response'],
                expected_answer=result['reference']
            )
            result['judge_score'] = score
    
    # Calculate per-skill performance
    for config_name in configs:
        skill_scores = {skill: [] for skill in FLASK_SKILLS}
        
        for result in results['results'][config_name]:
            score = result['judge_score']['total']
            for skill in result['skills']:
                if skill in skill_scores:
                    skill_scores[skill].append(score)
        
        results['results'][config_name]['skill_breakdown'] = {
            skill: sum(scores) / len(scores) if scores else 0
            for skill, scores in skill_scores.items()
        }
    
    # Save results
    output_file = output_file or "results/flask_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("FLASK SKILL BREAKDOWN")
    print("="*60)
    
    for config_name in configs:
        breakdown = results['results'][config_name].get('skill_breakdown', {})
        print(f"\n{config_name}:")
        for skill, score in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
            print(f"  {skill:25s} {score:.1f}/100")
    
    print("="*60 + "\n")
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python benchmark/flask_integration.py <config1> <config2> ...")
        print("\nOptions:")
        print("  --sample N    Test N prompts per skill (default: 20)")
        print("\nExample:")
        print("  python benchmark/flask_integration.py ultra-cheap high-end-reasoning --sample 20")
        sys.exit(1)
    
    # Parse args
    configs = []
    sample_per_skill = 20
    
    for arg in sys.argv[1:]:
        if arg == '--sample':
            continue
        elif sys.argv[sys.argv.index(arg) - 1] == '--sample':
            sample_per_skill = int(arg)
        else:
            configs.append(arg)
    
    if not configs:
        print("Error: No configs specified")
        sys.exit(1)
    
    asyncio.run(run_flask_benchmark(
        configs=configs,
        sample_per_skill=sample_per_skill
    ))
```

### Usage

```bash
# Sample test (20 prompts per skill = ~240 total)
python benchmark/flask_integration.py \
  ultra-cheap high-end-reasoning \
  --sample 20
```

### Cost Estimate

**Sample (240 prompts, 2 configs):**

| Item | Calculation | Cost |
|------|-------------|------|
| Benchmark | 240 × $0.0007 × 2 | $0.34 |
| Judge scoring | 240 × 2 × $0.005 | $2.40 |
| **TOTAL** | - | **$2.74** |

**Time:** ~90 minutes

### Expected Learnings

- Which skills benefit most from ensemble?
- Fine-grained capability comparison
- Skill-specific recommendations (when to use ensemble)
- Comparison to Wang et al.'s FLASK results

---

## Complete Budget Summary

| Phase | Description | Cost | Time | Priority |
|-------|-------------|------|------|----------|
| **Phase 1** | High-end models (current prompts) | $55.62 | 90 min | HIGH |
| **Phase 2** | MT-Bench (multi-turn) | $2.74 | 30 min | HIGH |
| **Phase 3** | AlpacaEval sample | $1.71 | 60 min | MEDIUM |
| **Phase 4** | FLASK sample | $2.74 | 90 min | LOW |
| **Buffer** | Unexpected costs | $12.71 | - | - |
| **TOTAL** | All phases | **$75.52** | **4.5 hrs** | - |

---

## Recommended Execution Order

### Option A: Comprehensive (all phases)
```bash
# 1. High-end models on current benchmark
python benchmark/run.py \
  --output results/premium_tier.json \
  --recipes high-end-reasoning mixed-capability same-model-premium

python benchmark/analyze_diversity.py results/premium_tier.json

# 2. MT-Bench
python benchmark/mtbench_integration.py \
  ultra-cheap high-end-reasoning same-model-baseline

# 3. AlpacaEval sample
python benchmark/alpacaeval_integration.py \
  ultra-cheap high-end-reasoning same-model-baseline \
  --sample 100

# 4. FLASK sample
python benchmark/flask_integration.py \
  ultra-cheap high-end-reasoning \
  --sample 20
```

**Total: $75.52, 4.5 hours**

### Option B: High-priority only (Phases 1-2)
```bash
# Just premium models + MT-Bench
# Total: $58.36, 2 hours
```

### Option C: Academic benchmarks only (Phases 2-4)
```bash
# Skip premium models, focus on Wang et al.'s benchmarks
# Total: $7.19, 3 hours
```

---

## Expected Research Questions Answered

1. **Does diversity matter at premium tier?**
   - Phase 1: Test opus+sonnet+nova-premier vs 3x opus

2. **Does diversity matter on instruction-following?**
   - Phase 3: AlpacaEval results for diverse vs same-model

3. **Can we replicate Wang et al.'s findings?**
   - Phases 2-4: Direct comparison on their benchmarks

4. **What's the cost/quality sweet spot?**
   - Phase 1: Map full frontier from ultra-cheap to premium

5. **Which tasks benefit from ensemble?**
   - Phase 4: FLASK skill breakdown

6. **Is multi-turn coherence maintained?**
   - Phase 2: MT-Bench conversation testing

---

## Implementation Checklist

### Phase 1: High-End Models
- [ ] Add 3 new recipes to `moa/models.py`
- [ ] Update baseline list in `benchmark/run.py`
- [ ] Run benchmark with `--recipes` flag
- [ ] Analyze diversity at premium tier
- [ ] Document cost/quality results

### Phase 2: MT-Bench
- [ ] Create `benchmark/mtbench_integration.py`
- [ ] Implement multi-turn conversation handling
- [ ] Test on 80 questions × 2 turns
- [ ] Score with Opus judge
- [ ] Create analysis script for turn-by-turn performance

### Phase 3: AlpacaEval
- [ ] Create `benchmark/alpacaeval_integration.py`
- [ ] Implement stratified sampling (100 prompts)
- [ ] Run selected configs
- [ ] Calculate win rates
- [ ] Compare to Wang et al.'s 65.1% baseline

### Phase 4: FLASK
- [ ] Create `benchmark/flask_integration.py`
- [ ] Implement per-skill sampling
- [ ] Score across 12 skill dimensions
- [ ] Create skill heatmap visualization
- [ ] Identify which skills benefit from ensemble

---

## Success Metrics

### Phase 1 Success
- [ ] Premium ensemble beats standalone Opus by ≥3 points
- [ ] Statistical significance (p<0.05) for diversity benefit at premium tier
- [ ] Cost/quality curve documented

### Phase 2 Success
- [ ] Multi-turn context maintained across turns
- [ ] Turn 2 responses reference Turn 1 appropriately
- [ ] Comparison to Wang et al.'s MT-Bench scores available

### Phase 3 Success
- [ ] Win rate calculated (% responses scoring ≥70/100)
- [ ] Diverse ensemble outperforms same-model (p<0.05)
- [ ] Comparison to Wang et al.'s 65.1% documented

### Phase 4 Success
- [ ] Per-skill scores calculated for all 12 skills
- [ ] Identify top 3 skills where ensemble helps most
- [ ] Identify skills where ensemble doesn't help

---

## Risk Assessment

### Technical Risks

1. **Dataset availability** (MEDIUM)
   - AlpacaEval/MT-Bench datasets may have moved
   - Mitigation: Verify URLs before starting

2. **Judge consistency** (MEDIUM)
   - Using Opus instead of GPT-4 may give different scores
   - Mitigation: Document judge model clearly, focus on relative comparisons

3. **Multi-turn context limits** (LOW)
   - Long conversations may exceed context windows
   - Mitigation: MT-Bench is designed for this, shouldn't be issue

### Cost Risks

1. **Premium models expensive** (HIGH)
   - Phase 1 is $55.62 (74% of total budget)
   - Mitigation: Can test fewer configs or fewer prompts

2. **Judge scoring adds up** (MEDIUM)
   - Judge costs ~30-40% of total
   - Mitigation: Can skip judge on some phases, use manual spot-checks

3. **Full AlpacaEval too expensive** (MEDIUM)
   - 805 prompts would be $13.77
   - Mitigation: Using 100-prompt sample ($1.71)

---

## Open Questions

1. **Should we test on all 805 AlpacaEval prompts?**
   - Pro: Most comparable to Wang et al.
   - Con: 8× more expensive than sample
   - Decision: Start with sample, expand if budget allows

2. **Should we use GPT-4 judge or Opus?**
   - Pro (GPT-4): Direct comparison to Wang et al.
   - Con (GPT-4): Need OpenAI API key
   - Decision: Use Opus for consistency with current implementation

3. **Should we test more than 3 configs on academic benchmarks?**
   - Pro: More data points
   - Con: Higher cost
   - Decision: Start with 3 (ultra-cheap, high-end, same-model), expand if interesting

4. **Should we implement FLASK first or last?**
   - Largest dataset, most detailed breakdown
   - But least comparable to Wang et al. (they used it as supplementary)
   - Decision: Save for Phase 4 (low priority)

---

## Next Steps

1. **Immediate:** Choose execution option (A, B, or C)
2. **Short-term:** Implement Phase 1 (high-end models)
3. **Medium-term:** Add MT-Bench integration if Phase 1 shows promising results
4. **Long-term:** Consider full AlpacaEval run if sample shows diversity benefit

---

**Status:** Ready to implement  
**Blockers:** None (AWS_BEARER_TOKEN_BEDROCK already set)  
**Decision needed:** Which execution option to pursue?
