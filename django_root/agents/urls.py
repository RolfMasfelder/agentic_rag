from django.urls import path

from .views import AgentQueryView, AgentStreamView

urlpatterns = [
    path("query/", AgentQueryView.as_view(), name="agent-query"),
    path("stream/", AgentStreamView.as_view(), name="agent-stream"),
]
