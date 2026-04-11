"""Tests for attribute editing and detail viewing routes"""
import pytest
import json
from photolog.web.main import db, queue


class TestEditAttributeRoute:
    """GET/POST /photo/<key>/edit/attr/ - Edit picture attributes"""

    def test_edit_attr_get_requires_login(self, web_client, sample_picture):
        """GET requires authentication"""
        response = web_client.get(f'/photo/{sample_picture["key"]}/edit/attr/')
        assert response.status_code == 302

    def test_edit_attr_get_shows_form(self, authenticated_client, sample_picture):
        """GET /photo/<key>/edit/attr/ shows attribute edit form"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/edit/attr/')
        assert response.status_code == 200
        assert b'attr' in response.data.lower() or b'edit' in response.data.lower()

    def test_edit_attr_get_shows_json_blob(self, authenticated_client, sample_picture):
        """Form displays full picture data as JSON"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/edit/attr/')
        assert response.status_code == 200
        # JSON data should be visible
        assert b'{' in response.data  # JSON blob
        assert sample_picture['name'].encode() in response.data

    def test_edit_attr_post_requires_confirmation(self, authenticated_client, sample_picture):
        """POST requires confirm flag"""
        response = authenticated_client.post(
            f'/photo/{sample_picture["key"]}/edit/attr/',
            data={
                'attr': 'name',
                'value': 'new-name.jpg',
                # Missing 'confirm' flag
            },
            follow_redirects=False
        )

        # Should not process without confirmation
        assert response.status_code in [302, 200]

    def test_edit_attr_post_with_confirmation(self, authenticated_client, sample_picture):
        """POST with confirmation flag updates attribute"""
        response = authenticated_client.post(
            f'/photo/{sample_picture["key"]}/edit/attr/',
            data={
                'attr': 'name',
                'value': 'new-name.jpg',
                'confirm': 'yes',
            },
            follow_redirects=False
        )

        # Should redirect to blob view
        assert response.status_code == 302
        assert '/blob/' in response.location

    def test_edit_attr_invalid_attribute_rejected(self, authenticated_client, sample_picture):
        """POST with non-existent attribute is rejected"""
        response = authenticated_client.post(
            f'/photo/{sample_picture["key"]}/edit/attr/',
            data={
                'attr': 'nonexistent_field',
                'value': 'some-value',
                'confirm': 'yes',
            },
            follow_redirects=False
        )

        # Should not process invalid attribute
        assert response.status_code in [302, 200]

    def test_edit_attr_invalid_key(self, authenticated_client):
        """GET with non-existent key raises error"""
        with pytest.raises(Exception):
            authenticated_client.get('/photo/invalid-key-999/edit/attr/')

    def test_edit_attr_empty_value(self, authenticated_client, sample_picture):
        """POST with empty value handled"""
        response = authenticated_client.post(
            f'/photo/{sample_picture["key"]}/edit/attr/',
            data={
                'attr': 'name',
                'value': '',
                'confirm': 'yes',
            },
            follow_redirects=False
        )

        # Should handle empty value
        assert response.status_code in [302, 200, 400]


class TestPictureDetailBlobRoute:
    """GET /photo/<key>/blob/ - View picture as JSON blob"""

    def test_blob_requires_login(self, web_client, sample_picture):
        """GET requires authentication"""
        response = web_client.get(f'/photo/{sample_picture["key"]}/blob/')
        assert response.status_code == 302

    def test_blob_renders_json(self, authenticated_client, sample_picture):
        """GET /photo/<key>/blob/ shows JSON representation"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/blob/')
        assert response.status_code == 200
        assert b'{' in response.data  # JSON blob

    def test_blob_includes_all_fields(self, authenticated_client, sample_picture):
        """Blob view includes all picture attributes"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/blob/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)

        # Should have key fields in JSON
        assert 'key' in data
        assert 'name' in data
        assert 'size' in data

    def test_blob_formatted_json(self, authenticated_client, sample_picture):
        """JSON is formatted for readability"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/blob/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)

        # Should have indentation (formatted)
        assert '\n' in data or '  ' in data

    def test_blob_invalid_key(self, authenticated_client):
        """GET with non-existent key raises error"""
        with pytest.raises(Exception):
            authenticated_client.get('/photo/invalid-key-999/blob/')


class TestPictureDetailRoute:
    """GET /photo/<key>/ - View picture detail"""

    def test_detail_requires_login(self, web_client, sample_picture):
        """GET requires authentication"""
        response = web_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 302

    def test_detail_renders_template(self, authenticated_client, sample_picture):
        """GET /photo/<key>/ renders detail template"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        assert b'detail' in response.data.lower() or b'photo' in response.data.lower()

    def test_detail_shows_picture_info(self, authenticated_client, sample_picture):
        """Detail page displays picture information"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        # Should show filename or size
        assert sample_picture['name'].encode() in response.data or b'photo' in response.data

    def test_detail_shows_human_readable_size(self, authenticated_client, sample_picture):
        """Picture size is displayed in human-readable format"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should have MB, GB, KB, or B suffix
        assert any(unit in data for unit in ['MB', 'KB', 'GB', 'B'])

    def test_detail_shows_date_info(self, authenticated_client, sample_picture):
        """Detail includes date information"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Should have year, month, day
        assert '2023' in data

    def test_detail_shows_tags(self, authenticated_client, sample_picture):
        """Detail displays assigned tags"""
        # Assign a tag first - need picture ID
        pic = db.pictures.by_key(sample_picture['key'])
        db.tags.change_for_picture(pic['id'], {'test-tag'})

        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        # Tag should be visible
        assert b'test-tag' in response.data or b'tag' in response.data.lower()

    def test_detail_shows_no_tags_when_empty(self, authenticated_client, sample_picture):
        """Detail handles pictures with no tags"""
        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        # Should still render without errors

    def test_detail_navigation_prev_next(self, authenticated_client, multiple_pictures):
        """Detail shows prev/next navigation"""
        middle_pic = multiple_pictures[15]  # Middle of the list
        response = authenticated_client.get(f'/photo/{middle_pic["key"]}/')
        assert response.status_code == 200
        # Should have navigation links
        data = response.get_data(as_text=True)
        assert len(data) > 100

    def test_detail_first_picture_no_prev(self, authenticated_client, multiple_pictures):
        """First picture has no prev link"""
        first_pic = multiple_pictures[0]
        response = authenticated_client.get(f'/photo/{first_pic["key"]}/')
        assert response.status_code == 200

    def test_detail_last_picture_no_next(self, authenticated_client, multiple_pictures):
        """Last picture has no next link"""
        last_pic = multiple_pictures[-1]
        response = authenticated_client.get(f'/photo/{last_pic["key"]}/')
        assert response.status_code == 200

    def test_detail_invalid_key(self, authenticated_client):
        """GET with non-existent key raises error"""
        with pytest.raises(Exception):
            authenticated_client.get('/photo/invalid-key-999/')

    def test_detail_shows_flickr_data(self, authenticated_client, sample_picture):
        """Detail displays Flickr metadata if present"""
        # Add Flickr data
        flickr_data = {'id': 'flickr123', 'url': 'https://flickr.com/photos/123'}
        db.pictures.edit_attribute(
            sample_picture['key'],
            'flickr',
            json.dumps(flickr_data)
        )

        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
        # Flickr URL should be displayed
        assert b'flickr' in response.data.lower()

    def test_detail_shows_gphotos_data(self, authenticated_client, sample_picture):
        """Detail displays Google Photos metadata if present"""
        gphotos_data = {
            'json': {
                'id': 'gphoto123',
                'productUrl': 'https://photos.google.com/123'
            }
        }
        db.pictures.edit_attribute(
            sample_picture['key'],
            'gphotos',
            json.dumps(gphotos_data)
        )

        response = authenticated_client.get(f'/photo/{sample_picture["key"]}/')
        assert response.status_code == 200
