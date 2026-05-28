from rest_framework import serializers

from apps.agent.models import AgentTask


class AgentTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTask
        fields = ["id", "query", "max_iterations", "status", "result", "error", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "result", "error", "created_at", "updated_at"]
