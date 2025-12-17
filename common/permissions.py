"""
These permissions check:
1. Organization membership (via request.profile.org)
2. Role-based access (ADMIN vs USER)
3. Object ownership (created_by)
"""
from rest_framework import permissions


class IsOrgMember(permissions.BasePermission):
    message = "You don't have access to this organization."

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and hasattr(request, 'profile')
                and request.profile is not None
        )


class IsOrgAdmin(permissions.BasePermission):
    message = "Only organization admins can perform this action."

    def has_permission(self, request, view):
        if not hasattr(request, 'profile') or not request.profile:
            return False
        return (
                request.user.is_superuser
                or request.profile.role == 'ADMIN'
                or request.profile.is_organization_admin
        )


class IsCreatorOrAdmin(permissions.BasePermission):
    message = "You don't have permission to access this object."

    def has_object_permission(self, request, view, obj):
        if not hasattr(request, 'profile') or not request.profile:
            return False

        if request.user.is_superuser or request.profile.role == 'ADMIN':
            return True

        if hasattr(obj, 'created_by') and obj.created_by == request.profile.user:
            return True

        return False


class CanViewActivityLogs(permissions.BasePermission):
    """
    Allow access if user is admin OR has can_view_others_activity_logs permission.
    For users list view: allows read-only access for activity log filtering.
    """
    message = "You don't have permission to view other users' information."

    def has_permission(self, request, view):
        if not hasattr(request, 'profile') or not request.profile:
            return False
        
        # Admins always have access
        if request.user.is_superuser or request.profile.role == 'ADMIN':
            return True
        
        # Users with can_view_others_activity_logs have read-only access
        if request.method in permissions.SAFE_METHODS:
            return request.profile.can_view_others_activity_logs
        
        return False


class IsCreatorSharedOrAdmin(permissions.BasePermission):
    message = "You don't have permission to access this object."

    def has_object_permission(self, request, view, obj):
        if not hasattr(request, 'profile') or not request.profile:
            return False

        if request.user.is_superuser or request.profile.role == 'ADMIN':
            return True

        if hasattr(obj, 'created_by') and obj.created_by == request.profile.user:
            return True

        if hasattr(obj, 'shared_to') and request.profile in obj.shared_to.all():
            return True

        return False


class IsCreatorOrAdminForDelete(permissions.BasePermission):
    message = "Only the creator or admins can delete this object."

    def has_object_permission(self, request, view, obj):
        if not hasattr(request, 'profile') or not request.profile:
            return False

        if request.user.is_superuser or request.profile.role == 'ADMIN':
            return True

        if hasattr(obj, 'created_by') and obj.created_by == request.profile.user:
            return True

        return False


class IsSameOrg(permissions.BasePermission):
    message = "This object belongs to a different organization."

    def has_object_permission(self, request, view, obj):
        if not hasattr(request, 'profile') or not request.profile:
            return False

        if hasattr(obj, 'org'):
            return obj.org == request.profile.org

        return True