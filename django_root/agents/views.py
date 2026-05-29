import json
import logging

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["agent"],
    request=inline_serializer(
        name="AgentQueryRequest",
        fields={
            "query": serializers.CharField(),
            "max_iterations": serializers.IntegerField(default=5, required=False),
            "async": serializers.BooleanField(default=False, required=False),
        },
    ),
    responses={
        200: inline_serializer(
            name="AgentQueryResponse",
            fields={
                "answer": serializers.CharField(),
                "plan": serializers.CharField(),
                "iterations": serializers.IntegerField(),
                "sources": serializers.ListField(child=serializers.DictField()),
            },
        ),
        202: inline_serializer(
            name="AgentQueryAsyncResponse",
            fields={
                "task_id": serializers.CharField(),
                "status": serializers.CharField(),
                "poll_url": serializers.CharField(),
            },
        ),
    },
)
class AgentQueryView(APIView):
    """POST /api/agent/query/

    Request body:
        {
            "query": "Was sind die wichtigsten Klauseln in Dokument 3?",
            "max_iterations": 5,   // optional, default 5
            "async": false         // optional, default false
        }

    Synchronous response:
        {"answer": "...", "iterations": 3, "sources": [...]}

    Async response (HTTP 202):
        {"task_id": "<uuid>", "status": "pending",
         "poll_url": "/api/agent/tasks/<uuid>/"}
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

        run_async: bool = bool(request.data.get("async", False))

        if run_async:
            return self._dispatch_async(query, max_iterations, request)

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
                "plan": result.get("plan", ""),
                "iterations": result.get("iterations", 0),
                "sources": sources,
            }
        )

    def _dispatch_async(self, query: str, max_iterations: int, request: Request) -> Response:
        from agents.tasks import run_agent_task
        from apps.agent.models import AgentTask

        task = AgentTask.objects.create(query=query, max_iterations=max_iterations)
        run_agent_task.delay(str(task.pk), query, max_iterations)

        poll_url = request.build_absolute_uri(f"/api/agent/tasks/{task.pk}/")
        return Response(
            {
                "task_id": str(task.pk),
                "status": task.status,
                "poll_url": poll_url,
            },
            status=status.HTTP_202_ACCEPTED,
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


@extend_schema(
    tags=["agent"],
    request=inline_serializer(
        name="AgentStreamRequest",
        fields={
            "query": serializers.CharField(),
            "max_iterations": serializers.IntegerField(default=5, required=False),
        },
    ),
    responses={200: OpenApiResponse(description="Server-Sent Events stream (text/event-stream)")},
)
class AgentStreamView(APIView):
    """POST /api/agent/stream/ – Server-Sent Events (SSE) streaming endpoint.

    Runs the full agentic loop and streams events as they occur.
    PLAN/TOOL events are emitted as single JSON objects; the final ANSWER is
    streamed token by token via ``answer_chunk`` events.

    Request body: ``{"query": "...", "max_iterations": 5}``

    SSE event format::

        data: {"type": "plan",        "content": "step1 | step2"}
        data: {"type": "tool_call",   "tool": "search_documents", "args": {...}}
        data: {"type": "tool_result", "content": [...]}
        data: {"type": "answer_chunk","content": "partial text"}
        data: {"type": "done",        "iterations": 3}
        data: [DONE]
    """

    def post(self, request: Request) -> StreamingHttpResponse:
        query: str = request.data.get("query", "").strip()
        if not query:
            return Response(  # type: ignore[return-value]
                {"detail": "Feld 'query' ist erforderlich."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_iterations: int = int(request.data.get("max_iterations", 5))
        if not 1 <= max_iterations <= 20:
            return Response(  # type: ignore[return-value]
                {"detail": "'max_iterations' muss zwischen 1 und 20 liegen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def event_generator():
            from agents.orchestrator import run_agent_stream

            try:
                for event in run_agent_stream(query, max_iterations=max_iterations):
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            except Exception:
                logger.exception("Streaming agent error for query: %s", query[:200])
                yield f"data: {json.dumps({'type': 'error', 'content': 'Interner Fehler.'})}\n\n"
            yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            event_generator(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
