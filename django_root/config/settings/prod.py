from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Strukturiertes Logging für Produktion (JSON-Format)
LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "logging.Formatter",
    "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
}
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
