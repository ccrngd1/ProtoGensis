"""HarnessGuard — agent harness bypass security tester (CoreBreak vulnerability class).

Tests whether an AI agent harness can have its tools triggered without the model
ever running. The architectural invariant under test:

    For every tool execution, exactly one unconsumed, unexpired, model-issued
    authorization exists whose bound fields match the call.

AUTHORIZED USE ONLY. See README.md.
"""

__version__ = "0.1.0"
