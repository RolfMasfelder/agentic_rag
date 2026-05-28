from django.urls import path

from .views import AgentQueryView

urlpatterns = [
    path("query/", AgentQueryView.as_view(), name="agent-query"),
]
