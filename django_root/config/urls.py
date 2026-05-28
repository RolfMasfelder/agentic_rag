from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("api/documents/", include("apps.documents.urls")),
    path("api/search/", include("retrieval.urls")),
    path("api/agent/", include("agents.urls")),
    path("api/agent/", include("apps.agent.urls")),
]
