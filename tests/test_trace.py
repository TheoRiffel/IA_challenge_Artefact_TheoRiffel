"""Tests for the debug trace formatter (no live API)."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

from emporio_agente.trace import format_trace


class _FakeResult:
    """Minimal stand-in for a pydantic_ai run result."""

    def __init__(self, messages):
        self._messages = messages

    def all_messages(self):
        return self._messages


def _result_with_one_tool():
    call = ToolCallPart(
        tool_name="get_order_status", args={"order_id": 17}, tool_call_id="c1"
    )
    ret = ToolReturnPart(
        tool_name="get_order_status", content="pedido 17: Cancelado", tool_call_id="c1"
    )
    return _FakeResult([ModelResponse(parts=[call]), ModelRequest(parts=[ret])])


def test_format_trace_includes_tool_model_and_latency():
    out = format_trace(
        _result_with_one_tool(), model="anthropic:claude-sonnet-4-5", elapsed_ms=123.4
    )
    assert "get_order_status" in out          # selected tool
    assert "anthropic:claude-sonnet-4-5" in out  # model
    assert "123" in out and "ms" in out        # latency figure
    assert "order_id" in out                   # tool arguments shown


def test_format_trace_shows_result_summary_line():
    out = format_trace(_result_with_one_tool(), model="m", elapsed_ms=1.0)
    # The one-line result summary appears under the tool call.
    assert "pedido 17: Cancelado" in out


def test_format_trace_handles_no_tool_calls():
    result = _FakeResult([ModelResponse(parts=[])])
    out = format_trace(result, model="m", elapsed_ms=5.0)
    assert "nenhuma tool" in out.lower()
    assert "5 ms" in out


def test_format_trace_args_json_string():
    # pydantic_ai sometimes stores args as a JSON string; it should still render.
    call = ToolCallPart(
        tool_name="search_products", args='{"category": "Violões"}', tool_call_id="c9"
    )
    out = format_trace(_FakeResult([ModelResponse(parts=[call])]), "m", 2.0)
    assert "search_products" in out
    assert "Violões" in out
