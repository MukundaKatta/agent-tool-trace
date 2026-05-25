"""In-memory recording and rendering of agent tool call sequences.

:class:`ToolTrace` records each tool call as a :class:`TraceStep` and can
render the full sequence as human-readable text for debugging.

Example::

    from agent_tool_trace import ToolTrace

    trace = ToolTrace()
    trace.record("search", {"query": "hello"}, result=["result1", "result2"])
    trace.record("read_file", {"path": "/tmp/x"}, result="file contents")
    trace.record("write_file", {"path": "/tmp/y"}, error=IOError("disk full"))

    print(trace.render())
    # [1] search(query='hello') -> ['result1', 'result2']
    # [2] read_file(path='/tmp/x') -> 'file contents'
    # [3] write_file(path='/tmp/y') -> ERROR: disk full

    # Statistics
    print(trace.call_count())   # 3
    print(trace.error_count())  # 1
    print(trace.tool_names())   # ['search', 'read_file', 'write_file']
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceStep:
    """A single recorded tool call.

    Attributes:
        seq:         1-based step number.
        tool_name:   Name of the tool called.
        args:        Arguments passed to the tool.
        result:      Return value (``None`` on error).
        error:       Exception if the call failed, or ``None``.
        duration_ms: Optional wall-clock duration in milliseconds.
        metadata:    Arbitrary extra data attached by the caller.
    """

    seq: int
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Exception | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """``True`` if no error was recorded."""
        return self.error is None

    @property
    def failed(self) -> bool:
        """``True`` if an error was recorded."""
        return self.error is not None

    def _args_repr(self) -> str:
        """Compact keyword-args string."""
        parts = []
        for k, v in self.args.items():
            try:
                parts.append(f"{k}={v!r}")
            except Exception:
                parts.append(f"{k}=<?>")
        return ", ".join(parts)

    def render_line(self) -> str:
        """Render this step as a single line of text."""
        call = f"{self.tool_name}({self._args_repr()})"
        if self.error is not None:
            err_msg = str(self.error) or type(self.error).__name__
            outcome = f"ERROR: {err_msg}"
        else:
            try:
                result_repr = repr(self.result)
            except Exception:
                result_repr = "<unrepresentable>"
            outcome = result_repr
        timing = (
            f"  [{self.duration_ms:.1f}ms]" if self.duration_ms is not None else ""
        )
        return f"[{self.seq}] {call} -> {outcome}{timing}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        error_info = None
        if self.error is not None:
            error_info = {
                "type": type(self.error).__name__,
                "message": str(self.error),
            }
        result_val: Any
        try:
            json.dumps(self.result)
            result_val = self.result
        except (TypeError, ValueError):
            result_val = repr(self.result)

        return {
            "seq": self.seq,
            "tool_name": self.tool_name,
            "args": self.args,
            "result": result_val,
            "error": error_info,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class ToolTrace:
    """Record and render a sequence of tool calls during an agent run.

    Example::

        trace = ToolTrace()
        trace.record("search", {"query": "hello"}, result=["a", "b"])
        trace.record("noop", {}, error=RuntimeError("boom"))
        print(trace.render())
        print(trace.error_count())  # 1
    """

    def __init__(self) -> None:
        self._steps: list[TraceStep] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        result: Any = None,
        error: Exception | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceStep:
        """Record a tool call step.

        Args:
            tool_name:   Name of the tool.
            args:        Argument dict (copied; ``None`` treated as empty).
            result:      Return value on success.
            error:       Exception on failure.
            duration_ms: Wall-clock duration in milliseconds.
            metadata:    Arbitrary extra data.

        Returns:
            The :class:`TraceStep` that was appended.
        """
        step = TraceStep(
            seq=len(self._steps) + 1,
            tool_name=tool_name,
            args=dict(args) if args is not None else {},
            result=result,
            error=error,
            duration_ms=duration_ms,
            metadata=dict(metadata) if metadata is not None else {},
        )
        self._steps.append(step)
        return step

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def steps(self) -> list[TraceStep]:
        """Return all recorded steps (in order)."""
        return list(self._steps)

    def step(self, seq: int) -> TraceStep:
        """Return the step with the given 1-based sequence number.

        Raises:
            IndexError: if *seq* is out of range.
        """
        if seq < 1 or seq > len(self._steps):
            raise IndexError(f"No step with seq={seq!r}")
        return self._steps[seq - 1]

    def call_count(self) -> int:
        """Total number of recorded calls."""
        return len(self._steps)

    def error_count(self) -> int:
        """Number of calls that recorded an error."""
        return sum(1 for s in self._steps if s.failed)

    def success_count(self) -> int:
        """Number of calls that recorded no error."""
        return sum(1 for s in self._steps if s.succeeded)

    def tool_names(self) -> list[str]:
        """Ordered list of tool names (one entry per call, may repeat)."""
        return [s.tool_name for s in self._steps]

    def unique_tools(self) -> list[str]:
        """Sorted list of distinct tool names that appear in the trace."""
        return sorted({s.tool_name for s in self._steps})

    def calls_for(self, tool_name: str) -> list[TraceStep]:
        """Return all steps for a specific tool name."""
        return [s for s in self._steps if s.tool_name == tool_name]

    def errors(self) -> list[TraceStep]:
        """Return all error steps."""
        return [s for s in self._steps if s.failed]

    def last(self) -> TraceStep | None:
        """Return the most recent step, or ``None`` if empty."""
        return self._steps[-1] if self._steps else None

    def first(self) -> TraceStep | None:
        """Return the first step, or ``None`` if empty."""
        return self._steps[0] if self._steps else None

    def total_duration_ms(self) -> float | None:
        """Sum of all recorded durations, or ``None`` if none were recorded."""
        durations = [s.duration_ms for s in self._steps if s.duration_ms is not None]
        if not durations:
            return None
        return sum(durations)

    def is_empty(self) -> bool:
        """``True`` if no steps have been recorded."""
        return len(self._steps) == 0

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, *, header: str | None = None, indent: str = "") -> str:
        """Render the trace as a human-readable multi-line string.

        Args:
            header: Optional title line prepended to the output.
            indent: Prefix for each line (e.g. ``"  "``).

        Returns:
            A string representation of all steps.
        """
        lines: list[str] = []
        if header is not None:
            lines.append(f"{indent}{header}")
        if not self._steps:
            lines.append(f"{indent}(empty trace)")
        else:
            for s in self._steps:
                lines.append(f"{indent}{s.render_line()}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a dict representation of the full trace."""
        return {
            "call_count": self.call_count(),
            "error_count": self.error_count(),
            "steps": [s.to_dict() for s in self._steps],
        }

    def to_jsonl(self) -> str:
        """Return each step as a JSON line (newline-separated)."""
        lines = []
        for s in self._steps:
            lines.append(json.dumps(s.to_dict()))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all recorded steps."""
        self._steps.clear()

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return (
            f"ToolTrace(calls={self.call_count()}, errors={self.error_count()})"
        )
