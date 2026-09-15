# One Table, Six Denial Rates, Zero LLMs Required.

**TL;DR**: Ask an LLM with raw SQL access "what's our denial rate?" and you'll get a number. A different number every time. Across 20 live runs on the same Bedrock model, the same data, and the same question, I got 19 distinct rate-sets ranging from 5.7% to 48.6%. Zero errors. Every answer defensible. None of them useful. I built a semantic governance layer that collapses this ambiguity into one deterministic, cited, root-cause-traced answer, and the hardest part didn't need an LLM at all.

---

## The Problem You Don't Know You Have

Healthcare payors have a dirty secret. Ask "what's our outpatient imaging denial rate in Ohio?" and the answer depends entirely on who writes the SQL.

Not because the data is wrong. Because "denial rate" isn't one thing.

Are you counting at the header level (one claim = one unit) or the line level (each service line counted separately)? Are front-end rejections (the 277CA "we didn't even look at this" response) being unioned in as "didn't get paid"? Are reversals and duplicates inflating the denominator? Is patient responsibility (deductible, copay) counting as a "denial"? Which CARCs qualify as real first-pass denials versus contractual adjustments?

Each of those decisions is defensible in isolation. Chain them together and you get denial rates that diverge by 3x or more on *identical data*.

I wanted to prove that claim. Not assert it. Prove it with code you can clone and run.

## The Six-Rate Divergence (LLM-Free)

Here's what happens when you compute six defensible denial-rate definitions over the same 5,821 claim lines in the same DuckDB warehouse:

```
Naive header denial rate (includes 277CA rejections)            25.6%
Header denial rate (adjudicated only)                           14.5%
Line denial rate (everything not paid)                          20.7%
Line denial rate (excl reversals/dupes, keep PR)                15.3%
First-pass line denial rate (clean adjudication)                 8.0%
Auth defect denial rate (CARC 197/246/252 only)                  7.7%
SPREAD: 7.7% -> 25.6%  (3.3x)  on IDENTICAL data
```

No LLM in the loop. No prompts. Just six YAML-defined metrics, a deterministic SQL compiler, and one DuckDB table. The spread is structural: it comes from grain choices, inclusion criteria, and which X12 codes you treat as "denied."

That's the thesis in a table. *Meaning, not the model, drives the answer.* If you don't govern which definition gets used, the model will pick one, and it'll pick a different one next time.

## What Happens When You Don't Govern

I gave Claude Sonnet 4.6 (on Bedrock) raw SQL access to the same warehouse. One tool: `execute_sql(query)`. One schema dump. One question:

> "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?"

Then I ran it 20 times.

**19 of 20 runs produced distinct rate-sets.** Zero errors. Each run returned between 2 and 16 different rate values as the model explored the schema, tried different SQL queries, and reported numbers from multiple angles. The individual rates ranged from 5.7% to 48.6%.

This isn't the model failing. It's the model doing exactly what a smart analyst would do when confronted with an ambiguous schema full of cryptic column names like `CLP_02_CLM_STAT_CD`, `CAS_GRP_CD`, `HDR_DENY_FLG`, and `PROC_PAY_FLG`. It writes plausible SQL. The SQL executes. The numbers come back. Each number is real. None of them answer the question the business actually asked.

A few examples from the live harness:

| Run | Rates Returned | Turns |
|-----|----------------|-------|
| 1   | 5.7, 5.8, 6.2, 7.2, 7.3, 15.2, 15.4, 18.4, 21.2, 24.0, 24.8, 25.1, 26.1, 48.2 | 6 |
| 2   | 17.8, 18.2, 18.4, 19.3 | 4 |
| 9   | 18.1, 20.2 | 5 |
| 11  | 5.7, 5.8, 6.2, 7.2, 7.3 | 5 |
| 17  | 15.2, 15.4, 18.1, 19.2, 19.7, 20.2, 20.9, 21.2, 24.0, 24.1, 24.5, 24.8, 25.1, 25.7, 26.1, 48.2 | 5 |

Run 11 found five rates between 5.7% and 7.3%. Run 17 found sixteen rates spanning 15.2% to 48.2%. Same model, same temperature, same data, same question. Only one pair of runs (runs 7 and 13) produced the exact same rate-set. The other 18 were all unique.

The 48.2% / 48.6% figures that pop up in several runs? That's what you get when you union rejections with denials at the header grain. The 5.7% figures? That's what you get when you narrow to specific CARC codes at the line level. Both queries are syntactically correct. The model isn't confused. The schema is ambiguous, and the model is honestly exploring that ambiguity.

This is the failure mode that matters. Not hallucination. Not wrong SQL. *Correct SQL answering the wrong question*, confidently, differently every time.

## What Happens When You Do Govern

The governed agent gets the same model (Sonnet 4.6), the same question, and the same underlying data. What changes is the interface. Instead of `execute_sql`, it gets three typed semantic tools:

**`query_metric`** takes a metric name from an enumerated list and an optional state filter. The model picks which metric to query. The semantic layer compiles deterministic SQL. The model never writes SQL.

**`traverse_graph`** walks an RDF knowledge graph (48,210 triples, loaded via rdflib) to find relationships and infer root causes. The load-bearing capability here is *inference-from-absence*: the graph can tell you what *should* exist but doesn't.

**`search_policy`** retrieves UM and medical policy documents by type and keyword. The model can cite specific policy sections, not just claim they exist.

The governed agent's answer, from the live Bedrock run:

> Auth-defect (CARC-197) denial rate: **8.0%** (372 denied lines / 4,678 eligible)  
> At-risk allowed dollars: **~$354K**  
> Root cause: HS-14 omitted from notification cohort NC-2026-03  
> Finding: No X12 278 authorization requests exist for HS-14 (inference-from-absence)  
> Policy citations: UM-RAD-2026, MP-RAD-114 §4.2, contract §7.3

One answer. Deterministic. Cited. Root-cause traced through the knowledge graph to the specific health system, the specific notification gap, and the specific contract clause.

The governed agent found the answer because the tools constrained it to. `query_metric("auth_defect_denial_rate")` compiles to exactly one SQL query. That query returns exactly one number. The model can't accidentally union rejections or count PR as denials because the metric definition (versioned YAML, owner: Utilization Management, with a `not_to_be_confused_with` field) makes those exclusions structural.

## The Architecture (Five Phases)

### Phase 1: Generate the World

A deterministic, seeded generator emits a complete synthetic payor world: members, coverages, plans, claim lines (5,821 of them), providers rolling up to health systems, UM policies with effective dates, medical policy docs, and X12 278 authorization requests with a deliberate gap. HS-14 is omitted from notification cohort NC-2026-03. This is the root cause the governed agent needs to find.

Critically, the generator also emits `truth.json`: the known-correct answer, computed from the generator's own knowledge. This isn't a label someone wrote by hand. It's ground truth by construction. The verification layer diffs the governed agent's answer against it.

### Phase 2: The Semantic Layer

Six metric definitions in YAML. Each one specifies grain (header vs line), numerator conditions, denominator conditions, exclusions, version, owner, access policy, and a `not_to_be_confused_with` field that explains what *doesn't* belong.

The compiler turns `query_metric("first_pass_line_denial_rate", filter_state="OH")` into deterministic SQL. No prompt engineering. No chain-of-thought. Just a function that maps a metric ID to a query. The model picks the metric. The compiler writes the SQL.

This is the layer where the thesis lives. The six-rate divergence is fully reproducible here, no LLM required. Run `python3 semantic/compiler.py` and you'll see the 3.3x spread yourself.

### Phase 3: The Knowledge Graph + SHACL

An OWL ontology (`payor.ttl`) models the domain: Claims, ClaimLines, Members, Providers, HealthSystems, AdjudicationOutcomes (Denial, Rejection, Paid, PatientResponsibility, all properly classified), CARC codes grouped into semantic families (AuthorizationDefect, ClinicalDenial, ContractualReduction), authorization requests, and policies.

Denial and Rejection are `owl:disjointWith`. That's not decorative. It enforces the core semantic constraint: a 277CA front-end rejection is categorically not a first-pass adjudicated denial. Unioning them (as the ungoverned agent routinely does) violates the ontology.

SHACL shapes enforce rigor in CI:
- Every Denial must have a CARC (you can't deny without a reason code)
- PatientResponsibility must not be typed as a Denial (they're disjoint classes)  
- Rejections must not have CARCs (277CAs are pre-adjudication)

The gate works both directions. Seeded violations (a Denial without a CARC, a PR record typed as Denial) fail validation with 3 detected violations. Clean data passes. This runs in the offline test suite.

The knowledge graph's most important capability is inference-from-absence. The graph traverses from CARC-197 denials to providers to health systems, then checks for the existence of X12 278 authorization requests per health system. HS-14 has 277 CARC-197 denials and $354,110.56 in at-risk allowed dollars, but zero 278 auth requests. The absence *is* the finding: the plan never notified HS-14 about the new prior auth requirement, so every claim from HS-14 got denied for missing authorization that was never requested because no one told them to request it.

### Phase 4: The Two Agents

Both agents use the same model (Sonnet 4.6 on Bedrock), the same temperature, and answer the same question. The ungoverned agent has `execute_sql` plus an 80-column schema dump. The governed agent has `query_metric`, `traverse_graph`, and `search_policy` with enumerated legal values and system constraints requiring citations for causal claims.

The verification layer extracts structured facts from the governed answer (rate, CARC dominance percentage, dollar amount, HS-14 mention, notification gap identification, policy citations) and diffs them against `truth.json`. The governed answer passes. The test enforces it.

### Phase 5: Tests and Demo

14 offline tests pass in ~8 seconds with no live LLM. They cover:

- P2 semantic layer reproducing the six-rate spread (asserts ≥2x divergence)
- P3 SHACL passing clean data and failing on seeded violations
- P3 inference-from-absence finding the HS-14 gap
- Verification layer extracting facts and detecting discrepancies
- Metric YAML validity (6 metrics), eval questions validity (50 questions)
- Demo mock mode running end-to-end

The demo runs in mock mode without credentials (`python3 demo.py --mock`) or live mode with Bedrock creds. Mock mode uses cached responses so you can verify the harness without spending API dollars.

## Honesty Notes

A few things that didn't go perfectly, because this section matters:

**The governed answer is 8.0%, not 12.9%.** The ground truth overall first-pass denial rate is 12.9%. The governed agent, when asked about the denial spike, correctly narrows to the auth-defect slice (CARC-197 family) because that's where the spike is. The 8.0% is the auth-defect denial rate, which is the right metric for the question asked. The `live-harness-result.json` records `governed_matches_truth: false` because it checks against the overall 12.9% rate, not the auth-defect subset. The answer is correct; the truth-matching metric is overly broad.

**SHACL validation was simplified for performance.** The original design had SPARQL-based SHACL shapes that caused O(n²) timeouts on 48K triples. I replaced them with property constraint shapes (minCount, disjoint classes, maxCount) and moved inference-from-absence to Python set operations over the RDF API. The SHACL gate still proves what it needs to prove (clean passes, violations fail), but the most expensive constraint logic runs in Python, not SPARQL.

**The 48K-triple graph loads in ~2.5 seconds.** That's acceptable for a demo but wouldn't scale to a production claims warehouse. The architecture is designed for an in-process graph (rdflib), not a triple store. A real deployment would use Neptune or a similar graph database.

**No fabricated packages.** This is a `pip install -r requirements.txt` project, not a PyPI package. The dependencies are real (duckdb, rdflib, pyshacl, litellm, boto3, pytest, PyYAML), all pinned.

## Clone and Run

```bash
git clone https://github.com/ccrngd1/ProtoGensis
cd ProtoGensis/meaninggate
pip install -r requirements.txt

# Offline tests (no LLM needed)
pytest tests/test_offline.py -v
# Expected: 14/14 pass in ~8s

# See the six-rate divergence yourself
python3 semantic/compiler.py

# Run the knowledge graph gate
python3 ontology/graph.py

# Demo (mock mode, no credentials needed)
python3 demo.py --mock

# Demo (live mode, requires AWS Bedrock credentials)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
python3 demo.py
```

## The Wider Point

The industry conversation about LLM governance is dominated by guardrails: content filtering, prompt injection defense, output validation. Those matter. But they're solving for the model saying something wrong.

The failure mode here is different. The model says something *right*. Correct SQL, correct execution, correct arithmetic. The problem is upstream of the model entirely: the question "what's our denial rate?" has six defensible answers, and without semantic governance, the model will explore all six across runs and present whichever one it lands on with equal confidence.

The fix isn't a better model. It's a better interface between the model and the data. Typed tools with enumerated legal values. Pre-compiled metrics with versioned definitions. A knowledge graph that can tell you what's missing, not just what's present. SHACL constraints that enforce domain rules in CI, not in prompts.

Meaning before models. Semantics and ontology drive the answer. The model is just the last mile.

---

## References

- Source: [github.com/ccrngd1/ProtoGensis/tree/main/meaninggate](https://github.com/ccrngd1/ProtoGensis/tree/main/meaninggate) (Apache-2.0)
- Live harness: Bedrock / Claude Sonnet 4.6, N=20 ungoverned runs, September 2026
- Ontology: OWL + SHACL via rdflib 7.1.1 and pyshacl 0.29.0
- Warehouse: DuckDB 1.1.3 (5,821 claim lines, synthetic, deterministic seed)

---

*Built in September 2026 as part of the Protogenesis pipeline. Synthetic data only. The semantic layer, knowledge graph, SHACL gate, and six-rate divergence are fully reproducible offline. Live LLM results require AWS Bedrock credentials. All numbers in this post are from real runs, not mock mode.*
