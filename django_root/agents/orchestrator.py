import json
import logging
from typing import Any

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
}

_SYSTEM_PROMPT = (
    "Du bist ein Analyse-Agent mit Zugriff auf folgende Werkzeuge:\n"
    + "\n".join(f"  - {name}" for name in TOOLS)
    + "\n\n"
    "Um ein Werkzeug aufzurufen, antworte ausschließlich mit:\n"
    "  TOOL: <name> ARGS: <json-objekt>\n\n"
    "Sobald du die Frage beantworten kannst, antworte mit:\n"
    "  ANSWER: <deine Antwort>"
)


def run_agent(user_query: str, max_iterations: int = 5) -> dict[str, Any]:
    """
    Agentic retrieval loop:
      1. Ask LLM which tool to call
      2. Execute tool and feed result back
      3. Repeat until LLM emits ANSWER or max_iterations reached
    """
    from llm.client import chat

    conversation: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        response = chat(conversation)
        conversation.append({"role": "assistant", "content": response})

        if response.startswith("ANSWER:"):
            return {
                "answer": response[len("ANSWER:") :].strip(),
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
        "iterations": max_iterations,
        "conversation": conversation,
    }


def _execute_tool_call(response: str) -> Any:
    try:
        rest = response[len("TOOL:") :].strip()
        tool_name, args_str = rest.split("ARGS:", 1)
        tool_name = tool_name.strip()
        args = json.loads(args_str.strip())
        if tool_name not in TOOLS:
            return {"error": f"Unknown tool: {tool_name}"}
        return TOOLS[tool_name](**args)
    except Exception as exc:
        logger.exception("Tool execution failed.")
        return {"error": str(exc)}
