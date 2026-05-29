import hashlib
import logging

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsAnalystOrAbove, IsOwnerOrAdmin

from .models import AnalysisResult, Document, DocumentRelation
from .serializers import (
    AnalysisResultSerializer,
    DocumentDetailSerializer,
    DocumentRelationSerializer,
    DocumentRelationWriteSerializer,
    DocumentSerializer,
)

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["file_type", "status"]
    permission_classes = [IsAuthenticated, IsAnalystOrAbove, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Document.objects.all()
        return Document.objects.filter(created_by=user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DocumentDetailSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        file = self.request.FILES.get("file")
        content_hash = ""
        if file:
            content_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)
        serializer.save(created_by=self.request.user, content_hash=content_hash)

    @action(detail=True, methods=["get"])
    def relations(self, request, pk=None):
        document = self.get_object()
        qs = DocumentRelation.objects.filter(source_document=document) | DocumentRelation.objects.filter(
            target_document=document
        )
        serializer = DocumentRelationSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        document = self.get_object()
        from ingestion.tasks import process_document

        process_document.delay(document.id)
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def batch_import(self, request):
        """POST /api/documents/batch_import/

        Upload multiple files at once.  Each file becomes a separate Document
        and is queued for processing.  Returns the list of created document IDs
        and a 'queued' status for each.

        Form fields:
            files   – one or more file uploads (field name repeated)
            file_type – FileType value applied to all uploads (default: 'other')
        """
        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"detail": "Mindestens eine Datei unter dem Feld 'files' erforderlich."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_type = request.data.get("file_type", Document.FileType.OTHER)
        if file_type not in Document.FileType.values:
            return Response(
                {"detail": f"Ungültiger 'file_type'. Erlaubt: {Document.FileType.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from ingestion.tasks import process_document

        created = []
        errors = []
        for uploaded_file in files:
            content_hash = hashlib.sha256(uploaded_file.read()).hexdigest()
            uploaded_file.seek(0)

            if Document.objects.filter(content_hash=content_hash).exists():
                errors.append({"filename": uploaded_file.name, "detail": "Duplikat – bereits importiert."})
                continue

            doc = Document.objects.create(
                title=uploaded_file.name,
                file=uploaded_file,
                file_type=file_type,
                content_hash=content_hash,
                created_by=request.user,
            )
            process_document.delay(doc.id)
            created.append({"id": doc.id, "title": doc.title, "status": "queued"})

        response_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED
        return Response({"created": created, "errors": errors}, status=response_status)


class DocumentRelationViewSet(viewsets.ModelViewSet):
    """CRUD for DocumentRelation.

    GET    /api/relations/             – list all
    POST   /api/relations/             – create
    GET    /api/relations/{id}/        – retrieve
    DELETE /api/relations/{id}/        – delete
    """

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source_document", "target_document", "relation_type"]
    http_method_names = ["get", "post", "delete", "head", "options"]
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return DocumentRelation.objects.select_related("source_document", "target_document").all()
        user_doc_ids = Document.objects.filter(created_by=user).values_list("id", flat=True)
        return DocumentRelation.objects.filter(
            Q(source_document_id__in=user_doc_ids) | Q(target_document_id__in=user_doc_ids)
        ).select_related("source_document", "target_document")

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentRelationWriteSerializer
        return DocumentRelationSerializer

    def perform_create(self, serializer):
        source_doc = serializer.validated_data.get("source_document")
        user = self.request.user
        if user.role != "admin" and source_doc.created_by != user:
            raise PermissionDenied("Du kannst nur Relationen für eigene Dokumente erstellen.")
        serializer.save(created_by=user.username)


class AnalysisResultViewSet(viewsets.ModelViewSet):
    """CRUD for AnalysisResult.

    GET    /api/analysis/              – list (filterable by document)
    POST   /api/analysis/              – create
    GET    /api/analysis/{id}/         – retrieve
    PUT    /api/analysis/{id}/         – update
    PATCH  /api/analysis/{id}/         – partial update
    DELETE /api/analysis/{id}/         – delete
    """

    serializer_class = AnalysisResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["document", "result_type"]
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return AnalysisResult.objects.select_related("document").all()
        return AnalysisResult.objects.filter(document__created_by=user).select_related("document")

    def perform_create(self, serializer):
        document = serializer.validated_data.get("document")
        user = self.request.user
        if user.role != "admin" and document.created_by != user:
            raise PermissionDenied("Du kannst nur Analysen für eigene Dokumente erstellen.")
        serializer.save()
