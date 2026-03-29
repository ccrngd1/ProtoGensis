#!/usr/bin/env python3
"""
Trace capture utility for CABAL agent executions.

Records agent tool calls, messages, and outputs as OpenAI-compatible
message format JSON. One file per execution.

Usage:
    python capture_trace.py --agent Main --task "Check heartbeat" --output traces/main-heartbeat-001.json
    python capture_trace.py --from-log agent.log --output traces/trace.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TraceCapture:
    """Captures and records agent execution traces."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def add_user_message(self, content: str) -> None:
        """Add a user message to the trace."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add an assistant message to the trace."""
        message: Dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result to the trace."""
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )

    def set_metadata(
        self,
        agent: str,
        task: str,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Set trace metadata."""
        self.metadata = {
            "agent": agent,
            "task": task,
            "timestamp": timestamp or datetime.now().isoformat(),
            **kwargs,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary format."""
        return {
            **self.metadata,
            "messages": self.messages,
        }

    def save(self, output_path: Path) -> None:
        """Save trace to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Trace saved to {output_path}")

    @classmethod
    def from_log(cls, log_content: str) -> "TraceCapture":
        """
        Parse a trace from agent log output.

        Expects log format with markers like:
        [USER] message
        [ASSISTANT] message
        [TOOL_CALL] function_name(args)
        [TOOL_RESULT] result
        """
        trace = cls()

        lines = log_content.strip().split("\n")
        current_tool_calls: List[Dict[str, Any]] = []
        current_content = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # User message
            if line.startswith("[USER]"):
                content = line.replace("[USER]", "").strip()
                trace.add_user_message(content)

            # Assistant message
            elif line.startswith("[ASSISTANT]"):
                if current_content and current_tool_calls:
                    trace.add_assistant_message(current_content, current_tool_calls)
                    current_tool_calls = []
                    current_content = ""

                current_content = line.replace("[ASSISTANT]", "").strip()

            # Tool call
            elif line.startswith("[TOOL_CALL]"):
                tool_call_str = line.replace("[TOOL_CALL]", "").strip()
                tool_call = cls._parse_tool_call(tool_call_str)
                if tool_call:
                    current_tool_calls.append(tool_call)

            # Tool result
            elif line.startswith("[TOOL_RESULT]"):
                result = line.replace("[TOOL_RESULT]", "").strip()
                if current_tool_calls:
                    tool_call_id = current_tool_calls[-1]["id"]
                    trace.add_tool_result(tool_call_id, result)

                # Flush assistant message with tool calls
                if current_content:
                    trace.add_assistant_message(current_content, current_tool_calls)
                    current_tool_calls = []
                    current_content = ""

        # Flush any remaining content
        if current_content:
            trace.add_assistant_message(
                current_content, current_tool_calls if current_tool_calls else None
            )

        return trace

    @staticmethod
    def _parse_tool_call(tool_call_str: str) -> Optional[Dict[str, Any]]:
        """Parse a tool call string like 'file_read(path="/root/.openclaw")'"""
        match = re.match(r"(\w+)\((.*)\)", tool_call_str)
        if not match:
            return None

        function_name = match.group(1)
        args_str = match.group(2)

        # Simple argument parsing (handles key="value" pairs)
        args = {}
        arg_pattern = re.compile(r'(\w+)="([^"]*)"')
        for arg_match in arg_pattern.finditer(args_str):
            key = arg_match.group(1)
            value = arg_match.group(2)
            args[key] = value

        return {
            "id": f"call_{abs(hash(tool_call_str)) % 10000:04d}",
            "type": "function",
            "function": {
                "name": function_name,
                "arguments": json.dumps(args),
            },
        }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Capture CABAL agent execution traces")
    parser.add_argument("--agent", help="Agent name (e.g., Main, PreCog)")
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--from-log", type=Path, help="Parse trace from log file")
    parser.add_argument(
        "--output", type=Path, required=True, help="Output trace file path"
    )
    parser.add_argument(
        "--metadata", type=json.loads, default="{}", help="Additional metadata as JSON"
    )

    args = parser.parse_args()

    if args.from_log:
        # Parse from log file
        if not args.from_log.exists():
            print(f"Error: Log file not found: {args.from_log}", file=sys.stderr)
            return 1

        with open(args.from_log) as f:
            log_content = f.read()

        trace = TraceCapture.from_log(log_content)

        # Set metadata from arguments or infer from log
        agent = args.agent or args.metadata.get("agent", "Unknown")
        task = args.task or args.metadata.get("task", "Unknown task")
        trace.set_metadata(agent=agent, task=task, **args.metadata)

    else:
        # Interactive mode
        if not args.agent or not args.task:
            print("Error: --agent and --task required in interactive mode", file=sys.stderr)
            return 1

        print(f"Starting trace capture for {args.agent}: {args.task}")
        print("Enter messages in format:")
        print("  user: <message>")
        print("  assistant: <message>")
        print("  tool: <name> <args_json>")
        print("  result: <tool_result>")
        print("  done")
        print()

        trace = TraceCapture()
        trace.set_metadata(agent=args.agent, task=args.task, **args.metadata)

        current_tool_calls = []

        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break

            if not line or line == "done":
                break

            if line.startswith("user:"):
                content = line.replace("user:", "").strip()
                trace.add_user_message(content)
                print("✓ User message added")

            elif line.startswith("assistant:"):
                content = line.replace("assistant:", "").strip()
                trace.add_assistant_message(
                    content, current_tool_calls if current_tool_calls else None
                )
                current_tool_calls = []
                print("✓ Assistant message added")

            elif line.startswith("tool:"):
                tool_str = line.replace("tool:", "").strip()
                parts = tool_str.split(None, 1)
                if len(parts) == 2:
                    tool_name, args_json = parts
                    try:
                        args = json.loads(args_json)
                        tool_call = {
                            "id": f"call_{len(trace.messages):03d}",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(args),
                            },
                        }
                        current_tool_calls.append(tool_call)
                        print(f"✓ Tool call added: {tool_name}")
                    except json.JSONDecodeError:
                        print("✗ Invalid JSON in arguments")

            elif line.startswith("result:"):
                result = line.replace("result:", "").strip()
                if current_tool_calls:
                    tool_call_id = current_tool_calls[-1]["id"]
                    trace.add_tool_result(tool_call_id, result)
                    print("✓ Tool result added")

    # Save trace
    trace.save(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
