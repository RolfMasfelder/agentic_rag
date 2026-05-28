import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AgentTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("query", models.TextField()),
                ("max_iterations", models.PositiveSmallIntegerField(default=5)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ausstehend"),
                            ("running", "Läuft"),
                            ("done", "Abgeschlossen"),
                            ("failed", "Fehlgeschlagen"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("result", models.JSONField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
