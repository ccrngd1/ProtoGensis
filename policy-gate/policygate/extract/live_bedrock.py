"""Gated live extraction ([bedrock] extra, CC-D2). NEVER run by tests or demos.

boto3 is imported lazily and only here. The command requires --max-usd; without
it the CLI returns exit 2 before this module is imported. Before any model call
the budget is checked; crossing --max-usd aborts (exit 5), keeping the partial
cache marked ABORTED_BUDGET.
"""

import sys


def run_live(ns):
    # --max-usd was already validated in cli.py (exit 2 otherwise), so reaching
    # here means a budget is set and the operator has opted into a paid run.
    try:
        import boto3  # noqa: F401  (lazy; only dependency of the [bedrock] extra)
    except ImportError:
        print("error: live extraction requires the [bedrock] extra (boto3); "
              "install with `pip install -e '.[bedrock]'`", file=sys.stderr)
        return 2
    print("live extraction is a CC-gated path (CC-D2) and is not implemented in v1; "
          "no paid call was made.", file=sys.stderr)
    return 2
