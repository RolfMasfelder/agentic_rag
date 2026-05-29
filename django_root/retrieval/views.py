import json
import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["retrieval"],
    parameters=[
        OpenApiParameter("q", str, description="Suchbegriff (erforderlich für hybrid/vector/fulltext)"),
        OpenApiParameter("mode", str, enum=["hybrid", "vector", "fulltext", "metadata"], default="hybrid"),
        OpenApiParameter("limit", int, description="Max. Treffer (default: 10, max: 100)"),
        OpenApiParameter("document_ids", str, description="Kommaseparierte Dokument-IDs"),
        OpenApiParameter("filters", str, description="JSON-Objekt für metadata-Modus"),
    ],
    responses={
        200: inline_serializer(
            name="SearchResponse",
            fields={
                "results": serializers.ListField(child=serializers.DictField()),
                "mode": serializers.CharField(),
                "count": serializers.IntegerField(),
            },
        )
    },
)
class SearchView(APIView):
    """GET /api/search/

    Query parameters:
        q           (str)  Search query (required for hybrid/vector/fulltext)
        mode        (str)  hybrid | vector | fulltext | metadata  (default: hybrid)
        limit       (int)  Max results (default: 10, max: 100)
        document_ids (str) Comma-separated document IDs to restrict search
        filters     (str)  JSON object for metadata mode, e.g. {"author": "Kafka"}

    Response:
        {"results": [...], "mode": "hybrid", "count": 5}
    """

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        mode: str = request.query_params.get("mode", "hybrid").lower()
        limit: int = min(int(request.query_params.get("limit", 10)), 100)

        raw_ids = request.query_params.get("document_ids", "")
        document_ids: list[int] | None = None
        if raw_ids:
            try:
                document_ids = [int(i) for i in raw_ids.split(",") if i.strip()]
            except ValueError:
                return Response(
                    {"detail": "'document_ids' muss eine kommaseparierte Liste von Ganzzahlen sein."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if mode not in ("hybrid", "vector", "fulltext", "metadata"):
            return Response(
                {"detail": "Ungültiger 'mode'. Erlaubt: hybrid, vector, fulltext, metadata."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if mode == "metadata":
            raw_filters = request.query_params.get("filters", "{}")
            try:
                filters: dict = json.loads(raw_filters)
            except json.JSONDecodeError:
                return Response(
                    {"detail": "'filters' muss ein gültiges JSON-Objekt sein."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            results = _search_metadata(filters, limit)
        else:
            if not query:
                return Response(
                    {"detail": "Parameter 'q' ist für diesen Suchmodus erforderlich."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            results = _search(query, mode, limit, document_ids)

        return Response({"results": results, "mode": mode, "count": len(results)})


def _search(
    query: str,
    mode: str,
    limit: int,
    document_ids: list[int] | None,
) -> list[dict]:
    try:
        if mode == "hybrid":
            from retrieval.hybrid import hybrid_search

            return hybrid_search(query, limit=limit, document_ids=document_ids)
        if mode == "vector":
            from llm.client import get_embedding
            from retrieval.vector_search import search_similar_chunks

            embedding = get_embedding(query)
            return search_similar_chunks(embedding, limit=limit, document_ids=document_ids)
        # fulltext
        from retrieval.fulltext_search import fulltext_search

        return fulltext_search(query, limit=limit, document_ids=document_ids)
    except Exception:
        logger.exception("Search failed (mode=%s, query=%s)", mode, query[:200])
        raise


def _search_metadata(filters: dict, limit: int) -> list[dict]:
    try:
        from retrieval.metadata_filter import filter_by_metadata

        return filter_by_metadata(filters, limit=limit)
    except Exception:
        logger.exception("Metadata search failed (filters=%s)", filters)
        raise
