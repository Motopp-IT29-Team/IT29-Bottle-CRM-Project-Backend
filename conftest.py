"""
Root conftest.py - Global fixtures available to all tests.

This file should contain ONLY truly global fixtures that are used across
multiple modules. Module-specific fixtures should go in their respective
conftest.py files (e.g., common/tests/conftest.py, leads/tests/conftest.py).

Available fixtures:
- api_client: Clean DRF APIClient
- org: Test organization
"""
import pytest
from rest_framework.test import APIClient
from common.models import Org


@pytest.fixture
def api_client():
    """
    Return a clean DRF APIClient instance.

    This is the most basic fixture - just a client with no authentication.
    Use authenticated_client from module-specific conftest if you need auth.
    """
    return APIClient()


@pytest.fixture
def org(db):
    """
    Create and return a test organization.

    This is a global fixture because almost all tests need an organization.
    """
    return Org.objects.create(
        name="Test Organization",
        is_active=True,
    )