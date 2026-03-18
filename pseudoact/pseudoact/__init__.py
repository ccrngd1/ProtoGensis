"""
PseudoAct - Pseudocode Planning for LLM Agents

A two-phase agent execution framework:
- Phase 1: Plan Synthesizer (Sonnet 4.6) - Generate pseudocode plans
- Phase 2: Control-Flow Executor (Haiku 4.5) - Execute plans step-by-step
- ReAct baseline for comparison
"""

from .synthesizer import PlanSynthesizer
from .parser import PseudocodeParser
from .executor import PlanExecutor
from .react import ReActAgent
from .context import ExecutionContext
from .tools import ToolRegistry, Tool, get_default_tools
from .utils import get_bedrock_client

__version__ = "0.1.0"

__all__ = [
    "PlanSynthesizer",
    "PseudocodeParser",
    "PlanExecutor",
    "ReActAgent",
    "ExecutionContext",
    "ToolRegistry",
    "Tool",
    "get_default_tools",
    "get_bedrock_client",
]


def run_pseudoact(query: str, tool_registry: ToolRegistry = None, save_plan: bool = True) -> dict:
    """
    Run PseudoAct approach: synthesize plan, parse, and execute.

    Args:
        query: User query/task
        tool_registry: Optional tool registry (uses default if not provided)
        save_plan: Whether to save the plan to disk

    Returns:
        Dictionary with result, usage, and other metadata
    """
    if tool_registry is None:
        tool_registry = get_default_tools()

    # Phase 1: Synthesize plan
    synthesizer = PlanSynthesizer()
    plan_result = synthesizer.synthesize_plan(
        query=query,
        tools=tool_registry.get_tool_descriptions(),
        save_path="plans/plan.md" if save_plan else None
    )

    # Phase 2: Parse pseudocode
    parser = PseudocodeParser()
    nodes = parser.parse(plan_result["plan"])

    # Phase 3: Execute plan
    executor = PlanExecutor(tool_registry)
    exec_result = executor.execute_plan(nodes)

    # Combine results
    return {
        "result": exec_result["result"],
        "plan": plan_result["plan"],
        "usage": {
            "synthesis": plan_result["usage"],
            "execution": exec_result["usage"],
            "total_input": plan_result["usage"]["input_tokens"] + exec_result["usage"]["input_tokens"],
            "total_output": plan_result["usage"]["output_tokens"] + exec_result["usage"]["output_tokens"]
        },
        "context": exec_result["context"]
    }


def run_react(query: str, tool_registry: ToolRegistry = None, max_iterations: int = 10) -> dict:
    """
    Run ReAct baseline approach.

    Args:
        query: User query/task
        tool_registry: Optional tool registry (uses default if not provided)
        max_iterations: Maximum reasoning-action cycles

    Returns:
        Dictionary with result, usage, and other metadata
    """
    if tool_registry is None:
        tool_registry = get_default_tools()

    agent = ReActAgent(tool_registry, max_iterations=max_iterations)
    return agent.run(query)
