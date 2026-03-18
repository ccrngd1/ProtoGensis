"""
Control-flow executor that walks the AST and executes steps.
"""

import ast
import json
import operator as op
import re
from typing import Any, List, Dict
from .parser import (
    PlanNode, ToolCallNode, AssignmentNode, ConditionalNode, LoopNode, CommentNode
)
from .context import ExecutionContext
from .tools import ToolRegistry
from .utils import get_bedrock_client, call_bedrock_model, extract_text_from_response, get_token_usage, HAIKU_MODEL_ID


class PlanExecutor:
    """
    Executes parsed plan AST with control flow support.
    Uses Haiku 4.5 for individual step execution.
    """

    # Define safe operators for arithmetic evaluation
    _SAFE_OPS = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.UAdd: op.pos,
        ast.Mod: op.mod,
        ast.FloorDiv: op.floordiv,
    }

    def __init__(self, tool_registry: ToolRegistry, client=None):
        """
        Initialize the plan executor.

        Args:
            tool_registry: Registry of available tools
            client: Optional Bedrock client (for testing)
        """
        self.tool_registry = tool_registry
        self.client = client or get_bedrock_client()
        self.model_id = HAIKU_MODEL_ID
        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

    def execute_plan(self, nodes: List[PlanNode], context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Execute a parsed plan.

        Args:
            nodes: List of plan nodes to execute
            context: Optional execution context (creates new if not provided)

        Returns:
            Dictionary with 'result', 'context', and 'usage' fields
        """
        if context is None:
            context = ExecutionContext()

        self.total_usage = {"input_tokens": 0, "output_tokens": 0}

        for node in nodes:
            self._execute_node(node, context)

        # Get final answer if it exists
        result = context.get("answer", "No answer variable found")

        return {
            "result": result,
            "context": context,
            "usage": self.total_usage.copy()
        }

    def _execute_node(self, node: PlanNode, context: ExecutionContext) -> Any:
        """Execute a single plan node."""
        if isinstance(node, ToolCallNode):
            return self._execute_tool_call(node, context)
        elif isinstance(node, AssignmentNode):
            return self._execute_assignment(node, context)
        elif isinstance(node, ConditionalNode):
            return self._execute_conditional(node, context)
        elif isinstance(node, LoopNode):
            return self._execute_loop(node, context)
        elif isinstance(node, CommentNode):
            return None  # Skip comments
        else:
            raise ValueError(f"Unknown node type: {node.node_type}")

    def _execute_tool_call(self, node: ToolCallNode, context: ExecutionContext) -> Any:
        """Execute a tool call with error recovery."""
        # Resolve arguments (replace variable references)
        resolved_args = self._resolve_arguments(node.arguments, context)

        # Check if tool exists (this should raise ValueError if not found)
        try:
            tool = self.tool_registry.get_tool(node.tool_name)
        except ValueError:
            # Tool not found - this is a programming error, re-raise
            raise

        # Execute the tool with error recovery
        try:
            result = tool.execute(**resolved_args)
        except Exception as e:
            # On tool execution failure, store error message and continue
            error_msg = f"ERROR: Tool '{node.tool_name}' failed: {str(e)}"
            result = error_msg

            # Log the failure
            context.add_history(
                step_type="tool_error",
                description=f"{node.tool_name}({resolved_args})",
                result=error_msg
            )

            # Store error result if there's a result variable
            if node.result_var:
                context.set(node.result_var, result)

            return result

        # Store result in context if there's a result variable
        if node.result_var:
            context.set(node.result_var, result)

        # Add to history
        context.add_history(
            step_type="tool_call",
            description=f"{node.tool_name}({resolved_args})",
            result=result
        )

        return result

    def _execute_assignment(self, node: AssignmentNode, context: ExecutionContext) -> Any:
        """Execute a variable assignment with arithmetic evaluation."""
        # Resolve the value
        value = self._resolve_value(node.value, context)

        # If the value is a string that looks like an arithmetic expression, try to evaluate it
        if isinstance(value, str) and any(op_char in value for op_char in ['+', '-', '*', '/', '%', '**']):
            try:
                value = self._safe_eval_expression(value)
            except:
                # If evaluation fails, keep as string
                pass

        # Store in context
        context.set(node.var_name, value)

        # Add to history
        context.add_history(
            step_type="assignment",
            description=f"{node.var_name} = {value}",
            result=value
        )

        return value

    def _execute_conditional(self, node: ConditionalNode, context: ExecutionContext) -> Any:
        """Execute a conditional statement."""
        # Evaluate condition using LLM
        condition_result = self._evaluate_condition(node.condition, context)

        # Execute appropriate branch
        if condition_result:
            for child_node in node.then_block:
                self._execute_node(child_node, context)
        else:
            for child_node in node.else_block:
                self._execute_node(child_node, context)

        # Add to history
        context.add_history(
            step_type="conditional",
            description=f"if {node.condition}",
            result=f"branch: {'then' if condition_result else 'else'}"
        )

        return condition_result

    def _execute_loop(self, node: LoopNode, context: ExecutionContext) -> Any:
        """Execute a loop with bounded iterations."""
        iterations = 0
        max_iterations = node.max_iterations

        # Extract loop variable name for 'for' loops
        loop_var = None
        if node.loop_type == "for":
            # Condition is like "i in range(10)" - extract variable name
            if " in " in node.condition:
                loop_var = node.condition.split(" in ")[0].strip()

        while iterations < max_iterations:
            # Bind loop variable for 'for' loops
            if loop_var:
                context.set(loop_var, iterations)

            # Check loop condition
            if node.loop_type == "while":
                should_continue = self._evaluate_condition(node.condition, context)
                if not should_continue:
                    break

            # Execute loop body
            for child_node in node.body:
                self._execute_node(child_node, context)

            iterations += 1

            # For 'for' loops, we just run max_iterations times
            if node.loop_type == "for":
                pass  # Continue until max_iterations

        # Add to history
        context.add_history(
            step_type="loop",
            description=f"{node.loop_type} loop: {node.condition}",
            result=f"completed {iterations} iterations"
        )

        return iterations

    def _evaluate_condition(self, condition: str, context: ExecutionContext) -> bool:
        """
        Evaluate a condition using the LLM.

        Args:
            condition: Condition string to evaluate
            context: Current execution context

        Returns:
            Boolean result
        """
        # Resolve any variable references in the condition
        resolved_condition = self._resolve_string_variables(condition, context)

        # Build prompt for LLM
        system_prompt = """You are evaluating conditions in code execution.
Given a condition and the current variable values, determine if the condition is true or false.
Respond with ONLY "true" or "false"."""

        context_str = json.dumps(context.variables, indent=2)
        user_message = f"""Condition: {resolved_condition}

Current variables:
{context_str}

Is the condition true or false? Respond with only "true" or "false"."""

        messages = [{"role": "user", "content": user_message}]

        response = call_bedrock_model(
            client=self.client,
            model_id=self.model_id,
            messages=messages,
            system=system_prompt,
            max_tokens=10,
            temperature=0.0
        )

        result_text = extract_text_from_response(response).strip().lower()
        usage = get_token_usage(response)

        # Update token usage
        self.total_usage["input_tokens"] += usage["input_tokens"]
        self.total_usage["output_tokens"] += usage["output_tokens"]

        return "true" in result_text

    def _resolve_arguments(self, arguments: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Resolve variable references in arguments."""
        resolved = {}
        for key, value in arguments.items():
            resolved[key] = self._resolve_value(value, context)
        return resolved

    def _safe_eval_expression(self, expr: str) -> Any:
        """Safely evaluate an arithmetic expression using AST parsing."""
        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif isinstance(node, ast.BinOp) and type(node.op) in self._SAFE_OPS:
                return self._SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.UnaryOp) and type(node.op) in self._SAFE_OPS:
                return self._SAFE_OPS[type(node.op)](_eval(node.operand))
            else:
                raise ValueError(f"Unsafe or unsupported expression: {ast.dump(node)}")

        try:
            return _eval(ast.parse(expr, mode='eval').body)
        except:
            # If evaluation fails, return the original string
            raise

    def _resolve_value(self, value: Any, context: ExecutionContext) -> Any:
        """Resolve a value, replacing variable references."""
        if isinstance(value, str):
            # Check if it's a variable reference (starts with $)
            if value.startswith("$"):
                var_name = value[1:]
                return context.get(var_name, value)
            else:
                # Try to resolve any embedded variables
                return self._resolve_string_variables(value, context)
        elif isinstance(value, list):
            return [self._resolve_value(v, context) for v in value]
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        else:
            return value

    def _resolve_string_variables(self, text: str, context: ExecutionContext) -> str:
        """Resolve variable references in a string using word boundaries."""
        result = text
        # Sort by length descending to avoid partial replacements
        for var_name in sorted(context.variables.keys(), key=len, reverse=True):
            var_value = str(context.variables[var_name])
            # Only replace whole-word occurrences using word boundaries
            result = re.sub(r'\b' + re.escape(var_name) + r'\b', var_value, result)
        return result
