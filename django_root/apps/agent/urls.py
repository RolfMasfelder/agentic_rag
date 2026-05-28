from django.urls import path

from apps.agent.views import AgentTaskStatusView

urlpatterns = [
    path("tasks/<str:task_id>/", AgentTaskStatusView.as_view(), name="agent-task-status"),
]
