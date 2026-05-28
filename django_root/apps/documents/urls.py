from rest_framework.routers import DefaultRouter

from .views import AnalysisResultViewSet, DocumentRelationViewSet, DocumentViewSet

router = DefaultRouter()
router.register("", DocumentViewSet, basename="document")
router.register(r"relations", DocumentRelationViewSet, basename="document-relation")
router.register(r"analysis", AnalysisResultViewSet, basename="analysis-result")

urlpatterns = router.urls
