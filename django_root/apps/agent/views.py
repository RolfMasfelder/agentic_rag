import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agent.models import AgentTask
from apps.agent.serializers import AgentTaskSerializer

logger = logging.getLogger(__name__)


@extend_schema(tags=["agent"], responses={200: AgentTaskSerializer, 404: None})
class AgentTaskStatusView(APIView):
    """GET /api/agent/tasks/{task_id}/ – poll an async agent task."""

    def get(self, request: Request, task_id: str) -> Response:
        try:
            task = AgentTask.objects.get(pk=task_id)
        except (AgentTask.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(AgentTaskSerializer(task).data)
