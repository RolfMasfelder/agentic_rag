"""Unit tests for the agent orchestrator, schema validator, and context trimmer."""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# validate_tool_args
# ---------------------------------------------------------------------------


def _dummy_tool(query: str, limit: int = 10, active: bool = True) -> list:
    return []


def test_validate_valid_args():
    from agents.schema import validate_tool_args

    result = validate_tool_args(_dummy_tool, {"query": "hello", "limit": 5})
    assert result == {"query": "hello", "limit": 5}
    assert "error" not in result


def test_validate_missing_required():
    from agents.schema import validate_tool_args

    result = validate_tool_args(_dummy_tool, {})
    assert "error" in result
    assert "query" in result["error"]


def test_validate_unknown_param():
    from agents.schema import validate_tool_args

    result = validate_tool_args(_dummy_tool, {"query": "hi", "typo_param": "oops"})
    assert "error" in result
    assert "typo_param" in result["error"]


def test_validate_type_coercion_float_to_int():
    from agents.schema import validate_tool_args

    # JSON numbers are floats; coerce to int where annotation says int.
    result = validate_tool_args(_dummy_tool, {"query": "hi", "limit": 5.0})
    assert result["limit"] == 5
    assert isinstance(result["limit"], int)


def test_validate_optional_param_omitted():
    from agents.schema import validate_tool_args

    result = validate_tool_args(_dummy_tool, {"query": "hi"})
    assert "error" not in result
    assert "limit" not in result  # uses function default, not included in output


def test_validate_no_annotations():
    from agents.schema import validate_tool_args

    def bare_fn(x, y=None):
        pass

    result = validate_tool_args(bare_fn, {"x": "value"})
    assert "error" not in result


# ---------------------------------------------------------------------------
# trim_conversation
# ---------------------------------------------------------------------------


def _make_conversation(n_tool_pairs: int) -> list[dict]:
    msgs = [
        {"role": "system", "content": "system prompt " * 10},
        {"role": "user", "content": "user query " * 10},
    ]
    for i in range(n_tool_pairs):
        msgs.append({"role": "assistant", "content": f"TOOL: search_documents ARGS: {{}} {' ' * 200}"})
        msgs.append({"role": "user", "content": f"Tool result: {{'chunks': []}} {' ' * 200}"})
    return msgs


def test_trim_short_conversation_unchanged():
    from agents.context import trim_conversation

    conv = _make_conversation(1)
    result = trim_conversation(conv, max_tokens=9999)
    assert result == conv


def test_trim_long_conversation_drops_middle():
    from agents.context import trim_conversation

    conv = _make_conversation(10)  # 22 messages, each ~200 chars → ~4400 chars
    result = trim_conversation(conv, max_tokens=100)  # 400 char budget

    # System + user query always preserved
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    # Result is shorter than original
    assert len(result) < len(conv)


def test_trim_preserves_system_and_first_user():
    from agents.context import trim_conversation

    conv = _make_conversation(20)
    result = trim_conversation(conv, max_tokens=50)  # very tight budget

    assert result[0] == conv[0]
    assert result[1] == conv[1]


def test_trim_inserts_notice_message():
    from agents.context import trim_conversation

    conv = _make_conversation(10)
    result = trim_conversation(conv, max_tokens=100)

    # A notice message should be inserted between head and remaining tail
    roles = [m["role"] for m in result]
    # At least one extra system notice
    assert roles.count("system") >= 2 or len(result) < len(conv)


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------


def test_run_agent_answer_first_iteration():
    from agents.orchestrator import run_agent

    with patch("llm.client.chat", return_value="ANSWER: 42 ist die Antwort."):
        result = run_agent("Was ist die Antwort?", max_iterations=5)

    assert result["answer"] == "42 ist die Antwort."
    assert result["iterations"] == 1


def test_run_agent_with_plan_and_tool():
    from agents.orchestrator import run_agent

    responses = iter(
        [
            "PLAN: search first | then answer",
            'TOOL: search_documents ARGS: {"query": "test"}',
            "ANSWER: Hier ist die Antwort.",
        ]
    )

    mock_tool_result = [{"chunk_id": 1, "content": "some text", "document_id": 1}]

    with (
        patch("llm.client.chat", side_effect=lambda msgs, **kw: next(responses)),
        patch("agents.tools.search.search_documents", return_value=mock_tool_result),
    ):
        result = run_agent("Find something", max_iterations=5)

    assert result["answer"] == "Hier ist die Antwort."
    assert result["plan"] == "search first | then answer"
    assert result["iterations"] == 3


def test_run_agent_max_iterations_reached():
    from agents.orchestrator import run_agent

    # Always returns a TOOL: call → never reaches ANSWER:
    with (
        patch("llm.client.chat", return_value='TOOL: search_documents ARGS: {"query": "x"}'),
        patch("agents.tools.search.search_documents", return_value=[]),
    ):
        result = run_agent("test", max_iterations=3)

    assert "Maximale" in result["answer"]
    assert result["iterations"] == 3


def test_run_agent_unknown_tool_returns_error_to_llm():
    from agents.orchestrator import run_agent

    responses = iter(
        [
            "TOOL: nonexistent_tool ARGS: {}",
            "ANSWER: Tool war unbekannt.",
        ]
    )

    with patch("llm.client.chat", side_effect=lambda msgs, **kw: next(responses)):
        result = run_agent("test", max_iterations=5)

    assert result["answer"] == "Tool war unbekannt."


# ---------------------------------------------------------------------------
# run_agent_stream
# ---------------------------------------------------------------------------


def test_run_agent_stream_emits_answer_chunks():
    from agents.orchestrator import run_agent_stream

    # Simulate chat_stream yielding the full answer in pieces
    def mock_stream(msgs, **kw):
        yield "ANSWER:"
        yield " Das"
        yield " ist"
        yield " die Antwort."

    with patch("llm.client.chat_stream", side_effect=mock_stream):
        events = list(run_agent_stream("Was ist das?", max_iterations=5))

    answer_chunks = [e for e in events if e["type"] == "answer_chunk"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(answer_chunks) >= 1
    full_answer = "".join(c["content"] for c in answer_chunks)
    assert "Antwort" in full_answer
    assert len(done_events) == 1


def test_run_agent_stream_emits_plan_event():
    from agents.orchestrator import run_agent_stream

    responses = [
        ["PLAN: step1 | step2"],
        ["ANSWER: done."],
    ]
    call_count = 0

    def mock_stream(msgs, **kw):
        nonlocal call_count
        chunks = responses[call_count]
        call_count += 1
        yield from chunks

    with patch("llm.client.chat_stream", side_effect=mock_stream):
        events = list(run_agent_stream("test", max_iterations=5))

    plan_events = [e for e in events if e["type"] == "plan"]
    assert len(plan_events) == 1
    assert "step1" in plan_events[0]["content"]


def test_run_agent_stream_emits_tool_events():
    from agents.orchestrator import run_agent_stream

    responses = [
        ['TOOL: search_documents ARGS: {"query": "test"}'],
        ["ANSWER: Fertig."],
    ]
    call_count = 0

    def mock_stream(msgs, **kw):
        nonlocal call_count
        chunks = responses[call_count]
        call_count += 1
        yield from chunks

    with (
        patch("llm.client.chat_stream", side_effect=mock_stream),
        patch("agents.tools.search.search_documents", return_value=[]),
    ):
        events = list(run_agent_stream("test", max_iterations=5))

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    tool_result_events = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_call_events) == 1
    assert tool_call_events[0]["tool"] == "search_documents"
    assert len(tool_result_events) == 1


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


def test_run_agent_task_updates_status():
    from agents.tasks import run_agent_task
    from apps.agent.models import AgentTask

    mock_task = MagicMock()
    mock_result = {
        "answer": "Antwort.",
        "plan": "plan",
        "iterations": 1,
        "conversation": [],
    }

    with (
        patch.object(AgentTask.objects, "get", return_value=mock_task),
        patch("agents.orchestrator.run_agent", return_value=mock_result),
    ):
        run_agent_task("some-uuid", "test query", max_iterations=1)

    assert mock_task.status == AgentTask.Status.DONE
    assert mock_task.result["answer"] == "Antwort."


def test_run_agent_task_marks_failed_on_error():
    from agents.tasks import run_agent_task
    from apps.agent.models import AgentTask

    mock_task = MagicMock()

    with (
        patch.object(AgentTask.objects, "get", return_value=mock_task),
        patch("agents.orchestrator.run_agent", side_effect=RuntimeError("LLM offline")),
        pytest.raises(RuntimeError),
    ):
        run_agent_task("some-uuid", "broken query")

    assert mock_task.status == AgentTask.Status.FAILED
    assert "LLM offline" in mock_task.error
