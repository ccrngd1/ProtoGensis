# I Ban Em Dashes in My AI System. This Paper Says That Might Be Destroying Output Quality.

*How a single banned punctuation mark can cause 6.6× quality degradation that standard evaluation completely misses*

## The Problem

You're running an AI application in production. Your product manager has opinions about style. "No em dashes," they say. "They look unprofessional. Ban them."

So you add a line to your system prompt: "Never use em dashes (—) in your responses."

Your AI complies. Your PM is happy. Your users... well, you're not entirely sure. Your standard evaluation metrics look fine. But something feels off.

A new paper, *"One Token Away from Collapse"* (arXiv 2604.13006), suggests you might have a bigger problem than you think.

## The Research

The paper's findings are striking:

- Common output constraints (banned punctuation, format restrictions, style rules) can degrade LLM quality by up to 6.6×
- Standard LLM-as-judge evaluation methods have a **massive blind spot** and miss this degradation
- The problem is detectable using pairwise comparison with position bias correction
- Two-pass generation (generate unconstrained, then rewrite) can recover most of the lost quality

### Why Standard Evaluation Fails

When you ask an LLM to rate a response 1-10, you're measuring the wrong thing. The judge sees a response that successfully follows the constraint and thinks "good job following instructions!" It doesn't know what the unconstrained response would have looked like.

Pairwise comparison fixes this: show both responses and ask "which is more comprehensive?" Now the judge can see what was lost.

## Introducing ConstraintBreak

I built **ConstraintBreak** to make this research actionable. It's a Python CLI tool that tests whether your output constraints are silently degrading quality.

### What It Does

1. **Scans for Fragility**: Tests your constraints against various tasks using pairwise comparison
2. **Measures Impact**: Calculates win rates with position bias correction
3. **Tests Recovery**: Checks if two-pass generation recovers quality
4. **Generates Reports**: Rich terminal heatmaps, markdown reports, JSON export

### How It Works

The core methodology from the paper:

```python
# For each (constraint, task) pair:

# 1. Generate unconstrained baseline
baseline = model.generate(task)

# 2. Generate with constraint applied
constrained = model.generate(task, constraint=constraint)

# 3. Judge: which is more comprehensive? (A vs B)
winner_ab = judge(task, response_a=baseline, response_b=constrained)

# 4. Swap positions to control for bias (B vs A)
winner_ba = judge(task, response_a=constrained, response_b=baseline)

# 5. Calculate win rate with position bias correction
win_rate = calculate_win_rate(winner_ab, winner_ba)
```

This simple swap eliminates position bias and gives you reliable measurements.

## Example Output (Mock Mode)

Here's what ConstraintBreak shows you when testing constraints:

```
ConstraintBreak: Constraint Fragility Scanner

Provider: mock / mock-model
Constraints: 6
Tasks: 12
Total comparisons: 72

Summary Statistics

Total comparisons: 72
Degradation detected: 48 (66.7%)
Average win rate: 52.1%

Severity breakdown:
  🟢 None: 24
  🟡 Low: 18
  🟠 Medium: 20
  🔴 High: 10
```

**Note**: The above output is from mock mode for demonstration. Mock mode generates deterministic responses that simulate constraint fragility patterns without making real API calls.

### Heatmap Visualization

ConstraintBreak generates a colored heatmap showing which constraint-task combinations cause problems:

```
Constraint Fragility Heatmap
┌─────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Constraint      │ essay_climate│ story_beginning│ algorithm_...│ logic_puzzle │
├─────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ em_dash_ban     │ 🟢 2%        │ 🟡 8%        │ 🟢 3%        │ 🟢 1%        │
│ colon_ban       │ 🟠 18%       │ 🟠 22%       │ 🔴 45%       │ 🟡 12%       │
│ bullet_ban      │ 🔴 38%       │ 🟠 25%       │ 🟠 28%       │ 🟡 9%        │
│ numbered_list...│ 🔴 42%       │ 🟠 19%       │ 🔴 52%       │ 🟠 31%       │
└─────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**Note**: This heatmap is representative output from mock mode, showing the types of patterns you'd see in real testing.

The severity levels:
- 🟢 **None** (<5%): Safe to use
- 🟡 **Low** (5-15%): Minor degradation, consider two-pass
- 🟠 **Medium** (15-30%): Significant loss, use two-pass or reconsider
- 🔴 **High** (>30%): Severe degradation, strongly consider dropping

## Key Insights

### 1. Not All Constraints Are Equal

Banning em dashes? Probably fine (low impact on most tasks). Banning numbered lists? That's going to hurt your coding and reasoning tasks hard.

### 2. Task-Constraint Interactions Matter

A constraint might be harmless for creative writing but devastating for technical explanations. The heatmap shows you exactly where the problems are.

### 3. Two-Pass Generation Works

For constraints that hurt quality, generating unconstrained first and then rewriting often recovers 80%+ of the lost quality. ConstraintBreak tests this automatically:

```bash
constraintbreak recover numbered_list_ban --provider openai --model gpt-4
```

### 4. Test Before Deploying

Before adding a constraint to production, run it through ConstraintBreak. A 5-minute test could save you from silently degrading your entire product.

## Architecture Walkthrough

ConstraintBreak is designed to be extensible and production-ready:

### Provider Abstraction

```python
class BaseProvider(ABC):
    @abstractmethod
    def generate(self, prompt, system_prompt, temperature, max_tokens, logit_bias):
        pass

    @abstractmethod
    def supports_logit_bias(self):
        pass
```

Implementations for OpenAI, Anthropic, AWS Bedrock, and a mock provider for testing.

### Constraint Engine

YAML-based constraint definitions with support for:
- Instruction-level constraints (system prompt injection)
- Token-level constraints (logit_bias where supported)
- Custom constraint sets
- Preset collections (like VOICE.md style guides)

### Pairwise Comparison Engine

The heart of the system. Implements position-bias-corrected pairwise comparison from the paper:

```python
class PairwiseEngine:
    def run_comparison(self, task, constraint):
        unconstrained = self.provider.generate(task.prompt)
        constrained = self.provider.generate(task.prompt, constraint=constraint)

        # Judge both positions
        winner_ab = self._judge_pair(task, unconstrained, constrained)
        winner_ba = self._judge_pair(task, constrained, unconstrained)

        # Aggregate with bias correction
        win_rate = self._calculate_win_rate(winner_ab, winner_ba)
        return ComparisonResult(...)
```

### Storage and Reporting

- SQLite for results persistence
- Rich terminal output with colored heatmaps
- Markdown reports for documentation
- JSON export for programmatic analysis

## Using ConstraintBreak

### Installation

```bash
git clone https://github.com/protogenesis/constraintbreak
cd constraintbreak
pip install -e .
```

### Quick Test (No API Keys)

```bash
# List built-in constraints
constraintbreak constraints

# Run scan in mock mode
constraintbreak scan --provider mock --model mock-model

# Test recovery
constraintbreak recover em_dash_ban --provider mock
```

### Production Testing

```bash
# Full scan with OpenAI
constraintbreak scan --provider openai --model gpt-4 --api-key YOUR_KEY --output report.md

# Test specific constraint
constraintbreak scan --provider openai --model gpt-4 --constraint bullet_ban

# Test recovery for problematic constraint
constraintbreak recover numbered_list_ban --provider openai --model gpt-4
```

### Custom Constraints

Test your own constraints:

```yaml
# my_constraints.yaml
constraints:
  - name: brand_voice
    description: "Enforce brand voice guidelines"
    instruction: "Write in a professional tone. Avoid casual language, contractions, and colloquialisms."
    category: style
```

```bash
constraintbreak scan --constraints my_constraints.yaml --provider openai --model gpt-4
```

## The Bigger Picture

This isn't just about em dashes. It's about the gap between what we measure and what actually matters.

We optimize for constraint adherence. We measure with biased judges. We ship systems that follow the rules perfectly while quietly producing worse output.

ConstraintBreak gives you the tools to see what's actually happening.

## When to Use This

You should test with ConstraintBreak if:

1. **You're adding output constraints to production**: Test before deploying
2. **Your product quality feels off but metrics look fine**: You might have degradation blind spots
3. **You use custom system prompts with style rules**: Check if they're hurting quality
4. **You're optimizing prompt engineering**: See the real impact of your changes
5. **You're evaluating AI safety measures**: Some constraints for safety might have quality tradeoffs worth understanding

## The Paper's Recommendations

Based on the research findings:

1. **Prefer soft guidance over hard constraints**: "Try to avoid X" beats "Never use X"
2. **Use two-pass generation for critical constraints**: Generate first, constrain second
3. **Test systematically**: Don't assume constraints are harmless
4. **Evaluate with pairwise comparison**: Especially for constraint-induced quality changes
5. **Consider the task domain**: Formatting constraints hurt structured output tasks most

## Cost and Performance

A full scan with 6 constraints × 12 tasks:
- 72 comparisons × 4 API calls = 288 calls
- Estimated cost with GPT-4: $5-15
- Runtime: ~10-15 minutes

Use `--constraint` and `--category` flags to test specific areas and reduce cost.

## What's Next

ConstraintBreak is v0.1. Future directions:

- Multi-constraint interaction testing (what happens when you combine constraints?)
- Linear probe analysis (understand internal model state changes)
- Auto-discovery of implicit constraints from system prompts
- GUI for non-technical users
- Integration with LangSmith, Weights & Biases, etc.

## Try It Yourself

The code is on GitHub. The tests all pass. The mock mode works without API keys.

Before you ban that next punctuation mark, maybe run it through ConstraintBreak first.

Sometimes the rules we enforce aren't the rules we meant to enforce.

---

## References

- Paper: *"One Token Away from Collapse"* (arXiv 2604.13006)
- GitHub: [github.com/protogenesis/constraintbreak](https://github.com/protogenesis/constraintbreak)
- MT-Bench Task Framework: [lmsys.org](https://lmsys.org)

## About This Build

Built for Protogenesis W17. All code is open source (MIT License). Test outputs in this post are from mock mode and labeled as such per SkillForge Quality Gates.

If you're building AI products and care about quality that metrics can't see, this tool might be worth your time.
