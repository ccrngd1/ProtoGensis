#!/usr/bin/env python3
"""
P4: Ungoverned SQL agent with raw schema dump.
Single execute_sql tool -> realistically ambiguous schema.
MUST fail honestly (never rigged to fail).
"""
import json
import duckdb
import litellm
from typing import Any, Dict


class UngovernedAgent:
    """
    Ungoverned agent with raw SQL access.
    Single tool: execute_sql(query: str) -> results
    """
    def __init__(self, db_path="warehouse/claims.duckdb", schema_path="warehouse/schema.txt"):
        self.db_path = db_path
        with open(schema_path) as f:
            self.schema = f.read()

        # Tool definition
        self.tools = [{
            "type": "function",
            "function": {
                "name": "execute_sql",
                "description": "Execute a SQL query against the claims warehouse and return results",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute"
                        }
                    },
                    "required": ["query"]
                }
            }
        }]

        self.system_prompt = f"""You are a healthcare claims analyst. You have access to a claims warehouse via SQL.

DATABASE SCHEMA:
{self.schema}

When given a question, write SQL queries to analyze the data and provide an answer.
Focus on denial rates, CARCs, and financial impact."""

    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Execute SQL and return results."""
        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            result = conn.execute(query).fetchdf()
            conn.close()
            return {"rows": result.to_dict('records'), "count": len(result)}
        except Exception as e:
            return {"error": str(e)}

    def answer(self, question: str, model: str = "bedrock/us.anthropic.claude-sonnet-4-6", timeout: int = 120) -> Dict[str, Any]:
        """
        Answer question using LLM + raw SQL tool.
        Bounded timeout, honest failures only.
        """
        messages = [{"role": "user", "content": question}]

        for turn in range(10):  # Max 10 turns
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
                    if tool_call.function.name == "execute_sql":
                        args = json.loads(tool_call.function.arguments)
                        result = self.execute_sql(args["query"])

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, default=str)
                        })

        return {"error": "Max turns exceeded", "partial_history": messages}


if __name__ == "__main__":
    import sys

    agent = UngovernedAgent()

    # Test question
    question = "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?"

    print("Ungoverned Agent Test")
    print("=" * 80)
    print(f"Question: {question}")
    print()

    result = agent.answer(question)

    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"Answer: {result['answer']}")
        print(f"Tool calls: {result['tool_calls']}, Turns: {result['turns']}")
