# PseudoAct - Comprehensive Code Review

**Reviewer:** Claude Code (Comprehensive Analysis)
**Date:** 2026-03-13
**Version:** 0.1.0
**Test Status:** 55/55 passing (0.29s)

---

## Summary

PseudoAct is a two-phase LLM agent execution framework that separates planning from execution to improve token efficiency and enable structured control flow. In Phase 1, Claude Sonnet 4.6 synthesizes a Python-like pseudocode plan with control structures (if/else, bounded loops) from a user query and available tools. In Phase 2, a custom AST parser converts the pseudocode into executable nodes, which are then executed step-by-step by a control-flow executor using Claude Haiku 4.5 for individual decisions (like condition evaluation). The framework includes a ReAct baseline for comparison, a pluggable tool system (Calculator, Search, GetFact), and comprehensive test coverage with mocked AWS Bedrock calls. The design aims to achieve ≥30% token savings compared to traditional ReAct approaches by using expensive models for planning and cheap models for execution, though actual production validation would require real Bedrock access. The codebase is well-structured with clean separation of concerns, but has critical bugs in variable resolution, loop handling, and security vulnerabilities that must be fixed before production use.

---

## Run Results

### Test Execution
All 55 tests passed successfully in 0.29 seconds:

```bash
$ python3 -m pytest tests/ -v
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-7.2.1, pluggy-1.0.0+repack
collected 55 items

tests/test_executor.py - 11 tests PASSED (tool calls, conditionals, loops, context)
tests/test_parser.py - 12 tests PASSED (AST parsing, assignments, control flow)
tests/test_synthesizer.py - 8 tests PASSED (plan generation, extraction, saving)
tests/test_tools.py - 24 tests PASSED (calculator, search, facts, registry)

============================== 55 passed in 0.29s
```

### What Was Tested
- ✅ Parser: Assignments, tool calls, conditionals, loops, nested structures, variable references, edge cases
- ✅ Executor: Tool execution, variable resolution, conditional branching, loop bounds, history tracking
- ✅ Synthesizer: Plan generation, pseudocode extraction, system prompts, file persistence
- ✅ Tools: Calculator operations (basic math, sqrt, power), search mock, fact retrieval, registry operations
- ✅ Edge cases: Empty plans, invalid syntax, unknown tools, loop iteration limits

### What Was NOT Tested
- ❌ Real AWS Bedrock integration (all tests use mocked clients)
- ❌ Demo script execution (requires AWS credentials)
- ❌ Benchmark script execution (requires AWS credentials)
- ❌ Token efficiency claims (≥30% savings not validated)
- ❌ End-to-end integration with real LLM responses
- ❌ Method calls like `list.append()` (mentioned in README but not covered)
- ❌ While loops with max_iterations extraction
- ❌ Arithmetic expression evaluation in assignments

### Dependencies
- boto3 ≥1.28.0 (AWS Bedrock client)
- pytest ≥7.4.0 (testing framework)
- pytest-cov ≥4.1.0 (coverage reporting)

All dependencies were pre-installed in the test environment. Installation via pip/pip3 was not available but tests ran successfully.

---

## Architecture

### High-Level Design
```
User Query + Tools
        │
        ▼
┌───────────────────┐
│ PlanSynthesizer   │  Phase 1: Synthesis (Sonnet 4.6)
│ synthesizer.py    │  • Generate Python-like pseudocode
│                   │  • Extract from markdown code blocks
└────────┬──────────┘  • Save plan to disk (optional)
         │
         ▼
┌───────────────────┐
│ PseudocodeParser  │  Phase 2: Parsing
│ parser.py         │  • Python AST parsing
│                   │  • Convert to custom node tree
└────────┬──────────┘  • Extract control flow structures
         │
         ▼
┌───────────────────┐
│ PlanExecutor      │  Phase 3: Execution (Haiku 4.5)
│ executor.py       │  • Walk AST nodes
│                   │  • Execute tools via registry
│                   │  • Evaluate conditions with LLM
│                   │  • Track variables in context
└────────┬──────────┘  • Enforce loop bounds
         │
         ▼
    Result + Metrics
```

### Module Structure

**Core Package** (`pseudoact/`, 8 files, ~1,280 lines)
- `__init__.py` (95 lines): Public API, `run_pseudoact()` and `run_react()` functions
- `synthesizer.py` (164 lines): Sonnet-based plan generation
- `parser.py` (240 lines): AST parser for pseudocode → node tree conversion
- `executor.py` (246 lines): Control-flow executor with context management
- `react.py` (183 lines): Traditional ReAct baseline for benchmarking
- `tools.py` (197 lines): Tool registry and 3 built-in tools
- `context.py` (53 lines): Execution context for variables and history
- `utils.py` (103 lines): Bedrock API client utilities

**Tests** (`tests/`, 4 files, 55 tests)
- `test_parser.py` (175 lines, 12 tests): AST parsing validation
- `test_executor.py` (188 lines, 11 tests): Execution engine testing
- `test_synthesizer.py` (197 lines, 8 tests): Plan synthesis testing
- `test_tools.py` (205 lines, 24 tests): Tool implementation testing

**Supporting Files**
- `benchmark.py` (227 lines): PseudoAct vs ReAct comparison on 6 tasks
- `demo/run_demo.py` (127 lines): Interactive demo with 3 examples
- `README.md` (290 lines): Comprehensive documentation
- `requirements.txt` (10 lines): Minimal dependencies

### Key Design Decisions

1. **Two-Model Architecture**: Sonnet 4.6 for planning (expensive, smart) + Haiku 4.5 for execution (cheap, fast)
   - **Rationale**: Amortize expensive reasoning across multiple cheap execution steps
   - **Trade-off**: Adds complexity, no dynamic replanning in V1

2. **Python AST Parsing**: Leverages Python's built-in `ast` module instead of custom grammar
   - **Rationale**: Claude naturally generates valid Python syntax, no parser development needed
   - **Trade-off**: Limited to Python semantics, some constructs silently ignored

3. **Mandatory Loop Bounds**: Every loop requires explicit `max_iterations` parameter
   - **Rationale**: Prevents infinite loops, provides safety guarantee
   - **Trade-off**: Requires upfront iteration count planning

4. **LLM Condition Evaluation**: Uses Haiku to evaluate if/while conditions
   - **Rationale**: Handle complex conditions referencing variables
   - **Trade-off**: Adds LLM call overhead, introduces non-determinism, wasteful for simple conditions

5. **Plan Persistence**: Plans saved to `plans/plan.md` by default
   - **Rationale**: Enables debugging and plan inspection
   - **Trade-off**: File overwrites on each run, no versioning

6. **No Dynamic Replanning**: V1 executes initial plan without recovery
   - **Rationale**: Scope limitation for V1 release
   - **Trade-off**: Total failure if plan is flawed

7. **Variable References via `$` Prefix**: Variables marked as `$varname` in expressions
   - **Rationale**: Simple convention for distinguishing literals from references
   - **Trade-off**: Fragile string-based resolution, substring corruption bugs

### Architecture Strengths
- ✅ Clean separation of concerns (synthesis, parse, execute)
- ✅ Well-defined interfaces between components
- ✅ Dependency injection for testability (client mocking)
- ✅ Pluggable tool system via registry pattern
- ✅ Bounded loops as enforced safety property
- ✅ Shared execution context for variable persistence

### Architecture Weaknesses
- ❌ `PlanExecutor.total_usage` is instance state → not thread-safe
- ❌ `run_pseudoact()` hardcodes save path, overwrites on each call
- ❌ No `setup.py`/`pyproject.toml` → not pip-installable
- ❌ LLM condition evaluation wasteful for simple expressions
- ❌ No error recovery or replanning mechanism
- ❌ Variable resolution uses naive string replacement → bugs

---

## Code Quality

### Overall Assessment: **B- (74/100)**

**Strengths:**
- Clean module organization with clear responsibilities
- Comprehensive test coverage (55 tests, 100% pass rate)
- Consistent PEP 8 style and naming conventions
- Good use of dependency injection for testability
- Proper docstrings on public methods
- Type hints on function signatures

**Weaknesses:**
- Critical security vulnerability in calculator tool (`eval()`)
- Multiple correctness bugs in variable resolution
- Missing error handling for external API calls
- No logging infrastructure
- Hardcoded configuration values
- Fragile string-based variable resolution

### Module-by-Module Analysis

#### `parser.py` (240 lines) - Grade: C+

**Issues:**
1. **Silent statement dropping**: `AugAssign` (`x += 1`) returns `None` and is silently ignored (line 113-128)
   ```python
   # _process_statement has no case for ast.AugAssign
   x += 1  # Silently disappears, no error raised
   ```

2. **Arithmetic expressions become strings**: BinOp expressions stored as unparsed strings (line 221), not evaluated
   ```python
   # x = x + 1 stores "x + 1" string, not computed result
   # After substitution: "5 + 1" string, not 6
   ```

3. **Loop variables never bound**: `for i in range(...)` doesn't set `i` in context, so loop body references fail

4. **While loops always fail**: `_extract_max_iterations()` always returns `None` for while loops (line 210-212), causing immediate error

**Strengths:**
- Clean AST walking with proper visitor pattern
- Good test coverage of parsing logic
- Proper error handling for syntax errors (line 98-99)
- Support for nested conditionals

#### `executor.py` (246 lines) - Grade: C

**Critical Bugs:**
1. **Variable substitution corrupts strings** (line 239-245):
   ```python
   # _resolve_string_variables does naive str.replace()
   # Context: i=0, items=[]
   # _resolve_string_variables("items", ctx) → "0tems" (BUG!)
   ```
   Any single-letter variable corrupts unrelated strings.

2. **Instance state accumulation**: `self.total_usage` accumulates across calls (line 32, 48), not thread-safe

3. **No error handling on tool execution**: Line 83 has no try/except, tool failures crash executor

4. **LLM condition evaluation wasteful**: Calls Haiku for simple conditions like `x > 5` (line 168-213) that Python could evaluate locally

**Strengths:**
- Clean AST node execution with visitor pattern
- Good history tracking in ExecutionContext
- Proper variable resolution for `$var_name` references
- Loop bound enforcement works correctly

#### `synthesizer.py` (164 lines) - Grade: B

**Issues:**
1. **`_save_plan` crashes on bare filenames** (line 152):
   ```python
   os.makedirs(os.path.dirname("plan.md"), ...)  # dirname("plan.md") = ""
   # os.makedirs("") raises FileNotFoundError
   ```

2. **Fallback extracts entire response**: If no code fence, returns full LLM output (line 148) including explanations

3. **No validation of extracted code**: Doesn't verify pseudocode is parseable before returning

**Strengths:**
- Clean system prompt construction
- Good code fence extraction logic
- Proper token usage tracking
- File saving with metadata

#### `react.py` (183 lines) - Grade: B-

**Issues:**
1. **Multi-line JSON parsing fails** (line 172-177):
   ```python
   # Only captures first line of Arguments:
   # If JSON spans multiple lines, json.loads fails silently → {}
   ```

2. **Fragile line-by-line parsing**: Breaks on format variations or multi-line content

3. **No validation of parsed actions**: Accepts malformed responses without error

**Strengths:**
- Clear ReAct loop implementation
- Good conversation history management
- Proper max iteration handling
- Correct use of Sonnet model throughout

#### `tools.py` (197 lines) - Grade: D

**CRITICAL:**
1. **Unsafe `eval()` usage** (line 65):
   ```python
   result = eval(expression, {"__builtins__": {}}, safe_dict)
   # SECURITY RISK: Code injection possible despite restricted builtins
   # Attacker can use safe_dict functions (sqrt, pow) for complex exploits
   ```

**Issues:**
2. **Mock tools not clearly labeled**: Search and GetFact are stubs with hardcoded data (line 90-106, 131-157)

3. **No input validation**: Tool arguments passed directly to execution without checks

**Strengths:**
- Clean Tool base class and registry pattern
- Good separation of concerns
- Comprehensive test coverage
- Error handling in calculator (line 67-68)

#### `context.py` (53 lines) - Grade: A

**Excellent:** Simple, focused, correct implementation with no issues found.

#### `utils.py` (103 lines) - Grade: C+

**Issues:**
1. **Hardcoded model IDs and region** (line 11-13): No environment variable support

2. **No error handling**: `call_bedrock_model()` has no try/except for API failures (line 24-62)

3. **No retry logic**: Single transient error crashes execution

**Strengths:**
- Clean API abstraction
- Good response parsing
- Proper token usage extraction

### Error Handling Analysis

**Missing Error Handling:**
- Bedrock API calls (network, auth, throttling, quotas)
- Tool execution failures
- File I/O errors in plan saving
- Parser errors beyond SyntaxError

**Good Error Handling:**
- Calculator tool catches exceptions (tools.py:67)
- Parser raises ValueError with context (parser.py:99)
- ToolRegistry raises on unknown tools (tools.py:173)

### Security Issues
1. **CRITICAL**: `eval()` in CalculatorTool (tools.py:65)
2. **HIGH**: No input sanitization on tool parameters
3. **MEDIUM**: Plans executed without validation

### Code Style
- ✅ PEP 8 compliant
- ✅ Consistent snake_case naming
- ✅ Good docstrings
- ❌ Magic numbers not extracted to constants
- ❌ Inconsistent string formatting (f-strings vs concatenation)
- ❌ No structured logging

---

## Issues Found

### Critical (Security & Correctness)

1. **CRITICAL: Unsafe `eval()` in Calculator**
   - **File**: `tools.py:65`
   - **Code**: `result = eval(expression, {"__builtins__": {}}, safe_dict)`
   - **Risk**: Code injection vulnerability despite restricted builtins
   - **Impact**: Arbitrary code execution if attacker controls calculator expressions
   - **Example**: Attacker could exploit `safe_dict` functions or use subclass tricks
   - **Fix**: Replace with `simpleeval` or `asteval` library

2. **CRITICAL: Variable Substitution Corruption**
   - **File**: `executor.py:239-245`
   - **Code**: `result = result.replace(var_name, str(var_value))`
   - **Bug**: Naive string replacement corrupts substrings
   - **Example**: Context `i=0, items=[]` → `"items"` becomes `"0tems"`
   - **Impact**: Any single-letter variable name breaks execution
   - **Fix**: Use regex with word boundaries `\b` or proper tokenization

3. **CRITICAL: While Loops Always Fail**
   - **File**: `parser.py:210-212`
   - **Code**: `# For while loops, we need max_iterations... return None`
   - **Bug**: Always returns `None`, then line 183 raises error
   - **Impact**: Documentation claims while loops work, but they never execute
   - **Fix**: Implement max_iterations extraction from comment or reject while loops

4. **CRITICAL: Method Calls Fail to Parse**
   - **File**: `parser.py:152-153`
   - **Bug**: `ValueError: Only simple function calls supported` for `list.append()`
   - **Impact**: README examples like `results.append(item)` don't work
   - **Evidence**: README line 211, synthesizer prompt line 113 both show append
   - **Fix**: Either support method calls or update prompts to avoid them

5. **HIGH: No Bedrock API Error Handling**
   - **File**: `utils.py:56-62`
   - **Bug**: No try/except around `client.invoke_model()`
   - **Impact**: Network errors, throttling, auth failures crash execution
   - **Fix**: Add retry decorator with exponential backoff

6. **HIGH: Tool Execution Failures Crash Executor**
   - **File**: `executor.py:83`
   - **Bug**: No try/except around `self.tool_registry.execute_tool()`
   - **Impact**: Any tool error terminates entire plan execution
   - **Fix**: Wrap in try/except, add error recovery

### High (Functionality)

7. **HIGH: Arithmetic Expressions Become Strings**
   - **File**: `parser.py:221`
   - **Bug**: BinOp expressions stored as unparsed strings via `ast.unparse()`
   - **Example**: `x = x + 1` stores `"x + 1"`, after substitution `"5 + 1"` (string, not 6)
   - **Impact**: Loop counters don't work, no arithmetic in plans
   - **Fix**: Evaluate expressions with safe eval in execution

8. **HIGH: Loop Variables Never Bound**
   - **File**: `executor.py:137-166`
   - **Bug**: `for i in range(...)` never sets `i` in context
   - **Impact**: Loop bodies referencing `i` get `$i` (undefined)
   - **Fix**: Set loop variable in context each iteration

9. **HIGH: AugAssign Silently Dropped**
   - **File**: `parser.py:113-128`
   - **Bug**: No case for `ast.AugAssign`, returns `None`, silently ignored
   - **Example**: `x += 1` disappears without error
   - **Impact**: Common loop counter pattern doesn't work
   - **Fix**: Add AugAssign handler or raise error

10. **HIGH: `_save_plan` Crashes on Bare Filenames**
    - **File**: `synthesizer.py:152`
    - **Bug**: `os.makedirs(os.path.dirname("plan.md"), ...)` → `os.makedirs("")` → FileNotFoundError
    - **Impact**: Crashes if user specifies filename without directory
    - **Fix**: Check `if dir_path: os.makedirs(...)`

11. **HIGH: LLM Condition Evaluation Wasteful**
    - **File**: `executor.py:168-213`
    - **Bug**: Calls Haiku for all conditions, even simple ones like `x > 5`
    - **Impact**: Adds latency, tokens, cost, non-determinism for no benefit
    - **Fix**: Try native eval first, fall back to LLM for semantic conditions

12. **HIGH: Instance State Accumulation**
    - **File**: `executor.py:32, 48`
    - **Bug**: `self.total_usage` accumulates across calls
    - **Impact**: Not thread-safe, token counts bleed between runs
    - **Fix**: Make `total_usage` local to `execute_plan()` method

### Medium (Quality & Reliability)

13. **MEDIUM: Multi-line JSON Parsing Fails**
    - **File**: `react.py:172-177`
    - **Bug**: `Arguments:` parsing only captures one line
    - **Impact**: Multi-line JSON from Sonnet silently becomes `{}`
    - **Fix**: Collect lines until next keyword prefix

14. **MEDIUM: Extract Pseudocode Too Permissive**
    - **File**: `synthesizer.py:148`
    - **Bug**: Returns entire response if no code fence found
    - **Impact**: Explanation text goes to parser, causes SyntaxError
    - **Fix**: Require code fence or raise error

15. **MEDIUM: No Logging Infrastructure**
    - **File**: All modules
    - **Impact**: Debugging production issues impossible
    - **Fix**: Add structured logging with levels

16. **MEDIUM: Hardcoded Configuration**
    - **File**: `utils.py:11-13`
    - **Bug**: Model IDs and region hardcoded, no env var support
    - **Impact**: Can't switch models/regions without code changes
    - **Fix**: Add environment variable support

17. **MEDIUM: No Plan Validation**
    - **File**: `__init__.py:58`
    - **Bug**: No check that tools exist or loops have bounds before execution
    - **Impact**: Runtime failures instead of early validation
    - **Fix**: Add validation step after parsing

18. **MEDIUM: No Token Budget Management**
    - **File**: `synthesizer.py`, `executor.py`
    - **Bug**: No tracking of cumulative tokens or budget limits
    - **Impact**: Can exceed Bedrock context window
    - **Fix**: Add token counting and budget warnings

### Low (Polish & Best Practices)

19. **LOW: Hardcoded Save Path**
    - **File**: `__init__.py:53`
    - **Bug**: `save_path="plans/plan.md"` overwrites on each call
    - **Impact**: Can't preserve multiple plans
    - **Fix**: Add timestamp or task ID to filename

20. **LOW: No Package Installation**
    - **File**: None (missing file)
    - **Bug**: No `setup.py` or `pyproject.toml`
    - **Impact**: Can't `pip install -e .`, requires PYTHONPATH
    - **Fix**: Add pyproject.toml with build system

21. **LOW: No .gitignore**
    - **File**: None (missing file)
    - **Bug**: `.pytest_cache/`, `__pycache__/` committed to repo
    - **Impact**: Pollutes version control
    - **Fix**: Add .gitignore with Python standard excludes

22. **LOW: Mock Tools Not Labeled**
    - **File**: `tools.py:73-106, 108-158`
    - **Bug**: Search and GetFact are stubs but look like real implementations
    - **Impact**: Users might think these are functional
    - **Fix**: Add "Mock" to class names, update docstrings

23. **LOW: Benchmark Import Fragility**
    - **File**: `benchmark.py:8`
    - **Bug**: `from pseudoact import ...` requires CWD = project root
    - **Impact**: Breaks if run from different directory
    - **Fix**: Add sys.path manipulation like demo script

24. **LOW: Test Coverage Gaps**
    - **File**: `tests/test_executor.py:105-119`
    - **Bug**: `test_execute_plan_complete` doesn't verify result correctness
    - **Impact**: Bug in calculator call not caught by tests
    - **Fix**: Add assertions on actual computed values

25. **LOW: No conftest.py**
    - **File**: None (missing file)
    - **Bug**: Every test file has `sys.path.insert` boilerplate
    - **Impact**: Code duplication, harder to maintain
    - **Fix**: Add conftest.py with sys.path setup

---

## Recommendations

### Immediate Fixes (P0 - Must Fix Before Any Use)

1. **Replace `eval()` with Safe Alternative** ⚠️ CRITICAL
   - **File**: `tools.py:65`
   - **Action**: Install `simpleeval` library and replace:
     ```python
     from simpleeval import simple_eval
     result = simple_eval(expression, functions=safe_dict)
     ```
   - **Rationale**: Eliminate code injection vulnerability
   - **Effort**: 30 minutes
   - **Test**: Add security test cases for injection attempts

2. **Fix Variable Substitution Bug** ⚠️ CRITICAL
   - **File**: `executor.py:239-245`
   - **Action**: Use regex word boundaries:
     ```python
     import re
     for var_name, var_value in context.variables.items():
         result = re.sub(r'\b' + re.escape(var_name) + r'\b',
                        str(var_value), result)
     ```
   - **Rationale**: Prevent substring corruption
   - **Effort**: 1 hour
   - **Test**: Add test for single-letter variables like `i`

3. **Fix or Disable While Loops** ⚠️ CRITICAL
   - **File**: `parser.py:210-212`
   - **Option A**: Parse `# max_iterations: N` comment
   - **Option B**: Remove while from documentation
   - **Rationale**: Feature claims are false currently
   - **Effort**: 2 hours
   - **Test**: Add while loop tests with max_iterations

4. **Fix Method Call Parsing** ⚠️ CRITICAL
   - **File**: `parser.py:152`, `synthesizer.py:113`
   - **Option A**: Add method call support to parser
   - **Option B**: Update system prompt to avoid methods
   - **Recommendation**: Option B (simpler) - Use `items = items + [item]`
   - **Rationale**: Align README examples with capabilities
   - **Effort**: 1 hour
   - **Test**: Verify README examples work

5. **Add Bedrock Error Handling** ⚠️ HIGH
   - **File**: `utils.py:56-62`
   - **Action**: Add retry decorator:
     ```python
     from tenacity import retry, stop_after_attempt, wait_exponential
     @retry(stop=stop_after_attempt(3),
            wait=wait_exponential(min=2, max=10))
     def call_bedrock_model(...):
     ```
   - **Rationale**: Handle transient failures gracefully
   - **Effort**: 1 hour
   - **Test**: Mock network failures

6. **Add Tool Execution Error Handling** ⚠️ HIGH
   - **File**: `executor.py:83`
   - **Action**: Wrap in try/except:
     ```python
     try:
         result = self.tool_registry.execute_tool(...)
     except Exception as e:
         context.add_history("tool_error", node.tool_name, str(e))
         raise PlanExecutionError(f"Tool {node.tool_name} failed: {e}")
     ```
   - **Rationale**: Fail gracefully with context
   - **Effort**: 1 hour
   - **Test**: Mock tool failures

### Short-Term Improvements (P1 - Next Week)

7. **Fix Arithmetic Expression Evaluation**
   - **File**: `executor.py:98-113`
   - **Action**: When value is string, try safe eval:
     ```python
     try:
         value = eval(node.value, {"__builtins__": {}},
                     context.variables)
     except:
         value = node.value  # Keep as string
     ```
   - **Rationale**: Enable loop counters and calculations
   - **Effort**: 2 hours

8. **Bind Loop Variables in Context**
   - **File**: `executor.py:137-166`
   - **Action**: Extract loop var name from condition, set in context
   - **Rationale**: Make loop variable accessible in body
   - **Effort**: 2 hours

9. **Add Native Condition Evaluation**
   - **File**: `executor.py:168-213`
   - **Action**: Try native eval first, fall back to LLM:
     ```python
     try:
         result = eval(resolved_condition, {"__builtins__": {}},
                      context.variables)
         return bool(result)
     except:
         return self._llm_evaluate_condition(...)
     ```
   - **Rationale**: Save tokens, reduce latency, improve determinism
   - **Effort**: 3 hours

10. **Fix Instance State Bug**
    - **File**: `executor.py:32, 48`
    - **Action**: Move `total_usage` initialization to line 48
    - **Rationale**: Thread safety, correct per-call metrics
    - **Effort**: 15 minutes

11. **Add Logging Infrastructure**
    - **File**: All modules
    - **Action**: Add structured logging:
      ```python
      import logging
      logger = logging.getLogger(__name__)
      logger.info("Plan synthesis", extra={"query": query})
      ```
    - **Rationale**: Essential for debugging production issues
    - **Effort**: 4 hours

12. **Add Configuration Management**
    - **File**: New `config.py`
    - **Action**: Environment variable support:
      ```python
      SONNET_MODEL = os.getenv("PSEUDOACT_SONNET_MODEL",
                               "us.anthropic.claude-sonnet-4-6...")
      ```
    - **Rationale**: Enable model switching without code changes
    - **Effort**: 2 hours

### Medium-Term (P2 - Next Sprint)

13. **Fix AugAssign Support**
    - **File**: `parser.py:113-128`
    - **Action**: Add case for `ast.AugAssign`
    - **Effort**: 3 hours

14. **Fix _save_plan Directory Handling**
    - **File**: `synthesizer.py:152`
    - **Action**: Check dirname before makedirs
    - **Effort**: 15 minutes

15. **Fix Multi-line JSON Parsing**
    - **File**: `react.py:172-177`
    - **Action**: Collect multi-line content
    - **Effort**: 2 hours

16. **Add Plan Validation**
    - **File**: New `validator.py`
    - **Action**: Validate tools exist, loops bounded, variables defined
    - **Effort**: 4 hours

17. **Add Token Budget Management**
    - **File**: `executor.py`, `synthesizer.py`
    - **Action**: Track cumulative tokens, warn on budget approach
    - **Effort**: 3 hours

18. **Add Package Installation**
    - **File**: New `pyproject.toml`
    - **Action**: Standard Python package structure
    - **Effort**: 1 hour

19. **Add .gitignore**
    - **File**: New `.gitignore`
    - **Action**: Python standard excludes
    - **Effort**: 10 minutes

20. **Fix Test Coverage Gaps**
    - **File**: `tests/test_executor.py`
    - **Action**: Assert on actual computed values
    - **Effort**: 2 hours

### Long-Term (P3 - Future Releases)

21. **Implement Dynamic Replanning**
    - On tool/condition failures, trigger re-synthesis
    - **Effort**: 2 weeks

22. **Add True Parallel Execution**
    - Detect independent nodes, use asyncio/threads
    - **Effort**: 1 week

23. **Expand Parser Support**
    - Handle try/except, with statements, list comprehensions
    - **Effort**: 2 weeks

24. **Add Plan Caching**
    - LRU cache for (query, tools) → plan
    - **Effort**: 1 week

25. **Build Observability Dashboard**
    - Metrics visualization, execution flow, alerting
    - **Effort**: 3 weeks

26. **Validate Token Efficiency Claims**
    - Run full benchmark with real Bedrock on 100+ tasks
    - **Effort**: 1 week

### Summary

**Production Readiness: 35%**
- Must fix 6 critical issues (items 1-6) before any real use
- Must add logging and configuration (items 11-12) for production
- Must validate token efficiency claim (item 26) to support marketing

**Research Readiness: 85%**
- Excellent foundation for research and prototyping
- Clean architecture for exploring structured planning
- Good baseline comparison with ReAct

**Recommended Immediate Actions:**
1. Fix eval() security vulnerability (30 min)
2. Fix variable substitution bug (1 hour)
3. Fix while loops or remove from docs (2 hours)
4. Add error handling for Bedrock + tools (2 hours)
5. Fix method call documentation mismatch (1 hour)

**Total time to minimal production readiness: ~2-3 weeks**

---

## Conclusion

**Overall Grade: B- (74/100)**

PseudoAct demonstrates innovative thinking in LLM agent architecture with its two-phase planning/execution approach. The separation of concerns is clean, the test coverage is comprehensive, and the codebase follows good Python practices. The use of Python's AST for parsing is pragmatic and elegant.

However, the project has **critical bugs that prevent production use**: unsafe eval(), variable substitution corruption, missing error handling, and mismatches between documentation and implementation. The LLM-based condition evaluation undermines the token efficiency claims for conditional-heavy workloads.

**Key Strengths:**
- ✅ Novel two-phase architecture with clear benefits for loop-heavy tasks
- ✅ Clean code organization and separation of concerns
- ✅ Comprehensive test suite (55 tests, 100% pass)
- ✅ Good documentation and examples
- ✅ Pluggable tool system for extensibility

**Key Weaknesses:**
- ❌ Critical security vulnerability (eval)
- ❌ Critical correctness bugs (variable resolution, loops)
- ❌ Missing error handling for external APIs
- ❌ Documentation-implementation mismatches
- ❌ No logging or observability

**Recommendation:**
1. **For Research/Prototyping**: Excellent foundation, use as-is with awareness of limitations
2. **For Production**: Fix critical issues (1-6), add logging (11), then re-evaluate
3. **For Token Efficiency Claims**: Run real Bedrock benchmarks (26) before making public claims

The concept is sound and the implementation is 70% there. With 2-3 weeks of focused work on critical fixes, this could be production-ready. As research prototype, it's very good.
