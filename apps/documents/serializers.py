from rest_framework import serializers

from .models import Document, Chunk, DocumentRelation, AnalysisResult


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = ['id', 'chunk_type', 'position', 'page_number', 'content', 'metadata', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file_type', 'status', 'metadata', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['status', 'created_by', 'created_at', 'updated_at']


class DocumentDetailSerializer(DocumentSerializer):
    chunks = ChunkSerializer(many=True, read_only=True)

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ['chunks']


class DocumentRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRelation
        fields = ['id', 'source_document', 'target_document', 'relation_type', 'confidence', 'created_by', 'created_at']


class AnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisResult
        fields = ['id', 'document', 'result_type', 'content', 'created_at']
