"""
Test coverage:
- Contact CRUD operations (Create, Read, Update, Delete)
- Permissions (ADMIN vs regular user, assigned_to)
- Filtering and search
- Comments and attachments
- Teams and assigned_to functionality
- Edge cases and error handling

Run with: pytest contacts/tests/test_contacts.py -v
Coverage: pytest contacts/tests/test_contacts.py --cov=contacts --cov-report=html
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from common.models import Address, Attachments, Comment
from contacts.models import Contact


@pytest.mark.django_db
class TestContactCreate:
    """Test contact creation."""
    url = "/api/contacts/"

    def test_admin_can_create_contact(self, admin_authenticated_client, org):
        """Test that admin can create contact."""
        contact_data = {
            'salutation': 'Mr',
            'first_name': 'John',
            'last_name': 'Doe',
            'organization': 'Test Company',
            'title': 'CEO',
            'primary_email': 'john@example.com',
            'secondary_email': 'john.secondary@example.com',
            'mobile_number': '+31612345678',
            'secondary_number': '+31687654321',
            'department': 'Sales',
            'language': 'English',
            'do_not_call': False,
            'address_line': '123 Test St',
            'street': 'Main Street',
            'city': 'Amsterdam',
            'state': 'NH',
            'postcode': '1011',
            'country': 'NL',
            'description': 'Test description',
            'linked_in_url': 'https://linkedin.com/in/johndoe',
            'facebook_url': 'https://facebook.com/johndoe',
            'twitter_username': '@johndoe',
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'Contact created Successfuly' in response.data['message']

        contact = Contact.objects.get(primary_email='john@example.com')
        assert contact.first_name == 'John'
        assert contact.organization == 'Test Company'
        assert contact.org == org

    def test_create_contact_with_assigned_to(self, admin_authenticated_client, org, create_user, create_profile):
        """Test creating contact with assigned users."""
        user1 = create_user(email='user1@test.com')
        profile1 = create_profile(user=user1, org=org, role='USER')

        contact_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'organization': 'Test Org',
            'primary_email': 'jane@test.com',
            'mobile_number': '+31623456789',
            'department': 'Marketing',
            'language': 'Dutch',
            'address_line': 'Test Address',
            'city': 'Rotterdam',
            'country': 'NL',
            'assigned_to': [str(profile1.id)],
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        contact = Contact.objects.get(primary_email='jane@test.com')
        assert profile1 in contact.assigned_to.all()

    def test_create_contact_with_teams(self, admin_authenticated_client, org, create_team, create_user, create_profile):
        """Test creating contact with teams."""
        user1 = create_user(email='user1@test.com')
        profile1 = create_profile(user=user1, org=org)
        team = create_team('Sales Team', org, users=[profile1])

        contact_data = {
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'organization': 'Test Org',
            'primary_email': 'bob@test.com',
            'mobile_number': '+31634567890',
            'department': 'Sales',
            'language': 'English',
            'address_line': 'Test Address',
            'city': 'Utrecht',
            'country': 'NL',
            'teams': [str(team.id)],
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        contact = Contact.objects.get(primary_email='bob@test.com')
        assert team in contact.teams.all()

    def test_create_contact_with_attachment(self, admin_authenticated_client, org):
        """Test creating contact with file attachment."""
        file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile('test.pdf', file_content, content_type='application/pdf')

        contact_data = {
            'first_name': 'Alice',
            'last_name': 'Williams',
            'organization': 'Test Org',
            'primary_email': 'alice@test.com',
            'mobile_number': '+31645678901',
            'department': 'HR',
            'language': 'English',
            'address_line': 'Test Address',
            'city': 'The Hague',
            'country': 'NL',
            'contact_attachment': uploaded_file,
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='multipart')

        assert response.status_code == status.HTTP_200_OK
        contact = Contact.objects.get(primary_email='alice@test.com')
        assert contact.contact_attachment.count() > 0

    def test_create_contact_duplicate_email_fails(self, admin_authenticated_client, org, create_contact):
        """Test that creating contact with duplicate email fails."""
        existing_contact = create_contact(org=org, primary_email='duplicate@test.com')

        contact_data = {
            'first_name': 'Duplicate',
            'last_name': 'User',
            'organization': 'Test Org',
            'primary_email': 'duplicate@test.com',
            'mobile_number': '+31656789012',
            'department': 'IT',
            'language': 'English',
            'address_line': 'Test Address',
            'city': 'Eindhoven',
            'country': 'NL',
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_contact_duplicate_first_name_fails(self, admin_authenticated_client, org, create_contact):
        """Test that creating contact with duplicate first name fails."""
        existing_contact = create_contact(org=org, first_name='DuplicateName')

        contact_data = {
            'first_name': 'DuplicateName',
            'last_name': 'Different',
            'organization': 'Test Org',
            'primary_email': 'unique@test.com',
            'mobile_number': '+31667890123',
            'department': 'Finance',
            'language': 'English',
            'address_line': 'Test Address',
            'city': 'Groningen',
            'country': 'NL',
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'contact_errors' in response.data['errors']

    def test_create_contact_missing_required_fields_fails(self, admin_authenticated_client):
        """Test that creating contact without required fields fails."""
        contact_data = {
            'salutation': 'Mr',
        }

        response = admin_authenticated_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] is True

    def test_unauthenticated_user_cannot_create_contact(self, api_client):
        """Test that unauthenticated user cannot create contact."""
        contact_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'primary_email': 'test@test.com',
        }

        response = api_client.post(self.url, contact_data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestContactList:
    """Test contact listing."""
    url = "/api/contacts/"

    def test_admin_can_list_all_contacts(self, admin_authenticated_client, org, create_contact):
        """Test that admin can see all contacts in org."""
        contact1 = create_contact(org=org, first_name='John', suffix='1')
        contact2 = create_contact(org=org, first_name='Jane', suffix='2')

        response = admin_authenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert 'contact_obj_list' in response.data
        assert len(response.data['contact_obj_list']) >= 2

    def test_regular_user_sees_all_contacts(self, authenticated_client, org, create_contact):
        """Test that regular user can see all contacts in organization."""
        contact1 = create_contact(org=org, first_name='Assigned', suffix='1')
        contact1.assigned_to.add(authenticated_client.profile)
        contact2 = create_contact(org=org, first_name='Other', suffix='2')

        response = authenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        contact_ids = [c['id'] for c in response.data['contact_obj_list']]
        assert str(contact1.id) in contact_ids
        assert str(contact2.id) in contact_ids

    def test_filter_contacts_by_name(self, admin_authenticated_client, org, create_contact):
        """Test filtering contacts by name."""
        contact1 = create_contact(org=org, first_name='Alice', suffix='1')
        contact2 = create_contact(org=org, first_name='Bob', suffix='2')

        response = admin_authenticated_client.get(f'{self.url}?name=Alice')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['contact_obj_list']) >= 1
        assert any(c['first_name'] == 'Alice' for c in response.data['contact_obj_list'])

    def test_filter_contacts_by_city(self, admin_authenticated_client, org, create_contact, create_address):
        """Test filtering contacts by city."""
        address1 = create_address(city='Amsterdam')
        address2 = create_address(city='Rotterdam')

        contact1 = create_contact(org=org, address=address1, suffix='1')
        contact2 = create_contact(org=org, address=address2, suffix='2')

        response = admin_authenticated_client.get(f'{self.url}?city=Amsterdam')

        assert response.status_code == status.HTTP_200_OK

    def test_filter_contacts_by_email(self, admin_authenticated_client, org, create_contact):
        """Test filtering contacts by email."""
        contact1 = create_contact(org=org, primary_email='search@test.com')

        response = admin_authenticated_client.get(f'{self.url}?email=search')

        assert response.status_code == status.HTTP_200_OK

    def test_pagination_works(self, admin_authenticated_client, org, create_contact):
        """Test that pagination works correctly."""
        for i in range(15):
            create_contact(org=org, first_name=f'Contact{i}', suffix=str(i))

        response = admin_authenticated_client.get(f'{self.url}?limit=10')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['contact_obj_list']) == 10
        assert 'offset' in response.data

    def test_unauthenticated_user_cannot_list_contacts(self, api_client):
        """Test that unauthenticated user cannot list contacts."""
        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestContactDetail:
    """Test contact detail view."""

    def test_admin_can_view_any_contact(self, admin_authenticated_client, org, create_contact):
        """Test that admin can view any contact."""
        contact = create_contact(org=org)
        url = f'/api/contacts/{contact.id}/'

        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'contact_obj' in response.data
        assert response.data['contact_obj']['id'] == str(contact.id)

    def test_assigned_user_can_view_contact(self, admin_authenticated_client, org, admin_profile, create_contact):
        """Test that user assigned to contact can view it."""
        contact = create_contact(org=org)
        contact.assigned_to.add(admin_profile)

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_unrelated_user_can_view_contact(self, authenticated_client, org, create_contact):
        """Test that any user can view contacts in their organization."""
        contact = create_contact(org=org)

        url = f'/api/contacts/{contact.id}/'
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['contact_obj']['id'] == str(contact.id)

    def test_contact_detail_includes_address(self, admin_authenticated_client, org, create_contact, create_address):
        """Test that contact detail includes address."""
        address = create_address(city='TestCity')
        contact = create_contact(org=org, address=address)

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'address_obj' in response.data
        assert response.data['address_obj']['city'] == 'TestCity'

    def test_contact_detail_includes_attachments(self, admin_authenticated_client, org, create_contact):
        """Test that contact detail includes attachments."""
        contact = create_contact(org=org)
        Attachments.objects.create(
            file_name='test.pdf',
            contact=contact,
            attachment='test.pdf'
        )

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'attachments' in response.data
        assert len(response.data['attachments']) > 0

    def test_contact_detail_includes_comments(self, admin_authenticated_client, org, admin_profile, create_contact):
        """Test that contact detail includes comments."""
        contact = create_contact(org=org)
        Comment.objects.create(
            contact=contact,
            comment='Test comment',
            commented_by=admin_profile
        )

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'comments' in response.data
        assert len(response.data['comments']) > 0


@pytest.mark.django_db
class TestContactUpdate:
    """Test contact update."""

    def test_admin_can_update_any_contact(self, admin_authenticated_client, org, create_contact):
        """Test that admin can update any contact."""
        contact = create_contact(org=org, first_name='OldName')
        url = f'/api/contacts/{contact.id}/'

        update_data = {
            'first_name': 'NewName',
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Updated Address',
            'city': 'Updated City',
            'country': 'NL',
        }

        response = admin_authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'Contact Updated Successfully' in response.data['message']

        contact.refresh_from_db()
        assert contact.first_name == 'NewName'

    def test_assigned_user_can_update_contact(self, authenticated_client, org, create_contact):
        """Test that assigned user can update contact."""
        contact = create_contact(org=org)
        contact.assigned_to.add(authenticated_client.profile)

        url = f'/api/contacts/{contact.id}/'
        update_data = {
            'first_name': 'Updated',
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
        }

        response = authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_200_OK

    def test_unrelated_user_cannot_update_contact(self, authenticated_client, org, create_contact):
        """Test that unrelated user cannot update contact."""
        contact = create_contact(org=org)

        url = f'/api/contacts/{contact.id}/'
        update_data = {
            'first_name': 'Hacked',
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
        }

        response = authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_contact_assigned_to(self, admin_authenticated_client, org, create_contact, create_user, create_profile):
        """Test updating contact's assigned users."""
        contact = create_contact(org=org)
        user1 = create_user(email='user1@test.com')
        profile1 = create_profile(user=user1, org=org)

        url = f'/api/contacts/{contact.id}/'
        update_data = {
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
            'assigned_to': str(profile1.id),
        }

        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_update_contact_teams(self, admin_authenticated_client, org, create_contact, create_team, create_user, create_profile):
        """Test updating contact's teams."""
        contact = create_contact(org=org)
        user1 = create_user(email='user1@test.com')
        profile1 = create_profile(user=user1, org=org)
        team = create_team('Updated Team', org, users=[profile1])

        url = f'/api/contacts/{contact.id}/'
        update_data = {
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
            'teams': str(team.id),
        }

        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_update_contact_from_different_org(self, admin_authenticated_client, org, create_contact):
        """Test that cannot update contact from different org."""
        from common.models import Org
        other_org = Org.objects.create(name='Other Org', is_active=True)
        contact = create_contact(org=other_org)

        url = f'/api/contacts/{contact.id}/'
        update_data = {
            'first_name': 'Hacked',
            'last_name': contact.last_name,
            'organization': contact.organization,
            'primary_email': contact.primary_email,
            'mobile_number': str(contact.mobile_number),
            'department': contact.department,
            'language': contact.language,
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
        }

        response = admin_authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestContactDelete:
    """Test contact deletion."""

    def test_admin_can_delete_any_contact(self, admin_authenticated_client, org, create_contact):
        """Test that admin can delete any contact."""
        contact = create_contact(org=org)
        url = f'/api/contacts/{contact.id}/'

        response = admin_authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'Contact Deleted Successfully' in response.data['message']
        assert not Contact.objects.filter(id=contact.id).exists()

    def test_regular_user_cannot_delete_contact(self, authenticated_client, org, create_contact):
        """Test that regular user cannot delete contact (only admin can)."""
        contact = create_contact(org=org)
        contact.assigned_to.add(authenticated_client.profile)

        url = f'/api/contacts/{contact.id}/'
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_contact_also_deletes_address(self, admin_authenticated_client, org, create_contact, create_address):
        """Test that deleting contact also deletes associated address."""
        address = create_address()
        contact = create_contact(org=org, address=address)
        address_id = address.id

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert not Address.objects.filter(id=address_id).exists()

    def test_cannot_delete_contact_from_different_org(self, admin_authenticated_client, org, create_contact):
        """Test that cannot delete contact from different org."""
        from common.models import Org
        other_org = Org.objects.create(name='Other Org', is_active=True)
        contact = create_contact(org=other_org)

        url = f'/api/contacts/{contact.id}/'
        response = admin_authenticated_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestContactComments:
    """Test contact comments functionality."""

    def test_admin_can_add_comment_to_contact(self, admin_authenticated_client, org, create_contact):
        """Test adding comment to contact."""
        contact = create_contact(org=org)
        url = f'/api/contacts/{contact.id}/'

        response = admin_authenticated_client.post(url, {'comment': 'Test comment'}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'comments' in response.data

    def test_assigned_user_can_add_comment(self, authenticated_client, org, create_contact):
        """Test that assigned user can add comment."""
        contact = create_contact(org=org)
        contact.assigned_to.add(authenticated_client.profile)

        url = f'/api/contacts/{contact.id}/'
        response = authenticated_client.post(url, {'comment': 'Assigned user comment'}, format='json')

        assert response.status_code == status.HTTP_200_OK

    def test_unrelated_user_cannot_add_comment(self, authenticated_client, org, create_contact):
        """Test that unrelated user cannot add comment."""
        contact = create_contact(org=org)

        url = f'/api/contacts/{contact.id}/'
        response = authenticated_client.post(url, {'comment': 'Unauthorized comment'}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_edit_own_comment(self, admin_authenticated_client, org, admin_profile, create_contact):
        """Test editing own comment."""
        contact = create_contact(org=org)
        comment = Comment.objects.create(
            contact=contact,
            comment='Original comment',
            commented_by=admin_profile
        )

        url = f'/api/contacts/comment/{comment.id}/'
        update_data = {'comment': 'Updated comment'}

        response = admin_authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.comment == 'Updated comment'

    def test_cannot_edit_others_comment(self, authenticated_client, org, admin_profile, create_contact):
        """Test that cannot edit someone else's comment."""
        contact = create_contact(org=org)
        comment = Comment.objects.create(
            contact=contact,
            comment='Admin comment',
            commented_by=admin_profile
        )

        url = f'/api/contacts/comment/{comment.id}/'
        update_data = {'comment': 'Hacked comment'}

        response = authenticated_client.put(url, update_data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_comment(self, admin_authenticated_client, org, admin_profile, create_contact):
        """Test deleting own comment."""
        contact = create_contact(org=org)
        comment = Comment.objects.create(
            contact=contact,
            comment='To be deleted',
            commented_by=admin_profile
        )
        comment_id = comment.id

        url = f'/api/contacts/comment/{comment_id}/'
        response = admin_authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert not Comment.objects.filter(id=comment_id).exists()


@pytest.mark.django_db
class TestContactAttachments:
    """Test contact attachments functionality."""

    def test_add_attachment_to_contact(self, admin_authenticated_client, org, create_contact):
        """Test adding attachment to contact."""
        contact = create_contact(org=org)
        url = f'/api/contacts/{contact.id}/'

        file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile('test_doc.pdf', file_content, content_type='application/pdf')

        data = {
            'contact_attachment': uploaded_file,
        }

        response = admin_authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_200_OK
        assert 'attachments' in response.data

    def test_delete_attachment(self, admin_authenticated_client, org, admin_profile, create_contact):
        """Test deleting attachment."""
        contact = create_contact(org=org)
        attachment = Attachments.objects.create(
            file_name='test.pdf',
            contact=contact,
            created_by=admin_profile.user,
            attachment='test.pdf'
        )
        attachment_id = attachment.id

        url = f'/api/contacts/attachment/{attachment_id}/'
        response = admin_authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert not Attachments.objects.filter(id=attachment_id).exists()

    def test_cannot_delete_others_attachment(self, authenticated_client, org, admin_profile, create_contact):
        """Test that cannot delete someone else's attachment."""
        contact = create_contact(org=org)
        attachment = Attachments.objects.create(
            file_name='admin_file.pdf',
            contact=contact,
            created_by=admin_profile.user,
            attachment='admin_file.pdf'
        )

        url = f'/api/contacts/attachment/{attachment.id}/'
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestContactEdgeCases:
    """Test edge cases and error handling."""

    def test_contact_not_found(self, admin_authenticated_client):
        """Test accessing non-existent contact."""
        fake_uuid = '00000000-0000-0000-0000-000000000000'
        url = f'/api/contacts/{fake_uuid}/'

        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_contact_with_invalid_phone_format(self, admin_authenticated_client, org):
        """Test creating contact with invalid phone format."""
        contact_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'organization': 'Test Org',
            'primary_email': 'test@test.com',
            'mobile_number': 'invalid-phone',
            'department': 'Sales',
            'language': 'English',
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
        }

        response = admin_authenticated_client.post('/api/contacts/', contact_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_contact_with_invalid_email_format(self, admin_authenticated_client, org):
        """Test creating contact with invalid email format."""
        contact_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'organization': 'Test Org',
            'primary_email': 'invalid-email',
            'mobile_number': '+31612345678',
            'department': 'Sales',
            'language': 'English',
            'address_line': 'Address',
            'city': 'City',
            'country': 'NL',
        }

        response = admin_authenticated_client.post('/api/contacts/', contact_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_contacts_returns_correct_metadata(self, admin_authenticated_client, org, create_contact):
        """Test that list endpoint returns correct metadata."""
        for i in range(5):
            create_contact(org=org, suffix=str(i))

        response = admin_authenticated_client.get('/api/contacts/')

        assert response.status_code == status.HTTP_200_OK
        assert 'contacts_count' in response.data
        assert 'per_page' in response.data
        assert 'countries' in response.data
        assert 'users' in response.data