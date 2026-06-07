"""Capture backends for collecting agent outputs."""

import json
from pathlib import Path
from datetime import datetime
from typing import Protocol, Callable, Any
from functools import wraps

from .models import AgentOutput


class CaptureBackend(Protocol):
    """Protocol for capture backends that collect agent outputs."""

    def capture(self, agent: str, input_data: str, output: str, metadata: dict = None) -> None:
        """Capture a single agent output.

        Args:
            agent: Agent identifier
            input_data: Input provided to the agent
            output: Agent's output
            metadata: Optional metadata dict
        """
        ...

    def get_outputs(self) -> list[AgentOutput]:
        """Retrieve all captured outputs.

        Returns:
            List of AgentOutput objects
        """
        ...


class LogCapture:
    """In-memory capture backend for programmatic use.

    Example:
        >>> capture = LogCapture()
        >>> capture.capture("summarizer", "text", "summary")
        >>> outputs = capture.get_outputs()
    """

    def __init__(self):
        self._outputs: list[AgentOutput] = []

    def capture(self, agent: str, input_data: str, output: str, metadata: dict = None) -> None:
        """Capture a single agent output to memory."""
        agent_output = AgentOutput(
            agent=agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
            input=input_data,
            output=output,
            metadata=metadata or {}
        )
        self._outputs.append(agent_output)

    def get_outputs(self) -> list[AgentOutput]:
        """Retrieve all captured outputs."""
        return self._outputs

    def clear(self) -> None:
        """Clear all captured outputs."""
        self._outputs.clear()


class FileCapture:
    """File-based capture backend that writes to JSONL.

    Example:
        >>> capture = FileCapture("outputs.jsonl")
        >>> capture.capture("agent1", "input", "output")
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self._outputs: list[AgentOutput] = []

    def capture(self, agent: str, input_data: str, output: str, metadata: dict = None) -> None:
        """Capture a single agent output and append to JSONL file."""
        agent_output = AgentOutput(
            agent=agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
            input=input_data,
            output=output,
            metadata=metadata or {}
        )
        self._outputs.append(agent_output)

        # Append to file
        with open(self.file_path, "a") as f:
            f.write(agent_output.model_dump_json() + "\n")

    def get_outputs(self) -> list[AgentOutput]:
        """Retrieve all captured outputs from memory cache."""
        return self._outputs

    def load_from_file(self) -> list[AgentOutput]:
        """Load all outputs from the JSONL file.

        Returns:
            List of AgentOutput objects from file
        """
        outputs = []
        if self.file_path.exists():
            with open(self.file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        outputs.append(AgentOutput.model_validate_json(line))
        return outputs


class DecoratorCapture:
    """Decorator-based capture for wrapping agent functions.

    Example:
        >>> capture = DecoratorCapture()
        >>> @capture.agent("summarizer")
        ... def summarize(text: str) -> str:
        ...     return text[:100]
        >>> result = summarize("long text...")
        >>> outputs = capture.get_outputs()
    """

    def __init__(self, backend: CaptureBackend = None):
        self.backend = backend or LogCapture()

    def agent(self, agent_name: str, metadata: dict = None):
        """Decorator to capture agent function calls.

        Args:
            agent_name: Name of the agent
            metadata: Optional static metadata to attach to all captures

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                # Reconstruct input as string
                input_str = f"args={args}, kwargs={kwargs}"

                # Call the actual function
                result = func(*args, **kwargs)

                # Capture the output
                output_str = str(result)
                self.backend.capture(
                    agent=agent_name,
                    input_data=input_str,
                    output=output_str,
                    metadata=metadata or {}
                )

                return result

            return wrapper
        return decorator

    def get_outputs(self) -> list[AgentOutput]:
        """Retrieve all captured outputs from the backend."""
        return self.backend.get_outputs()


def load_outputs_from_jsonl(file_path: str | Path) -> list[AgentOutput]:
    """Load agent outputs from a JSONL file.

    Args:
        file_path: Path to JSONL file

    Returns:
        List of AgentOutput objects
    """
    outputs = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                outputs.append(AgentOutput.model_validate_json(line))
    return outputs


def load_outputs_from_directory(dir_path: str | Path) -> list[AgentOutput]:
    """Load agent outputs from a directory where each file is one agent's output.

    The filename (without extension) is used as the agent name.
    Each file should contain the agent's output text.

    Args:
        dir_path: Path to directory containing agent output files

    Returns:
        List of AgentOutput objects
    """
    dir_path = Path(dir_path)
    outputs = []

    for file_path in sorted(dir_path.iterdir()):
        if file_path.is_file() and not file_path.name.startswith("."):
            agent_name = file_path.stem
            output_text = file_path.read_text()

            agent_output = AgentOutput(
                agent=agent_name,
                timestamp=datetime.utcnow().isoformat() + "Z",
                input="",  # Not available from file
                output=output_text,
                metadata={"source_file": str(file_path)}
            )
            outputs.append(agent_output)

    return outputs
