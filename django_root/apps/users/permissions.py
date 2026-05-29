from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAnalystOrAbove(BasePermission):
    """Allow write operations only for ANALYST and ADMIN roles.

    Safe-method requests (GET, HEAD, OPTIONS) are allowed for all
    authenticated users regardless of role.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in ("admin", "analyst")


class IsOwnerOrAdmin(BasePermission):
    """Object-level permission: owners may modify their own objects; admins may
    modify any object.

    Expects the object to have a ``created_by`` field that is a FK to the
    User model (i.e. a User instance, not a plain string).

    Safe-method requests always pass this check.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == "admin":
            return True
        owner = getattr(obj, "created_by", None)
        return owner == request.user
