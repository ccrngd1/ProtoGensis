#!/usr/bin/env python3
"""
P4: Governed agent with typed semantic tools.
Three tools: query_metric, traverse_graph, search_policy.
"""
import json
import litellm
from typing import Any, Dict
from semantic.compiler import DenialMetrics
from ontology.graph import PayorGraph


class GovernedAgent:
    """
    Governed agent with semantic tool boundaries.
    """
    def __init__(self):
        # Load semantic layer
        self.metrics = DenialMetrics()

        # Load knowledge graph
        self.graph = PayorGraph()
        self.graph.load_instances()

        # Load policy documents
        with open("generate/um_policy.json") as f:
            self.um_policy = json.load(f)
        with open("generate/med_policy.json") as f:
            self.med_policy = json.load(f)

        # Tool definitions
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_metric",
                    "description": "Query a pre-compiled denial metric. Returns validated metric value with eligibility criteria and version.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric_name": {
                                "type": "string",
                                "enum": [
                                    "first_pass_line_denial_rate",
                                    "header_denial_rate",
                                    "clean_claim_rate",
                                    "carc_197_as_pct_of_denials"
                                ],
                                "description": "Name of the metric to query"
                            },
                            "filter_state": {
                                "type": "string",
                                "description": "Optional: filter to a specific state (e.g., 'OH')"
                            }
                        },
                        "required": ["metric_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "traverse_graph",
                    "description": "Traverse the knowledge graph to find relationships and infer root causes via reasoning (e.g., absence of authorization requests).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "starting_point": {
                                "type": "string",
                                "enum": ["carc_197_denials", "authorization_gaps"],
                                "description": "Where to start the traversal"
                            }
                        },
                        "required": ["starting_point"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_policy",
                    "description": "Search UM and medical policy documents for relevant rules and citations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "policy_type": {
                                "type": "string",
                                "enum": ["um_policy", "medical_policy"],
                                "description": "Which policy to search"
                            },
                            "keyword": {
                                "type": "string",
                                "description": "Keyword to search for (e.g., 'prior auth', 'notification')"
                            }
                        },
                        "required": ["policy_type"]
                    }
                }
            }
        ]

        self.system_prompt = """You are a healthcare claims analyst with access to:
1. Pre-compiled denial metrics (validated, versioned)
2. A knowledge graph with inference capabilities
3. Policy documents (UM and medical policies)

When analyzing denials:
- Start by querying relevant metrics
- Use graph traversal to find root causes
- Reference policy documents for accountability and citations

Be precise and cite your sources."""

    def query_metric(self, metric_name: str, filter_state: str = None) -> Dict[str, Any]:
        """Query a pre-compiled metric."""
        result = self.metrics.compute_metric(metric_name, filter_state=filter_state)
        return result

    def traverse_graph(self, starting_point: str) -> Dict[str, Any]:
        """Traverse the knowledge graph."""
        if starting_point == "carc_197_denials":
            # Python-based traversal (already optimized in graph.py)
            from collections import defaultdict

            hs_denials = defaultdict(lambda: {'count': 0, 'allowed': 0.0})

            # Find all Denial outcomes with CARC_197
            from rdflib.namespace import RDF
            from rdflib import Namespace
            NS = Namespace("http://meaninggate.example.org/ontology/payor#")

            for outcome in self.graph.g.subjects(RDF.type, NS.Denial):
                carc_triples = list(self.graph.g.objects(outcome, NS.hasCARC))
                if NS.CARC_197 not in carc_triples:
                    continue

                # Find the line that has this outcome
                for line in self.graph.g.subjects(NS.hasOutcome, outcome):
                    allowed_lit = list(self.graph.g.objects(line, NS.allowedAmount))
                    allowed = float(allowed_lit[0]) if allowed_lit else 0.0

                    providers = list(self.graph.g.objects(line, NS.providedBy))
                    if not providers:
                        continue
                    provider = providers[0]

                    health_systems = list(self.graph.g.objects(provider, NS.partOfHealthSystem))
                    if not health_systems:
                        continue
                    hs = health_systems[0]

                    hs_denials[hs]['count'] += 1
                    hs_denials[hs]['allowed'] += allowed

            # Convert to serializable format
            result = []
            for hs, stats in hs_denials.items():
                hs_id = str(hs).split("_")[-1]
                result.append({
                    "health_system": hs_id,
                    "carc_197_count": stats['count'],
                    "at_risk_allowed": stats['allowed']
                })

            return {"carc_197_by_health_system": sorted(result, key=lambda x: x['carc_197_count'], reverse=True)}

        elif starting_point == "authorization_gaps":
            # Inference-from-absence
            absence_results = self.graph.traverse_carc_197_to_root_cause()
            gaps = []
            for row in absence_results:
                hs_id = str(row.hs).split("_")[-1]
                gaps.append({
                    "health_system": hs_id,
                    "gap_type": "no_278_auth_requests",
                    "inference": "HS has CARC-197 denials but no authorization requests found"
                })
            return {"authorization_gaps": gaps}

        return {"error": "Unknown starting point"}

    def search_policy(self, policy_type: str, keyword: str = None) -> Dict[str, Any]:
        """Search policy documents."""
        if policy_type == "um_policy":
            policy = self.um_policy
        elif policy_type == "medical_policy":
            policy = self.med_policy
        else:
            return {"error": "Unknown policy type"}

        # Simple keyword filter if provided
        if keyword:
            relevant = {k: v for k, v in policy.items() if keyword.lower() in str(v).lower()}
            return {"policy_type": policy_type, "matches": relevant}

        return {"policy_type": policy_type, "full_policy": policy}

    def answer(self, question: str, model: str = "bedrock/us.anthropic.claude-sonnet-4-6", timeout: int = 120) -> Dict[str, Any]:
        """
        Answer question using LLM + governed semantic tools.
        """
        messages = [{"role": "user", "content": question}]

        for turn in range(15):  # Max 15 turns (governed may need more depth)
            try:
                response = litellm.completion(
                    model=model,
                    messages=[{"role": "system", "content": self.system_prompt}] + messages,
                    tools=self.tools,
                    timeout=timeout
                )
            except litellm.exceptions.Timeout:
                return {"error": "LLM timeout", "partial_history": messages}
            except Exception as e:
                return {"error": f"LLM error: {e}", "partial_history": messages}

            assistant_msg = response.choices[0].message

            # Check if done
            if assistant_msg.content and not assistant_msg.tool_calls:
                return {
                    "answer": assistant_msg.content,
                    "tool_calls": sum(1 for m in messages if m.get("tool_calls")),
                    "turns": turn + 1
                }

            # Execute tool calls
            messages.append(assistant_msg.model_dump())

            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if func_name == "query_metric":
                        result = self.query_metric(**args)
                    elif func_name == "traverse_graph":
                        result = self.traverse_graph(**args)
                    elif func_name == "search_policy":
                        result = self.search_policy(**args)
                    else:
                        result = {"error": f"Unknown tool: {func_name}"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str)
                    })

        return {"error": "Max turns exceeded", "partial_history": messages}


if __name__ == "__main__":
    agent = GovernedAgent()

    question = "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?"

    print("Governed Agent Test")
    print("=" * 80)
    print(f"Question: {question}")
    print()

    result = agent.answer(question)

    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"Answer: {result['answer']}")
        print(f"Tool calls: {result['tool_calls']}, Turns: {result['turns']}")
