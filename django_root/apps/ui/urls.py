from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    # Auth
    path("login/", LoginView.as_view(template_name="ui/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="ui:login"), name="logout"),
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    path("partials/stats/", views.dashboard_stats, name="dashboard_stats"),
    path("partials/tasks/", views.dashboard_tasks, name="dashboard_tasks"),
    # Documents
    path("documents/", views.document_list, name="document_list"),
    path("documents/upload/", views.document_upload, name="document_upload"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/status/", views.document_status, name="document_status"),
    path("documents/<int:pk>/delete/", views.document_delete, name="document_delete"),
    # Agent
    path("agent/", views.agent_query, name="agent_query"),
    path("agent/clear-history/", views.agent_clear_history, name="agent_clear_history"),
    # Search
    path("search/", views.search, name="search"),
    # Admin actions
    path("admin/reembed/", views.admin_reembed, name="admin_reembed"),
]
