from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

app_name = "crm"

def api_home(request):
    return JsonResponse({
        'status': 'running',
        'message': 'Bottle CRM API is running successfully',
        'endpoints': {
            'api': '/api/',
            'swagger': '/swagger-ui/',
            'redoc': '/api/schema/redoc/',
            'admin': '/admin/',
            'django_admin': '/django/admin/',
        }
    })


urlpatterns = [
    path("", api_home, name="api_home"),
    re_path(r"^healthz/$", TemplateView.as_view(template_name="healthz.html"), name="healthz"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/", include("common.app_urls", namespace="common_urls")),
    path("logout/", views.LogoutView.as_view(), {"next_page": "/login/"}, name="logout"),
    path("django/admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("pages/", include(wagtail_urls)),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)