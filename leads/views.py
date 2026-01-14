from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account, Tags
from common.activity_logger import log_activity
from common.base_views import OrgFilteredListCreateView, OrgFilteredDetailView
from common.models import APISettings, Attachments, Comment, Profile
from common.models import User
from common.serializer import (
    AttachmentsSerializer,
    CommentSerializer,
    LeadCommentSerializer,
    ProfileSerializer,
)
from common.utils import COUNTRIES, INDCHOICES, LEAD_SOURCE, LEAD_STATUS
from contacts.models import Contact
from leads import swagger_params1
from leads.forms import LeadListForm
from leads.models import Company
from leads.models import Lead
from leads.serializer import CompanySerializer
from leads.serializer import (
    CompanySwaggerSerializer,
    LeadCreateSerializer,
    LeadSerializer,
    TagsSerializer,
    LeadCreateSwaggerSerializer,
    LeadDetailEditSwaggerSerializer,
    LeadCommentEditSwaggerSerializer,
    CreateLeadFromSiteSwaggerSerializer,
    LeadUploadSwaggerSerializer,
    LeadConversionRequestSerializer,
    LeadConversionResponseSerializer,
    LeadDuplicateCheckResponseSerializer,
)
from leads.services import LeadConversionService, LeadConversionError
from leads.tasks import (
    create_lead_from_file,
    send_email_to_assigned_user,
    send_lead_assigned_emails,
)
from teams.models import Teams
from teams.serializer import TeamsSerializer

class LeadListView(APIView, LimitOffsetPagination):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        queryset = (
            self.model.objects.filter(org=self.request.profile.org)
            .select_related("created_by", "assigned_to")
            .prefetch_related("tags")
        ).order_by("-id")

        if params:
            if params.get("name"):
                queryset = queryset.filter(
                    Q(first_name__icontains=params.get("name"))
                    & Q(last_name__icontains=params.get("name"))
                )
            if params.get("title"):
                queryset = queryset.filter(title__icontains=params.get("title"))
            if params.get("source"):
                queryset = queryset.filter(source=params.get("source"))
            if params.getlist("assigned_to"):
                queryset = queryset.filter(
                    assigned_to__id__in=params.get("assigned_to")
                )
            if params.get("status"):
                queryset = queryset.filter(status=params.get("status"))
            if params.get("tags"):
                queryset = queryset.filter(tags__in=params.get("tags"))
            if params.get("city"):
                queryset = queryset.filter(city__icontains=params.get("city"))
            if params.get("email"):
                queryset = queryset.filter(email__icontains=params.get("email"))
        context = {}
        queryset_open = queryset.exclude(status="closed").exclude(status="converted")
        results_leads_open = self.paginate_queryset(
            queryset_open.distinct(), self.request, view=self
        )
        open_leads = LeadSerializer(results_leads_open, many=True).data
        if results_leads_open:
            offset = queryset_open.filter(id__gte=results_leads_open[-1].id).count()
            if offset == queryset_open.count():
                offset = None
        else:
            offset = 0
        context["per_page"] = 10
        page_number = (int(self.offset / 10) + 1,)
        context["page_number"] = page_number
        context["open_leads"] = {
            "leads_count": self.count,
            "open_leads": open_leads,
            "offset": offset,
        }

        queryset_close = queryset.filter(status="converted")
        results_leads_close = self.paginate_queryset(
            queryset_close.distinct(), self.request, view=self
        )
        close_leads = LeadSerializer(results_leads_close, many=True).data
        if results_leads_close:
            offset = queryset_close.filter(id__gte=results_leads_close[-1].id).count()
            if offset == queryset_close.count():
                offset = None
        else:
            offset = 0

        context["close_leads"] = {
            "leads_count": self.count,
            "close_leads": close_leads,
            "offset": offset,
        }
        contacts = Contact.objects.filter(org=self.request.profile.org).values(
            "id", "first_name"
        )

        context["contacts"] = contacts
        context["status"] = LEAD_STATUS
        context["source"] = LEAD_SOURCE
        context["companies"] = CompanySerializer(
            Company.objects.filter(org=self.request.profile.org), many=True
        ).data
        context["tags"] = TagsSerializer(Tags.objects.all(), many=True).data

        users = Profile.objects.filter(is_active=True, org=self.request.profile.org).values(
            "id", "user__email", "user__is_active", "user__first_name", "user__last_name"
        )
        context["users"] = users
        context["countries"] = COUNTRIES
        context["industries"] = INDCHOICES
        return context

    @extend_schema(tags=["Leads"], parameters=swagger_params1.lead_list_get_params)
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return Response(context)

    @extend_schema(
        tags=["Leads"], description="Leads Create", parameters=swagger_params1.organization_params,
        request=LeadCreateSwaggerSerializer
    )
    def post(self, request, *args, **kwargs):
        data = request.data
        serializer = LeadCreateSerializer(data=data, request_obj=request)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=request.profile.user,
                org=request.profile.org,
                organization=request.profile.org.name
            )
            if data.get("tags", None):
                tags = data.get("tags")
                for t in tags:
                    tag = Tags.objects.filter(slug=t.lower())
                    if tag.exists():
                        tag = tag[0]
                    else:
                        tag = Tags.objects.create(name=t)
                    lead_obj.tags.add(tag)

            if data.get("contacts", None):
                obj_contact = Contact.objects.filter(
                    id__in=data.get("contacts"), org=request.profile.org
                )
                lead_obj.contacts.add(*obj_contact)

            # FIXED: assigned_to is now ForeignKey, not ManyToManyField
            if data.get("assigned_to", None):
                assigned_to_id = data.get("assigned_to")

                if isinstance(assigned_to_id, list):
                    assigned_to_id = assigned_to_id[0] if assigned_to_id else None

                if assigned_to_id:
                    try:
                        profile = Profile.objects.get(id=assigned_to_id, org=request.profile.org)
                        lead_obj.assigned_to = profile
                        lead_obj.save()

                        # Send email to assigned user
                        # recipients = [lead_obj.assigned_to.id]
                        # try:
                        #     send_email_to_assigned_user(recipients, lead_obj.id)
                        # except Exception as e:
                            # Celery not available, skip async email
                            # pass
                    except Profile.DoesNotExist:
                        pass

            files = request.FILES.getlist("lead_attachment")
            for file in files:
                attachment = Attachments()
                attachment.created_by = request.profile.user
                attachment.file_name = file.name
                attachment.lead = lead_obj
                attachment.attachment = file
                attachment.save()

            if data.get("teams", None):
                teams_list = data.get("teams")
                teams = Teams.objects.filter(id__in=teams_list, org=request.profile.org)
                lead_obj.teams.add(*teams)

            if data.get("status") == "qualified":
                account_object = Account.objects.create(
                    created_by=request.profile.user,
                    name=lead_obj.account_name,
                    email=lead_obj.email,
                    phone=lead_obj.phone,
                    description=data.get("description"),
                    website=data.get("website"),
                    org=request.profile.org,
                )

                account_object.billing_address_line = lead_obj.address_line
                account_object.billing_street = lead_obj.street
                account_object.billing_city = lead_obj.city
                account_object.billing_state = lead_obj.state
                account_object.billing_postcode = lead_obj.postcode
                account_object.billing_country = lead_obj.country
                comments = Comment.objects.filter(lead=lead_obj)
                if comments.exists():
                    for comment in comments:
                        comment.account_id = account_object.id
                attachments = Attachments.objects.filter(lead=lead_obj)
                if attachments.exists():
                    for attachment in attachments:
                        attachment.account_id = account_object.id
                for tag in lead_obj.tags.all():
                    account_object.tags.add(tag)

                if data.get("assigned_to", None):
                    assigned_to_list = data.getlist("assigned_to")
                    # recipients = assigned_to_list
                    # send_email_to_assigned_user(
                    #     recipients,
                    #     lead_obj.id,
                    # )
                # Log lead creation and conversion
                log_activity(
                    request,
                    action="CREATE",
                    entity_type="Lead",
                    entity_id=lead_obj.id,
                    entity_name=lead_obj.title,
                    details={"converted_to_account": True, "account_id": str(account_object.id)},
                )
                return Response(
                    {
                        "error": False,
                        "message": "Lead Converted to Account Successfully",
                    },
                    status=status.HTTP_200_OK,
                )
            # Log lead creation
            log_activity(
                request,
                action="CREATE",
                entity_type="Lead",
                entity_id=lead_obj.id,
                entity_name=lead_obj.title,
            )
            return Response(
                {"error": False, "message": "Lead Created Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LeadDetailView(APIView):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        return get_object_or_404(Lead, id=pk)

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        context = {}

        comments = Comment.objects.filter(lead=self.lead_obj).order_by("-id")
        attachments = Attachments.objects.filter(lead=self.lead_obj).order_by("-id")

        assigned_data = []
        if self.lead_obj.assigned_to:
            assigned_data.append({
                "id": self.lead_obj.assigned_to.id,
                "name": self.lead_obj.assigned_to.user.email
            })

        users_mention = list(
            Profile.objects.filter(is_active=True, org=self.request.profile.org).values(
                "user__email"
            )
        )

        users = Profile.objects.filter(
            is_active=True, org=self.request.profile.org
        ).order_by("user__email")

        team_ids = [user.id for user in self.lead_obj.get_team_users]
        all_user_ids = [user.id for user in users]
        users_excluding_team_id = set(all_user_ids) - set(team_ids)
        users_excluding_team = Profile.objects.filter(id__in=users_excluding_team_id)

        context.update(
            {
                "lead_obj": LeadSerializer(self.lead_obj).data,
                "attachments": AttachmentsSerializer(attachments, many=True).data,
                "comments": LeadCommentSerializer(comments, many=True).data,
                "users_mention": users_mention,
                "assigned_data": assigned_data,
            }
        )
        context["users"] = ProfileSerializer(users, many=True).data
        context["users_excluding_team"] = ProfileSerializer(
            users_excluding_team, many=True
        ).data
        context["source"] = LEAD_SOURCE
        context["status"] = LEAD_STATUS
        context["teams"] = TeamsSerializer(
            Teams.objects.filter(org=self.request.profile.org), many=True
        ).data
        context["countries"] = COUNTRIES

        return context

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params, description="Lead Detail")
    def get(self, request, pk, **kwargs):
        self.lead_obj = self.get_object(pk)
        context = self.get_context_data(**kwargs)
        return Response(context)

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params,
                   request=LeadDetailEditSwaggerSerializer)
    def post(self, request, pk, **kwargs):
        params = request.data

        context = {}
        self.lead_obj = Lead.objects.get(pk=pk)
        if self.lead_obj.org != request.profile.org:
            return Response(
                {"error": True, "errors": "User company doesnot match with header...."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # FIXED: assigned_to is now ForeignKey
        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            if not (
                    (self.request.profile.user == self.lead_obj.created_by)
                    or (self.request.profile == self.lead_obj.assigned_to)
            ):
                return Response(
                    {
                        "error": True,
                        "errors": "You do not have Permission to perform this action",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        comment_serializer = CommentSerializer(data=params)
        if comment_serializer.is_valid():
            if params.get("comment"):
                comment_serializer.save(
                    lead_id=self.lead_obj.id,
                    commented_by_id=self.request.profile.id,
                )

            if self.request.FILES.get("lead_attachment"):
                attachment = Attachments()
                attachment.created_by = User.objects.get(id=self.request.profile.user.id)

                attachment.file_name = self.request.FILES.get("lead_attachment").name
                attachment.lead = self.lead_obj
                attachment.attachment = self.request.FILES.get("lead_attachment")
                attachment.save()

        comments = Comment.objects.filter(lead__id=self.lead_obj.id).order_by("-id")
        attachments = Attachments.objects.filter(lead__id=self.lead_obj.id).order_by(
            "-id"
        )
        context.update(
            {
                "lead_obj": LeadSerializer(self.lead_obj).data,
                "attachments": AttachmentsSerializer(attachments, many=True).data,
                "comments": LeadCommentSerializer(comments, many=True).data,
            }
        )
        return Response(context)

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params, request=LeadCreateSwaggerSerializer)
    def put(self, request, pk, **kwargs):
        params = request.data
        self.lead_obj = self.get_object(pk)
        if self.lead_obj.org != request.profile.org:
            return Response(
                {
                    "error": True,
                    "errors": "User company does not match with header....",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = LeadCreateSerializer(
            data=params,
            instance=self.lead_obj,
            request_obj=request,
        )
        if serializer.is_valid():
            # FIXED: Store previous assigned_to for email notification
            previous_assigned_to = self.lead_obj.assigned_to.id if self.lead_obj.assigned_to else None

            lead_obj = serializer.save()
            lead_obj.tags.clear()
            if params.get("tags"):
                tags = params.getlist("tags")
                for t in tags:
                    tag = Tags.objects.filter(slug=t.lower())
                    if tag.exists():
                        tag = tag[0]
                    else:
                        tag = Tags.objects.create(name=t)
                    lead_obj.tags.add(tag)

            # FIXED: Handle single assigned_to
            if params.get("assigned_to"):
                assigned_to_id = params.get("assigned_to")

                if isinstance(assigned_to_id, list):
                    assigned_to_id = assigned_to_id[0] if assigned_to_id else None

                if assigned_to_id:
                    try:
                        profile = Profile.objects.get(id=assigned_to_id, org=request.profile.org)
                        lead_obj.assigned_to = profile
                    except Profile.DoesNotExist:
                        lead_obj.assigned_to = None
            else:
                lead_obj.assigned_to = None

            lead_obj.save()

            # Send email only to newly assigned user
            current_assigned_to = lead_obj.assigned_to.id if lead_obj.assigned_to else None
            recipients = [
                current_assigned_to] if current_assigned_to and current_assigned_to != previous_assigned_to else []

            # if recipients:
            #     send_email_to_assigned_user(recipients, lead_obj.id)

            if request.FILES.get("lead_attachment"):
                attachment = Attachments()
                attachment.created_by = request.profile.user
                attachment.file_name = request.FILES.get("lead_attachment").name
                attachment.lead = lead_obj
                attachment.attachment = request.FILES.get("lead_attachment")
                attachment.save()

            lead_obj.contacts.clear()
            if params.get("contacts"):
                contacts_list = params.getlist("contacts")
                obj_contacts = Contact.objects.filter(
                    id__in=contacts_list, org=request.profile.org
                )
                lead_obj.contacts.add(*obj_contacts)

            lead_obj.teams.clear()
            if params.get("teams"):
                teams_list = params.getlist("teams")
                teams = Teams.objects.filter(id__in=teams_list, org=request.profile.org)
                lead_obj.teams.add(*teams)

            if params.get("status") == "qualified":
                account_object = Account.objects.create(
                    created_by=request.profile.user,
                    name=lead_obj.account_name,
                    email=lead_obj.email,
                    phone=lead_obj.phone,
                    description=params.get("description"),
                    website=params.get("website"),
                    lead=lead_obj,
                    org=request.profile.org,
                )
                account_object.billing_address_line = lead_obj.address_line
                account_object.billing_street = lead_obj.street
                account_object.billing_city = lead_obj.city
                account_object.billing_state = lead_obj.state
                account_object.billing_postcode = lead_obj.postcode
                account_object.billing_country = lead_obj.country
                comments = Comment.objects.filter(lead=self.lead_obj)
                if comments.exists():
                    for comment in comments:
                        comment.account_id = account_object.id
                attachments = Attachments.objects.filter(lead=self.lead_obj)
                if attachments.exists():
                    for attachment in attachments:
                        attachment.account_id = account_object.id
                for tag in lead_obj.tags.all():
                    account_object.tags.add(tag)
                # if params.get("assigned_to"):
                    # assigned_to_list = params.getlist("assigned_to")
                    # recipients = assigned_to_list
                    # send_email_to_assigned_user(
                    #     recipients,
                    #     lead_obj.id,
                    # )

                for comment in lead_obj.leads_comments.all():
                    comment.account = account_object
                    comment.save()
                account_object.save()
                # Log lead conversion
                log_activity(
                    request,
                    action="UPDATE",
                    entity_type="Lead",
                    entity_id=lead_obj.id,
                    entity_name=lead_obj.title,
                    details={"converted_to_account": True, "account_id": str(account_object.id)},
                )
                return Response(
                    {
                        "error": False,
                        "message": "Lead Converted to Account Successfully",
                    },
                    status=status.HTTP_200_OK,
                )
            # Log lead update
            log_activity(
                request,
                action="UPDATE",
                entity_type="Lead",
                entity_id=lead_obj.id,
                entity_name=lead_obj.title,
            )
            return Response(
                {"error": False, "message": "Lead updated Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params, description="Lead Delete")
    def delete(self, request, pk, **kwargs):
        self.object = self.get_object(pk)
        if (
                request.profile.role == "ADMIN"
                or request.user.is_superuser
                or request.profile.user == self.object.created_by
        ) and self.object.org == request.profile.org:
            # Capture entity info before deletion
            entity_id = self.object.id
            entity_name = self.object.title
            self.object.delete()
            # Log lead deletion
            log_activity(
                request,
                action="DELETE",
                entity_type="Lead",
                entity_id=entity_id,
                entity_name=entity_name,
            )
            return Response(
                {"error": False, "message": "Lead deleted Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": "you don't have permission to delete this lead"},
            status=status.HTTP_403_FORBIDDEN,
        )


class LeadUploadView(APIView):
    model = Lead
    permission_classes = (IsAuthenticated,)

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params, request=LeadUploadSwaggerSerializer)
    def post(self, request, *args, **kwargs):
        lead_form = LeadListForm(request.POST, request.FILES)
        if lead_form.is_valid():
            create_lead_from_file(
                lead_form.validated_rows,
                lead_form.invalid_rows,
                request.profile.id,
                request.get_host(),
                request.profile.org.id,
            )
            return Response(
                {"error": False, "message": "Leads created Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": lead_form.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LeadCommentView(APIView):
    model = Comment
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        return self.model.objects.get(pk=pk)

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params,
                   request=LeadCommentEditSwaggerSerializer)
    def put(self, request, pk, format=None):
        params = request.data
        obj = self.get_object(pk)
        if (
                request.profile.role == "ADMIN"
                or request.user.is_superuser
                or request.profile == obj.commented_by
        ):
            serializer = LeadCommentSerializer(obj, data=params)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"error": False, "message": "Comment Submitted"},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"error": True, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "error": True,
                "errors": "You don't have permission to perform this action",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params)
    def delete(self, request, pk, format=None):
        self.object = self.get_object(pk)
        if (
                request.profile.role == "ADMIN"
                or request.user.is_superuser
                or request.profile == self.object.commented_by
        ):
            self.object.delete()
            return Response(
                {"error": False, "message": "Comment Deleted Successfully"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "error": True,
                "errors": "You do not have permission to perform this action",
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class LeadAttachmentView(APIView):
    model = Attachments
    permission_classes = (IsAuthenticated,)

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params)
    def post(self, request, pk, format=None):
        """Upload attachment to lead"""
        try:
            lead = Lead.objects.get(pk=pk, org=request.profile.org)
        except Lead.DoesNotExist:
            return Response(
                {"error": True, "errors": "Lead not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # FIXED: assigned_to is now ForeignKey
        if request.profile.role != "ADMIN" and not request.user.is_superuser:
            if not (
                    (request.profile.user == lead.created_by)
                    or (request.profile == lead.assigned_to)
            ):
                return Response(
                    {
                        "error": True,
                        "errors": "You do not have Permission to perform this action",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        if request.FILES.get("lead_attachment"):
            attachment = Attachments()
            attachment.created_by = request.profile.user
            attachment.file_name = request.FILES.get("lead_attachment").name
            attachment.lead = lead
            attachment.attachment = request.FILES.get("lead_attachment")
            attachment.save()

            # Return updated data
            attachments = Attachments.objects.filter(lead=lead).order_by("-id")
            return Response(
                {
                    "error": False,
                    "message": "Attachment uploaded successfully",
                    "attachment": AttachmentsSerializer(attachment).data,
                    "attachments": AttachmentsSerializer(attachments, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"error": True, "errors": "No file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(tags=["Leads"], parameters=swagger_params1.organization_params)
    def delete(self, request, pk, format=None):
        self.object = self.model.objects.get(pk=pk)
        if (
                request.profile.role == "ADMIN"
                or request.user.is_superuser
                or request.profile.user == self.object.created_by
        ):
            self.object.delete()
            return Response(
                {"error": False, "message": "Attachment Deleted Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "error": True,
                "errors": "You don't have permission to perform this action",
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class CreateLeadFromSite(APIView):
    @extend_schema(
        tags=["Leads"],
        parameters=swagger_params1.organization_params,
        request=CreateLeadFromSiteSwaggerSerializer
    )
    def post(self, request, *args, **kwargs):
        params = request.data
        api_key = params.get("apikey")
        api_setting = APISettings.objects.filter(apikey=api_key).first()

        if not api_setting:
            return Response(
                {
                    "error": True,
                    "message": "You don't have permission, please contact the admin!.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if api_setting and params.get("email") and params.get("title"):
            user = api_setting.created_by

            profile = Profile.objects.filter(user=user, org=api_setting.org).first()
            if not profile:
                return Response(
                    {"error": True, "message": "Profile not found for API settings owner"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lead = Lead.objects.create(
                title=params.get("title"),
                first_name=params.get("first_name"),
                last_name=params.get("last_name"),
                status="assigned",
                source=api_setting.website,
                description=params.get("message"),
                email=params.get("email"),
                phone=params.get("phone"),
                is_active=True,
                created_by=user,
                org=api_setting.org,
                assigned_to=profile,  # FIXED: Direct assignment instead of .add()
            )

            site_address = request.scheme + "://" + request.META["HTTP_HOST"]
            send_lead_assigned_emails(lead.id, [profile.id], site_address)

            try:
                contact = Contact.objects.create(
                    first_name=params.get("title"),
                    email=params.get("email"),
                    phone=params.get("phone"),
                    description=params.get("message"),
                    created_by=user,
                    is_active=True,
                    org=api_setting.org,
                )
                contact.assigned_to.add(profile)
                lead.contacts.add(contact)
            except Exception:
                pass

            return Response(
                {"error": False, "message": "Lead Created sucessfully."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": True, "message": "Invalid data"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CheckDuplicateLeadView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Leads"],
        parameters=[
            OpenApiParameter(name='email', type=str, required=False),
            OpenApiParameter(name='phone', type=str, required=False),
        ]
    )
    def get(self, request):
        email = request.query_params.get('email')
        phone = request.query_params.get('phone')

        if not email and not phone:
            return Response(
                {'error': True, 'message': 'Email or phone required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        duplicates = Lead.objects.filter(org=request.profile.org)

        if email:
            duplicates = duplicates.filter(email=email)

        if phone:
            duplicates = duplicates.filter(phone=phone)

        exists = duplicates.exists()

        return Response({
            'duplicate': exists,
            'message': 'Duplicate lead found' if exists else 'No duplicate found'
        })


class CompaniesView(OrgFilteredListCreateView):
    """
    List and create companies.

    Permissions:
    - Must be org member
    """
    model = Company
    serializer_class = CompanySerializer

    @extend_schema(tags=["Company"], parameters=swagger_params1.organization_params)
    def get(self, request, *args, **kwargs):
        """List companies for current org."""
        companies = self.get_queryset()
        serializer = CompanySerializer(companies, many=True)
        return Response(
            {"error": False, "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Company"],
        description="Company Create",
        parameters=swagger_params1.organization_params,
        request=CompanySwaggerSerializer
    )
    def post(self, request, *args, **kwargs):
        """Create new company."""
        # Check for duplicates
        if Company.objects.filter(org=request.profile.org, **request.data).exists():
            return Response(
                {"error": True, "message": "This data already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CompanySerializer(data=request.data)
        if serializer.is_valid():
            # perform_create automatically sets created_by and org
            self.perform_create(serializer)
            return Response(
                {"error": False, "message": "Company created successfully"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CompanyDetail(OrgFilteredDetailView):
    """
    Retrieve, update or delete company.

    Permissions:
    - Must be org member
    - Creator or admin can modify
    """
    model = Company
    serializer_class = CompanySerializer

    @extend_schema(tags=["Company"], parameters=swagger_params1.organization_params)
    def get(self, request, *args, **kwargs):
        """Get company details."""
        company = self.get_object()
        serializer = CompanySerializer(company)
        return Response(
            {"error": False, "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Company"],
        description="Company Update",
        parameters=swagger_params1.organization_params,
        request=CompanySerializer
    )
    def put(self, request, *args, **kwargs):
        """Update company."""
        company = self.get_object()
        serializer = CompanySerializer(company, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"error": False, "data": serializer.data, 'message': 'Updated Successfully'},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": True, 'message': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(tags=["Company"], parameters=swagger_params1.organization_params)
    def delete(self, request, *args, **kwargs):
        """Delete company."""
        company = self.get_object()
        company.delete()
        return Response(
            {"error": False, 'message': 'Deleted successfully'},
            status=status.HTTP_200_OK,
        )


# ============================================
# Lead Conversion Views
# ============================================

class LeadCheckDuplicatesView(APIView):
    """
    Check for potential duplicate accounts and contacts before lead conversion.

    Returns matching accounts and contacts based on lead's email, phone, and company name.
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Lead Conversion"],
        description="Check for potential duplicates before converting a lead",
        parameters=swagger_params1.organization_params,
        responses={200: LeadDuplicateCheckResponseSerializer}
    )
    def get(self, request, pk, *args, **kwargs):
        """Check for duplicate accounts and contacts."""
        try:
            lead = Lead.objects.get(pk=pk, org=request.profile.org)
        except Lead.DoesNotExist:
            return Response(
                {"error": True, "message": "Lead not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        service = LeadConversionService(
            lead=lead,
            user=request.user,
            org=request.profile.org
        )

        duplicates = service.check_duplicates()

        return Response({
            "error": False,
            "data": duplicates
        }, status=status.HTTP_200_OK)


class LeadConvertView(APIView):
    """
    Convert a lead into Account, Contact, and Opportunity.

    This endpoint performs an atomic conversion that:
    1. Creates or links to an Account
    2. Creates or links to a Contact
    3. Optionally creates an Opportunity
    4. Marks the lead as converted (read-only)

    All operations are performed in a single transaction - if any step fails,
    all changes are rolled back.
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Lead Conversion"],
        description="Convert a lead to Account, Contact, and Opportunity",
        parameters=swagger_params1.organization_params,
        request=LeadConversionRequestSerializer,
        responses={
            200: LeadConversionResponseSerializer,
            400: None,
            404: None
        }
    )
    def post(self, request, pk, *args, **kwargs):
        """Convert the lead."""
        # Get the lead
        try:
            lead = Lead.objects.get(pk=pk, org=request.profile.org)
        except Lead.DoesNotExist:
            return Response(
                {"error": True, "message": "Lead not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate request data
        serializer = LeadConversionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": True, "message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform conversion
        service = LeadConversionService(
            lead=lead,
            user=request.user,
            org=request.profile.org
        )

        try:
            result = service.convert(
                account_options=serializer.validated_data.get('account'),
                contact_options=serializer.validated_data.get('contact'),
                opportunity_options=serializer.validated_data.get('opportunity')
            )

            # Log the lead conversion
            from common.models import ActivityLog
            try:
                account_obj = result.get('account')
                contact_obj = result.get('contact')
                opportunity_obj = result.get('opportunity')
                ActivityLog.objects.create(
                    user=request.user,
                    user_email=request.user.email,
                    user_role=request.profile.role,
                    org=request.profile.org,
                    action="CONVERT",
                    entity_type="Lead",
                    entity_id=str(lead.id),
                    entity_name=lead.title or f"{lead.first_name} {lead.last_name}",
                    details={
                        "account_id": str(account_obj.id) if account_obj else '',
                        "contact_id": str(contact_obj.id) if contact_obj else '',
                        "opportunity_id": str(opportunity_obj.id) if opportunity_obj else '',
                    },
                )
            except Exception as log_error:
                pass  # Don't break conversion if logging fails

            response_data = {
                'success': True,
                'message': 'Lead converted successfully',
                'lead': result.get('lead'),
                'account': result.get('account'),
                'contact': result.get('contact'),
                'opportunity': result.get('opportunity')
            }

            response_serializer = LeadConversionResponseSerializer(response_data)

            return Response({
                "error": False,
                "message": "Lead converted successfully",
                "data": response_serializer.data
            }, status=status.HTTP_200_OK)

        except LeadConversionError as e:
            return Response(
                {"error": True, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": True, "message": f"Conversion failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )