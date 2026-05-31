import ast
import inspect
import json
import logging
from collections.abc import Iterator
from typing import Any

from agents.context import trim_conversation
from agents.schema import validate_tool_args
from agents.tools import documents as doc_tools
from agents.tools import raspi as raspi_tools
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
    # Raspberry Pi hardware tools
    "raspi_led_on": raspi_tools.raspi_led_on,
    "raspi_led_off": raspi_tools.raspi_led_off,
    "raspi_led_blink": raspi_tools.raspi_led_blink,
    "raspi_led_status": raspi_tools.raspi_led_status,
    "raspi_temperature_list_sensors": raspi_tools.raspi_temperature_list_sensors,
    "raspi_temperature_read": raspi_tools.raspi_temperature_read,
}


def _tool_signature_line(name: str, func: Any) -> str:
    """Return a compact signature line for the system prompt, e.g.
    ``  - raspi_led_blink(pin: int, n: int = 3, ...)  # Blink the LED``"""
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return f"  - {name}()"
    parts: list[str] = []
    for pname, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            type_str = "Any"
        elif hasattr(ann, "__name__"):
            type_str = ann.__name__
        else:
            type_str = str(ann)
        if param.default is not inspect.Parameter.empty:
            parts.append(f"{pname}: {type_str} = {param.default!r}")
        else:
            parts.append(f"{pname}: {type_str}")
    doc_first = ((func.__doc__ or "").strip().splitlines() or [""])[0]
    sig_str = f"  - {name}({', '.join(parts)})"
    return f"{sig_str}  # {doc_first}" if doc_first else sig_str


_TOOL_LIST = "\n".join(_tool_signature_line(name, func) for name, func in TOOLS.items())

_SYSTEM_PROMPT = f"""\
Du bist ein Analyse-Agent mit Zugriff auf folgende Werkzeuge:
{_TOOL_LIST}

Raspberry Pi GPIO-Pin-Zuordnung (BCM-Nummerierung):
  rote LED = pin 17, gelbe LED = pin 27, grüne LED = pin 22

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


_DIRECTIVES = ("PLAN:", "TOOL:", "ANSWER:")


def _python_call_to_tool(text: str) -> str | None:
    """Try to parse a Python-style function call like ``name(a=1, b=2)``
    and return a normalised ``TOOL: name ARGS: {...}`` string, or None."""
    stripped = text.strip()
    # Quick pre-check before the expensive ast parse.
    paren = stripped.find("(")
    if paren == -1 or not stripped.endswith(")"):
        return None
    candidate_name = stripped[:paren].strip()
    if candidate_name not in TOOLS:
        return None
    try:
        tree = ast.parse(stripped, mode="eval")
        call = tree.body
        if not isinstance(call, ast.Call):
            return None
        kwargs: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is not None:
                kwargs[kw.arg] = ast.literal_eval(kw.value)
        # Positional args mapped by parameter order.
        sig = inspect.signature(TOOLS[candidate_name])
        params = [
            p
            for p in sig.parameters.values()
            if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        for i, arg_node in enumerate(call.args):
            if i < len(params):
                kwargs[params[i].name] = ast.literal_eval(arg_node)
        return f"TOOL: {candidate_name} ARGS: {json.dumps(kwargs)}"
    except Exception:
        return None


def _extract_directive(text: str) -> str:
    """Return *text* starting from the first known directive keyword.

    LLMs sometimes emit preamble (markdown tables, reasoning artefacts, …)
    before the actual directive, or use Python call syntax instead of the
    expected ``TOOL: name ARGS: {...}`` format.  We normalise all of that
    so the main loop can rely on ``str.startswith``.
    If no directive is found the original text is returned unchanged.
    """
    earliest_pos = len(text)
    for directive in _DIRECTIVES:
        pos = text.find(directive)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
    if earliest_pos == len(text):
        # No directive found – check every line for Python call syntax.
        for line in text.splitlines():
            converted = _python_call_to_tool(line)
            if converted:
                logger.debug("Converted Python call to TOOL directive: %r", line[:80])
                return converted
        return text
    skipped = text[:earliest_pos].strip()
    if skipped:
        logger.debug("Skipped LLM preamble before directive: %r", skipped[:120])
    return text[earliest_pos:]


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
    tool_calls: int = 0
    # Nudge threshold: after this many tool calls, remind the model to answer.
    _nudge_after = max(2, max_iterations - 2)

    for iteration in range(max_iterations):
        trimmed = trim_conversation(conversation)
        response = chat(trimmed)
        response = _extract_directive(response)
        if not response:
            logger.warning("LLM returned empty response on iteration %d – nudging.", iteration)
            conversation.append({"role": "assistant", "content": "(empty)"})
            conversation.append(
                {
                    "role": "user",
                    "content": "Bitte antworte mit TOOL: <name> ARGS: {...} oder ANSWER: <antwort>.",
                }
            )
            continue
        conversation.append({"role": "assistant", "content": response})

        if response.startswith("PLAN:"):
            rest = response[len("PLAN:") :].strip()
            # qwen2.5/qwen3.5 sometimes packs PLAN + TOOL/ANSWER into a single response.
            # TOOL: takes priority: execute it first, let the LLM answer naturally afterwards.
            if "TOOL:" in rest:
                idx = rest.index("TOOL:")
                plan = rest[:idx].strip()
                logger.info("Agent plan (inline tool): %s", plan)
                tool_result = _execute_tool_call("TOOL:" + rest[idx + len("TOOL:") :])
                tool_calls += 1
                conversation.append(
                    {
                        "role": "user",
                        "content": _tool_result_message(tool_result, tool_calls, _nudge_after),
                    }
                )
                continue
            if "ANSWER:" in rest:
                idx = rest.index("ANSWER:")
                plan = rest[:idx].strip()
                logger.info("Agent plan (inline answer): %s", plan)
                return {
                    "answer": rest[idx + len("ANSWER:") :].strip(),
                    "plan": plan,
                    "iterations": iteration + 1,
                    "conversation": conversation,
                }
            plan = rest
            logger.info("Agent plan: %s", plan)
            # If the plan itself looks like a direct tool call (Python syntax),
            # convert and execute immediately instead of waiting for next turn.
            converted = _python_call_to_tool(plan)
            if converted:
                logger.info("Plan contained Python call – executing directly: %s", converted)
                tool_result = _execute_tool_call(converted)
                tool_calls += 1
                conversation.append(
                    {
                        "role": "user",
                        "content": _tool_result_message(tool_result, tool_calls, _nudge_after),
                    }
                )
                continue
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
            tool_calls += 1
            conversation.append(
                {
                    "role": "user",
                    "content": _tool_result_message(tool_result, tool_calls, _nudge_after),
                }
            )
        else:
            logger.warning("Unexpected agent response: %s", response[:120])
            # Model ignored directive format – return its text directly as answer.
            return {
                "answer": response,
                "plan": plan,
                "iterations": iteration + 1,
                "conversation": conversation,
            }

    return {
        "answer": "Maximale Iterationsanzahl erreicht.",
        "plan": plan,
        "iterations": max_iterations,
        "conversation": conversation,
    }


def _tool_result_message(tool_result: Any, tool_calls: int, nudge_after: int) -> str:
    """Build the user message appended after a tool call.

    After *nudge_after* tool calls we add a reminder so the model transitions
    to ANSWER: instead of calling more tools indefinitely.
    """
    base = f"Tool result:\n{json.dumps(tool_result, ensure_ascii=False, default=str)}"
    if tool_calls >= nudge_after:
        base += (
            "\n\nDu hast genug Informationen gesammelt. "
            "Antworte jetzt auf die ursprüngliche Frage mit:\nANSWER: <deine Antwort>"
        )
    return base


def _execute_tool_call(response: str) -> Any:
    try:
        rest = response[len("TOOL:") :].strip()
        if "ARGS:" in rest:
            tool_name, args_str = rest.split("ARGS:", 1)
            tool_name = tool_name.strip()
            raw_args: dict[str, Any] = json.loads(args_str.strip())
        else:
            # LLM omitted "ARGS:" – try to split on first '{' instead.
            brace = rest.find("{")
            if brace == -1:
                return {"error": f"Cannot parse tool call – no ARGS and no JSON object found: {rest[:80]}"}
            tool_name = rest[:brace].strip()
            raw_args = json.loads(rest[brace:])

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
    tool_calls: int = 0
    _nudge_after = max(2, max_iterations - 2)

    for iteration in range(max_iterations):
        trimmed = trim_conversation(conversation)

        response_buf = ""
        directive_type: str | None = None  # "answer" | "directive"
        answer_emitted_len = 0  # chars of answer content already yielded

        for chunk in chat_stream(trimmed):
            response_buf += chunk

            # Determine directive type from the growing buffer.
            if directive_type is None:
                trimmed_buf = _extract_directive(response_buf)
                if trimmed_buf.startswith("ANSWER:"):
                    directive_type = "answer"
                    response_buf = trimmed_buf
                elif trimmed_buf.startswith(("PLAN:", "TOOL:")):
                    directive_type = "directive"
                    response_buf = trimmed_buf
                elif len(response_buf) > 50:
                    # Long preamble with no directive found yet – keep buffering
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
        response = _extract_directive(response_buf)
        conversation.append({"role": "assistant", "content": response})

        if directive_type == "answer" or response.startswith("ANSWER:"):
            yield {"type": "done", "iterations": iteration + 1}
            return

        if response.startswith("PLAN:"):
            rest = response[len("PLAN:") :].strip()
            # TOOL: takes priority over ANSWER: – execute the tool first.
            if "TOOL:" in rest:
                idx = rest.index("TOOL:")
                plan_text = rest[:idx].strip()
                logger.info("Agent plan (inline tool): %s", plan_text)
                yield {"type": "plan", "content": plan_text}
                tool_result = _execute_tool_call("TOOL:" + rest[idx + len("TOOL:") :])
                tool_calls += 1
                conversation.append(
                    {
                        "role": "user",
                        "content": _tool_result_message(tool_result, tool_calls, _nudge_after),
                    }
                )
                yield {"type": "tool_result", "content": tool_result}
                continue
            if "ANSWER:" in rest:
                idx = rest.index("ANSWER:")
                plan_text = rest[:idx].strip()
                logger.info("Agent plan (inline answer): %s", plan_text)
                answer_text = rest[idx + len("ANSWER:") :].strip()
                yield {"type": "plan", "content": plan_text}
                yield {"type": "answer_chunk", "content": answer_text}
                yield {"type": "done", "iterations": iteration + 1}
                return
            plan_text = rest
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
            tool_calls += 1
            conversation.append(
                {
                    "role": "user",
                    "content": _tool_result_message(tool_result, tool_calls, _nudge_after),
                }
            )
            yield {"type": "tool_result", "content": tool_result}
        else:
            yield {"type": "error", "content": f"Unexpected response: {response[:120]}"}
            break

    yield {"type": "done", "iterations": max_iterations}
