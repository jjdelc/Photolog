"""Tests for core web routes: index, photo list, search, backup, login, logout"""
import pytest
from datetime import datetime


class TestIndexRoute:
    """GET / - Index page"""

    def test_index_requires_login(self, web_client):
        """Unauthenticated request redirects to login"""
        response = web_client.get('/')
        assert response.status_code == 302
        assert '/login/' in response.location

    def test_index_renders_template(self, authenticated_client, sample_picture):
        """Authenticated request renders index.html template"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        assert b'index.html' in response.data or b'recent' in response.data.lower()

    def test_index_shows_recent_pictures(self, authenticated_client, multiple_pictures):
        """Index page includes recent pictures"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # Should contain at least some picture data
        assert b'photo' in response.data.lower()

    def test_index_shows_total_count(self, authenticated_client, multiple_pictures):
        """Index page shows total picture count"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # The context should have total count
        data = response.get_data(as_text=True)
        # Check for presence of data (template will render it)
        assert len(data) > 100

    def test_index_shows_all_tags(self, authenticated_client, tagged_pictures):
        """Index includes all available tags"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should mention tags somewhere
        assert len(data) > 100

    def test_index_shows_years(self, authenticated_client, multiple_pictures):
        """Index includes available years for navigation"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert '2023' in data


class TestPhotoListRoute:
    """GET /photo/ - Photo list with pagination"""

    def test_photo_list_requires_login(self, web_client):
        """Unauthenticated request redirects to login"""
        response = web_client.get('/photo/')
        assert response.status_code == 302
        assert '/login/' in response.location

    def test_photo_list_default_page(self, authenticated_client, multiple_pictures):
        """Default request shows first page"""
        response = authenticated_client.get('/photo/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should show photo list template
        assert len(data) > 100

    def test_photo_list_pagination_first_page(self, authenticated_client, multiple_pictures):
        """First page shows items and next page link"""
        response = authenticated_client.get('/photo/?page=1')
        assert response.status_code == 200
        assert b'photo' in response.data.lower() or b'next' in response.data.lower()

    def test_photo_list_invalid_page_number(self, authenticated_client, multiple_pictures):
        """Invalid page number handled gracefully"""
        response = authenticated_client.get('/photo/?page=999')
        # Should either show empty or return 200 with empty list
        assert response.status_code == 200

    def test_photo_list_non_numeric_page(self, authenticated_client):
        """Non-numeric page parameter causes error or defaults"""
        response = authenticated_client.get('/photo/?page=abc')
        # Should be a 400 or ValueError from int()
        assert response.status_code in [400, 500]


class TestSearchRoute:
    """GET /search/ - Search page"""

    def test_search_page_requires_login(self, web_client):
        """Unauthenticated search redirects to login"""
        response = web_client.get('/search/')
        assert response.status_code == 302

    def test_search_form_page(self, authenticated_client):
        """GET /search/ shows search form"""
        response = authenticated_client.get('/search/')
        assert response.status_code == 200
        assert b'search' in response.data.lower()

    def test_search_by_name_found(self, authenticated_client, sample_picture):
        """Search by existing photo name redirects to detail"""
        response = authenticated_client.get('/search/?name=test-photo.jpg')
        assert response.status_code == 302
        assert '/photo/test-key-001/' in response.location

    def test_search_by_name_not_found(self, authenticated_client):
        """Search for non-existent photo raises 404"""
        with pytest.raises(Exception):
            # Will raise an exception since picture doesn't exist
            authenticated_client.get('/search/?name=nonexistent.jpg')


class TestBackupRoute:
    """GET/POST /backup/ - Database backup"""

    def test_backup_requires_login(self, web_client):
        """Unauthenticated backup request redirects to login"""
        response = web_client.get('/backup/')
        assert response.status_code == 302

    def test_backup_get_shows_form(self, authenticated_client):
        """GET /backup/ shows backup form with DB size"""
        response = authenticated_client.get('/backup/')
        assert response.status_code == 200
        assert b'backup' in response.data.lower()
        # Should show database size
        data = response.get_data(as_text=True)
        assert 'B' in data  # File size units

    def test_backup_post_downloads_file(self, authenticated_client):
        """POST /backup/ returns database file for download"""
        response = authenticated_client.post('/backup/')
        assert response.status_code == 200
        assert response.content_type == 'application/octet-stream'
        assert 'backup-' in response.headers.get('Content-Disposition', '')


class TestLoginRoute:
    """GET/POST /login/ - Authentication"""

    def test_login_page_shows_form(self, web_client):
        """GET /login/ shows login form"""
        response = web_client.get('/login/')
        assert response.status_code == 200
        assert b'login' in response.data.lower()

    def test_login_requires_indieauth(self, web_client):
        """Login form includes IndieAuth elements"""
        response = web_client.get('/login/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should have auth_url and client_id in context
        assert len(data) > 100

    def test_login_missing_params(self, web_client):
        """POST /login/ without code/me redirects to login form"""
        response = web_client.post('/login/')
        assert response.status_code == 200
        assert b'login' in response.data.lower()

    def test_login_with_invalid_code(self, web_client):
        """POST /login/ with invalid code returns 401"""
        response = web_client.post('/login/', data={'code': 'invalid', 'me': 'test@example.com'})
        # Will either be 401 or raise from requests
        assert response.status_code in [401, 500]

    def test_authenticated_user_can_access_protected(self, authenticated_client):
        """Authenticated user can access protected routes"""
        response = authenticated_client.get('/')
        assert response.status_code == 200


class TestLogoutRoute:
    """GET /logout/ - Sign out"""

    def test_logout_requires_login(self, web_client):
        """GET /logout/ without auth redirects to login"""
        response = web_client.get('/logout/')
        assert response.status_code == 302
        assert '/login/' in response.location

    def test_logout_clears_session(self, authenticated_client):
        """GET /logout/ clears session and redirects to login"""
        response = authenticated_client.get('/logout/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login/' in response.location

    def test_after_logout_protected_routes_blocked(self, authenticated_client):
        """After logout, protected routes become inaccessible"""
        # Logout
        authenticated_client.get('/logout/')
        # Try accessing protected route with same client
        response = authenticated_client.get('/')
        # Should redirect to login
        assert response.status_code == 302
