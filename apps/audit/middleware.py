import logging

logger = logging.getLogger(__name__)


class AuditLogMiddleware:
    """Logs write operations (POST, PUT, PATCH, DELETE) to the audit log."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.user.is_authenticated:
            try:
                from .models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action=request.method,
                    resource_type=request.resolver_match.url_name if request.resolver_match else '',
                    resource_id='',
                    ip_address=self._get_client_ip(request),
                )
            except Exception:
                logger.exception('Failed to write audit log.')
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
