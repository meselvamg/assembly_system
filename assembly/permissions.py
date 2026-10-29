from rest_framework.permissions import BasePermission


def role_required(*roles):
    """Allow only users whose UserProfile.user_type is in `roles` (superusers always pass)."""

    class HasRole(BasePermission):
        message = "Your role is not allowed to use this API."

        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            if user.is_superuser:
                return True
            profile = getattr(user, "profile", None)
            return profile is not None and profile.user_type in roles

    return HasRole
