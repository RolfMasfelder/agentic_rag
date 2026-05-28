from django.contrib import admin

from .models import AnalysisResult, Chunk, Document, DocumentRelation


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "file_type", "status", "created_by", "created_at")
    list_filter = ("file_type", "status")
    search_fields = ("title", "content_hash")
    readonly_fields = ("content_hash", "created_at", "updated_at")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_type", "position", "page_number", "created_at")
    list_filter = ("chunk_type",)
    search_fields = ("document__title", "content")
    raw_id_fields = ("document",)


@admin.register(DocumentRelation)
class DocumentRelationAdmin(admin.ModelAdmin):
    list_display = ("source_document", "relation_type", "target_document", "confidence", "created_by")
    list_filter = ("relation_type",)


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("document", "result_type", "created_at")
    list_filter = ("result_type",)
