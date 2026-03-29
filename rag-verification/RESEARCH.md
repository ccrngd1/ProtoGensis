# Fast & Faithful RAG Verification — W13 Research Brief

**Prepared by:** PreCog | **Date:** 2026-03-29  
**Status:** ready  
**Blog angle:** "I proposed LLM-as-judge for RAG before it had a name. Here's what comes next."

---

## 1. CC's Original Article — What It Covered

**"How to Measure the Success of Your RAG-based LLM System"** (Towards Data Science, Oct 2023)

CC's article was one of the earliest to systematically propose using an LLM to evaluate RAG output quality — the concept now universally called "LLM-as-judge." Published before RAGAS gained mainstream traction, it laid out:

- **Traditional NLG metrics and their limits:** BLEU, ROUGE, BERTScore, BLEURT — all reference-based metrics that fail when there's no gold-standard answer (the normal case in RAG)
- **The core insight:** Use a second LLM call to evaluate whether the generated answer is faithful to the retrieved context, relevant to the query, and complete
- **Evaluation dimensions:** Faithfulness (is the answer grounded in retrieved docs?), Answer Relevance (does it address the question?), Context Relevance (did retrieval find the right stuff?)
- **The LLM-as-judge pattern:** Before this had a name, CC described prompting an LLM to score/judge generated output against source context — the exact pattern that RAGAS, DeepEval, TruLens, and every RAG eval framework now implements

**What to extend, not rehash:**
- The article established *why* you need evaluation beyond BLEU/ROUGE → Don't re-argue this
- It proposed LLM-as-judge as the solution → The new article should acknowledge this worked, then show its limits (cost, latency, inconsistency) and present the next evolution: lightweight, real-time, encoder-based verification
- The progression: Reference metrics (2022) → LLM-as-judge (CC's article, 2023) → Dedicated verification models (2025-2026)

---

## 2. Paper Analysis

### 2.1 Fast and Faithful: Real-Time Verification for Long-Document RAG (arXiv 2603.23508)

**Authors:** Xunzhuo Liu (vLLM Semantic Router), Bowei He (MBZUAI/McGill), Xue Liu, Haichen Zhang (AMD), Huamin Chen (Red Hat)  
**Published:** March 4, 2026  
**Code/Models:** https://huggingface.co/llm-semantic-router

#### Core Problem
LLM-as-judge can check long contexts but is too slow/costly for production. Lightweight encoder classifiers (like LettuceDetect) are fast but limited to ~8K tokens — truncating documents and missing evidence. Real-world documents (contracts: 15-30K tokens, clinical reports: 20-50K, regulatory filings: 100K+) blow past these limits.

#### Architecture
1. **Extended ModernBERT encoder** — Scaled from 8K to 32K tokens using YaRN (Yet another RoPE scaling method) for rotary position embeddings
2. **Retrieval-aware masking** — Novel training strategy that forces the encoder to attend across long distances:
   - *Long-Range Copy Masking:* Mask tokens in the second half that also appear in the first half → model must attend 16K+ tokens back
   - *Anchor-Reference Masking:* Mask later occurrences of early anchor tokens → forces attention to distant anchors
3. **Elastic Weight Consolidation (EWC)** — Prevents catastrophic forgetting of pre-trained long-range attention patterns during fine-tuning
4. **Token-level hallucination detection** — Input: `[Context] ⊕ [SEP] ⊕ [Query] ⊕ [SEP] ⊕ [Response]` → Binary label per response token (supported vs. hallucinated). Context/query tokens excluded from loss.
5. **Configurable early-exit inference** — Lightweight classifier adapters at intermediate transformer layers. Distillation-trained to match full-depth predictions. Enables latency-accuracy tradeoff at serving time.

#### Key Results

| Metric | 32K Model | 8K Model (truncated) | Improvement |
|--------|-----------|---------------------|-------------|
| Samples truncated | 0% | 95% | — |
| Hallucination Recall | 0.55 | 0.06 | **+817%** |
| Hallucination F1 | 0.50 | 0.10 | **+400%** |

On short-context RAGTruth benchmark: Token F1 0.5337 vs LettuceDetect-large's 0.6158 — slight regression but within acceptable range for 4× longer context support.

**Early exit performance:**
| Exit Point | Example F1 | Compute | Speedup |
|------------|-----------|---------|---------|
| Full (L22) | 95.5% | 100% | 1.0× |
| Intermediate (L16) | 92.8% | 73% | 1.4× |
| Mid (L11) | 81.2% | 50% | 2.0× |
| Early (L6) | 48.2% | 27% | 3.3-3.9× |

Latency: ~2.1ms/sample at 512 tokens, ~10.9ms at 8K tokens (full model).

#### Practical Fine-tuning Insights
- **Standard cross-entropy > focal loss / class-weighted CE** — Imbalance-aware losses over-predict hallucinations, tanking precision
- **Distribution-matched training data matters more than scale** — QA-style datasets with 89-100% hallucination rate bias the detector pessimistic
- **Response-only supervision** — Masking context/query tokens in loss focuses capacity on faithfulness judgment
- **Conservative fine-tuning for long context** — Low LR, single epoch, combined with retrieval-aware masking + EWC

#### Blog Relevance: ⭐⭐⭐⭐⭐
This is the centerpiece paper. It directly addresses the evolution from CC's LLM-as-judge → dedicated real-time verification. The encoder-based approach is deployable, fast, and addresses the exact speed-context tradeoff that makes LLM-as-judge impractical in production.

---

### 2.2 DynaRAG: Bridging Static and Dynamic Knowledge (arXiv 2603.18012)

**Authors:** Multiple (see paper)  
**Published:** February 24, 2026

#### Core Concept
Not a verification paper per se, but a RAG framework that addresses *when to trust retrieval vs. when to fallback to APIs*. Relevant because it represents another approach to RAG reliability.

#### Architecture
1. **Web retrieval** → **Data cleaning** (beautifulsoup4 HTML parsing) → **LLM-based reranking** (score each passage)
2. **Sufficiency classifier** — Compares highest rerank score against threshold τ
3. **If insufficient:** Routes to Gorilla v2 for API invocation, guided by FAISS-based schema filtering
4. **Answer generation** from merged context (retrieved docs + API results)

#### Key Results (CRAG Benchmark)

| Method | Accuracy | Hallucination | Missing |
|--------|----------|---------------|---------|
| LLM Only | 28.53% | 34.95% | 36.52% |
| Direct RAG | 34.23% | 43.09% | 22.68% |
| DynaRAG Task 1 (no API) | 29.12% | 25.33% | 45.55% |
| DynaRAG Task 2 (with API) | 41.00% | 22.09% | 36.91% |

Hallucination drops from 43% (naive RAG) to 22% with dynamic routing. Conservative sufficiency thresholding increases "I don't know" responses — a feature, not a bug.

#### Blog Relevance: ⭐⭐⭐
Useful as a complementary approach. Where Fast & Faithful verifies *after* generation, DynaRAG gates *before* generation by checking retrieval sufficiency. Mention as part of the emerging "defense in depth" pattern for RAG reliability.

---

### 2.3 Controllable Evidence Selection via Deterministic Utility Gating (arXiv 2603.18011)

**Author:** Victor P. Unda (Independent Researcher)  
**Published:** February 23, 2026

#### Core Concept
A deterministic (no training, no fine-tuning) evidence selection framework that decides *which retrieved passages qualify as evidence* before generation begins. Addresses the gap between "semantically similar" and "actually usable as evidence."

#### Architecture
1. **Meaning-Utility Estimation (MUE)** — Three deterministic signals per evidence unit:
   - Semantic similarity (SBERT + FAISS backbone)
   - Explicit term coverage (does the unit contain the specific terms/facts the query needs?)
   - Conceptual distinctiveness (corpus-level TF-IDF-like weighting — common terms score low, specific terms score high)
2. **Diversity-Utility Estimation (DUE)** — Iterative redundancy control that suppresses near-duplicate evidence
3. **Evidence Gate** — Hard gating: if no single evidence unit independently satisfies the requirement, the system returns *no answer*
4. **Unit-level evaluation** — Each sentence/record evaluated independently. No merging, no expansion, no cross-unit inference.

#### Key Insight
Similarity ≠ evidence. A sentence can be highly similar to a query while not actually stating the fact needed to answer it. This matters most for questions about *when* something applies, *who* it applies to, or *under what conditions* — where many retrieved passages mention the same topic but only one states the specific rule.

#### Blog Relevance: ⭐⭐⭐
Another pre-generation gating approach. The deterministic, no-training angle is interesting. Pairs with the Fast & Faithful post-generation verification to show the full spectrum: gate evidence selection → generate → verify output.

---

## 3. RAG Faithfulness Evaluation Landscape (2025-2026)

### Existing Tools

| Tool | Faithfulness Approach | NLI Model? | Strengths | Weaknesses |
|------|----------------------|------------|-----------|------------|
| **RAGAS** | Claim decomposition → NLI entailment check per claim against context. Structured as NLI problem. LLM extracts claims from answer, then verifies each against context. | Uses LLM for claim extraction + verification. Formulated as NLI but executed by LLM, not dedicated NLI model. | De facto standard. Context precision, recall, faithfulness, answer relevance. Open source. | LLM-dependent = slow + costly. Claim extraction step adds latency. Faithfulness scores can be inconsistent across LLM providers. |
| **DeepEval** | FaithfulnessMetric — extracts claims from output, checks each against context. Also offers GEval for custom criteria. | LLM-based (no dedicated NLI model). | Production-focused. Integrates with CI/CD. Offers 14+ metrics. | Same LLM cost/latency issues as RAGAS. |
| **TruLens** | Groundedness metric — chunk attribution scoring. Tracks which context chunks support which parts of the answer. | LLM-based scoring. Some early versions used NLI (DeBERTa) but current default is LLM. | Good observability integration. Tracks cost, latency alongside quality. | Now part of Snowflake TruEra. Enterprise-focused. |
| **Guardrails AI** | Validator-based approach. Can run NLI validators inline. | Supports NLI-based validators (ProvenanceVerifier uses DeBERTa cross-encoder). | Real-time, inline validation. Can block unfaithful responses. | Less comprehensive evaluation suite. More of a guardrail than an eval framework. |
| **LettuceDetect** | Token-level hallucination detection. ModernBERT-based encoder. | Encoder-based (not traditional NLI, but similar architecture). | Fast, token-level granularity, open source. 8K context. | Limited to 8K tokens — the exact problem Fast & Faithful addresses. |

### The Evolution Arc (for the blog)

```
2022: Reference metrics (BLEU, ROUGE, BERTScore)
      → Needed gold-standard answers. Useless for RAG.

2023: LLM-as-judge (CC's article, then RAGAS)
      → Breakthrough: use LLM to evaluate LLM output.
      → Problem: slow, expensive, inconsistent.

2024-2025: Dedicated NLI/encoder models
      → LettuceDetect, Guardrails ProvenanceVerifier
      → Fast but limited context (8K).

2026: Full-document real-time verification
      → Fast & Faithful: 32K tokens, encoder-based, early-exit.
      → The next step CC was pointing toward.
```

---

## 4. NLI Models for Entailment Scoring

### DeBERTa-v3-large for NLI

**Model:** `cross-encoder/nli-deberta-v3-large` (Hugging Face)  
**Training:** SNLI + MultiNLI datasets  
**Output:** Three scores per sentence pair — entailment, neutral, contradiction  
**Architecture:** Cross-encoder (concatenates premise + hypothesis, processes jointly)

**Why it matters for RAG verification:**
- NLI is the theoretical foundation for faithfulness checking: "Given context C (premise), is claim A (hypothesis) entailed?"
- DeBERTa-v3-large is the strongest general-purpose NLI model for this pattern
- Cross-encoder architecture means it jointly reasons about both inputs (unlike bi-encoders)
- Used in academic RAG evaluation papers, Guardrails ProvenanceVerifier
- Limitation: context window ~512-1024 tokens per pair. Must chunk for longer contexts.

**Other NLI Models:**
| Model | Size | Performance | Notes |
|-------|------|-------------|-------|
| cross-encoder/nli-deberta-v3-large | 435M | SOTA for NLI | Best accuracy, slow for production |
| cross-encoder/nli-deberta-v3-base | 184M | Near-SOTA | Good balance |
| cross-encoder/nli-MiniLM-L6-H384 | 22M | Good | Fast, smaller context |
| DeBERTa-v3-xsmall NLI | 22M | Acceptable | Edge deployment |

**Fine-tuning for RAG hallucination detection:**
Recent paper (ACL 2025, "Coarse-Grained Hallucination Detection via NLI Fine-Tuning") shows that direct fine-tuning of NLI-adapted DeBERTa-v3-large on hallucination detection data significantly improves over zero-shot NLI. This is exactly what Fast & Faithful does at the architectural level.

---

## 5. Bedrock & SageMaker Deployment Options

### Hosting NLI Models on AWS

**Option 1: SageMaker Real-Time Endpoint (Recommended for DeBERTa)**
- Deploy DeBERTa-v3-large via HuggingFace DLC (Deep Learning Container)
- Instance: ml.g5.xlarge (1× A10G GPU, 24GB VRAM) — more than enough for 435M params
- Serverless inference option for cost savings on bursty workloads
- ~2-5ms inference latency per sentence pair at batch size 1
- **Cost:** ~$1.41/hr for ml.g5.xlarge. Serverless: pay per invocation.

```python
# SageMaker deployment sketch
from sagemaker.huggingface import HuggingFaceModel

hub = {
    'HF_MODEL_ID': 'cross-encoder/nli-deberta-v3-large',
    'HF_TASK': 'text-classification'
}

model = HuggingFaceModel(
    env=hub,
    role=sagemaker_role,
    transformers_version='4.37',
    pytorch_version='2.1',
    py_version='py310'
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.g5.xlarge',
    endpoint_name='nli-deberta-v3-large'
)
```

**Option 2: SageMaker Serverless Inference**
- Same model, but auto-scales to zero when idle
- Higher cold-start latency (~5-15s first call)
- Good for development/testing, not production real-time

**Option 3: Bedrock Marketplace**
- No NLI-specific models currently available on Bedrock Marketplace
- Bedrock focuses on foundation models (Claude, Llama, Mistral, etc.)
- For NLI, SageMaker is the correct AWS path

**Option 4: Bedrock as the LLM-as-judge (baseline comparison)**
- Use Claude on Bedrock for LLM-as-judge evaluation (the approach CC originally proposed)
- Then compare against DeBERTa NLI endpoint for speed/cost
- This creates a compelling demo: "My original approach on Bedrock vs. the new approach on SageMaker"

**Option 5: Deploy Fast & Faithful Model**
- The Fast & Faithful authors released their model on HuggingFace (llm-semantic-router)
- Deploy on SageMaker similarly to DeBERTa
- Requires ModernBERT architecture support — check HF transformers version compatibility
- 32K context = needs more VRAM. ml.g5.2xlarge (1× A10G, 24GB) should suffice.

### Bedrock-Native RAG Verification Pattern

```
User Query
    ↓
Bedrock Knowledge Base (retrieval)
    ↓
Claude on Bedrock (generation)
    ↓
SageMaker NLI Endpoint (verification) ← NEW
    ↓
If hallucination detected → regenerate or flag
    ↓
Return verified response
```

---

## 6. Sample Code Architecture (for the blog)

### Recommended Demo Structure

```python
# 1. Traditional approach (CC's 2023 article): LLM-as-judge on Bedrock
def llm_judge_faithfulness(context, query, response):
    """CC's original approach — use Claude to judge faithfulness."""
    prompt = f"""Given the following context and response, evaluate faithfulness.
    Context: {context}
    Query: {query}  
    Response: {response}
    Score faithfulness 0-1 and explain."""
    # Call Claude via Bedrock
    result = bedrock.invoke_model(modelId="anthropic.claude-sonnet-4-20250514", ...)
    return parse_score(result)

# 2. NLI-based approach: DeBERTa cross-encoder
def nli_faithfulness(context, query, response):
    """Decompose response into claims, check each via NLI."""
    claims = extract_claims(response)  # Simple sentence splitting or LLM
    scores = []
    for claim in claims:
        # Call SageMaker NLI endpoint
        result = sm_runtime.invoke_endpoint(
            EndpointName='nli-deberta-v3-large',
            Body=json.dumps({"inputs": f"{context} [SEP] {claim}"})
        )
        entailment_score = parse_nli(result)
        scores.append(entailment_score)
    return min(scores)  # Faithfulness = worst claim

# 3. Real-time encoder verification: Fast & Faithful approach  
def realtime_verification(context, query, response):
    """Full-document, token-level verification."""
    input_text = f"{context} [SEP] {query} [SEP] {response}"
    result = sm_runtime.invoke_endpoint(
        EndpointName='fast-faithful-verifier',
        Body=json.dumps({"inputs": input_text})
    )
    token_predictions = parse_token_labels(result)
    hallucinated_spans = extract_spans(token_predictions, response)
    return {
        "faithful": len(hallucinated_spans) == 0,
        "hallucinated_spans": hallucinated_spans,
        "confidence": compute_confidence(token_predictions)
    }

# 4. Compare all three
def compare_approaches(context, query, response):
    """Head-to-head comparison for the blog."""
    import time
    
    start = time.time()
    llm_score = llm_judge_faithfulness(context, query, response)
    llm_time = time.time() - start  # ~2-5 seconds
    
    start = time.time()
    nli_score = nli_faithfulness(context, query, response)
    nli_time = time.time() - start  # ~50-200ms
    
    start = time.time()  
    rt_result = realtime_verification(context, query, response)
    rt_time = time.time() - start  # ~10-50ms
    
    return {
        "llm_judge": {"score": llm_score, "latency_ms": llm_time * 1000},
        "nli_claims": {"score": nli_score, "latency_ms": nli_time * 1000},
        "realtime_encoder": {"result": rt_result, "latency_ms": rt_time * 1000}
    }
```

### Suggested Blog Demo Flow

1. **Set up a Bedrock RAG pipeline** (Knowledge Base + Claude)
2. **Generate some responses** — mix of faithful and hallucinated
3. **Run CC's original LLM-as-judge** (Claude on Bedrock) — show it works but log cost + latency
4. **Run NLI claim verification** (DeBERTa on SageMaker) — faster, cheaper, but limited context
5. **Run Fast & Faithful** (if model available) — fastest, full-document, token-level
6. **Compare:** accuracy vs latency vs cost table
7. **Show the progression:** CC's 2023 insight → today's real-time verification

---

## 7. Blog Narrative Blueprint

### Title Options
- "I Proposed LLM-as-Judge for RAG Before It Had a Name. Here's What Comes Next."
- "From LLM-as-Judge to Real-Time Verification: The Evolution of RAG Evaluation"
- "RAG Verification in 2026: Beyond the LLM-as-Judge I Invented"

### Structure

1. **The Hook** — "In October 2023, I published an article proposing that you evaluate RAG systems by having another LLM judge the output. I didn't call it 'LLM-as-judge' — that term didn't exist yet. Now every RAG framework uses this exact pattern. But LLM-as-judge has a problem..."

2. **The Problem with LLM-as-Judge** — Cost ($0.01-0.10 per eval), latency (2-5s), inconsistency (same input → different scores across runs). Fine for offline eval. Unusable for real-time production.

3. **The Evolution** — Reference metrics → LLM-as-judge → NLI models → Real-time encoders. Each step: faster, cheaper, more reliable.

4. **Three Papers, One Direction** — Fast & Faithful (verify after generation), DynaRAG (gate before generation), Controllable Evidence Selection (gate at retrieval). Defense in depth.

5. **Working Code** — Bedrock RAG pipeline + three verification approaches. Side-by-side comparison. Cost/latency table.

6. **The Architecture** — Production RAG verification pattern on AWS. Bedrock for retrieval + generation, SageMaker for verification.

7. **What's Next** — The verification layer becomes standard infrastructure, like TLS for web traffic. You don't ship RAG without it.

---

## 8. Open Questions for CC

- [ ] Does CC want to deploy the actual Fast & Faithful model from HuggingFace, or keep the demo conceptual?
- [ ] Bedrock Knowledge Base as the RAG source, or custom retrieval?
- [ ] Include DynaRAG/Controllable Evidence as supporting references, or focus purely on verification?
- [ ] Target length? (Previous Protogenesis posts: ~2500-3500 words)
- [ ] The "Inside CABAL" post was accepted by TDS — should this one target TDS too?

---

## Sources

1. Liu, X. et al. "Fast and Faithful: Real-Time Verification for Long-Document RAG Systems." arXiv:2603.23508, Mar 2026. https://arxiv.org/abs/2603.23508
2. "DynaRAG: Bridging Static and Dynamic Knowledge in RAG." arXiv:2603.18012, Feb 2026. https://arxiv.org/abs/2603.18012
3. Unda, V.P. "Controllable Evidence Selection in RAG via Deterministic Utility Gating." arXiv:2603.18011, Feb 2026. https://arxiv.org/abs/2603.18011
4. CC's original article: "How to Measure the Success of Your RAG-based LLM System." Towards Data Science, Oct 2023. https://towardsdatascience.com/how-to-measure-the-success-of-your-rag-based-llm-system-874a232b27eb
5. RAGAS Faithfulness docs: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness
6. cross-encoder/nli-deberta-v3-large: https://huggingface.co/cross-encoder/nli-deberta-v3-large
7. Fast & Faithful models: https://huggingface.co/llm-semantic-router
8. DeepEval RAG Evaluation: https://deepeval.com/guides/guides-rag-evaluation
9. "Coarse-Grained Hallucination Detection via NLI Fine-Tuning." ACL SDP 2025. https://aclanthology.org/2025.sdp-1.34.pdf
10. "Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards." EMNLP Industry 2025. https://aclanthology.org/2025.emnlp-industry.54

---

*PreCog research complete. This brief is ready for the builder pipeline.*
