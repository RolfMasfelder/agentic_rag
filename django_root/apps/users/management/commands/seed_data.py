"""Management command: seed the database with demo users and sample documents.

Idempotent – safe to run multiple times.  Existing objects are left unchanged.

Usage::

    python manage.py seed_data

    # Skip sample document ingestion (users only)
    python manage.py seed_data --no-documents

Demo accounts created
---------------------
  admin   / admin123    role=admin    (Django superuser)
  analyst / analyst123  role=analyst
  viewer  / viewer123   role=viewer

Sample documents
----------------
  Three small Markdown files from data/markdown/ are uploaded and queued for
  ingestion (parse → chunk → embed) via Celery.  If the worker is not running
  the documents remain in PENDING state until the worker starts.
"""

import hashlib
import logging
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Files relative to the repository root (= /app inside the container).
_SAMPLE_DOCS = [
    ("Django – Kurzreferenz", "data/markdown/django.rst", "rst"),
    ("pytest – Kurzreferenz", "data/markdown/pytest.rst", "rst"),
    ("Ruff – Linter-Referenz", "data/markdown/ruff.md", "md"),
    ("httpx – HTTP-Client-Referenz", "data/markdown/httpx.md", "md"),
]

# Map file extension to Document.FileType value.
_EXT_TO_FILETYPE = {
    "md": "markdown",
    "rst": "markdown",  # treat RST as markdown (plain text chunking)
    "txt": "text",
    "pdf": "pdf",
}

_DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@local.test",
        "password": "admin123",
        "role": "admin",
        "is_superuser": True,
        "is_staff": True,
    },
    {
        "username": "analyst",
        "email": "analyst@local.test",
        "password": "analyst123",
        "role": "analyst",
        "is_superuser": False,
        "is_staff": False,
    },
    {
        "username": "viewer",
        "email": "viewer@local.test",
        "password": "viewer123",
        "role": "viewer",
        "is_superuser": False,
        "is_staff": False,
    },
]


class Command(BaseCommand):
    help = "Seed the database with demo users and sample documents (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-documents",
            action="store_true",
            default=False,
            help="Create demo users only, skip sample document upload.",
        )

    def handle(self, *args, **options):
        self._seed_users()
        if not options["no_documents"]:
            self._seed_documents()
        self.stdout.write(self.style.SUCCESS("seed_data completed."))

    # ── Users ────────────────────────────────────────────────────────────────

    def _seed_users(self):
        from apps.users.models import User

        for spec in _DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": spec["role"],
                    "is_superuser": spec["is_superuser"],
                    "is_staff": spec["is_staff"],
                },
            )
            if created:
                user.set_password(spec["password"])
                user.save(update_fields=["password"])
                self.stdout.write(f"  created user  {spec['username']!r:12} role={spec['role']}")
            else:
                self.stdout.write(f"  exists  user  {spec['username']!r:12} role={user.role}  (skipped)")

    # ── Documents ────────────────────────────────────────────────────────────

    def _seed_documents(self):
        from apps.documents.models import Document
        from apps.users.models import User
        from ingestion.tasks import process_document

        try:
            owner = User.objects.get(username="admin")
        except User.DoesNotExist:
            self.stderr.write("  admin user not found – skipping document seed.")
            return

        # Repository root is one level above django_root.
        repo_root = Path(settings.BASE_DIR).parent

        queued = 0
        for title, rel_path, ext in _SAMPLE_DOCS:
            source = repo_root / rel_path
            if not source.exists():
                self.stderr.write(f"  missing file {rel_path} – skipped")
                continue

            raw = source.read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
            file_type = _EXT_TO_FILETYPE.get(ext, "text")

            doc, created = Document.objects.get_or_create(
                content_hash=content_hash,
                defaults={
                    "title": title,
                    "file_type": file_type,
                    "created_by": owner,
                    "metadata": {"seeded": True},
                },
            )
            if created:
                # Attach the file content so the parser can read it.
                doc.file.save(source.name, ContentFile(raw), save=True)
                process_document.delay(doc.id)
                queued += 1
                self.stdout.write(f"  queued  doc   {title!r}")
            else:
                self.stdout.write(f"  exists  doc   {title!r}  (skipped)")

        if queued:
            self.stdout.write(f"  {queued} document(s) queued for ingestion (worker must be running to process them).")
