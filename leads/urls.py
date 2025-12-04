from django.urls import path

from leads import views

app_name = "api_leads"

urlpatterns = [
    path("create-from-site/", views.CreateLeadFromSite.as_view(), name="create_lead_from_site"),
    path("check-duplicate/", views.CheckDuplicateLeadView.as_view()),
    path("upload/", views.LeadUploadView.as_view()),
    path("companies/", views.CompaniesView.as_view()),
    path("comment/<str:pk>/", views.LeadCommentView.as_view()),
    path("company/<str:pk>/", views.CompanyDetail.as_view()),
    path("<str:pk>/attachments/", views.LeadAttachmentView.as_view()),
    path("attachments/<str:pk>/", views.LeadAttachmentView.as_view()),
    # Lead Conversion endpoints
    path("<str:pk>/convert/", views.LeadConvertView.as_view(), name="lead_convert"),
    path("<str:pk>/check-duplicates/", views.LeadCheckDuplicatesView.as_view(), name="lead_check_duplicates"),
    path("<str:pk>/", views.LeadDetailView.as_view()),
    path("", views.LeadListView.as_view()),
]