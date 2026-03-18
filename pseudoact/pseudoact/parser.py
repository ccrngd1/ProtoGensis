"""
Parser for pseudocode plans using Python's AST module.
"""

import ast
from typing import Any, List, Dict, Union


class PlanNode:
    """Base class for plan AST nodes."""

    def __init__(self, node_type: str):
        self.node_type = node_type


class ToolCallNode(PlanNode):
    """Represents a tool call."""

    def __init__(self, tool_name: str, arguments: Dict[str, Any], result_var: str = None):
        super().__init__("tool_call")
        self.tool_name = tool_name
        self.arguments = arguments
        self.result_var = result_var

    def __repr__(self):
        return f"ToolCall({self.tool_name}, args={self.arguments}, result={self.result_var})"


class AssignmentNode(PlanNode):
    """Represents a variable assignment."""

    def __init__(self, var_name: str, value: Any):
        super().__init__("assignment")
        self.var_name = var_name
        self.value = value

    def __repr__(self):
        return f"Assignment({self.var_name} = {self.value})"


class ConditionalNode(PlanNode):
    """Represents an if/elif/else conditional."""

    def __init__(self, condition: str, then_block: List[PlanNode], else_block: List[PlanNode] = None):
        super().__init__("conditional")
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block or []

    def __repr__(self):
        return f"Conditional(if {self.condition})"


class LoopNode(PlanNode):
    """Represents a loop (for/while)."""

    def __init__(self, loop_type: str, condition: str, body: List[PlanNode], max_iterations: int):
        super().__init__("loop")
        self.loop_type = loop_type  # 'for' or 'while'
        self.condition = condition
        self.body = body
        self.max_iterations = max_iterations

    def __repr__(self):
        return f"Loop({self.loop_type}, max_iter={self.max_iterations})"


class CommentNode(PlanNode):
    """Represents a comment."""

    def __init__(self, text: str):
        super().__init__("comment")
        self.text = text

    def __repr__(self):
        return f"Comment({self.text[:30]}...)"


class PseudocodeParser:
    """
    Parses Python-like pseudocode into an executable AST.
    """

    def parse(self, pseudocode: str) -> List[PlanNode]:
        """
        Parse pseudocode into a list of plan nodes.

        Args:
            pseudocode: Python-like pseudocode string

        Returns:
            List of PlanNode objects
        """
        try:
            # Parse using Python's AST
            tree = ast.parse(pseudocode)
            return self._process_body(tree.body)
        except SyntaxError as e:
            raise ValueError(f"Invalid pseudocode syntax: {e}")

    def _process_body(self, statements: List[ast.stmt]) -> List[PlanNode]:
        """Process a list of AST statements."""
        nodes = []
        for stmt in statements:
            node = self._process_statement(stmt)
            if node:
                if isinstance(node, list):
                    nodes.extend(node)
                else:
                    nodes.append(node)
        return nodes

    def _process_statement(self, stmt: ast.stmt) -> Union[PlanNode, List[PlanNode], None]:
        """Process a single AST statement."""
        if isinstance(stmt, ast.Assign):
            return self._process_assignment(stmt)
        elif isinstance(stmt, ast.Expr):
            # Expression statement (e.g., function call without assignment)
            if isinstance(stmt.value, ast.Call):
                return self._process_function_call(stmt.value)
        elif isinstance(stmt, ast.If):
            return self._process_conditional(stmt)
        elif isinstance(stmt, (ast.For, ast.While)):
            return self._process_loop(stmt)
        elif isinstance(stmt, ast.Pass):
            return None  # Ignore pass statements

        return None

    def _process_assignment(self, stmt: ast.Assign) -> Union[PlanNode, List[PlanNode]]:
        """Process an assignment statement."""
        if len(stmt.targets) != 1:
            raise ValueError("Multiple assignment targets not supported")

        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            raise ValueError("Only simple variable assignments supported")

        var_name = target.id
        value = stmt.value

        # Check if it's a function call (tool call)
        if isinstance(value, ast.Call):
            return self._process_function_call(value, result_var=var_name)
        else:
            # Regular assignment
            evaluated_value = self._evaluate_expression(value)
            return AssignmentNode(var_name, evaluated_value)

    def _process_function_call(self, call: ast.Call, result_var: str = None) -> ToolCallNode:
        """Process a function call (tool call)."""
        if not isinstance(call.func, ast.Name):
            raise ValueError("Only simple function calls supported")

        tool_name = call.func.id
        arguments = {}

        # Process keyword arguments
        for keyword in call.keywords:
            arg_value = self._evaluate_expression(keyword.value)
            arguments[keyword.arg] = arg_value

        # Process positional arguments (if any)
        for i, arg in enumerate(call.args):
            arg_value = self._evaluate_expression(arg)
            arguments[f"arg{i}"] = arg_value

        return ToolCallNode(tool_name, arguments, result_var)

    def _process_conditional(self, stmt: ast.If) -> ConditionalNode:
        """Process an if statement."""
        condition = ast.unparse(stmt.test)
        then_block = self._process_body(stmt.body)
        else_block = self._process_body(stmt.orelse) if stmt.orelse else []

        return ConditionalNode(condition, then_block, else_block)

    def _process_loop(self, stmt: Union[ast.For, ast.While]) -> LoopNode:
        """Process a loop statement."""
        max_iterations = self._extract_max_iterations(stmt)

        # Set default max_iterations if not found (especially for while loops)
        if max_iterations is None:
            max_iterations = 100  # Default safety limit

        if isinstance(stmt, ast.For):
            loop_type = "for"
            condition = ast.unparse(stmt.target) + " in " + ast.unparse(stmt.iter)
        else:  # While
            loop_type = "while"
            condition = ast.unparse(stmt.test)

        body = self._process_body(stmt.body)

        return LoopNode(loop_type, condition, body, max_iterations)

    def _extract_max_iterations(self, stmt: Union[ast.For, ast.While]) -> int:
        """Extract max_iterations from a loop."""
        # Look for range(max_iterations=N) in for loops
        if isinstance(stmt, ast.For):
            if isinstance(stmt.iter, ast.Call):
                if isinstance(stmt.iter.func, ast.Name) and stmt.iter.func.id == "range":
                    # Check for max_iterations keyword
                    for keyword in stmt.iter.keywords:
                        if keyword.arg == "max_iterations":
                            return self._evaluate_expression(keyword.value)
                    # Check if it's just range(N)
                    if len(stmt.iter.args) == 1:
                        return self._evaluate_expression(stmt.iter.args[0])

        # For while loops, we need max_iterations in a comment or as a marker
        # For now, return None if not found
        return None

    def _evaluate_expression(self, expr: ast.expr) -> Any:
        """Safely evaluate an expression to extract its value or representation."""
        if isinstance(expr, ast.Constant):
            return expr.value
        elif isinstance(expr, ast.Name):
            return f"${expr.id}"  # Variable reference
        elif isinstance(expr, ast.BinOp):
            return ast.unparse(expr)
        elif isinstance(expr, ast.List):
            return [self._evaluate_expression(e) for e in expr.elts]
        elif isinstance(expr, ast.Dict):
            return {
                self._evaluate_expression(k): self._evaluate_expression(v)
                for k, v in zip(expr.keys, expr.values)
            }
        elif isinstance(expr, ast.Call):
            # Function call - return unparsed version
            return ast.unparse(expr)
        elif isinstance(expr, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
            return ast.unparse(expr)
        elif isinstance(expr, ast.Attribute):
            return ast.unparse(expr)
        elif isinstance(expr, ast.Subscript):
            return ast.unparse(expr)
        else:
            return ast.unparse(expr)
