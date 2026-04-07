from hashlib import md5
from io import BytesIO

import pytest
from unittest.mock import patch

from photolog.api.main import app, queue
from tests.conftest import TEST_API_SECRET

VALID_HASH = md5(TEST_API_SECRET.encode('utf-8')).hexdigest()


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_queue(setup_test_files):
    # Clear stale cached connections (the DB file is recreated each session)
    queue._connection_cache.clear()
    with queue._get_conn() as conn:
        for table in queue._create:
            conn.execute(table)
        conn.execute('DELETE FROM queue')
        conn.execute('DELETE FROM bad_jobs')


# GET /photos/ — list queue

def test_get_photos_success(client):
    response = client.get('/photos/')
    assert response.status_code == 200
    assert 'last' in response.get_json()


# POST /photos/batch/ — start batch upload

def test_post_batch_success(client):
    with patch('photolog.api.main.start_batch', return_value='user123:album456'):
        response = client.post('/photos/batch/', headers={'X-PHOTOLOG-SECRET': VALID_HASH})
    assert response.status_code == 200
    assert 'batch_id' in response.get_json()


def test_post_batch_invalid_auth(client):
    response = client.post('/photos/batch/', headers={'X-PHOTOLOG-SECRET': 'wrong-secret'})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_post_batch_missing_auth(client):
    response = client.post('/photos/batch/')
    assert response.status_code == 400


# DELETE /photos/batch/<id>/ — finish batch

def test_delete_batch_success(client):
    with patch('photolog.api.main.end_batch'):
        response = client.delete(
            '/photos/batch/user123:album456/',
            headers={'X-PHOTOLOG-SECRET': VALID_HASH}
        )
    assert response.status_code == 204


def test_delete_batch_invalid_auth(client):
    response = client.delete(
        '/photos/batch/test-batch-123/',
        headers={'X-PHOTOLOG-SECRET': 'wrong-secret'}
    )
    assert response.status_code == 400


# GET /photos/verify/ — check if file exists

def test_verify_photo_invalid_auth(client):
    response = client.get(
        '/photos/verify/',
        query_string={'filename': 'test', 'checksum': 'abc'},
        headers={'X-PHOTOLOG-SECRET': 'wrong-secret'}
    )
    assert response.status_code == 400


def test_verify_photo_valid_auth_not_found(client):
    response = client.get(
        '/photos/verify/',
        query_string={'filename': 'nonexistent', 'checksum': 'xyz'},
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 404


# POST /photos/ — upload photo

def test_add_photo_success(client):
    data = {
        'photo_file': (BytesIO(b'fake image data'), 'test.jpg'),
        'tags': 'tag1,tag2',
        'batch_id': 'batch-1',
        'is_last': '1'
    }
    response = client.post(
        '/photos/',
        data=data,
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 202


def test_add_photo_no_file(client):
    response = client.post(
        '/photos/',
        data={'tags': 'tag1,tag2'},
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 400
    assert 'Must send' in response.get_json()['error']


def test_add_photo_invalid_extension(client):
    data = {
        'photo_file': (BytesIO(b'fake data'), 'test.exe'),
        'tags': 'tag1'
    }
    response = client.post(
        '/photos/',
        data=data,
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 400
    assert 'Invalid file extension' in response.get_json()['error']


def test_add_photo_invalid_auth(client):
    data = {
        'photo_file': (BytesIO(b'fake image data'), 'test.jpg'),
        'tags': 'tag1'
    }
    response = client.post(
        '/photos/',
        data=data,
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': 'wrong-secret'}
    )
    assert response.status_code == 400


def test_add_photo_missing_auth(client):
    data = {
        'photo_file': (BytesIO(b'fake image data'), 'test.jpg'),
        'tags': 'tag1'
    }
    response = client.post('/photos/', data=data, content_type='multipart/form-data')
    assert response.status_code == 400


def test_add_photo_with_metadata(client):
    data = {
        'photo_file': (BytesIO(b'fake image data'), 'test.jpg'),
        'metadata_file': (BytesIO(b'{"metadata": "value"}'), 'metadata.json'),
        'tags': 'tag1',
        'batch_id': 'batch-2'
    }
    response = client.post(
        '/photos/',
        data=data,
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 202


def test_add_photo_with_target_date(client):
    data = {
        'photo_file': (BytesIO(b'fake image data'), 'test.jpg'),
        'tags': 'tag1',
        'target_date': '2020-06-15'
    }
    response = client.post(
        '/photos/',
        data=data,
        content_type='multipart/form-data',
        headers={'X-PHOTOLOG-SECRET': VALID_HASH}
    )
    assert response.status_code == 202
