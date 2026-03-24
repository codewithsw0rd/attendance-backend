from rest_framework.permissions import BasePermission
from accounts.models import UserType

class IsClientUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == UserType.ADMIN
        )