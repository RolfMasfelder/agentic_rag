from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # django_root/
REPO_ROOT = BASE_DIR.parent  # project root

env = environ.Env()
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

AUTH_USER_MODEL = "users.User"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.users",
    "apps.documents",
    "apps.audit",
    "apps.agent",
    "apps.ui",
]

LOGIN_URL = "/ui/login/"
LOGIN_REDIRECT_URL = "/ui/"
LOGOUT_REDIRECT_URL = "/ui/login/"

# Agent settings
AGENT_MAX_CONTEXT_TOKENS = env.int("AGENT_MAX_CONTEXT_TOKENS", default=6_000)

# Upload limits
DATA_UPLOAD_MAX_NUMBER_FILES = env.int("DATA_UPLOAD_MAX_NUMBER_FILES", default=500)

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="agentic_rag"),
        "USER": env("DB_USER", default="rag_user"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="db"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = REPO_ROOT / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_ROOT / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Redis / Celery
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Raspberry Pi MCP server
RASPI_MCP_URL = env("RASPI_MCP_URL")

# LLM / Ollama
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL")
OLLAMA_EMBED_MODEL = env("OLLAMA_EMBED_MODEL")
OLLAMA_CHAT_MODEL = env("OLLAMA_CHAT_MODEL")
# Leave empty to disable fallback; set e.g. "llama3.2:3b" for a lighter model.
OLLAMA_FALLBACK_MODEL = env("OLLAMA_FALLBACK_MODEL", default="")
EMBEDDING_DIM = env.int("EMBEDDING_DIM", default=768)

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Hybrid Agentic RAG API",
    "DESCRIPTION": (
        "REST API für das lokale KI-gestützte Analyse- und Retrieval-System. "
        "Authentifizierung: Token (Header `Authorization: Token <token>`) "
        "oder Session."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "TAGS": [
        {"name": "auth", "description": "Token-Authentifizierung"},
        {"name": "documents", "description": "Dokumentenverwaltung und -verarbeitung"},
        {"name": "retrieval", "description": "Semantische und Volltext-Suche"},
        {"name": "agent", "description": "Agentische Abfragen (Tool-Calling-Loop)"},
    ],
    "ENUM_NAME_OVERRIDES": {
        "DocumentStatusEnum": "apps.documents.models.Document.Status",
        "AgentTaskStatusEnum": "apps.agent.models.AgentTask.Status",
    },
}

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "ingestion": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "retrieval": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "agents": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
