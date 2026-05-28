import hashlib

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Document, DocumentRelation
from .serializers import (
    DocumentDetailSerializer,
    DocumentRelationSerializer,
    DocumentSerializer,
)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['file_type', 'status']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        content_hash = ''
        if file:
            content_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)
        serializer.save(created_by=self.request.user, content_hash=content_hash)

    @action(detail=True, methods=['get'])
    def relations(self, request, pk=None):
        document = self.get_object()
        qs = (
            DocumentRelation.objects.filter(source_document=document)
            | DocumentRelation.objects.filter(target_document=document)
        )
        serializer = DocumentRelationSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        document = self.get_object()
        from ingestion.tasks import process_document
        process_document.delay(document.id)
        return Response({'status': 'queued'}, status=status.HTTP_202_ACCEPTED)
