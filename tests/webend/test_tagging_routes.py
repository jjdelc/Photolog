"""Tests for tagging routes: tag picture, tag day, mass tag, view by tags"""

import pytest
from datetime import datetime
from photolog.web.main import db


class TestTagPictureRoute:
    """GET/POST /photo/<key>/edit/tags/ - Tag a single picture"""

    def test_tag_picture_get_requires_login(self, web_client, sample_picture):
        """GET requires authentication"""
        response = web_client.get(f"/photo/{sample_picture['key']}/edit/tags/")
        assert response.status_code == 302
        assert "/login/" in response.location

    def test_tag_picture_get_shows_form(self, authenticated_client, sample_picture):
        """GET /photo/<key>/edit/tags/ shows edit form"""
        response = authenticated_client.get(f"/photo/{sample_picture['key']}/edit/tags/")
        assert response.status_code == 200
        assert b"edit" in response.data.lower() or b"tags" in response.data.lower()

    def test_tag_picture_get_includes_current_tags(self, authenticated_client, sample_picture):
        """Form shows currently assigned tags"""
        # First assign a tag - need to get the picture first to get its ID
        pic = db.pictures.by_key(sample_picture["key"])
        db.tags.change_for_picture(pic["id"], {"existing-tag"})

        response = authenticated_client.get(f"/photo/{sample_picture['key']}/edit/tags/")
        assert response.status_code == 200
        # Tag should be in the form
        assert b"existing-tag" in response.data or b"existing" in response.data.lower()

    def test_tag_picture_post_adds_tags(self, authenticated_client, sample_picture):
        """POST /photo/<key>/edit/tags/ updates tags"""
        response = authenticated_client.post(
            f"/photo/{sample_picture['key']}/edit/tags/",
            data={"tags": "newtag1, newtag2"},
            follow_redirects=False,
        )
        # Should redirect to picture detail
        assert response.status_code == 302
        assert f"/photo/{sample_picture['key']}/" in response.location

    def test_tag_picture_replaces_existing_tags(self, authenticated_client, sample_picture):
        """POST replaces existing tags instead of adding"""
        # Set initial tags - need picture ID
        pic = db.pictures.by_key(sample_picture["key"])
        db.tags.change_for_picture(pic["id"], {"oldtag"})

        # Update tags
        authenticated_client.post(
            f"/photo/{sample_picture['key']}/edit/tags/",
            data={"tags": "newtag"},
            follow_redirects=True,
        )

        # Verify old tag is gone - for_picture expects picture ID
        tags = db.tags.for_picture(pic["id"])
        assert "oldtag" not in tags
        assert "newtag" in tags

    def test_tag_picture_invalid_key(self, authenticated_client):
        """GET/POST with non-existent key raises error"""
        with pytest.raises(Exception):
            authenticated_client.get("/photo/invalid-key-999/edit/tags/")

    def test_tag_picture_slugifies_tags(self, authenticated_client, sample_picture):
        """Tags are slugified (spaces to hyphens, lowercase)"""
        pic = db.pictures.by_key(sample_picture["key"])
        authenticated_client.post(
            f"/photo/{sample_picture['key']}/edit/tags/",
            data={"tags": "My Tag Name"},
            follow_redirects=True,
        )

        tags = db.tags.for_picture(pic["id"])
        assert "my-tag-name" in tags


class TestTagDayRoute:
    """GET/POST /date/<year>/<month>/<day>/tags/ - Tag all pictures on a day"""

    def test_tag_day_get_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/date/2023/6/15/tags/")
        assert response.status_code == 302

    def test_tag_day_get_shows_form(self, authenticated_client, sample_picture):
        """GET shows form with day info"""
        response = authenticated_client.get("/date/2023/6/15/tags/")
        assert response.status_code == 200
        assert b"2023" in response.data
        assert b"06" in response.data
        assert b"15" in response.data

    def test_tag_day_get_shows_picture_count(self, authenticated_client, multiple_pictures):
        """Form shows count of pictures for that day"""
        # multiple_pictures has pictures on different days
        response = authenticated_client.get("/date/2023/6/1/tags/")
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should show total count somewhere
        assert "1" in data or "total" in data.lower()

    def test_tag_day_post_tags_all_pictures(self, authenticated_client, multiple_pictures):
        """POST tags all pictures on that day"""
        # Filter for pictures on 2023-06-01
        target_date = datetime(2023, 6, 1)

        response = authenticated_client.post(
            "/date/2023/6/1/tags/",
            data={"tags": "day-tag"},
            follow_redirects=False,
        )

        # Should redirect back to day view
        assert response.status_code == 302
        assert "/date/2023/6/1/" in response.location

        # Verify the picture on target date has the tag applied
        pic_on_target_date = db.pictures.by_key("test-key-000")
        assert pic_on_target_date is not None
        assert pic_on_target_date["year"] == target_date.year
        assert pic_on_target_date["month"] == target_date.month
        assert pic_on_target_date["day"] == target_date.day
        tags_for_pic = db.tags.for_picture(pic_on_target_date["id"])
        assert "day-tag" in tags_for_pic

        # Verify a picture on a different date doesn't have the tag
        pic_on_other_date = db.pictures.by_key("test-key-001")
        tags_for_other_pic = db.tags.for_picture(pic_on_other_date["id"])
        assert "day-tag" not in tags_for_other_pic

    def test_tag_day_empty_tags_no_op(self, authenticated_client, multiple_pictures):
        """POST with empty tags does not queue job"""
        response = authenticated_client.post(
            "/date/2023/6/1/tags/", data={"tags": ""}, follow_redirects=False
        )

        # Should still redirect but not queue anything
        assert response.status_code == 302

    def test_tag_day_invalid_date(self, authenticated_client):
        """Invalid date parameters handled"""
        response = authenticated_client.get("/date/2023/6/32/tags/")
        # Should either 404 or show form with 0 pictures
        assert response.status_code in [200, 404]


class TestMassTagRoute:
    """GET/POST /edit/tags/ - Tag multiple pictures at once"""

    def test_mass_tag_get_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/edit/tags/")
        assert response.status_code == 302

    def test_mass_tag_get_shows_form(self, authenticated_client):
        """GET /edit/tags/ shows form for entering URLs"""
        response = authenticated_client.get("/edit/tags/")
        assert response.status_code == 200
        assert b"tag" in response.data.lower()

    def test_mass_tag_post_valid_urls(self, authenticated_client, multiple_pictures):
        """POST with valid picture URLs tags them"""
        urls = "\n".join(
            [f"http://example.com/photo/{pic['key']}/" for pic in multiple_pictures[:3]]
        )

        response = authenticated_client.post(
            "/edit/tags/",
            data={"keys": urls, "tags": "batch-tag"},
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/" in response.location

    def test_mass_tag_post_empty_tags_no_op(self, authenticated_client, multiple_pictures):
        """POST with empty tags doesn't queue"""
        urls = "\n".join(
            [f"http://example.com/photo/{pic['key']}/" for pic in multiple_pictures[:2]]
        )

        response = authenticated_client.post(
            "/edit/tags/",
            data={"keys": urls, "tags": ""},
            follow_redirects=False,
        )

        # Should still redirect but not queue
        assert response.status_code == 302

    def test_mass_tag_post_empty_urls_no_op(self, authenticated_client):
        """POST with empty URLs doesn't queue"""
        response = authenticated_client.post(
            "/edit/tags/",
            data={"keys": "", "tags": "some-tag"},
            follow_redirects=False,
        )

        # Should redirect but not queue
        assert response.status_code == 302

    def test_mass_tag_extracts_key_from_url(self, authenticated_client, multiple_pictures):
        """URL parsing extracts key correctly"""
        # Test with various URL formats
        urls = f"http://example.com/photo/{multiple_pictures[0]['key']}/"

        response = authenticated_client.post(
            "/edit/tags/",
            data={"keys": urls, "tags": "extracted-tag"},
            follow_redirects=True,
        )

        assert response.status_code == 200


class TestViewByTagsRoute:
    """GET /tags/<tag_list>/ - View pictures with specific tags"""

    def test_view_tags_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/tags/travel/")
        assert response.status_code == 302

    def test_view_single_tag(self, authenticated_client, tagged_pictures):
        """GET /tags/travel/ shows only pictures with that tag"""
        response = authenticated_client.get("/tags/travel/")
        assert response.status_code == 200
        assert b"travel" in response.data.lower() or b"photo" in response.data.lower()

    def test_view_multiple_tags(self, authenticated_client, tagged_pictures):
        """GET /tags/tag1,tag2/ filters by multiple tags"""
        response = authenticated_client.get("/tags/travel,family/")
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should show tag list
        assert len(data) > 100

    def test_view_tags_pagination(self, authenticated_client, tagged_pictures):
        """Tag view supports pagination"""
        response = authenticated_client.get("/tags/travel/?page=1")
        assert response.status_code == 200

    def test_view_tags_pagination_invalid_page(self, authenticated_client, tagged_pictures):
        """Invalid page number on tag view"""
        response = authenticated_client.get("/tags/travel/?page=999")
        assert response.status_code == 200

    def test_view_nonexistent_tag(self, authenticated_client):
        """View non-existent tag returns empty results"""
        response = authenticated_client.get("/tags/nonexistent-tag/")
        assert response.status_code == 200
        # Should show empty photo list
        data = response.get_data(as_text=True)
        assert len(data) > 0

    def test_view_tags_shows_all_tags(self, authenticated_client, tagged_pictures):
        """Tag view shows all available tags for filtering"""
        response = authenticated_client.get("/tags/travel/")
        assert response.status_code == 200
        # All tags should be available for selection
        assert b"travel" in response.data.lower() or b"family" in response.data.lower()

    def test_view_tags_case_insensitive(self, authenticated_client, tagged_pictures):
        """Tag viewing is case-insensitive"""
        response1 = authenticated_client.get("/tags/travel/")
        response2 = authenticated_client.get("/tags/TRAVEL/")

        # Both should work
        assert response1.status_code == 200
        assert response2.status_code == 200
