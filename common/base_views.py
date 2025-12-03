"""
Base views for org-filtered CRUD operations.
All modules (Leads, Accounts, Contacts, etc.) should extend these classes.
"""

from django.db.models import Q
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)

from common.permissions import (
    IsOrgMember,
    IsOrgAdmin,
    IsSameOrg,
    IsCreatorOrAdmin,
)


class OrgFilteredListCreateView(ListCreateAPIView):
    permission_classes = [IsOrgMember]
    model = None
    create_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        queryset = self.model.objects.filter(org=self.request.profile.org)

        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            queryset = queryset.filter(
                Q(created_by=self.request.profile.user) |
                Q(assigned_to=self.request.profile)
            )

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == 'POST' and self.create_serializer_class:
            return self.create_serializer_class
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.profile.user,
            org=self.request.profile.org
        )


class OrgFilteredDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsOrgMember, IsSameOrg, IsCreatorOrAdmin]
    model = None
    update_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        return self.model.objects.filter(org=self.request.profile.org)

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH'] and self.update_serializer_class:
            return self.update_serializer_class
        return super().get_serializer_class()


class OrgAdminListCreateView(ListCreateAPIView):
    permission_classes = [IsOrgMember, IsOrgAdmin]
    model = None
    create_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        return self.model.objects.filter(org=self.request.profile.org).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == 'POST' and self.create_serializer_class:
            return self.create_serializer_class
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.profile.user,
            org=self.request.profile.org
        )


class OrgAdminDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsOrgMember, IsSameOrg, IsOrgAdmin]
    model = None
    update_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        return self.model.objects.filter(org=self.request.profile.org)

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH'] and self.update_serializer_class:
            return self.update_serializer_class
        return super().get_serializer_class()


class AssignedFilteredListView(ListCreateAPIView):
    permission_classes = [IsOrgMember]
    model = None
    create_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        queryset = self.model.objects.filter(org=self.request.profile.org)

        if self.request.profile.role == "ADMIN" or self.request.user.is_superuser:
            return queryset.order_by("-created_at")

        filters = Q(created_by=self.request.profile.user)

        if hasattr(self.model, 'assigned_to'):
            filters |= Q(assigned_to=self.request.profile)

        if hasattr(self.model, 'shared_to'):
            filters |= Q(shared_to=self.request.profile)

        return queryset.filter(filters).distinct().order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == 'POST' and self.create_serializer_class:
            return self.create_serializer_class
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.profile.user,
            org=self.request.profile.org
        )


class AssignedFilteredDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsOrgMember, IsSameOrg]
    model = None
    update_serializer_class = None

    def get_queryset(self):
        if not self.model:
            raise NotImplementedError("Subclass must define 'model' attribute")

        return self.model.objects.filter(org=self.request.profile.org)

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)

        if request.profile.role == "ADMIN" or request.user.is_superuser:
            return

        if hasattr(obj, 'created_by') and obj.created_by == request.profile.user:
            return

        if hasattr(obj, 'assigned_to') and obj.assigned_to == request.profile:
            return

        if hasattr(obj, 'shared_to') and request.profile in obj.shared_to.all():
            return

        self.permission_denied(
            request,
            message="You don't have permission to access this object"
        )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH'] and self.update_serializer_class:
            return self.update_serializer_class
        return super().get_serializer_class()

    def perform_destroy(self, instance):
        if (
                self.request.profile.role != "ADMIN"
                and not self.request.user.is_superuser
                and instance.created_by != self.request.profile.user
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the creator or admins can delete this object")

        instance.delete()