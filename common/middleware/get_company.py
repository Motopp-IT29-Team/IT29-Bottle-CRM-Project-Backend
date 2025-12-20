import jwt
from django.conf import settings
from django.contrib.auth import logout
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework import status
from rest_framework.response import Response
from crum import get_current_user
from django.utils.functional import SimpleLazyObject

from common.models import Org, Profile, User

# URLs that don't require authentication or org
EXEMPT_URLS = [
    '/api/auth/login/',
    '/api/auth/google/',
    '/api/auth/register/',
    '/api/auth/activate-user/',
    '/api/org/',
    '/admin/',
]

# URLs that need auth but can work without org/profile
AUTH_OPTIONAL_ORG_URLS = [
    '/api/auth/logout/',
]


def get_actual_value(request):
    if request.user is None:
        return None
    return request.user


class GetProfileAndOrg(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        return self.get_response(request)

    def process_request(self, request):
        # Skip middleware for exempt URLs
        for exempt_url in EXEMPT_URLS:
            if request.path.startswith(exempt_url):
                request.profile = None
                return
        
        # Check if this is an auth-optional-org URL
        is_auth_optional_org = False
        for optional_url in AUTH_OPTIONAL_ORG_URLS:
            if request.path.startswith(optional_url):
                is_auth_optional_org = True
                break

        try:
            request.profile = None
            user_id = None

            # Get JWT token from Authorization header
            if request.headers.get("Authorization"):
                token1 = request.headers.get("Authorization")
                if " " in token1:
                    token = token1.split(" ")[1]
                else:
                    token = token1
                decoded = jwt.decode(token, (settings.SECRET_KEY), algorithms=[settings.JWT_ALGO])
                user_id = decoded['user_id']

            # Get API key from Token header
            api_key = request.headers.get('Token')
            if api_key:
                try:
                    organization = Org.objects.get(api_key=api_key)
                    api_key_user = organization
                    request.META['org'] = api_key_user.id
                    profile = Profile.objects.filter(org=api_key_user, role="ADMIN").first()
                    user_id = profile.user.id
                except Org.DoesNotExist:
                    raise PermissionDenied('Invalid API Key')

            if user_id is not None:
                org_header = request.headers.get("org")
                if org_header and org_header != "null" and org_header != "None":
                    try:
                        profile = Profile.objects.get(
                            user_id=user_id, org=org_header, is_active=True
                        )
                        if profile:
                            request.profile = profile
                    except Profile.DoesNotExist:
                        # For auth-optional-org URLs, don't raise error, just leave profile as None
                        if not is_auth_optional_org:
                            raise PermissionDenied()
        except (ValidationError, jwt.DecodeError):
            raise PermissionDenied()