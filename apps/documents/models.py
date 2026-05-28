from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    class FileType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        MARKDOWN = 'markdown', 'Markdown'
        XML = 'xml', 'XML'
        CODE = 'code', 'Source Code'
        OPENAPI = 'openapi', 'OpenAPI Spec'
        TEXT = 'text', 'Plain Text'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=512)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=20, choices=FileType.choices, default=FileType.OTHER)
    content_hash = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Chunk(models.Model):
    class ChunkType(models.TextChoices):
        PARAGRAPH = 'paragraph', 'Paragraph'
        CLAUSE = 'clause', 'Contract Clause'
        XML_BLOCK = 'xml_block', 'XML Block'
        FUNCTION = 'function', 'Function'
        CLASS = 'class', 'Class'
        API_ENDPOINT = 'api_endpoint', 'API Endpoint'
        MARKDOWN_SECTION = 'markdown_section', 'Markdown Section'
        OTHER = 'other', 'Other'

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    content = models.TextField()
    chunk_type = models.CharField(max_length=30, choices=ChunkType.choices, default=ChunkType.OTHER)
    position = models.IntegerField()
    page_number = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'position']
        indexes = [
            models.Index(fields=['document', 'position']),
        ]

    def __str__(self):
        return f'{self.document.title} – Chunk {self.position}'


class DocumentRelation(models.Model):
    class RelationType(models.TextChoices):
        REFERENCES = 'referenziert', 'Referenziert'
        EXTENDS = 'erweitert', 'Erweitert'
        CONTRADICTS = 'widerspricht', 'Widerspricht'
        SIMILAR = 'aehnlich', 'Ähnlich'
        BELONGS_TO = 'gehoert_zu', 'Gehört zu'
        BASED_ON = 'basiert_auf', 'Basiert auf'

    source_document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='relations_as_source'
    )
    target_document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='relations_as_target'
    )
    relation_type = models.CharField(max_length=30, choices=RelationType.choices)
    confidence = models.FloatField(default=1.0)
    created_by = models.CharField(max_length=100, default='system')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['source_document', 'target_document', 'relation_type']]

    def __str__(self):
        return f'{self.source_document} → {self.relation_type} → {self.target_document}'


class AnalysisResult(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='analysis_results')
    result_type = models.CharField(max_length=100)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document.title} – {self.result_type}'
