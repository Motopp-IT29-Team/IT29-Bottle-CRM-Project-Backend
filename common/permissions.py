from rest_framework.permissions import BasePermission

class IsOrgAdmin(BasePermission):
    """
    Allow only org ADMINs. Assumes `request.profile` is set by your auth
    (CustomDualAuthentication) and has a `role` field with 'ADMIN'/'USER'.
    """
    message = "You must be an organization admin to access this resource."

    def has_permission(self, request, view):
        profile = getattr(request, "profile", None)
        return bool(profile and getattr(profile, "role", "").upper() == "ADMIN")