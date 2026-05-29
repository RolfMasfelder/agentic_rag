from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("ui/", include("apps.ui.urls")),
    path("api/auth/token/", obtain_auth_token),
    path("api/documents/", include("apps.documents.urls")),
    path("api/search/", include("retrieval.urls")),
    path("api/agent/", include("agents.urls")),
    path("api/agent/", include("apps.agent.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
