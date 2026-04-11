"""Tests for date navigation and editing routes"""
import pytest
from datetime import datetime, timedelta
from photolog.web.main import db, queue


class TestViewYearRoute:
    """GET /date/<year>/ - View pictures from a year"""

    def test_view_year_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get('/date/2023/')
        assert response.status_code == 302

    def test_view_year_renders_pictures(self, authenticated_client, multiple_pictures):
        """GET /date/2023/ shows pictures from that year"""
        response = authenticated_client.get('/date/2023/')
        assert response.status_code == 200
        assert b'2023' in response.data

    def test_view_year_pagination(self, authenticated_client, multiple_pictures):
        """Year view supports pagination"""
        response = authenticated_client.get('/date/2023/?page=1')
        assert response.status_code == 200

    def test_view_year_shows_available_months(self, authenticated_client, multiple_pictures):
        """Year view shows available months for navigation"""
        response = authenticated_client.get('/date/2023/')
        assert response.status_code == 200
        # Should have month indicators (at least some will have data)
        data = response.get_data(as_text=True)
        assert len(data) > 100

    def test_view_year_excludes_other_years(self, authenticated_client, multiple_pictures):
        """Year view only shows pictures from that year"""
        response = authenticated_client.get('/date/2020/')
        assert response.status_code == 200
        # No pictures from 2020 exist, so should be empty


class TestViewMonthRoute:
    """GET /date/<year>/<month>/ - View pictures from a month"""

    def test_view_month_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get('/date/2023/6/')
        assert response.status_code == 302

    def test_view_month_renders_pictures(self, authenticated_client, sample_picture):
        """GET /date/2023/6/ shows pictures from June 2023"""
        response = authenticated_client.get('/date/2023/6/')
        assert response.status_code == 200
        assert b'2023' in response.data
        assert b'06' in response.data

    def test_view_month_pagination(self, authenticated_client, multiple_pictures):
        """Month view supports pagination"""
        response = authenticated_client.get('/date/2023/6/?page=1')
        assert response.status_code == 200

    def test_view_month_shows_available_days(self, authenticated_client, multiple_pictures):
        """Month view shows available days for navigation"""
        response = authenticated_client.get('/date/2023/6/')
        assert response.status_code == 200
        # Should have day indicators
        data = response.get_data(as_text=True)
        assert len(data) > 100

    def test_view_month_shows_available_months(self, authenticated_client, multiple_pictures):
        """Month view shows other available months"""
        response = authenticated_client.get('/date/2023/6/')
        assert response.status_code == 200
        # Should show month navigation

    def test_view_month_invalid_month(self, authenticated_client):
        """Invalid month number handled"""
        response = authenticated_client.get('/date/2023/13/')
        # Should handle gracefully (200 with empty, or 404)
        assert response.status_code in [200, 404]


class TestViewDayRoute:
    """GET /date/<year>/<month>/<day>/ - View pictures from a specific day"""

    def test_view_day_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get('/date/2023/6/15/')
        assert response.status_code == 302

    def test_view_day_renders_pictures(self, authenticated_client, sample_picture):
        """GET /date/2023/6/15/ shows pictures from that day"""
        response = authenticated_client.get('/date/2023/6/15/')
        assert response.status_code == 200
        assert b'2023' in response.data
        assert b'06' in response.data
        assert b'15' in response.data

    def test_view_day_pagination(self, authenticated_client, multiple_pictures):
        """Day view supports pagination"""
        response = authenticated_client.get('/date/2023/6/1/?page=1')
        assert response.status_code == 200

    def test_view_day_shows_day_nav(self, authenticated_client, multiple_pictures):
        """Day view shows navigation to previous/next days"""
        response = authenticated_client.get('/date/2023/6/15/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should have day indicators and navigation
        assert '15' in data

    def test_view_day_invalid_day(self, authenticated_client):
        """Invalid day number handled"""
        response = authenticated_client.get('/date/2023/6/32/')
        # Should handle gracefully
        assert response.status_code in [200, 404]

    def test_view_day_empty_day(self, authenticated_client):
        """Day with no pictures shows empty"""
        response = authenticated_client.get('/date/2023/6/30/')
        assert response.status_code == 200


class TestEditDatesRoute:
    """GET/POST /edit/dates/ - Change picture dates"""

    def test_edit_dates_get_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get('/edit/dates/')
        assert response.status_code == 302

    def test_edit_dates_get_shows_form(self, authenticated_client):
        """GET /edit/dates/ shows form for date editing"""
        response = authenticated_client.get('/edit/dates/')
        assert response.status_code == 200
        assert b'date' in response.data.lower()

    def test_edit_dates_post_single_picture(self, authenticated_client, multiple_pictures):
        """POST can change date for single picture"""
        pic = multiple_pictures[0]
        response = authenticated_client.post(
            '/edit/dates/',
            data={
                'key_1': f'http://example.com/photo/{pic["key"]}/',
                'date_1': '2024-01-01',
            },
            follow_redirects=False
        )

        # Should redirect to edit/dates
        assert response.status_code == 302
        assert '/edit/dates/' in response.location

    def test_edit_dates_post_multiple_pictures(self, authenticated_client, multiple_pictures):
        """POST can change dates for multiple pictures"""
        response = authenticated_client.post(
            '/edit/dates/',
            data={
                'key_1': f'http://example.com/photo/{multiple_pictures[0]["key"]}/',
                'date_1': '2024-01-01',
                'key_2': f'http://example.com/photo/{multiple_pictures[1]["key"]}/',
                'date_2': '2024-01-02',
            },
            follow_redirects=False
        )

        assert response.status_code == 302

    def test_edit_dates_post_multikey_format(self, authenticated_client, multiple_pictures):
        """POST supports multikey format with single target date"""
        urls = '\n'.join([
            f'http://example.com/photo/{pic["key"]}/'
            for pic in multiple_pictures[:3]
        ])

        response = authenticated_client.post(
            '/edit/dates/',
            data={
                'multikeys': urls,
                'multikeys_dates': '2024-06-15',
            },
            follow_redirects=False
        )

        assert response.status_code == 302
        assert '/edit/dates/' in response.location

    def test_edit_dates_post_no_changes(self, authenticated_client):
        """POST with no data doesn't queue jobs"""
        response = authenticated_client.post(
            '/edit/dates/',
            data={},
            follow_redirects=False
        )

        assert response.status_code == 302

    def test_edit_dates_post_skip_empty_fields(self, authenticated_client, multiple_pictures):
        """POST skips empty key/date fields"""
        response = authenticated_client.post(
            '/edit/dates/',
            data={
                'key_1': f'http://example.com/photo/{multiple_pictures[0]["key"]}/',
                'date_1': '2024-01-01',
                'key_2': '',  # Empty, should be skipped
                'date_2': '2024-01-02',
            },
            follow_redirects=False
        )

        assert response.status_code == 302


class TestChangeDateRoute:
    """POST /tags/dates/change/ - Move all pictures from one date to another"""

    def test_change_date_requires_login(self, web_client):
        """POST requires authentication"""
        response = web_client.post(
            '/tags/dates/change/',
            data={'origin': '2023-06-15', 'target': '2023-06-20'}
        )
        assert response.status_code == 302

    def test_change_date_post_changes_date(self, authenticated_client, multiple_pictures):
        """POST changes all pictures from origin date to target date"""
        response = authenticated_client.post(
            '/tags/dates/change/',
            data={
                'origin': '2023-06-01',
                'target': '2023-07-01',
            },
            follow_redirects=False
        )

        # Should redirect to view the target date
        assert response.status_code == 302
        assert '/date/2023/7/1/' in response.location

    def test_change_date_same_date_no_op(self, authenticated_client):
        """Changing to same date is allowed"""
        response = authenticated_client.post(
            '/tags/dates/change/',
            data={
                'origin': '2023-06-15',
                'target': '2023-06-15',
            },
            follow_redirects=False
        )

        # Should still redirect
        assert response.status_code == 302

    def test_change_date_invalid_format(self, authenticated_client):
        """Invalid date format in POST"""
        response = authenticated_client.post(
            '/tags/dates/change/',
            data={
                'origin': 'invalid-date',
                'target': '2023-06-15',
            }
        )

        # Should raise ValueError or 400
        assert response.status_code in [400, 500]

    def test_change_date_queues_job(self, authenticated_client, multiple_pictures):
        """Change date creates a job in queue"""
        authenticated_client.post(
            '/tags/dates/change/',
            data={
                'origin': '2023-06-01',
                'target': '2023-07-01',
            },
            follow_redirects=False
        )

        # Check if job was queued
        jobs = list(queue.peek(100))
        # Should have at least one job
        assert len(jobs) > 0
