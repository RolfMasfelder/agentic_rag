import json
import logging
from collections.abc import Iterator
from typing import Any

from agents.context import trim_conversation
from agents.schema import validate_tool_args
from agents.tools import documents as doc_tools
from agents.tools import search as search_tools

logger = logging.getLogger(__name__)

TOOLS: dict[str, Any] = {
    "search_documents": search_tools.search_documents,
    "search_similar_chunks": search_tools.search_similar_chunks,
    "search_by_metadata": search_tools.search_by_metadata,
    "load_document": doc_tools.load_document,
    "find_related_documents": doc_tools.find_related_documents,
    "list_document_relations": doc_tools.list_document_relations,
    "summarize_document": doc_tools.summarize_document,
    "graph_traversal": doc_tools.graph_traversal,
    "find_similar_documents": doc_tools.find_similar_documents,
}

_TOOL_LIST = "\n".join(f"  - {name}" for name in TOOLS)

_SYSTEM_PROMPT = f"""\
Du bist ein Analyse-Agent mit Zugriff auf folgende Werkzeuge:
{_TOOL_LIST}

Arbeitsablauf:
1. Antworte zuerst mit einem Retrievalplan:
   PLAN: <Schritt 1> | <Schritt 2> | ...
2. Führe die Schritte aus, indem du je ein Werkzeug aufrufst:
   TOOL: <name> ARGS: <json-objekt>
3. Sobald du die Frage beantworten kannst:
   ANSWER: <deine Antwort>

Regeln:
- Pro Antwort genau eine Direktive (PLAN:, TOOL: oder ANSWER:).
- Kein freier Text außerhalb der Direktiven.\
"""


def run_agent(user_query: str, max_iterations: int = 5) -> dict[str, Any]:
    """Agentic retrieval loop with planning, schema validation, and context trimming.

    Steps:
      1. LLM emits PLAN: outlining intended tool calls.
      2. LLM calls tools one by one via TOOL: / receives results.
      3. LLM emits ANSWER: when done.
    """
    from llm.client import chat

    conversation: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    plan: str = ""

    for iteration in range(max_iterations):
        trimmed = trim_conversation(conversation)
        response = chat(trimmed)
        conversation.append({"role": "assistant", "content": response})

        if response.startswith("PLAN:"):
            plan = response[len("PLAN:") :].strip()
            logger.info("Agent plan: %s", plan)
            continue  # proceed to first TOOL: call

        if response.startswith("ANSWER:"):
            return {
                "answer": response[len("ANSWER:") :].strip(),
                "plan": plan,
                "iterations": iteration + 1,
                "conversation": conversation,
            }

        if response.startswith("TOOL:"):
            tool_result = _execute_tool_call(response)
            conversation.append(
                {
                    "role": "user",
                    "content": f"Tool result:\n{json.dumps(tool_result, ensure_ascii=False, default=str)}",
                }
            )
        else:
            logger.warning("Unexpected agent response: %s", response[:120])
            break

    return {
        "answer": "Maximale Iterationsanzahl erreicht.",
        "plan": plan,
        "iterations": max_iterations,
        "conversation": conversation,
    }


def _execute_tool_call(response: str) -> Any:
    try:
        rest = response[len("TOOL:") :].strip()
        tool_name, args_str = rest.split("ARGS:", 1)
        tool_name = tool_name.strip()
        raw_args: dict[str, Any] = json.loads(args_str.strip())

        if tool_name not in TOOLS:
            return {"error": f"Unknown tool: {tool_name}"}

        validated = validate_tool_args(TOOLS[tool_name], raw_args)
        if "error" in validated and len(validated) == 1:
            return validated  # validation failed – return error to LLM

        return TOOLS[tool_name](**validated)
    except Exception as exc:
        logger.exception("Tool execution failed.")
        return {"error": str(exc)}


def run_agent_stream(user_query: str, max_iterations: int = 5) -> Iterator[dict[str, Any]]:
    """Streaming agentic loop – yields Server-Sent Event payload dicts.

    Event types:
    - ``{"type": "plan",        "content": "step1 | step2"}``
    - ``{"type": "tool_call",   "tool": "...", "args": {...}}``
    - ``{"type": "tool_result", "content": {...}}``
    - ``{"type": "answer_chunk","content": "partial text"}``
    - ``{"type": "done",        "iterations": N}``
    - ``{"type": "error",       "content": "..."}``

    PLAN/TOOL responses are accumulated silently (they are short directives).
    ANSWER chunks are forwarded to the caller as they arrive from the LLM.
    """
    from llm.client import chat_stream

    conversation: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        trimmed = trim_conversation(conversation)

        response_buf = ""
        directive_type: str | None = None  # "answer" | "directive"
        answer_emitted_len = 0  # chars of answer content already yielded

        for chunk in chat_stream(trimmed):
            response_buf += chunk

            # Determine directive type from the growing buffer.
            if directive_type is None:
                if response_buf.startswith("ANSWER:"):
                    directive_type = "answer"
                elif response_buf.startswith(("PLAN:", "TOOL:")):
                    directive_type = "directive"
                elif len(response_buf) > 12:
                    directive_type = "directive"

            if directive_type == "answer":
                # Emit new content, stripping the "ANSWER:" prefix once.
                raw_after_prefix = response_buf[len("ANSWER:") :]
                content_so_far = raw_after_prefix.lstrip()
                if len(content_so_far) > answer_emitted_len:
                    new_text = content_so_far[answer_emitted_len:]
                    yield {"type": "answer_chunk", "content": new_text}
                    answer_emitted_len = len(content_so_far)

        # ── Post-stream processing ──────────────────────────────────────────
        response = response_buf
        conversation.append({"role": "assistant", "content": response})

        if directive_type == "answer" or response.startswith("ANSWER:"):
            yield {"type": "done", "iterations": iteration + 1}
            return

        if response.startswith("PLAN:"):
            plan_text = response[len("PLAN:") :].strip()
            logger.info("Agent plan: %s", plan_text)
            yield {"type": "plan", "content": plan_text}
            continue

        if response.startswith("TOOL:"):
            # Parse tool name / args for the event payload.
            try:
                rest = response[len("TOOL:") :].strip()
                tool_name, args_str = rest.split("ARGS:", 1)
                raw_args = json.loads(args_str.strip())
            except Exception:
                raw_args = {}
                tool_name = response
            yield {"type": "tool_call", "tool": tool_name.strip(), "args": raw_args}
            tool_result = _execute_tool_call(response)
            conversation.append(
                {
                    "role": "user",
                    "content": f"Tool result:\n{json.dumps(tool_result, ensure_ascii=False, default=str)}",
                }
            )
            yield {"type": "tool_result", "content": tool_result}
        else:
            yield {"type": "error", "content": f"Unexpected response: {response[:120]}"}
            break

    yield {"type": "done", "iterations": max_iterations}
