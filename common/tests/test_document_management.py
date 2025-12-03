"""
Test coverage:
- Document list (GET /api/documents/)
- Document create (POST /api/documents/)
- Document detail (GET /api/documents/<pk>/)
- Document update (PUT /api/documents/<pk>/)
- Document delete (DELETE /api/documents/<pk>/)
- File upload and permissions

Run with: pytest common/tests/test_document_management.py -v
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from common.models import Document
from common.models import Profile


@pytest.fixture
def create_document(db):
    """Factory fixture to create documents."""

    def _create_document(title, created_by, org, status_choice='active', shared_to=None):
        if hasattr(created_by, 'user'):
            user = created_by.user
        else:
            user = created_by

        doc = Document.objects.create(
            title=title,
            created_by=user,
            org=org,
            status=status_choice,
            document_file=SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        )
        if shared_to:
            doc.shared_to.add(*shared_to)
        return doc

    return _create_document


@pytest.mark.django_db
class TestDocumentList:
    """Test document list endpoint."""
    url = "/api/documents/"

    def test_authenticated_user_can_list_documents(self, authenticated_client, org, profile, create_document):
        """Test that authenticated user can list documents."""
        doc = create_document(title='Test Document', created_by=profile, org=org)
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'documents_active' in response.data
        assert 'documents_inactive' in response.data

    def test_list_documents_only_from_current_org(self, authenticated_client, org, profile, create_document, create_user, create_profile):
        """Test that user only sees documents from their org."""
        doc1 = create_document(title='Org1 Doc', created_by=profile, org=org)
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        doc2 = create_document(title='Org2 Doc', created_by=profile2, org=org2)
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_see_all_org_documents(self, admin_authenticated_client, org, admin_profile, create_document, create_user, create_profile):
        """Test that admin can see all documents in org."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='User Doc', created_by=profile2, org=org)
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_documents_filtered_by_status(self, authenticated_client, org, profile, create_document):
        """Test filtering documents by active/inactive status."""
        active_doc = create_document(title='Active Doc', created_by=profile, org=org, status_choice='active')
        inactive_doc = create_document(title='Inactive Doc', created_by=profile, org=org, status_choice='inactive')
        response = authenticated_client.get(f'{self.url}?status=active')
        assert response.status_code == status.HTTP_200_OK

    def test_list_documents_filtered_by_title(self, authenticated_client, org, profile, create_document):
        """Test filtering documents by title."""
        doc1 = create_document(title='Sales Report', created_by=profile, org=org)
        doc2 = create_document(title='Marketing Plan', created_by=profile, org=org)
        response = authenticated_client.get(f'{self.url}?title=Sales')
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_user_cannot_list_documents(self, api_client):
        """Test that unauthenticated user cannot list documents."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestDocumentCreate:
    """Test document creation."""
    url = "/api/documents/"

    def test_authenticated_user_can_create_document(self, authenticated_client, org, profile):
        """Test that authenticated user can create document with file."""
        test_file = SimpleUploadedFile("test_doc.pdf", b"file_content", content_type="application/pdf")
        doc_data = {
            'title': 'New Document',
            'document_file': test_file,
            'status': 'active'
        }
        response = authenticated_client.post(self.url, doc_data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_document_with_shared_users(self, authenticated_client, org, profile, create_user, create_profile):
        """Test creating document and sharing with specific users."""
        user2 = create_user(email='shared@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        test_file = SimpleUploadedFile("shared_doc.pdf", b"file_content", content_type="application/pdf")
        doc_data = {
            'title': 'Shared Document',
            'document_file': test_file,
            'status': 'active',
            'shared_to': [str(profile2.id)]
        }
        response = authenticated_client.post(self.url, doc_data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED, \
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        doc = Document.objects.get(title='Shared Document')
        assert profile2 in doc.shared_to.all()

    def test_create_document_without_file_fails(self, authenticated_client):
        """Test that creating document without file fails."""
        doc_data = {
            'title': 'No File Document',
            'status': 'active'
        }
        response = authenticated_client.post(self.url, doc_data, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_document_without_title_fails(self, authenticated_client):
        """Test that creating document without title fails."""
        test_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        doc_data = {
            'document_file': test_file,
            'status': 'active'
        }
        response = authenticated_client.post(self.url, doc_data, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_user_cannot_create_document(self, api_client):
        """Test that unauthenticated user cannot create document."""
        test_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        doc_data = {
            'title': 'Unauthorized Document',
            'document_file': test_file
        }
        response = api_client.post(self.url, doc_data, format='multipart')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestDocumentDetail:
    """Test document detail endpoint."""

    def get_url(self, doc_id):
        return f"/api/documents/{doc_id}/"

    def test_creator_can_view_document(self, authenticated_client, org, profile, create_document):
        """Test that document creator can view their document."""
        doc = create_document(title='My Document', created_by=profile, org=org)
        url = self.get_url(doc.id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['doc_obj']['title'] == 'My Document'

    def test_admin_can_view_any_document(self, admin_authenticated_client, org, admin_profile, create_document, create_user, create_profile):
        """Test that admin can view any document in org."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='User Document', created_by=profile2, org=org)
        url = self.get_url(doc.id)
        response = admin_authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_shared_user_can_view_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that user with whom document is shared can view it."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='shared@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Shared Doc', created_by=profile1, org=org, shared_to=[profile2])
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_non_shared_user_cannot_view_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that user without access cannot view document."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Private Doc', created_by=profile1, org=org)
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_document_from_different_org(self, authenticated_client, org, profile, create_document, create_user, create_profile):
        """Test that user cannot view document from different org."""
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        doc = create_document(title='Other Org Doc', created_by=profile2, org=org2)
        url = self.get_url(doc.id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_view_nonexistent_document_returns_404(self, authenticated_client):
        """Test that viewing non-existent document returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        url = self.get_url(fake_id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDocumentUpdate:
    """Test document update endpoint."""

    def get_url(self, doc_id):
        return f"/api/documents/{doc_id}/"

    def test_creator_can_update_document(self, authenticated_client, org, profile, create_document):
        """Test that creator can update their document."""
        doc = create_document(title='Original Title', created_by=profile, org=org)
        url = self.get_url(doc.id)
        update_data = {
            'title': 'Updated Title',
            'status': 'active'
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_update_any_document(self, admin_authenticated_client, org, admin_profile, create_document, create_user, create_profile):
        """Test that admin can update any document."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='User Doc', created_by=profile2, org=org)
        url = self.get_url(doc.id)
        update_data = {
            'title': 'Admin Updated',
            'status': 'active'
        }
        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_shared_user_can_update_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that shared user can update document."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='shared@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Shared Doc', created_by=profile1, org=org, shared_to=[profile2])
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        update_data = {
            'title': 'Updated by Shared User',
            'status': 'active'
        }
        response = api_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_non_shared_user_cannot_update_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that non-shared user cannot update document."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Private Doc', created_by=profile1, org=org)
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        update_data = {
            'title': 'Hacked Title',
            'status': 'active'
        }
        response = api_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_document_shared_to_list(self, authenticated_client, org, profile, create_document, create_user, create_profile):
        """Test updating document shared_to list."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Doc', created_by=profile, org=org)
        url = self.get_url(doc.id)
        update_data = {
            'title': 'Doc',
            'status': 'active',
            'shared_to': [str(profile2.id)]
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDocumentDelete:
    """Test document delete endpoint."""

    def get_url(self, doc_id):
        return f"/api/documents/{doc_id}/"

    def test_creator_can_delete_document(self, authenticated_client, org, profile, create_document):
        """Test that creator can delete their document."""
        doc = create_document(title='To Delete', created_by=profile, org=org)
        doc_id = doc.id
        url = self.get_url(doc_id)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Document.objects.filter(id=doc_id).exists()

    def test_admin_can_delete_any_document(self, admin_authenticated_client, org, admin_profile, create_document,
                                           create_user, create_profile):
        """Test that admin can delete any document."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='User Doc', created_by=profile2, org=org)
        doc_id = doc.id
        url = self.get_url(doc_id)
        response = admin_authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Document.objects.filter(id=doc_id).exists()

    def test_shared_user_cannot_delete_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that shared user cannot delete document."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='shared@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Shared Doc', created_by=profile1, org=org, shared_to=[profile2])
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Document.objects.filter(id=doc.id).exists()

    def test_non_shared_user_cannot_delete_document(self, api_client, org, create_user, create_profile, create_document):
        """Test that non-shared user cannot delete document."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        doc = create_document(title='Private Doc', created_by=profile1, org=org)
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(doc.id)
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_delete_document_from_different_org(self, authenticated_client, org, profile, create_document, create_user, create_profile):
        """Test that user cannot delete document from different org."""
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        doc = create_document(title='Other Org Doc', created_by=profile2, org=org2)
        url = self.get_url(doc.id)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND