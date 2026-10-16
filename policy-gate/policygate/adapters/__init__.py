"""Input adapters: both emit the same Event stream consumed by replay.

Event shapes (dicts):
  {"type": "turn", "role", "text", "principal", "provenance_source", "ts"}
  {"type": "call", "tool", "args", "ts"}
  {"type": "result", "tool", "ok", "text"}
"""
