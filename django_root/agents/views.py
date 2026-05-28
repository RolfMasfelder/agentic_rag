import json
import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class AgentQueryView(APIView):
    """POST /api/agent/query/

    Request body:
        {
            "query": "Was sind die wichtigsten Klauseln in Dokument 3?",
            "max_iterations": 5  // optional, default 5
        }

    Response:
        {
            "answer": "...",
            "iterations": 3,
            "sources": [{"chunk_id": 1, "document_id": 2, "content": "..."}, ...]
        }
    """

    def post(self, request: Request) -> Response:
        query: str = request.data.get("query", "").strip()
        if not query:
            return Response(
                {"detail": "Feld 'query' ist erforderlich."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_iterations: int = int(request.data.get("max_iterations", 5))
        if not 1 <= max_iterations <= 20:
            return Response(
                {"detail": "'max_iterations' muss zwischen 1 und 20 liegen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from agents.orchestrator import run_agent

            result = run_agent(query, max_iterations=max_iterations)
        except Exception:
            logger.exception("Agent query failed for query: %s", query[:200])
            return Response(
                {"detail": "Interner Fehler beim Ausführen des Agenten."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        sources = _extract_sources(result.get("conversation", []))
        return Response(
            {
                "answer": result.get("answer", ""),
                "iterations": result.get("iterations", 0),
                "sources": sources,
            }
        )


def _extract_sources(conversation: list[dict]) -> list[dict]:
    """Parse chunk references from tool-result messages in the conversation."""
    seen_chunk_ids: set[int] = set()
    sources: list[dict] = []

    for msg in conversation:
        if msg.get("role") != "user":
            continue
        content: str = msg.get("content", "")
        if not content.startswith("Tool result:"):
            continue
        try:
            data = json.loads(content[len("Tool result:") :].strip())
        except (json.JSONDecodeError, ValueError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            chunk_id = item.get("chunk_id")
            if chunk_id is not None and chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                sources.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": item.get("document_id"),
                        "content": item.get("content", ""),
                        "chunk_type": item.get("chunk_type", ""),
                        "score": item.get("score") or item.get("hybrid_score"),
                    }
                )

    return sources
