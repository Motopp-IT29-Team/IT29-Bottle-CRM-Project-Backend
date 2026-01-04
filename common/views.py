import datetime
import json
import sys
import traceback

import requests
from django.db.models import Q
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.utils import json
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import Account, Contact, Tags
from accounts.serializer import AccountSerializer
from cases.models import Case
from cases.serializer import CaseSerializer
from common import swagger_params1
from common.base_views import AssignedFilteredDetailView
from common.base_views import AssignedFilteredListView
from common.permissions import IsCreatorOrAdmin
from common.permissions import IsOrgMember
from common.permissions import CanViewActivityLogs
from common.serializer import *
from common.serializer import EmailTokenObtainPairSerializer
from common.tasks import (
    resend_activation_link_to_user,
    send_email_to_new_user,
    send_email_user_delete,
)
from common.token_generator import account_activation_token
from common.utils import COUNTRIES
from contacts.serializer import ContactSerializer
from leads.models import Lead
from leads.serializer import LeadSerializer
from opportunity.models import Opportunity
from opportunity.serializer import OpportunitySerializer
from teams.models import Teams
from teams.serializer import TeamsSerializer


class GetTeamsAndUsersView(APIView):
    """
    Get all teams and active profiles for current organization.
    Used for assignment dropdowns.

    Permissions:
    - Must be org member
    """
    permission_classes = [IsOrgMember]

    @extend_schema(tags=["users"], parameters=swagger_params1.organization_params)
    def get(self, request, *args, **kwargs):
        """Get teams and profiles for current org."""
        teams = Teams.objects.filter(org=request.profile.org).order_by("-id")
        profiles = Profile.objects.filter(
            is_active=True,
            org=request.profile.org
        ).order_by("user__email")

        return Response({
            "teams": TeamsSerializer(teams, many=True).data,
            "profiles": ProfileSerializer(profiles, many=True).data,
        })

class ActivateUserView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, uid, token, activation_key):
        try:
            user_id = urlsafe_base64_decode(uid).decode()
            user = User.objects.get(pk=user_id)

            if user.is_active:
                return Response(
                    {"error": "Account already activated"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if user.activation_key != activation_key:
                return Response(
                    {"error": "Invalid or expired activation link"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            activation_time_str = activation_key.replace(token, '')
            activation_time = datetime.datetime.strptime(
                activation_time_str, "%Y-%m-%d-%H-%M-%S"
            )
            activation_time = activation_time.replace(tzinfo=datetime.timezone.utc)

            if datetime.datetime.now(datetime.timezone.utc) > activation_time:
                return Response(
                    {"error": "Activation link has expired"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not account_activation_token.check_token(user, token):
                return Response(
                    {"error": "Invalid activation token"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {
                    "message": "Link is valid",
                    "email": user.email
                },
                status=status.HTTP_200_OK
            )

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid activation link"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def post(self, request, uid, token, activation_key):
        print(1)
        try:
            user_id = urlsafe_base64_decode(uid).decode()
            user = User.objects.get(pk=user_id)

            if user.is_active:
                return Response(
                    {"error": "Account already activated"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if user.activation_key != activation_key:
                return Response(
                    {"error": "Invalid or expired activation link"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            activation_time_str = activation_key.replace(token, '')
            activation_time = datetime.datetime.strptime(
                activation_time_str, "%Y-%m-%d-%H-%M-%S"
            )
            activation_time = activation_time.replace(tzinfo=datetime.timezone.utc)

            if datetime.datetime.now(datetime.timezone.utc) > activation_time:
                return Response(
                    {"error": "Activation link has expired"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not account_activation_token.check_token(user, token):
                return Response(
                    {"error": "Invalid activation token"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            password = request.data.get('password')
            password_confirm = request.data.get('password_confirm')

            if not password:
                return Response(
                    {"error": "Password is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if password != password_confirm:
                return Response(
                    {"error": "Passwords do not match"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(password) < 8:
                return Response(
                    {"error": "Password must be at least 8 characters"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(password)
            user.is_active = True
            user.activation_key = None
            user.save()

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Account activated successfully",
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": {
                        "email": user.email,
                        "id": str(user.id)
                    }
                },
                status=status.HTTP_200_OK
            )

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid activation link"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "Activation failed"},
                status=status.HTTP_400_BAD_REQUEST
            )


from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from common.permissions import IsOrgAdmin, IsSameOrg  # IsOrgMember already imported at top
from django.db import transaction
from drf_spectacular.utils import extend_schema
import string
import secrets


class UsersListView(ListCreateAPIView):
    """
    List and create users (profiles).

    Permissions:
    - GET: Org members with can_view_others_activity_logs OR admins
    - POST: Admins only
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsOrgMember]
    pagination_class = LimitOffsetPagination
    
    def get_permissions(self):
        """Set permissions based on request method."""
        if self.request.method == 'GET':
            # Allow users with activity log permission to view users list
            return [IsOrgMember(), CanViewActivityLogs()]
        else:
            # Only admins can create users
            return [IsOrgMember(), IsOrgAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        """Filter profiles to current org."""
        queryset = Profile.objects.filter(org=self.request.profile.org).order_by("-id")

        # Filter by query params
        params = self.request.query_params
        status_param = params.get("status", "active")

        if params.get("email"):
            queryset = queryset.filter(user__email__icontains=params.get("email"))
        if params.get("role"):
            queryset = queryset.filter(role=params.get("role"))

        # Filter by active status
        is_active = status_param == "active"
        queryset = queryset.filter(user__is_active=is_active)

        return queryset

    @extend_schema(parameters=swagger_params1.user_list_params)
    def get(self, request, *args, **kwargs):
        """List users with pagination."""
        queryset = self.get_queryset()
        total_count = queryset.count()

        results = self.paginate_queryset(queryset.distinct())
        users = ProfileSerializer(results, many=True).data

        return Response({
            "users": users,
            "total_count": total_count,
            "status": request.query_params.get("status", "active"),
        })

    @extend_schema(
        parameters=swagger_params1.organization_params,
        request=UserCreateSwaggerSerializer
    )
    def post(self, request, *args, **kwargs):
        params = request.data

        user_serializer = CreateUserSerializer(data=params, org=request.profile.org)
        address_serializer = BillingAddressSerializer(data=params)
        profile_serializer = CreateProfileSerializer(data=params)

        errors = {}
        if not user_serializer.is_valid():
            errors["user_errors"] = user_serializer.errors
        if not profile_serializer.is_valid():
            errors["profile_errors"] = profile_serializer.errors
        if not address_serializer.is_valid():
            errors["address_errors"] = address_serializer.errors

        if errors:
            return Response(
                {"error": True, "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                address_obj = address_serializer.save()

                password = params.get("password")
                if not password:
                    alphabet = string.ascii_letters + string.digits
                    password = ''.join(secrets.choice(alphabet) for _ in range(12))

                user_serializer.validated_data['password'] = password
                user_serializer.validated_data['first_name'] = params.get("first_name")
                user_serializer.validated_data['last_name'] = params.get("last_name")

                user = user_serializer.save(is_active=False)
                user.set_password(password)
                user.save()

                Profile.objects.create(
                    user=user,
                    first_name=params.get("first_name", ""),
                    last_name=params.get("last_name", ""),
                    date_of_joining=timezone.now(),
                    role=params.get("role"),
                    address=address_obj,
                    org=request.profile.org,
                )

            send_email_to_new_user(user.id)

            return Response(
                {"error": False, "message": "User created successfully"},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": True, "errors": f"Failed to create user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete user profile.

    Permissions:
    - Must be org member and admin (or viewing self)
    - Must be same org
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsOrgMember, IsSameOrg]

    def get_queryset(self):
        """Filter to current org."""
        return super().get_queryset().filter(org=self.request.profile.org)

    def check_object_permissions(self, request, obj):
        """Check if user can access this profile."""
        super().check_object_permissions(request, obj)

        # Admin can access anyone, user can only access self
        if (
                request.profile.role != "ADMIN"
                and not request.profile.is_admin
                and request.profile.id != obj.id
        ):
            self.permission_denied(
                request,
                message="You can only view your own profile"
            )

    @extend_schema(tags=["users"], parameters=swagger_params1.organization_params)
    def get(self, request, *args, **kwargs):
        """Get user profile with assigned data."""
        profile_obj = self.get_object()

        # Get assigned data for dropdowns
        assigned_data = Profile.objects.filter(
            org=request.profile.org,
            is_active=True
        ).values("id", "user__email")

        # Get related objects
        opportunity_list = Opportunity.objects.filter(assigned_to=profile_obj)
        contacts = Contact.objects.filter(assigned_to=profile_obj)
        cases = Case.objects.filter(assigned_to=profile_obj)
        comments = profile_obj.user_comments.all()

        return Response({
            "error": False,
            "data": {
                "profile_obj": ProfileSerializer(profile_obj).data,
                "opportunity_list": OpportunitySerializer(opportunity_list, many=True).data,
                "contacts": ContactSerializer(contacts, many=True).data,
                "cases": CaseSerializer(cases, many=True).data,
                "assigned_data": assigned_data,
                "comments": CommentSerializer(comments, many=True).data,
                "countries": COUNTRIES,
            }
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["users"],
        parameters=swagger_params1.organization_params,
        request=UserCreateSwaggerSerializer
    )
    def put(self, request, *args, **kwargs):
        profile = self.get_object()
        address_obj = profile.address
        params = request.data

        if (
                request.profile.role != "ADMIN"
                and not request.user.is_superuser
                and request.profile.id != profile.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_serializer = CreateUserSerializer(
            data=params,
            instance=profile.user,
            org=request.profile.org
        )
        address_serializer = BillingAddressSerializer(
            data=params,
            instance=address_obj
        )
        profile_serializer = CreateProfileSerializer(
            data=params,
            instance=profile
        )

        errors = {}
        if not user_serializer.is_valid():
            errors["user_errors"] = user_serializer.errors
        if not address_serializer.is_valid():
            errors["address_errors"] = address_serializer.errors
        if not profile_serializer.is_valid():
            errors["profile_errors"] = profile_serializer.errors

        if errors:
            errors["error"] = True
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = user_serializer.save()
            address_obj = address_serializer.save()
            profile_obj = profile_serializer.save()
            profile_obj.address = address_obj
            profile_obj.updated_by = request.profile
            
            try:
                profile_obj.save()
            except Exception:
                # If save fails due to FK constraint, try without updated_by
                profile_obj.updated_by = None
                profile_obj.save()

            return Response(
                {"error": False, "message": "User Updated Successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": True, "errors": f"Failed to update user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(tags=["users"], parameters=swagger_params1.organization_params)
    def delete(self, request, *args, **kwargs):
        try:
            profile = self.get_object()
        except Profile.DoesNotExist:
            return Response(
                {"error": False, "message": "User already deleted"},
                status=status.HTTP_200_OK
            )

        if request.profile.role != "ADMIN" and not request.profile.is_admin:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if profile.id == request.profile.id:
            return Response(
                {"error": True, "errors": "Cannot delete your own account"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # user_email = profile.user.email
        # deleted_by = request.profile.user.email
        user = profile.user

        try:
            Attachments.objects.filter(created_by=user).delete()
            Document.objects.filter(created_by=user).delete()
            APISettings.objects.filter(created_by=user).delete()

            user.delete()

            # send_email_user_delete.delay(user_email, deleted_by=deleted_by)

            return Response(
                {
                    "error": False,
                    "message": "User and all associated data deleted successfully"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "error": True,
                    "errors": f"Failed to delete user: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResendInvitationView(APIView):
    """
    Resend activation invitation to inactive user.

    Permissions:
    - Must be org member and admin
    """
    permission_classes = [IsOrgMember, IsOrgAdmin]

    @extend_schema(
        tags=["users"],
        parameters=swagger_params1.organization_params
    )
    def post(self, request, pk, format=None):
        """Resend activation invitation to inactive user."""
        try:
            # Try to get profile in current org
            profile = Profile.objects.filter(pk=pk, org=request.profile.org).first()

            if not profile:
                return Response(
                    {"error": True, "message": "User not found in this organization"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user = profile.user

            # Check if user is already active
            if user.is_active:
                return Response(
                    {"error": True, "message": "User is already active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Resend activation email
            resend_activation_link_to_user(user.email)

            return Response(
                {
                    "error": False,
                    "message": "Invitation sent successfully"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"error": True, "message": "Failed to send invitation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ApiHomeView(APIView):

    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=swagger_params1.organization_params)
    def get(self, request, format=None):
        accounts = Account.objects.filter(status="open", org=request.profile.org)
        contacts = Contact.objects.filter(org=request.profile.org)
        leads = Lead.objects.filter(org=request.profile.org).exclude(
            Q(status="converted") | Q(status="closed")
        )
        opportunities = Opportunity.objects.filter(org=request.profile.org)

        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            accounts = accounts.filter(
                Q(assigned_to=self.request.profile) | Q(created_by=self.request.profile.user)
            )
            contacts = contacts.filter(
                Q(assigned_to=self.request.profile) | Q(created_by=self.request.profile.user)
            )
            leads = leads.filter(
                Q(assigned_to=self.request.profile) | Q(created_by=self.request.profile.user)
            ).exclude(status="closed")
            opportunities = opportunities.filter(
                Q(assigned_to=self.request.profile) | Q(created_by=self.request.profile.user)
            )

        # Calculate pipeline value (sum of non-closed opportunity amounts)
        from django.db.models import Sum
        from decimal import Decimal
        pipeline_value = opportunities.exclude(
            stage__in=['CLOSED WON', 'CLOSED LOST']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        context = {}
        context["accounts_count"] = accounts.count()
        context["contacts_count"] = contacts.count()
        context["leads_count"] = leads.count()
        context["opportunities_count"] = opportunities.count()
        context["pipeline_value"] = float(pipeline_value)
        context["accounts"] = AccountSerializer(accounts, many=True).data
        context["contacts"] = ContactSerializer(contacts, many=True).data
        context["leads"] = LeadSerializer(leads, many=True).data
        context["opportunities"] = OpportunitySerializer(opportunities, many=True).data

        # Add recent activities
        try:
            from common.models import ActivityLog
            activity_logs_qs = ActivityLog.objects.filter(org=request.profile.org).order_by('-created_at')[:10]
            context["recent_activities"] = [
                {
                    'id': str(log.id),
                    'action': log.action,
                    'model_name': log.entity_type,
                    'object_id': str(log.entity_id) if log.entity_id else None,
                    'object_repr': log.entity_name,
                    'user_email': log.user_email or (log.user.email if log.user else None),
                    'created_at': log.created_at.isoformat(),
                    'created_on_arrow': log.created_on_arrow if hasattr(log, 'created_on_arrow') else None,
                }
                for log in activity_logs_qs
            ]
        except Exception:
            context["recent_activities"] = []

        return Response(context, status=status.HTTP_200_OK)


class OrgProfileCreateView(APIView):
    """
    Create organization and admin profile, or list user's organizations.

    POST: Create new org (or update existing profile to admin)
    GET: List all orgs user has access to
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description="Organization and profile creation API",
        request=OrgProfileCreateSerializer
    )
    def post(self, request, format=None):
        """
        Create organization and admin profile.
        If org exists, creates/updates profile to admin.
        """
        try:
            data = request.data
            org_name = data.get('name')

            # Check if org already exists
            existing_org = Org.objects.filter(name=org_name).first()

            if existing_org:
                org_obj = existing_org
            else:
                # Create new org
                data['api_key'] = secrets.token_hex(16)
                serializer = OrgProfileCreateSerializer(data=data)

                if not serializer.is_valid():
                    return Response(
                        {
                            "error": True,
                            "errors": serializer.errors,
                            "status": status.HTTP_400_BAD_REQUEST,
                        }
                    )

                org_obj = serializer.save()

            # Check if profile exists for this user in this org
            existing_profile = Profile.objects.filter(user=request.user, org=org_obj).first()

            if existing_profile:
                # Update existing profile to admin
                existing_profile.is_organization_admin = True
                existing_profile.role = 'ADMIN'
                existing_profile.save()
                profile_obj = existing_profile
            else:
                # Create new admin profile
                first_name = data.get('first_name') or getattr(request.user, 'first_name', '') or ''
                last_name = data.get('last_name') or getattr(request.user, 'last_name', '') or ''

                # Fallback to existing profile if names not provided
                if not first_name or not last_name:
                    existing_user_profile = Profile.objects.filter(user=request.user).first()
                    if existing_user_profile:
                        first_name = first_name or existing_user_profile.first_name
                        last_name = last_name or existing_user_profile.last_name

                profile_obj = Profile.objects.create(
                    user=request.user,
                    org=org_obj,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_joining=timezone.now().date(),
                    is_organization_admin=True,
                    role='ADMIN'
                )

            return Response(
                {
                    "error": False,
                    "message": "New Org is Created." if not existing_org else "Profile updated to ADMIN.",
                    "org": OrgProfileCreateSerializer(org_obj).data,
                    "status": status.HTTP_201_CREATED,
                }
            )

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            raise

    @extend_schema(
        description="List all organizations associated with the user"
    )
    def get(self, request, format=None):
        """
        List all organizations the user has profiles in.
        Returns profile details including org info and role.
        """
        profile_list = Profile.objects.filter(user=request.user)
        serializer = ShowOrganizationListSerializer(profile_list, many=True)

        return Response(
            {
                "error": False,
                "status": status.HTTP_200_OK,
                "profile_org_list": serializer.data,
            }
        )


class ProfileView(APIView):
    """
    Get current user's profile in the specified organization.

    Permissions:
    - Must be authenticated
    - Org header validated by middleware (sets request.profile)
    """
    permission_classes = [IsOrgMember]

    @extend_schema(parameters=swagger_params1.organization_params)
    def get(self, request, format=None):
        """
        Get user profile and org info.
        Middleware already validated org access and set request.profile.
        """
        return Response({
            "user_obj": ProfileSerializer(request.profile).data,
            "current_org": {
                "id": str(request.profile.org.id),
                "name": request.profile.org.name
            }
        }, status=status.HTTP_200_OK)


class DocumentListView(AssignedFilteredListView):
    """
    List and create documents.
    GET returns documents split by status (active/inactive) with pagination.
    POST creates new document with file upload.
    """
    model = Document
    serializer_class = DocumentSerializer
    create_serializer_class = DocumentCreateSerializer
    pagination_class = LimitOffsetPagination

    def filter_queryset(self, queryset):
        """Apply search filters from query params."""
        params = self.request.query_params

        if params.get("title"):
            queryset = queryset.filter(title__icontains=params.get("title"))

        if params.get("status"):
            queryset = queryset.filter(status=params.get("status"))

        if params.get("shared_to"):
            import json
            try:
                shared_to_ids = json.loads(params.get("shared_to"))
                queryset = queryset.filter(shared_to__id__in=shared_to_ids)
            except (json.JSONDecodeError, ValueError):
                pass

        return queryset

    def get(self, request, *args, **kwargs):
        """Custom GET with split active/inactive documents."""
        queryset = self.filter_queryset(self.get_queryset())

        # Get profiles for sharing dropdown
        profile_list = Profile.objects.filter(is_active=True, org=request.profile.org)
        if request.profile.role == "ADMIN" or request.profile.is_admin:
            profiles = profile_list.order_by("user__email")
        else:
            profiles = profile_list.filter(role="ADMIN").order_by("user__email")

        # Check if search is active
        search = bool(
            request.query_params.get("document_file") or
            request.query_params.get("status") or
            request.query_params.get("shared_to")
        )

        # Paginate active documents
        queryset_active = queryset.filter(status="active")
        results_active = self.paginate_queryset(queryset_active.distinct())
        documents_active = DocumentSerializer(results_active, many=True).data

        active_offset = None
        if results_active:
            offset = queryset_active.filter(id__gte=results_active[-1].id).count()
            if offset < queryset_active.count():
                active_offset = offset

        # Paginate inactive documents
        queryset_inactive = queryset.filter(status="inactive")
        results_inactive = self.paginate_queryset(queryset_inactive.distinct())
        documents_inactive = DocumentSerializer(results_inactive, many=True).data

        inactive_offset = None
        if results_inactive:
            offset = queryset_inactive.filter(id__gte=results_inactive[-1].id).count()
            if offset < queryset_inactive.count():
                inactive_offset = offset

        return Response({
            "search": search,
            "documents_active": {
                "documents_active_count": queryset_active.count(),
                "documents_active": documents_active,
                "offset": active_offset,
            },
            "documents_inactive": {
                "documents_inactive_count": queryset_inactive.count(),
                "documents_inactive": documents_inactive,
                "offset": inactive_offset,
            },
            "users": ProfileSerializer(profiles, many=True).data,
            "status_choices": Document.DOCUMENT_STATUS_CHOICE,
        })

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, request_obj=request)

        if not serializer.is_valid():
            return Response(
                {"error": True, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc = serializer.save(
            created_by=request.profile.user,
            org=request.profile.org,
            document_file=request.FILES.get("document_file"),
        )

        if request.data.get("shared_to"):
            shared_to_list = self._parse_list_field(request.data.get("shared_to"))
            profiles = Profile.objects.filter(
                id__in=shared_to_list,
                org=request.profile.org,
                is_active=True
            )
            if profiles:
                doc.shared_to.add(*profiles)

        if request.data.get("teams"):
            teams_list = self._parse_list_field(request.data.get("teams"))
            teams = Teams.objects.filter(id__in=teams_list, org=request.profile.org)
            if teams:
                doc.teams.add(*teams)

        return Response(
            {"error": False, "message": "Document Created Successfully"},
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _parse_list_field(value):
        """Parse list field that might come as string or list from form data."""
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return [value]
        return value


class DocumentDetailView(AssignedFilteredDetailView):
    """
    Retrieve, update or delete a document.
    Permissions handled by AssignedFilteredDetailView.
    """
    model = Document
    queryset = Document.objects.select_related('created_by', 'org').prefetch_related('shared_to', 'teams')
    serializer_class = DocumentSerializer
    update_serializer_class = DocumentCreateSerializer

    @extend_schema(tags=["documents"])
    def get(self, request, *args, **kwargs):
        """Get document with additional context."""
        instance = self.get_object()

        # Get profiles for sharing dropdown
        profile_list = Profile.objects.filter(org=request.profile.org, is_active=True)
        if request.profile.role == "ADMIN" or request.user.is_superuser:
            profiles = profile_list.order_by("user__email")
        else:
            profiles = profile_list.filter(role="ADMIN").order_by("user__email")

        return Response({
            'doc_obj': DocumentSerializer(instance).data,
            'file_type_code': instance.file_type()[1],
            'users': ProfileSerializer(profiles, many=True).data,
        }, status=status.HTTP_200_OK)

    @extend_schema(tags=["documents"], request=DocumentEditSwaggerSerializer)
    def put(self, request, *args, **kwargs):
        """Update document and manage shared_to/teams relationships."""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            request_obj=request
        )

        if not serializer.is_valid():
            return Response(
                {"error": True, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save document
        doc = serializer.save(
            document_file=request.FILES.get("document_file") or instance.document_file
        )

        # Update shared_to M2M
        doc.shared_to.clear()
        if request.data.get("shared_to"):
            shared_to_list = self._parse_list_field(request.data.get("shared_to"))
            profiles = Profile.objects.filter(
                id__in=shared_to_list,
                org=request.profile.org,
                is_active=True
            )
            if profiles:
                doc.shared_to.add(*profiles)

        # Update teams M2M
        doc.teams.clear()
        if request.data.get("teams"):
            teams_list = self._parse_list_field(request.data.get("teams"))
            teams = Teams.objects.filter(id__in=teams_list, org=request.profile.org)
            if teams:
                doc.teams.add(*teams)

        return Response(
            {"error": False, "message": "Document Updated Successfully"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(tags=["documents"])
    def delete(self, request, *args, **kwargs):
        """Delete document (permission check in perform_destroy)."""
        return super().delete(request, *args, **kwargs)

    @staticmethod
    def _parse_list_field(value):
        """Parse list field that might come as string or list from form data."""
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return [value]
        return value


class UserStatusView(APIView):
    """
    Toggle user active/inactive status.

    Permissions:
    - Must be org member and admin
    """
    permission_classes = [IsOrgMember, IsOrgAdmin]

    @extend_schema(
        tags=["users"],
        parameters=swagger_params1.organization_params,
        request=UserUpdateStatusSwaggerSerializer
    )
    def post(self, request, pk, format=None):
        try:
            profile = Profile.objects.get(id=pk, org=request.profile.org)
            user = profile.user

            # Check if trying to deactivate self
            if profile.id == request.profile.id:
                return Response(
                    {"error": True, "errors": "You cannot change your own status"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.is_active = not user.is_active
            user.save()

            if not user.is_active:
                # Ensure request.profile exists and is saved
                if hasattr(request, 'profile') and request.profile and request.profile.id:
                    profile.deactivated_by = request.profile
                    profile.deactivated_at = timezone.now()
                else:
                    # Fallback: set to None if no valid profile
                    profile.deactivated_by = None
                    profile.deactivated_at = timezone.now()
            else:
                profile.deactivated_by = None
                profile.deactivated_at = None

            profile.save()

            return Response(
                {
                    "error": False,
                    "message": f"User {'activated' if user.is_active else 'deactivated'} successfully"
                },
                status=status.HTTP_200_OK
            )

        except Profile.DoesNotExist:
            return Response(
                {"error": True, "errors": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class DomainList(ListCreateAPIView):
    """
    List and create API settings.

    Permissions:
    - Must be org member
    - All members can create API settings
    """
    queryset = APISettings.objects.all()
    serializer_class = APISettingsListSerializer
    permission_classes = [IsOrgMember]

    def get_queryset(self):
        """Filter API settings to current org only."""
        return super().get_queryset().filter(org=self.request.profile.org)

    @extend_schema(tags=["Settings"])
    def get(self, request, *args, **kwargs):
        """List API settings with users for assignment dropdown."""
        api_settings = self.get_queryset()
        users = Profile.objects.filter(
            is_active=True,
            org=request.profile.org
        ).order_by("user__email")

        return Response({
            "error": False,
            "api_settings": APISettingsListSerializer(api_settings, many=True).data,
            "users": ProfileSerializer(users, many=True).data,
        }, status=status.HTTP_200_OK)

    @extend_schema(tags=["Settings"], request=APISettingsSwaggerSerializer)
    def post(self, request, *args, **kwargs):
        serializer = APISettingsSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"error": True, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings_obj = serializer.save(
            created_by=request.profile.user,
            org=request.profile.org
        )

        if request.data.get("tags"):
            for tag_name in request.data.get("tags"):
                tag_obj, _ = Tags.objects.get_or_create(name=tag_name)
                settings_obj.tags.add(tag_obj)

        if request.data.get("lead_assigned_to"):
            assign_to_list = request.data.get("lead_assigned_to")
            if isinstance(assign_to_list, str):
                import json
                try:
                    assign_to_list = json.loads(assign_to_list)
                except (json.JSONDecodeError, ValueError):
                    assign_to_list = [assign_to_list]

            profiles = Profile.objects.filter(
                id__in=assign_to_list,
                org=request.profile.org,
                is_active=True
            )
            if profiles:
                settings_obj.lead_assigned_to.add(*profiles)

        return Response(
            {"error": False, "message": "API setting Created Successfully"},
            status=status.HTTP_201_CREATED,
        )


class DomainDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete API setting.

    Permissions:
    - Must be org member
    - Must be same org
    - Can access if: creator or admin
    """
    queryset = APISettings.objects.all()
    serializer_class = APISettingsListSerializer
    permission_classes = [IsOrgMember, IsSameOrg, IsCreatorOrAdmin]

    def get_queryset(self):
        """Filter to current org only."""
        return super().get_queryset().filter(org=self.request.profile.org)

    @extend_schema(tags=["Settings"])
    def get(self, request, *args, **kwargs):
        """Get API setting details."""
        instance = self.get_object()
        return Response({
            "error": False,
            "api_settings": APISettingsListSerializer(instance).data,
        }, status=status.HTTP_200_OK)

    @extend_schema(tags=["Settings"], request=APISettingsSwaggerSerializer)
    def put(self, request, *args, **kwargs):
        """Update API setting with tags and lead assignments."""
        instance = self.get_object()
        serializer = APISettingsSerializer(data=request.data, instance=instance)

        if not serializer.is_valid():
            return Response(
                {"error": True, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update API setting
        api_setting = serializer.save()

        # Clear and update tags
        api_setting.tags.clear()
        if request.data.get("tags"):
            for tag_name in request.data.get("tags"):
                tag_obj, _ = Tags.objects.get_or_create(name=tag_name)
                api_setting.tags.add(tag_obj)

        # Clear and update lead_assigned_to
        api_setting.lead_assigned_to.clear()
        if request.data.get("lead_assigned_to"):
            assign_to_list = request.data.get("lead_assigned_to")
            if isinstance(assign_to_list, str):
                import json
                try:
                    assign_to_list = json.loads(assign_to_list)
                except (json.JSONDecodeError, ValueError):
                    assign_to_list = [assign_to_list]

            profiles = Profile.objects.filter(
                id__in=assign_to_list,
                org=request.profile.org,
                is_active=True
            )
            if profiles:
                api_setting.lead_assigned_to.add(*profiles)

        return Response(
            {"error": False, "message": "API setting Updated Successfully"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(tags=["Settings"])
    def delete(self, request, *args, **kwargs):
        """Delete API setting."""
        instance = self.get_object()
        instance.delete()
        return Response(
            {"error": False, "message": "API setting Deleted Successfully"},
            status=status.HTTP_200_OK,
        )


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        description="Login through Google", request=SocialLoginSerializer,
    )
    def post(self, request):
        payload = {'access_token': request.data.get("token")}
        r = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', params=payload)
        data = json.loads(r.text)

        if 'error' in data:
            content = {'message': 'wrong google token / this google token is already expired.'}
            return Response(content)

        # Get or create user
        user, user_created = User.objects.get_or_create(
            email=data['email'],
            defaults={
                'profile_pic': data.get('picture', ''),
                'first_name': data.get('given_name', ''),
                'last_name': data.get('family_name', ''),
            }
        )

        if user_created:
            user.set_unusable_password()
            user.save()
        else:
            if not user.first_name and data.get('given_name'):
                user.first_name = data.get('given_name', '')
            if not user.last_name and data.get('family_name'):
                user.last_name = data.get('family_name', '')
            user.save()

        existing_profiles = Profile.objects.filter(user=user)
        if existing_profiles.exists():
            for profile in existing_profiles:
                if not profile.first_name:
                    profile.first_name = user.first_name
                if not profile.last_name:
                    profile.last_name = user.last_name
                profile.save()

        token = RefreshToken.for_user(user)
        response = {}
        response['username'] = user.email
        response['access_token'] = str(token.access_token)
        response['refresh_token'] = str(token)
        response['user_id'] = user.id

        # LOGIN is now logged when user selects an organization (LogOrgSelectionView)
        return Response(response)


class EmailLoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Body: { "email": "user@example.com", "password": "MySecurePass123" }
    Response: { "refresh": "...", "access": "..." }
    """
    serializer_class = EmailTokenObtainPairSerializer
    authentication_classes = []  # public
    permission_classes = []

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "").lower().strip()
        
        response = super().post(request, *args, **kwargs)
        
        # Log successful login
        if response.status_code == 200 and email:
            from common.models import ActivityLog
            try:
                user = User.objects.get(email=email)
                profile = Profile.objects.filter(user=user, is_active=True).first()
                if profile:
                    ActivityLog.objects.create(
                        user=user,
                        user_email=user.email,
                        user_role=profile.role,
                        org=profile.org,
                        action="LOGIN",
                        entity_type="User",
                        entity_name="Email Login",
                    )
            except Exception as e:
                pass  # Don't break login if logging fails
        
        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Logs the user logout event.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Auth"], parameters=swagger_params1.organization_params)
    def post(self, request, *args, **kwargs):
        from common.models import ActivityLog, Profile
        import traceback
        
        # Log the logout - handle missing profile gracefully
        try:
            # Ensure we have a profile
            if not hasattr(request, 'profile') or request.profile is None:
                # Try to get profile from org header
                org_header = request.headers.get("org")
                if org_header and org_header not in ["null", "None", ""]:
                    try:
                        request.profile = Profile.objects.get(
                            user=request.user, 
                            org=org_header, 
                            is_active=True
                        )
                    except Profile.DoesNotExist:
                        # Try to get any active profile for this user
                        request.profile = Profile.objects.filter(
                            user=request.user,
                            is_active=True
                        ).first()
                else:
                    # No org header, try to get any active profile
                    request.profile = Profile.objects.filter(
                        user=request.user,
                        is_active=True
                    ).first()
            
            # Create activity log if we have a profile
            if hasattr(request, 'profile') and request.profile:
                ActivityLog.objects.create(
                    user=request.user,
                    user_email=request.user.email,
                    user_role=request.profile.role,
                    org=request.profile.org,
                    action="LOGOUT",
                    entity_type="User",
                    entity_name="User Logout",
                )
            else:
                print(f"Logout: No profile found for user {request.user.email}")
        except Exception as e:
            # Don't let logging errors prevent logout
            print(f"Logout logging error for {request.user.email}: {e}")
            traceback.print_exc()
        
        return Response(
            {"error": False, "message": "Logged out successfully"},
            status=status.HTTP_200_OK,
        )


class LogOrgSelectionView(APIView):
    """
    POST /api/auth/log-org-selection/
    Logs when a user selects/switches to an organization.
    This serves as the LOGIN event for that org.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Auth"], parameters=swagger_params1.organization_params)
    def post(self, request, *args, **kwargs):
        from common.models import ActivityLog
        
        # Log the org selection as LOGIN
        ActivityLog.objects.create(
            user=request.user,
            user_email=request.user.email,
            user_role=request.profile.role,
            org=request.profile.org,
            action="LOGIN",
            entity_type="User",
            entity_name="Organization Login",
        )
        
        return Response(
            {"error": False, "message": "Login logged successfully"},
            status=status.HTTP_200_OK,
        )


class ActivityLogListView(APIView, LimitOffsetPagination):
    """
    List activity logs for the current organization.
    
    Permission Model:
    - Admins: Can view all activity logs
    - Users: Can always view their own logs
    - Users with can_view_others_activity_logs=True: Can view all org logs and filter by user
    
    Query Parameters:
    - offset: Pagination offset
    - limit: Number of records per page
    - user_id: Filter by specific user ID (UUID) - only available to admins and users with can_view_others permission
    - user: Filter by user email (partial match)
    - action: Filter by action type (LOGIN, LOGOUT, CREATE, UPDATE, DELETE, VIEW)
    - entity_type: Filter by entity type (Lead, Contact, Account, etc.)
    - date_from: Filter logs from this date (YYYY-MM-DD)
    - date_to: Filter logs until this date (YYYY-MM-DD)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(tags=["Activity Log"], parameters=swagger_params1.organization_params)
    def get(self, request, *args, **kwargs):
        from common.models import ActivityLog
        
        # Check if profile exists (should be set by middleware)
        if not hasattr(request, 'profile') or request.profile is None:
            return Response(
                {"error": True, "message": "Organization context required"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Determine user permissions
        is_admin = request.profile.role == "ADMIN" or request.user.is_superuser
        can_view_others = request.profile.can_view_others_activity_logs
        
        # Base queryset filtered by org
        queryset = ActivityLog.objects.filter(org=request.profile.org)
        
        # Apply permission-based filtering
        if not is_admin and not can_view_others:
            # Regular users can only see their own logs
            queryset = queryset.filter(user=request.user)
        
        # Apply filters
        params = request.query_params
        
        # User ID filter - only allow if admin or can view others
        if params.get("user_id") and (is_admin or can_view_others):
            queryset = queryset.filter(user__id=params.get("user_id"))
        
        # Email filter
        if params.get("user") and (is_admin or can_view_others):
            queryset = queryset.filter(user_email__icontains=params.get("user"))
        
        if params.get("action"):
            queryset = queryset.filter(action=params.get("action"))
        
        if params.get("entity_type"):
            queryset = queryset.filter(entity_type=params.get("entity_type"))
        
        if params.get("date_from"):
            try:
                date_from = datetime.datetime.strptime(params.get("date_from"), "%Y-%m-%d")
                queryset = queryset.filter(created_at__gte=date_from)
            except ValueError:
                pass
        
        if params.get("date_to"):
            try:
                date_to = datetime.datetime.strptime(params.get("date_to"), "%Y-%m-%d")
                date_to = date_to + datetime.timedelta(days=1)  # Include the end date
                queryset = queryset.filter(created_at__lt=date_to)
            except ValueError:
                pass
        
        # Get total count before pagination
        total_count = queryset.count()
        
        # Paginate
        results = self.paginate_queryset(queryset, request, view=self)
        
        # Serialize
        serializer = ActivityLogSerializer(results, many=True)
        
        return Response({
            "error": False,
            "logs": serializer.data,
            "total_count": total_count,
            "can_view_others": is_admin or can_view_others,  # Frontend hint for showing user filter
            "viewing_mode": "all" if (is_admin or can_view_others) else "own"
        })
