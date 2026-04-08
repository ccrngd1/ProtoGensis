# Quick Wins Implementation Plan

**Project:** ensemble-moa-bedrock-guide - Methodology Improvements  
**Date:** April 3, 2026  
**Timeline:** 3-4 days  
**Estimated Cost:** $3.50 in API calls  
**Goal:** Address critical methodology gaps with high-impact, low-effort improvements  

---

## Overview

This plan implements the three "Quick Win" improvements identified in METHODOLOGY_REVIEW.md:

1. ✅ **Judge Model Scoring** - Automated quality assessment using Opus
2. ✅ **Expand to 50 Prompts** - Increase sample size for statistical validity
3. ✅ **Same-Model Ensemble Test** - Validate diversity hypothesis

**Why these first?**
- High impact on methodology rigor
- Low implementation cost (1-3 days each)
- Minimal API budget ($0.50-$2.50 per task)
- Unblocks statistical analysis

---

## Prerequisites

### Environment Setup

```bash
# Verify bearer token is set
echo $AWS_BEARER_TOKEN_BEDROCK

# Install dependencies (if not already)
pip install requests scipy numpy

# Verify current implementation works
python test_auth.py
python benchmark/run.py --limit 3  # Quick smoke test
```

### Baseline Metrics

Before starting, capture current state:

```bash
# Run current benchmark (20 prompts)
python benchmark/run.py --output results/baseline_20prompts.json

# Note the outputs:
# - results/baseline_20prompts.json (raw results)
# - Cost: ~$0.50-1.00 for full run
# - Time: ~5-10 minutes
```

---

## Task 1: Judge Model Scoring

**Goal:** Replace manual quality estimates with automated Opus-based scoring  
**Effort:** 1 day  
**Cost:** ~$0.50 for 100 responses  

### Implementation Steps

#### Step 1.1: Create Judge Module

**File:** `moa/judge.py`

```python
"""
Automated quality assessment using Opus as judge model.
"""

import asyncio
from typing import Dict, List
from dataclasses import dataclass

from .bedrock_client import BedrockClient
from .models import get_model_pricing


@dataclass
class JudgeScore:
    """Quality score from judge model."""
    
    correctness: float  # 0-40 points
    completeness: float  # 0-30 points
    clarity: float  # 0-30 points
    total: float  # 0-100 points
    justification: str
    

class QualityJudge:
    """
    Automated quality judge using Opus.
    
    Scores responses on:
    - Correctness (40%): Is the answer accurate?
    - Completeness (30%): Does it address all parts?
    - Clarity (30%): Is it well-explained?
    """
    
    def __init__(self, judge_model: str = "opus"):
        """Initialize judge with specified model."""
        self.judge_model = judge_model
        self.client = BedrockClient()
        
    async def score_response(
        self,
        prompt: str,
        response: str,
        expected_answer: str = None
    ) -> JudgeScore:
        """
        Score a single response.
        
        Args:
            prompt: Original prompt
            response: Model response to score
            expected_answer: Optional expected answer for reference
            
        Returns:
            JudgeScore with breakdown
        """
        judge_prompt = self._build_judge_prompt(prompt, response, expected_answer)
        
        pricing = get_model_pricing(self.judge_model)
        result = await self.client.invoke_model(
            model_id=pricing.model_id,
            prompt=judge_prompt,
            max_tokens=500,
            temperature=0.3  # Lower temp for consistent judging
        )
        
        # Parse judge response
        score = self._parse_judge_response(result["response"])
        return score
    
    def _build_judge_prompt(
        self,
        prompt: str,
        response: str,
        expected_answer: str = None
    ) -> str:
        """Build prompt for judge model."""
        
        base_prompt = f"""You are an expert judge evaluating the quality of an AI response.

Original Prompt:
{prompt}

Response to Evaluate:
{response}
"""
        
        if expected_answer:
            base_prompt += f"""
Expected Answer (for reference):
{expected_answer}
"""
        
        base_prompt += """

Score this response on three dimensions:

1. CORRECTNESS (0-40 points)
   - Is the information accurate?
   - Are there factual errors or hallucinations?
   - Does it address the right question?

2. COMPLETENESS (0-30 points)
   - Does it cover all parts of the prompt?
   - Are there missing elements?
   - Is sufficient detail provided?

3. CLARITY (0-30 points)
   - Is it well-structured and easy to follow?
   - Is the explanation clear?
   - Is the language appropriate?

Provide your evaluation in this exact format:

CORRECTNESS: [score]/40
[brief justification]

COMPLETENESS: [score]/30
[brief justification]

CLARITY: [score]/30
[brief justification]

TOTAL: [sum]/100

SUMMARY: [1-2 sentence overall assessment]
"""
        return base_prompt
    
    def _parse_judge_response(self, response: str) -> JudgeScore:
        """Parse judge model output into structured score."""
        import re
        
        # Extract scores using regex
        correctness_match = re.search(r'CORRECTNESS:\s*(\d+(?:\.\d+)?)/40', response)
        completeness_match = re.search(r'COMPLETENESS:\s*(\d+(?:\.\d+)?)/30', response)
        clarity_match = re.search(r'CLARITY:\s*(\d+(?:\.\d+)?)/30', response)
        total_match = re.search(r'TOTAL:\s*(\d+(?:\.\d+)?)/100', response)
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?:\n|$)', response)
        
        correctness = float(correctness_match.group(1)) if correctness_match else 0.0
        completeness = float(completeness_match.group(1)) if completeness_match else 0.0
        clarity = float(clarity_match.group(1)) if clarity_match else 0.0
        total = float(total_match.group(1)) if total_match else correctness + completeness + clarity
        summary = summary_match.group(1).strip() if summary_match else "No summary provided"
        
        return JudgeScore(
            correctness=correctness,
            completeness=completeness,
            clarity=clarity,
            total=total,
            justification=summary
        )
    
    async def score_batch(
        self,
        evaluations: List[Dict]
    ) -> List[JudgeScore]:
        """
        Score multiple responses in parallel.
        
        Args:
            evaluations: List of dicts with 'prompt', 'response', 'expected_answer'
            
        Returns:
            List of JudgeScore objects
        """
        tasks = [
            self.score_response(
                prompt=eval_dict['prompt'],
                response=eval_dict['response'],
                expected_answer=eval_dict.get('expected_answer')
            )
            for eval_dict in evaluations
        ]
        
        return await asyncio.gather(*tasks)
```

#### Step 1.2: Update Benchmark Runner

**File:** `benchmark/run.py`

Add judge scoring to benchmark:

```python
# At top of file
from moa.judge import QualityJudge

# In run_benchmark_suite(), after running all configurations:

async def run_benchmark_suite(
    prompts: List[Dict],
    limit: int | None = None,
    enable_judge: bool = True  # NEW parameter
) -> Dict:
    """Run full benchmark suite with optional judge scoring."""
    
    # ... existing code to run benchmarks ...
    
    # NEW: Score all responses with judge model
    if enable_judge:
        print("\n" + "="*60)
        print("SCORING RESPONSES WITH JUDGE MODEL")
        print("="*60)
        
        judge = QualityJudge(judge_model="opus")
        
        # Score single models
        for model_key, result_list in results["single_models"].items():
            print(f"\nScoring {model_key}...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i]['response'],
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]
            
            scores = await judge.score_batch(evaluations)
            
            # Add scores to results
            for i, score in enumerate(scores):
                if i < len(result_list) and 'response' in result_list[i]:
                    result_list[i]['judge_score'] = {
                        'correctness': score.correctness,
                        'completeness': score.completeness,
                        'clarity': score.clarity,
                        'total': score.total,
                        'justification': score.justification
                    }
        
        # Score ensembles
        for recipe, result_list in results["ensembles"].items():
            print(f"\nScoring {recipe} ensemble...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i]['response'],
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]
            
            scores = await judge.score_batch(evaluations)
            
            for i, score in enumerate(scores):
                if i < len(result_list) and 'response' in result_list[i]:
                    result_list[i]['judge_score'] = {
                        'correctness': score.correctness,
                        'completeness': score.completeness,
                        'clarity': score.clarity,
                        'total': score.total,
                        'justification': score.justification
                    }
        
        # Score baselines
        for model_key, result_list in results["baselines"].items():
            print(f"\nScoring {model_key} baseline...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i]['response'],
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]
            
            scores = await judge.score_batch(evaluations)
            
            for i, score in enumerate(scores):
                if i < len(result_list) and 'response' in result_list[i]:
                    result_list[i]['judge_score'] = {
                        'correctness': score.correctness,
                        'completeness': score.completeness,
                        'clarity': score.clarity,
                        'total': score.total,
                        'justification': score.justification
                    }
    
    return results
```

#### Step 1.3: Update Summary Stats

**File:** `benchmark/run.py`

Update `calculate_summary_stats()` to include quality scores:

```python
def calculate_summary_stats(results: Dict) -> Dict:
    """Calculate summary statistics including quality scores."""
    summary = {
        "single_models": {},
        "ensembles": {},
        "baselines": {}
    }
    
    def calc_stats(result_list: List[Dict]) -> Dict:
        costs = [r['cost'] for r in result_list if 'cost' in r]
        latencies = [r['latency_ms'] for r in result_list if 'latency_ms' in r]
        
        # NEW: Quality scores
        quality_scores = [
            r['judge_score']['total'] 
            for r in result_list 
            if 'judge_score' in r
        ]
        
        stats = {
            "avg_cost": round(sum(costs) / len(costs), 6) if costs else 0,
            "total_cost": round(sum(costs), 6) if costs else 0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "num_runs": len(result_list)
        }
        
        # Add quality stats if available
        if quality_scores:
            stats["avg_quality"] = round(sum(quality_scores) / len(quality_scores), 2)
            stats["min_quality"] = round(min(quality_scores), 2)
            stats["max_quality"] = round(max(quality_scores), 2)
            
            # Calculate standard deviation
            import numpy as np
            stats["quality_std"] = round(np.std(quality_scores), 2)
        
        return stats
    
    # Calculate for each category
    for category in ['single_models', 'ensembles', 'baselines']:
        for key, result_list in results.get(category, {}).items():
            summary[category][key] = calc_stats(result_list)
    
    return summary
```

#### Step 1.4: Update CLI

**File:** `benchmark/run.py`

Add judge flag to CLI:

```python
def main():
    """Main benchmark execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run MoA benchmarks")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=str, default="results/benchmark_results.json")
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Disable judge model scoring (faster, cheaper)"
    )
    
    args = parser.parse_args()
    
    prompts = load_prompts()
    
    results = asyncio.run(run_benchmark_suite(
        prompts=prompts,
        limit=args.limit,
        enable_judge=not args.no_judge  # Enable by default
    ))
    
    # ... rest of main() ...
    
    # Print quality stats in summary
    if not args.no_judge:
        print("\n" + "="*60)
        print("QUALITY SCORES (Judge Model: Opus)")
        print("="*60)
        
        print("\nSingle Models (avg quality /100):")
        for model, stats in summary['single_models'].items():
            if 'avg_quality' in stats:
                print(f"  {model:20s} {stats['avg_quality']:.1f} ± {stats['quality_std']:.1f}")
        
        print("\nEnsembles (avg quality /100):")
        for recipe, stats in summary['ensembles'].items():
            if 'avg_quality' in stats:
                print(f"  {recipe:20s} {stats['avg_quality']:.1f} ± {stats['quality_std']:.1f}")
        
        print("\nBaselines (avg quality /100):")
        for model, stats in summary['baselines'].items():
            if 'avg_quality' in stats:
                print(f"  {model:20s} {stats['avg_quality']:.1f} ± {stats['quality_std']:.1f}")
```

### Testing

```bash
# Test judge on single prompt
python -c "
import asyncio
from moa.judge import QualityJudge

async def test():
    judge = QualityJudge()
    score = await judge.score_response(
        prompt='What is 2+2?',
        response='2+2 equals 4.',
        expected_answer='4'
    )
    print(f'Score: {score.total}/100')
    print(f'Justification: {score.justification}')

asyncio.run(test())
"

# Test full benchmark with judge (limited)
python benchmark/run.py --limit 3 --output results/judge_test.json

# Verify output contains judge_score fields
cat results/judge_test.json | grep -A 5 "judge_score"
```

### Cost Estimate

```
Judge model: Opus
Cost per scoring: ~$0.005 (500 tokens @ $0.015/1K output)

Configurations to score:
- 1 single model (Nova Lite)
- 3 ensembles (ultra-cheap, code-gen, reasoning)
- 3 baselines (Nova Lite, Haiku, Sonnet)
= 7 configurations

For 20 prompts: 7 × 20 × $0.005 = $0.70
For 50 prompts: 7 × 50 × $0.005 = $1.75
```

**Task 1 Total Cost:** ~$0.70 (20 prompts) or ~$1.75 (50 prompts)

---

## Task 2: Expand to 50 Prompts

**Goal:** Increase sample size from 20 → 50 for statistical validity  
**Effort:** 1 day  
**Cost:** ~$2.50 for benchmark run  

### Implementation Steps

#### Step 2.1: Add 30 New Prompts

**File:** `benchmark/prompts.json`

Add prompts to reach these targets:

| Category | Current | Target | Add |
|----------|---------|--------|-----|
| Reasoning | 4 | 8 | +4 |
| Code | 4 | 8 | +4 |
| Creative | 4 | 8 | +4 |
| Factual | 3 | 8 | +5 |
| Analysis | 3 | 8 | +5 |
| Multi-step | 2 | 6 | +4 |
| Edge-cases | 1 | 4 | +3 |
| **NEW: Adversarial** | 0 | 5 | +5 |

**New adversarial category** - prompts where cheap models typically fail:

```json
{
  "id": "adversarial-1",
  "category": "adversarial",
  "difficulty": "hard",
  "prompt": "What is 847 multiplied by 923? Show your work step by step.",
  "expected_answer": "781,481 (tests arithmetic accuracy)"
},
{
  "id": "adversarial-2",
  "category": "adversarial",
  "difficulty": "hard",
  "prompt": "What was the GDP of Lesotho in 1991 (in USD)? Provide only if you have verified data.",
  "expected_answer": "Tests hallucination resistance - model should admit uncertainty if unsure"
},
{
  "id": "adversarial-3",
  "category": "adversarial",
  "difficulty": "medium",
  "prompt": "If all Bloops are Razzles, and all Razzles are Lazzles, are all Bloops Lazzles? Explain your reasoning using formal logic.",
  "expected_answer": "Yes, by transitivity. Uses nonsense words to test pure logic."
},
{
  "id": "adversarial-4",
  "category": "adversarial",
  "difficulty": "hard",
  "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?",
  "expected_answer": "$0.05 (tests resistance to intuitive but wrong answer of $0.10)"
},
{
  "id": "adversarial-5",
  "category": "adversarial",
  "difficulty": "hard",
  "prompt": "Translate this to French: 'The old man the boat.' Is this sentence grammatically correct in English? Explain.",
  "expected_answer": "Garden path sentence - 'man' is a verb. Tests parsing ambiguity."
}
```

**Full prompt set structure:**

```json
{
  "prompts": [
    // ... existing 20 prompts ...
    
    // NEW: 4 more reasoning prompts
    {
      "id": "reasoning-4",
      "category": "reasoning",
      "difficulty": "hard",
      "prompt": "You have 12 balls, one of which is slightly heavier or lighter than the others. You have a balance scale and can use it 3 times. How do you identify the odd ball and determine if it's heavier or lighter?",
      "expected_answer": "Divide into groups of 4-4-4, systematic elimination approach"
    },
    {
      "id": "reasoning-5",
      "category": "reasoning",
      "difficulty": "medium",
      "prompt": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
      "expected_answer": "5 minutes (rate problem, not 100 minutes)"
    },
    {
      "id": "reasoning-6",
      "category": "reasoning",
      "difficulty": "hard",
      "prompt": "A snail is at the bottom of a 30-foot well. Each day it climbs up 3 feet, but each night it slides back 2 feet. How many days does it take to reach the top?",
      "expected_answer": "28 days (on day 28 it reaches the top before sliding back)"
    },
    {
      "id": "reasoning-7",
      "category": "reasoning",
      "difficulty": "medium",
      "prompt": "In a country where everyone wants a boy, each family continues having children until they have a boy, then stops. What is the expected ratio of boys to girls?",
      "expected_answer": "1:1 (probability/expectation calculation)"
    },
    
    // NEW: 4 more code prompts
    {
      "id": "code-5",
      "category": "code",
      "difficulty": "hard",
      "prompt": "Implement a thread-safe LRU cache in Python that supports concurrent read and write operations. Explain your concurrency strategy.",
      "expected_answer": "Uses locks/RLock, OrderedDict or custom linked list, thread safety considerations"
    },
    {
      "id": "code-6",
      "category": "code",
      "difficulty": "medium",
      "prompt": "Write a function to detect if a linked list has a cycle. What's the time and space complexity?",
      "expected_answer": "Floyd's cycle detection (tortoise and hare), O(n) time, O(1) space"
    },
    {
      "id": "code-7",
      "category": "code",
      "difficulty": "hard",
      "prompt": "Design a rate limiter that allows N requests per user per minute using Redis. Show the Redis commands and explain the race condition handling.",
      "expected_answer": "Sliding window or token bucket, MULTI/EXEC for atomicity, Lua scripts"
    },
    {
      "id": "code-8",
      "category": "code",
      "difficulty": "easy",
      "prompt": "Write a regex pattern to validate an email address. Explain what edge cases it handles and what it doesn't.",
      "expected_answer": "Basic pattern, acknowledges RFC 5322 complexity, lists limitations"
    },
    
    // NEW: 4 more creative prompts
    {
      "id": "creative-5",
      "category": "creative",
      "difficulty": "medium",
      "prompt": "Write a 280-character tweet announcing a breakthrough in quantum computing that's exciting but accurate. Target audience: tech-savvy but not quantum physicists.",
      "expected_answer": "Concise, accurate, engaging, fits Twitter limit"
    },
    {
      "id": "creative-6",
      "category": "creative",
      "difficulty": "hard",
      "prompt": "Come up with a metaphor to explain neural network training to a 10-year-old. Make it memorable and accurate.",
      "expected_answer": "Age-appropriate, captures key concepts (learning from examples, adjusting)"
    },
    {
      "id": "creative-7",
      "category": "creative",
      "difficulty": "medium",
      "prompt": "Write an email subject line for a product recall that is clear, urgent, but not panic-inducing. Product: smart home cameras, issue: potential security vulnerability.",
      "expected_answer": "Clear about issue, action-oriented, appropriately urgent"
    },
    {
      "id": "creative-8",
      "category": "creative",
      "difficulty": "hard",
      "prompt": "Create a 4-line rhyming poem about distributed systems that captures the CAP theorem. AABB rhyme scheme.",
      "expected_answer": "Rhymes, technically accurate, captures CAP trade-offs"
    },
    
    // NEW: 5 more factual prompts
    {
      "id": "factual-4",
      "category": "factual",
      "difficulty": "easy",
      "prompt": "What is the difference between Docker and a virtual machine? Why would you choose one over the other?",
      "expected_answer": "Containers vs VMs, overhead, use cases, isolation levels"
    },
    {
      "id": "factual-5",
      "category": "factual",
      "difficulty": "medium",
      "prompt": "Explain eventual consistency in distributed databases. Give a real-world example where it's acceptable vs unacceptable.",
      "expected_answer": "Definition, trade-offs, examples like social media feeds (ok) vs banking (not ok)"
    },
    {
      "id": "factual-6",
      "category": "factual",
      "difficulty": "hard",
      "prompt": "What is the Byzantine Generals Problem? How does blockchain solve it?",
      "expected_answer": "Consensus in presence of malicious actors, proof-of-work/stake approaches"
    },
    {
      "id": "factual-7",
      "category": "factual",
      "difficulty": "easy",
      "prompt": "What are the main differences between REST and GraphQL APIs?",
      "expected_answer": "Resource-based vs query-based, over/under-fetching, flexibility vs simplicity"
    },
    {
      "id": "factual-8",
      "category": "factual",
      "difficulty": "medium",
      "prompt": "Explain the SOLID principles in software engineering. Give a brief example of violating each one.",
      "expected_answer": "5 principles with examples: SRP, OCP, LSP, ISP, DIP"
    },
    
    // NEW: 5 more analysis prompts
    {
      "id": "analysis-4",
      "category": "analysis",
      "difficulty": "medium",
      "prompt": "A mobile app has a 60% day-1 retention rate and 20% day-7 retention. Is this good? What additional metrics would you want to see?",
      "expected_answer": "Context-dependent, cohort analysis, engagement depth, industry benchmarks"
    },
    {
      "id": "analysis-5",
      "category": "analysis",
      "difficulty": "hard",
      "prompt": "Your API latency p50 is 100ms, p95 is 500ms, and p99 is 5000ms. What does this tell you about your system? Where should you investigate?",
      "expected_answer": "Long tail problem, outlier analysis, potential causes (cold starts, timeouts, retries)"
    },
    {
      "id": "analysis-6",
      "category": "analysis",
      "difficulty": "hard",
      "prompt": "You're deciding between building in-house vs buying a vendor solution for authentication. What factors would you consider?",
      "expected_answer": "Build vs buy trade-offs: cost, time, customization, security expertise, maintenance"
    },
    {
      "id": "analysis-7",
      "category": "analysis",
      "difficulty": "medium",
      "prompt": "A company wants to adopt microservices. They have 5 engineers and a Django monolith. Should they? Why or why not?",
      "expected_answer": "Probably not - team size, operational complexity, premature optimization"
    },
    {
      "id": "analysis-8",
      "category": "analysis",
      "difficulty": "hard",
      "prompt": "Analyze the trade-offs of using serverless (AWS Lambda) vs containers (ECS) for a data processing pipeline that runs every hour.",
      "expected_answer": "Cost (pay per invoke), cold starts, execution time limits, state management"
    },
    
    // NEW: 4 more multi-step prompts
    {
      "id": "multistep-3",
      "category": "multistep",
      "difficulty": "hard",
      "prompt": "Design a global content delivery system for video streaming (think Netflix scale). Cover: storage, CDN strategy, encoding pipeline, and cost optimization.",
      "expected_answer": "Multi-region storage, edge caching, adaptive bitrate, encoding formats, costs"
    },
    {
      "id": "multistep-4",
      "category": "multistep",
      "difficulty": "hard",
      "prompt": "You need to build a search feature for a 10TB dataset updated daily. Design the indexing strategy, query execution, and update pipeline. Budget: $5K/month.",
      "expected_answer": "Elasticsearch/OpenSearch, incremental indexing, replication, sharding, cost breakdown"
    },
    {
      "id": "multistep-5",
      "category": "multistep",
      "difficulty": "hard",
      "prompt": "Design a system for A/B testing that can handle 1M DAU across mobile and web. Cover: assignment logic, metrics collection, statistical significance calculation.",
      "expected_answer": "User bucketing, event tracking, analytics pipeline, statistical tests, feature flags"
    },
    {
      "id": "multistep-6",
      "category": "multistep",
      "difficulty": "hard",
      "prompt": "Build a monitoring and alerting system for a microservices architecture (20 services). What do you monitor? How do you avoid alert fatigue?",
      "expected_answer": "Golden signals (latency, traffic, errors, saturation), SLOs, alert tuning, on-call rotation"
    },
    
    // NEW: 3 more edge case prompts
    {
      "id": "edge-case-2",
      "category": "edge-cases",
      "difficulty": "medium",
      "prompt": "Your sorting function works on all test cases except when the array has duplicate values. What's likely wrong?",
      "expected_answer": "Comparison function issues, stable vs unstable sort, equality handling"
    },
    {
      "id": "edge-case-3",
      "category": "edge-cases",
      "difficulty": "hard",
      "prompt": "A user reports your mobile app crashes only when they change time zones while using it. What are potential causes?",
      "expected_answer": "Timezone conversion, Date object handling, server time vs local time, DST transitions"
    },
    {
      "id": "edge-case-4",
      "category": "edge-cases",
      "difficulty": "medium",
      "prompt": "Your string validation passes all ASCII input but fails on emoji. Why might this happen?",
      "expected_answer": "Unicode handling, UTF-8/UTF-16, character vs byte length, regex character classes"
    },
    
    // NEW: 5 adversarial prompts (listed above)
    // ... (insert the 5 adversarial prompts here)
  ]
}
```

#### Step 2.2: Verify Prompt Quality

Create a validation script:

**File:** `benchmark/validate_prompts.py`

```python
#!/usr/bin/env python3
"""Validate prompt set completeness and quality."""

import json
from collections import Counter

def validate_prompts(prompts_file="benchmark/prompts.json"):
    """Validate prompt set."""
    
    with open(prompts_file) as f:
        data = json.load(f)
    
    prompts = data['prompts']
    
    print("="*60)
    print("PROMPT SET VALIDATION")
    print("="*60)
    
    # Count by category
    categories = Counter(p['category'] for p in prompts)
    print("\nPrompts by Category:")
    for category, count in sorted(categories.items()):
        print(f"  {category:15s} {count:3d} prompts")
    
    print(f"\nTotal: {len(prompts)} prompts")
    
    # Count by difficulty
    difficulties = Counter(p['difficulty'] for p in prompts)
    print("\nPrompts by Difficulty:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff:10s} {count:3d} prompts")
    
    # Check for missing expected_answer
    missing_answers = [p['id'] for p in prompts if 'expected_answer' not in p]
    if missing_answers:
        print(f"\n⚠️  Warning: {len(missing_answers)} prompts missing expected_answer:")
        for pid in missing_answers:
            print(f"    - {pid}")
    else:
        print("\n✅ All prompts have expected answers")
    
    # Check for duplicate IDs
    ids = [p['id'] for p in prompts]
    duplicates = [pid for pid in ids if ids.count(pid) > 1]
    if duplicates:
        print(f"\n❌ Error: Duplicate IDs found: {set(duplicates)}")
    else:
        print("✅ All prompt IDs are unique")
    
    # Category balance check
    target = 50
    balanced = all(count >= 4 for count in categories.values())
    if balanced:
        print("✅ Categories are reasonably balanced (all ≥4 prompts)")
    else:
        print("⚠️  Warning: Some categories have <4 prompts")
    
    print("\n" + "="*60)
    
    return len(prompts) >= target

if __name__ == "__main__":
    is_valid = validate_prompts()
    exit(0 if is_valid else 1)
```

Run validation:

```bash
python benchmark/validate_prompts.py
```

### Testing

```bash
# Test with new prompt set (limited)
python benchmark/run.py --limit 10 --output results/expanded_test.json

# Full run with 50 prompts
python benchmark/run.py --output results/benchmark_50prompts.json

# Compare to baseline
python -c "
import json

with open('results/baseline_20prompts.json') as f:
    baseline = json.load(f)

with open('results/benchmark_50prompts.json') as f:
    expanded = json.load(f)

print(f'Baseline prompts: {baseline[\"metadata\"][\"num_prompts\"]}')
print(f'Expanded prompts: {expanded[\"metadata\"][\"num_prompts\"]}')

# Compare average costs (should be similar per-prompt)
"
```

### Cost Estimate

```
Configurations: 7 (1 single + 3 ensemble + 3 baseline)
Prompts: 50
Average cost per (config × prompt): $0.0007

Benchmark cost: 7 × 50 × $0.0007 = $2.45
Judge scoring: 7 × 50 × $0.005 = $1.75

Total: $4.20
```

**Task 2 Total Cost:** ~$4.20 (includes judge scoring)

---

## Task 3: Same-Model Ensemble Test

**Goal:** Test if diversity matters or if it's just the aggregation step  
**Effort:** 0.5 days  
**Cost:** ~$0.50  

### Implementation Steps

#### Step 3.1: Add Same-Model Configuration

**File:** `moa/models.py`

Add new recipe:

```python
RECIPES = {
    # ... existing recipes ...
    
    "same-model-baseline": {
        "name": "Same-Model Ensemble (Ablation)",
        "description": "3x Nova Lite proposers + aggregator (tests if diversity matters)",
        "proposers": ["nova-lite", "nova-lite", "nova-lite"],  # Same model 3x
        "aggregator": "nova-pro",
        "layers": 2,
        "use_case": "Ablation study - tests diversity hypothesis",
    },
    
    "same-model-cheap": {
        "name": "Same-Model Ensemble Ultra-Cheap",
        "description": "3x Nova Lite proposers + Nova Lite aggregator",
        "proposers": ["nova-lite", "nova-lite", "nova-lite"],
        "aggregator": "nova-lite",
        "layers": 2,
        "use_case": "Ablation study - minimum cost same-model test",
    },
}
```

#### Step 3.2: Update Benchmark to Include Ablation

**File:** `benchmark/run.py`

Add to ensemble test list:

```python
ensemble_recipes = [
    "ultra-cheap",
    "code-generation",
    "reasoning",
    "same-model-baseline",  # NEW: Ablation test
]
```

#### Step 3.3: Create Analysis Script

**File:** `benchmark/analyze_diversity.py`

```python
#!/usr/bin/env python3
"""
Analyze diversity benefit by comparing diverse vs same-model ensembles.
"""

import json
import sys
from pathlib import Path

def analyze_diversity(results_file: str):
    """Compare diverse ensemble vs same-model ensemble."""
    
    with open(results_file) as f:
        results = json.load(f)
    
    # Get diverse ensemble (ultra-cheap)
    diverse = results['ensembles']['ultra-cheap']
    
    # Get same-model ensemble
    same_model = results['ensembles']['same-model-baseline']
    
    # Extract quality scores
    diverse_scores = [
        r['judge_score']['total'] 
        for r in diverse 
        if 'judge_score' in r
    ]
    
    same_scores = [
        r['judge_score']['total'] 
        for r in same_model 
        if 'judge_score' in r
    ]
    
    if not diverse_scores or not same_scores:
        print("❌ Missing judge scores. Run with --enable-judge")
        return
    
    print("="*60)
    print("DIVERSITY ANALYSIS")
    print("="*60)
    
    import numpy as np
    
    diverse_mean = np.mean(diverse_scores)
    same_mean = np.mean(same_scores)
    
    diverse_std = np.std(diverse_scores)
    same_std = np.std(same_scores)
    
    print(f"\nDiverse Ensemble (Nova Lite + Mistral + Llama):")
    print(f"  Quality: {diverse_mean:.1f} ± {diverse_std:.1f}")
    print(f"  Cost: ${results['summary']['ensembles']['ultra-cheap']['avg_cost']:.6f}")
    
    print(f"\nSame-Model Ensemble (3x Nova Lite):")
    print(f"  Quality: {same_mean:.1f} ± {same_std:.1f}")
    print(f"  Cost: ${results['summary']['ensembles']['same-model-baseline']['avg_cost']:.6f}")
    
    # Statistical test
    from scipy import stats
    t_stat, p_value = stats.ttest_ind(diverse_scores, same_scores)
    
    print(f"\nStatistical Test (t-test):")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")
    
    if p_value < 0.05:
        if diverse_mean > same_mean:
            print("  ✅ Diverse ensemble is SIGNIFICANTLY better (p<0.05)")
            print("     → Diversity DOES matter!")
        else:
            print("  ⚠️  Same-model is SIGNIFICANTLY better (p<0.05)")
            print("     → Diversity may hurt quality!")
    else:
        print("  ⚠️  No significant difference (p≥0.05)")
        print("     → Diversity may not matter, just aggregation!")
    
    # Effect size (Cohen's d)
    pooled_std = np.sqrt((diverse_std**2 + same_std**2) / 2)
    cohens_d = (diverse_mean - same_mean) / pooled_std
    
    print(f"\nEffect Size (Cohen's d): {cohens_d:.3f}")
    if abs(cohens_d) < 0.2:
        print("  → Small effect size")
    elif abs(cohens_d) < 0.5:
        print("  → Medium effect size")
    else:
        print("  → Large effect size")
    
    print("\n" + "="*60)
    
    # Per-category breakdown
    print("\nQuality by Category:")
    print(f"{'Category':15s} {'Diverse':>8s} {'Same-Model':>11s} {'Delta':>8s}")
    print("-"*50)
    
    categories = set(r['category'] for r in diverse)
    for category in sorted(categories):
        diverse_cat = [
            r['judge_score']['total'] 
            for r in diverse 
            if r['category'] == category and 'judge_score' in r
        ]
        same_cat = [
            r['judge_score']['total'] 
            for r in same_model 
            if r['category'] == category and 'judge_score' in r
        ]
        
        if diverse_cat and same_cat:
            diverse_cat_mean = np.mean(diverse_cat)
            same_cat_mean = np.mean(same_cat)
            delta = diverse_cat_mean - same_cat_mean
            
            print(f"{category:15s} {diverse_cat_mean:8.1f} {same_cat_mean:11.1f} {delta:+8.1f}")
    
    print("="*60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark/analyze_diversity.py <results_file>")
        sys.exit(1)
    
    analyze_diversity(sys.argv[1])
```

### Testing

```bash
# Run benchmark including same-model ablation
python benchmark/run.py --limit 20 --output results/diversity_test.json

# Analyze diversity benefit
python benchmark/analyze_diversity.py results/diversity_test.json
```

### Expected Output

```
============================================================
DIVERSITY ANALYSIS
============================================================

Diverse Ensemble (Nova Lite + Mistral + Llama):
  Quality: 78.3 ± 8.2
  Cost: $0.000050

Same-Model Ensemble (3x Nova Lite):
  Quality: 74.1 ± 9.1
  Cost: $0.000045

Statistical Test (t-test):
  t-statistic: 2.341
  p-value: 0.0234
  ✅ Diverse ensemble is SIGNIFICANTLY better (p<0.05)
     → Diversity DOES matter!

Effect Size (Cohen's d): 0.478
  → Medium effect size

============================================================
Quality by Category:
Category        Diverse  Same-Model    Delta
--------------------------------------------------
adversarial        72.1        65.3     +6.8
analysis           81.2        78.5     +2.7
code               79.4        76.1     +3.3
creative           77.8        73.2     +4.6
factual            76.5        75.1     +1.4
reasoning          80.1        72.9     +7.2
============================================================
```

### Cost Estimate

```
Same-model ensemble configs: 1
Prompts: 20
Cost per run: $0.00005

Benchmark cost: 1 × 20 × $0.00005 = $0.001
Judge scoring: 1 × 20 × $0.005 = $0.10

Total: ~$0.10
```

**Task 3 Total Cost:** ~$0.10

---

## Timeline

### Day 1: Judge Model Implementation
- Morning: Implement `moa/judge.py` (2-3 hours)
- Afternoon: Update `benchmark/run.py` with judge integration (2-3 hours)
- Evening: Test on small sample (1 hour)

**Deliverable:** Working judge model scoring

### Day 2: Expand Prompt Set
- Morning: Write 30 new prompts (3-4 hours)
- Afternoon: Validate prompt set, update `prompts.json` (2 hours)
- Evening: Test with expanded set (1 hour)

**Deliverable:** 50-prompt benchmark suite

### Day 3: Same-Model Ablation
- Morning: Add same-model recipes, update benchmark (2 hours)
- Afternoon: Implement diversity analysis script (2 hours)
- Evening: Run full benchmark with all improvements (2-3 hours)

**Deliverable:** Complete methodology improvements

### Day 4: Analysis & Documentation
- Morning: Analyze results, generate visualizations (2 hours)
- Afternoon: Update BLOG.md and README.md with findings (3 hours)
- Evening: Create summary report (1 hour)

**Deliverable:** Updated documentation with validated claims

---

## Success Criteria

### Task 1: Judge Model Scoring
- ✅ Judge scores all responses automatically
- ✅ Output includes correctness, completeness, clarity breakdown
- ✅ Scores are reproducible (same prompt → similar score)
- ✅ Cost per scoring ≤ $0.01

### Task 2: Expand Prompt Set
- ✅ Total prompts ≥ 50
- ✅ All categories have ≥ 4 prompts
- ✅ Includes adversarial prompts (cheap model failures)
- ✅ All prompts have expected answers

### Task 3: Same-Model Ablation
- ✅ Same-model ensemble runs successfully
- ✅ Statistical comparison shows whether diversity matters
- ✅ Analysis script provides clear verdict
- ✅ Results inform "when to use ensembles" guidance

### Overall
- ✅ Total cost ≤ $5.00
- ✅ Implementation time ≤ 4 days
- ✅ All claims in BLOG.md are now validated with data
- ✅ Can report statistical significance (p-values, confidence intervals)

---

## Cost Summary

| Task | Component | Cost |
|------|-----------|------|
| **Task 1** | Judge scoring (50 prompts) | $1.75 |
| **Task 2** | Benchmark run (50 prompts, 7 configs) | $2.45 |
| **Task 3** | Same-model ablation | $0.10 |
| **Buffer** | Re-runs, debugging | $1.00 |
| **Total** | | **$5.30** |

---

## Risk Mitigation

### Risk 1: Judge Model Inconsistency

**Risk:** Opus gives different scores for same response

**Mitigation:**
- Use low temperature (0.3) for judging
- Test judge reliability on 10 duplicates
- If variance >10%, add prompt engineering or use ensemble of judges

### Risk 2: API Rate Limits

**Risk:** Hit Bedrock throttling with 350+ API calls

**Mitigation:**
- Rate limiter already in `ensemble-shared` (0.1s delay)
- Run benchmark in batches if needed
- Monitor for 429 errors and increase delays if seen

### Risk 3: Prompt Quality Issues

**Risk:** New prompts are poorly constructed

**Mitigation:**
- Validation script checks completeness
- Test each new prompt manually before full run
- Get feedback on adversarial prompts from another person

### Risk 4: Budget Overrun

**Risk:** Exceed $5 budget

**Mitigation:**
- Test with `--limit 5` before full runs
- Check costs in results JSON after each run
- Stop if costs are 2x expected

---

## Next Steps After Quick Wins

Once these are complete, you'll have:
- ✅ Measured quality scores (not estimates)
- ✅ Statistical validity (n=50, p-values)
- ✅ Validated diversity hypothesis
- ✅ Per-prompt ROI data

Then tackle medium-effort improvements:
- Full ablation suite (aggregation effect, temperature, compute budget)
- Adversarial prompt deep-dive
- Complexity classifier for smart routing

---

## Commands Reference

```bash
# Setup
export AWS_BEARER_TOKEN_BEDROCK=your_token
python test_auth.py

# Validate prompts
python benchmark/validate_prompts.py

# Run benchmark with judge scoring
python benchmark/run.py --output results/benchmark_50prompts.json

# Run without judge (faster, cheaper)
python benchmark/run.py --no-judge --output results/benchmark_nojudge.json

# Limited test run
python benchmark/run.py --limit 5 --output results/test.json

# Analyze diversity
python benchmark/analyze_diversity.py results/benchmark_50prompts.json

# Check costs
cat results/benchmark_50prompts.json | jq '.summary'
```

---

**Ready to start? Begin with Task 1 (Judge Model) as it's the foundation for the other two.**
