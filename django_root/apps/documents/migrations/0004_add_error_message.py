from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="error_message",
            field=models.TextField(blank=True, default=""),
        ),
    ]
