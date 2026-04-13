import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

WEBEND_TESTS_DIR = os.path.dirname(__file__)

# Must be set before importing photolog.web.main
os.environ["SETTINGS"] = os.environ.get("SETTINGS", "/tmp/test_settings.yaml")

from photolog.web.main import app, db, queue, user, login_manager  # noqa: E402

# Configure login manager for testing
login_manager.login_view = "login"
login_manager.login_message_category = "info"


@pytest.fixture(autouse=True)
def mock_requests(monkeypatch):
    """Mock requests.post to return 401 for invalid codes"""

    def mock_post(*args, **kwargs):
        # Simulate auth failure for invalid code
        response = Mock()
        response.status_code = 401
        return response

    monkeypatch.setattr("photolog.web.main.requests.post", mock_post)


@pytest.fixture
def web_client():
    """Flask test client with app context"""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def authenticated_client(web_client):
    """Test client with authenticated user"""
    # Set the session to indicate an authenticated user
    with web_client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()

    yield web_client


@pytest.fixture(autouse=True)
def reset_web_db(setup_test_files):
    """Reset web app's database and queue before each test"""
    # Clear connections
    db._connection_cache.clear()
    queue._connection_cache.clear()

    # Drop and recreate tables
    with db._get_conn() as conn:
        conn.execute("DROP TABLE IF EXISTS tagged_pics")
        conn.execute("DROP TABLE IF EXISTS tags")
        conn.execute("DROP TABLE IF EXISTS pictures")
        for table in db._create:
            conn.execute(table)

    with queue._get_conn() as conn:
        conn.execute("DROP TABLE IF EXISTS queue")
        conn.execute("DROP TABLE IF EXISTS bad_jobs")
        for table in queue._create:
            conn.execute(table)

    yield

    # Cleanup after test
    db._connection_cache.clear()
    queue._connection_cache.clear()


@pytest.fixture
def sample_picture(reset_web_db):
    """Add a sample picture to database for testing"""
    picture_data = {
        "key": "test-key-001",
        "name": "test-photo.jpg",
        "size": 1024000,
        "taken_time": datetime(2023, 6, 15, 14, 30, 0),
        "year": 2023,
        "month": 6,
        "day": 15,
        "checksum": "abc123def456",
    }
    db.add_picture(picture_data, [])
    return picture_data


@pytest.fixture
def multiple_pictures(reset_web_db):
    """Add multiple pictures spanning different dates and tags"""
    pictures = []
    for i in range(30):
        taken_time = datetime(2023, 6, 1) + timedelta(days=i)
        picture_data = {
            "key": f"test-key-{i:03d}",
            "name": f"photo-{i:03d}.jpg",
            "size": 1024000 + i * 1000,
            "taken_time": taken_time,
            "year": taken_time.year,
            "month": taken_time.month,
            "day": taken_time.day,
            "checksum": f"checksum-{i}",
        }
        db.add_picture(picture_data, [])
        pictures.append(picture_data)
    return pictures


@pytest.fixture
def tagged_pictures(reset_web_db):
    """Add pictures with various tags for testing"""
    pictures = []
    tags_list = ["travel", "family", "nature"]

    for i in range(9):
        taken_time = datetime(2023, 1, 1) + timedelta(days=i * 10)
        picture_data = {
            "key": f"tagged-key-{i:03d}",
            "name": f"tagged-photo-{i:03d}.jpg",
            "size": 2048000 + i * 1000,
            "taken_time": taken_time,
            "year": taken_time.year,
            "month": taken_time.month,
            "day": taken_time.day,
            "checksum": f"tagged-checksum-{i}",
        }
        db.add_picture(picture_data, [])

        # Get picture ID and assign tags
        assigned_tags = {tags_list[i % len(tags_list)]}
        pic = db.pictures.by_key(picture_data["key"])
        db.tags.change_for_picture(pic["id"], assigned_tags)

        pictures.append(picture_data)

    return pictures
