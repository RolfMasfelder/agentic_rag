import uuid

from django.db import models


class AgentTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        RUNNING = "running", "Läuft"
        DONE = "done", "Abgeschlossen"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.TextField()
    max_iterations = models.PositiveSmallIntegerField(default=5)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AgentTask({self.id}, {self.status})"
