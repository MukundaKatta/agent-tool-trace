"""Tests for agent_tool_trace."""

from __future__ import annotations

import json

import pytest

from agent_tool_trace import ToolTrace, TraceStep

# ---------------------------------------------------------------------------
# TraceStep
# ---------------------------------------------------------------------------


def test_trace_step_succeeded():
    s = TraceStep(seq=1, tool_name="t")
    assert s.succeeded is True
    assert s.failed is False


def test_trace_step_failed():
    s = TraceStep(seq=1, tool_name="t", error=ValueError("boom"))
    assert s.failed is True
    assert s.succeeded is False


def test_trace_step_render_line_success():
    s = TraceStep(seq=1, tool_name="search", args={"q": "hello"}, result="res")
    line = s.render_line()
    assert "[1]" in line
    assert "search" in line
    assert "q='hello'" in line
    assert "'res'" in line


def test_trace_step_render_line_error():
    s = TraceStep(seq=2, tool_name="t", error=RuntimeError("kaboom"))
    line = s.render_line()
    assert "ERROR" in line
    assert "kaboom" in line


def test_trace_step_render_line_with_duration():
    s = TraceStep(seq=1, tool_name="t", result=None, duration_ms=12.5)
    line = s.render_line()
    assert "12.5ms" in line


def test_trace_step_render_line_no_duration():
    s = TraceStep(seq=1, tool_name="t")
    line = s.render_line()
    assert "ms" not in line


def test_trace_step_to_dict_success():
    s = TraceStep(seq=1, tool_name="search", args={"q": "a"}, result="r")
    d = s.to_dict()
    assert d["seq"] == 1
    assert d["tool_name"] == "search"
    assert d["args"] == {"q": "a"}
    assert d["result"] == "r"
    assert d["error"] is None


def test_trace_step_to_dict_error():
    s = TraceStep(seq=1, tool_name="t", error=TypeError("bad"))
    d = s.to_dict()
    assert d["error"]["type"] == "TypeError"
    assert d["error"]["message"] == "bad"


def test_trace_step_to_dict_non_json_result():
    class Custom:
        def __repr__(self):
            return "Custom()"

    s = TraceStep(seq=1, tool_name="t", result=Custom())
    d = s.to_dict()
    # Non-serialisable result should fall back to repr string
    assert isinstance(d["result"], str)
    assert "Custom" in d["result"]


def test_trace_step_defaults():
    s = TraceStep(seq=5, tool_name="ping")
    assert s.args == {}
    assert s.result is None
    assert s.error is None
    assert s.duration_ms is None
    assert s.metadata == {}


# ---------------------------------------------------------------------------
# ToolTrace — empty state
# ---------------------------------------------------------------------------


def test_empty_trace():
    t = ToolTrace()
    assert t.call_count() == 0
    assert t.error_count() == 0
    assert t.success_count() == 0
    assert t.tool_names() == []
    assert t.unique_tools() == []
    assert t.errors() == []
    assert t.last() is None
    assert t.first() is None
    assert t.total_duration_ms() is None
    assert t.is_empty() is True
    assert len(t) == 0


def test_repr_empty():
    t = ToolTrace()
    assert "calls=0" in repr(t)
    assert "errors=0" in repr(t)


def test_render_empty():
    t = ToolTrace()
    rendered = t.render()
    assert "empty" in rendered.lower()


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


def test_record_returns_step():
    t = ToolTrace()
    step = t.record("search", {"q": "hi"}, result="r")
    assert isinstance(step, TraceStep)
    assert step.seq == 1
    assert step.tool_name == "search"


def test_record_increments_seq():
    t = ToolTrace()
    s1 = t.record("a", result=1)
    s2 = t.record("b", result=2)
    s3 = t.record("c", result=3)
    assert s1.seq == 1
    assert s2.seq == 2
    assert s3.seq == 3


def test_record_args_none():
    t = ToolTrace()
    step = t.record("t")
    assert step.args == {}


def test_record_args_copy():
    t = ToolTrace()
    args = {"x": 1}
    t.record("t", args)
    args["y"] = 2
    assert "y" not in t.step(1).args


def test_record_with_error():
    t = ToolTrace()
    err = ValueError("bad")
    step = t.record("t", error=err)
    assert step.error is err


def test_record_with_duration():
    t = ToolTrace()
    step = t.record("t", result=1, duration_ms=42.5)
    assert step.duration_ms == 42.5


def test_record_with_metadata():
    t = ToolTrace()
    step = t.record("t", metadata={"key": "value"})
    assert step.metadata["key"] == "value"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def test_call_count():
    t = ToolTrace()
    for _ in range(5):
        t.record("t")
    assert t.call_count() == 5
    assert len(t) == 5


def test_error_count():
    t = ToolTrace()
    t.record("a", result=1)
    t.record("b", error=RuntimeError("x"))
    t.record("c", error=ValueError("y"))
    assert t.error_count() == 2
    assert t.success_count() == 1


def test_tool_names_order():
    t = ToolTrace()
    t.record("search")
    t.record("read")
    t.record("search")
    assert t.tool_names() == ["search", "read", "search"]


def test_unique_tools_sorted():
    t = ToolTrace()
    t.record("z")
    t.record("a")
    t.record("m")
    t.record("a")
    assert t.unique_tools() == ["a", "m", "z"]


def test_calls_for_tool():
    t = ToolTrace()
    t.record("search", result=1)
    t.record("read")
    t.record("search", result=2)
    calls = t.calls_for("search")
    assert len(calls) == 2
    assert all(s.tool_name == "search" for s in calls)


def test_calls_for_no_match():
    t = ToolTrace()
    t.record("search")
    assert t.calls_for("nope") == []


def test_errors():
    t = ToolTrace()
    t.record("a", result=1)
    e = RuntimeError("boom")
    t.record("b", error=e)
    errs = t.errors()
    assert len(errs) == 1
    assert errs[0].error is e


def test_last():
    t = ToolTrace()
    t.record("a")
    t.record("b")
    assert t.last().tool_name == "b"


def test_first():
    t = ToolTrace()
    t.record("a")
    t.record("b")
    assert t.first().tool_name == "a"


def test_step_by_seq():
    t = ToolTrace()
    t.record("a")
    t.record("b")
    assert t.step(1).tool_name == "a"
    assert t.step(2).tool_name == "b"


def test_step_out_of_range():
    t = ToolTrace()
    t.record("a")
    with pytest.raises(IndexError):
        t.step(0)
    with pytest.raises(IndexError):
        t.step(2)


def test_total_duration():
    t = ToolTrace()
    t.record("a", duration_ms=10.0)
    t.record("b", duration_ms=20.0)
    assert t.total_duration_ms() == 30.0


def test_total_duration_none():
    t = ToolTrace()
    t.record("a")
    assert t.total_duration_ms() is None


def test_total_duration_partial():
    t = ToolTrace()
    t.record("a", duration_ms=5.0)
    t.record("b")  # no duration
    assert t.total_duration_ms() == 5.0


def test_is_empty():
    t = ToolTrace()
    assert t.is_empty() is True
    t.record("t")
    assert t.is_empty() is False


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def test_render_basic():
    t = ToolTrace()
    t.record("search", {"q": "hello"}, result="found")
    rendered = t.render()
    assert "[1]" in rendered
    assert "search" in rendered
    assert "q='hello'" in rendered


def test_render_header():
    t = ToolTrace()
    t.record("t")
    rendered = t.render(header="== TRACE ==")
    assert "== TRACE ==" in rendered


def test_render_indent():
    t = ToolTrace()
    t.record("t")
    rendered = t.render(indent="  ")
    assert rendered.startswith("  ")


def test_render_multiple_steps():
    t = ToolTrace()
    t.record("a", result=1)
    t.record("b", error=ValueError("x"))
    lines = t.render().splitlines()
    assert len(lines) == 2
    assert "[1]" in lines[0]
    assert "[2]" in lines[1]


def test_render_error_step():
    t = ToolTrace()
    t.record("t", error=RuntimeError("oops"))
    rendered = t.render()
    assert "ERROR" in rendered
    assert "oops" in rendered


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------


def test_to_dict():
    t = ToolTrace()
    t.record("search", {"q": "a"}, result="r")
    d = t.to_dict()
    assert d["call_count"] == 1
    assert d["error_count"] == 0
    assert len(d["steps"]) == 1


def test_to_jsonl():
    t = ToolTrace()
    t.record("a", result=1)
    t.record("b", error=ValueError("x"))
    jsonl = t.to_jsonl()
    lines = jsonl.splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["tool_name"] == "a"
    assert parsed[1]["tool_name"] == "b"


def test_to_jsonl_empty():
    t = ToolTrace()
    assert t.to_jsonl() == ""


def test_to_dict_non_json_args():
    class Custom:
        def __repr__(self):
            return "Custom()"

    s = TraceStep(seq=1, tool_name="t", args={"obj": Custom(), "n": 5})
    d = s.to_dict()
    # Non-serialisable arg values fall back to repr; plain values are kept.
    assert d["args"]["obj"] == "Custom()"
    assert d["args"]["n"] == 5


def test_to_dict_non_json_metadata():
    class Custom:
        def __repr__(self):
            return "Custom()"

    s = TraceStep(
        seq=1,
        tool_name="t",
        metadata={"nested": {"obj": Custom()}, "items": [1, Custom()]},
    )
    d = s.to_dict()
    assert d["metadata"]["nested"]["obj"] == "Custom()"
    assert d["metadata"]["items"] == [1, "Custom()"]


def test_to_jsonl_non_json_payload_is_parseable():
    class Custom:
        def __repr__(self):
            return "Custom()"

    t = ToolTrace()
    t.record("t", {"obj": Custom()}, result=Custom(), metadata={"x": Custom()})
    # to_jsonl must always produce valid JSON, even for unserialisable values.
    parsed = [json.loads(line) for line in t.to_jsonl().splitlines()]
    assert len(parsed) == 1
    assert parsed[0]["args"]["obj"] == "Custom()"
    assert parsed[0]["result"] == "Custom()"
    assert parsed[0]["metadata"]["x"] == "Custom()"


def test_to_dict_empty():
    t = ToolTrace()
    d = t.to_dict()
    assert d["call_count"] == 0
    assert d["steps"] == []


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear():
    t = ToolTrace()
    t.record("a")
    t.record("b")
    t.clear()
    assert t.is_empty() is True
    assert t.call_count() == 0


def test_clear_resets_seq():
    t = ToolTrace()
    t.record("a")
    t.clear()
    step = t.record("b")
    assert step.seq == 1


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr():
    t = ToolTrace()
    t.record("a", result=1)
    t.record("b", error=RuntimeError("x"))
    r = repr(t)
    assert "calls=2" in r
    assert "errors=1" in r


# ---------------------------------------------------------------------------
# steps() copy
# ---------------------------------------------------------------------------


def test_steps_returns_copy():
    t = ToolTrace()
    t.record("a")
    steps = t.steps()
    steps.append(TraceStep(seq=99, tool_name="injected"))
    assert t.call_count() == 1
