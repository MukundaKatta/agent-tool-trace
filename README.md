# agent-tool-trace

In-memory recording of agent tool call sequences with human-readable rendering. Zero dependencies.

## Install

```bash
pip install agent-tool-trace
```

## Usage

```python
from agent_tool_trace import ToolTrace

trace = ToolTrace()
trace.record("search", {"query": "hello"}, result=["result1", "result2"])
trace.record("read_file", {"path": "/tmp/x"}, result="file contents")
trace.record("write_file", {"path": "/tmp/y"}, error=IOError("disk full"))

print(trace.render())
# [1] search(query='hello') -> ['result1', 'result2']
# [2] read_file(path='/tmp/x') -> 'file contents'
# [3] write_file(path='/tmp/y') -> ERROR: disk full

print(trace.call_count())    # 3
print(trace.error_count())   # 1
print(trace.success_count()) # 2
print(trace.tool_names())    # ['search', 'read_file', 'write_file']
print(trace.unique_tools())  # ['read_file', 'search', 'write_file']
```

## With timing

```python
import time

start = time.monotonic()
result = my_tool(query="hello")
elapsed_ms = (time.monotonic() - start) * 1000

trace.record("my_tool", {"query": "hello"}, result=result, duration_ms=elapsed_ms)
```

## Querying

```python
# All calls to a specific tool
calls = trace.calls_for("search")

# All failed calls
errors = trace.errors()

# First/last call
first = trace.first()
last  = trace.last()

# Call by 1-based sequence number
step = trace.step(2)

# Total wall time (if durations recorded)
total_ms = trace.total_duration_ms()
```

## Serialisation

```python
# JSONL (one JSON object per line)
jsonl = trace.to_jsonl()

# Dict
d = trace.to_dict()
```

## Render with header and indent

```python
print(trace.render(header="=== Tool Trace ===", indent="  "))
```

## TraceStep fields

| Field | Type | Description |
|-------|------|-------------|
| `seq` | `int` | 1-based step number |
| `tool_name` | `str` | Tool name |
| `args` | `dict` | Arguments passed |
| `result` | `Any` | Return value on success |
| `error` | `Exception \| None` | Exception on failure |
| `duration_ms` | `float \| None` | Wall-clock duration |
| `metadata` | `dict` | Arbitrary extra data |
| `succeeded` | `bool` | `True` if no error |
| `failed` | `bool` | `True` if error |

## License

MIT
