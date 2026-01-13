from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from common import views
from common.views import EmailLoginView, LogoutView, LogOrgSelectionView

app_name = "api_common"

urlpatterns = [
    path("dashboard/", views.ApiHomeView.as_view()),

    # email + password login (SimpleJWT)
    path("auth/login/", EmailLoginView.as_view(), name="email_login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/log-org-selection/", LogOrgSelectionView.as_view(), name="log_org_selection"),

    path(
        "auth/refresh-token/",
        jwt_views.TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # GoogleLoginView
    path("auth/google/", views.GoogleLoginView.as_view()),

    # User Activation
    path("auth/activate-user/<str:uid>/<str:token>/<str:activation_key>/", views.ActivateUserView.as_view()),

    # Password Reset
    path("auth/forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("auth/reset-password/<str:uidb64>/<str:token>/", views.ResetPasswordView.as_view(), name="reset_password"),

    # Organizations
    path("org/", views.OrgProfileCreateView.as_view()),
    path('org/update/', views.OrgUpdateView.as_view(), name='org-update'),
    path("profile/", views.ProfileView.as_view()),

    # Users
    path("users/get-teams-and-users/", views.GetTeamsAndUsersView.as_view()),
    path("users/", views.UsersListView.as_view()),
    path("user/<str:pk>/", views.UserDetailView.as_view()),
    path("user/<str:pk>/resend-invitation/", views.ResendInvitationView.as_view()),
    path("user/<str:pk>/status/", views.UserStatusView.as_view()),

    # Documents
    path("documents/", views.DocumentListView.as_view()),
    path("documents/<str:pk>/", views.DocumentDetailView.as_view()),

    # API Settings
    path("api-settings/", views.DomainList.as_view()),
    path("api-settings/<str:pk>/", views.DomainDetailView.as_view()),

    # Activity Logs
    path("activity-logs/", views.ActivityLogListView.as_view()),
]