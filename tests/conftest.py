import os
import shutil

import pytest

TESTS_DIR = os.path.dirname(__file__)
TEST_FILES = os.path.join(TESTS_DIR, "files")
TEST_SETTINGS_FILE = "/tmp/test_settings.yaml"
TEST_DB_FILE = os.path.join(TEST_FILES, "test.db")
TEST_API_SECRET = "test-secret"

# Create the files dir and write test settings before any photolog imports
os.makedirs(TEST_FILES, exist_ok=True)
_settings_content = f"""DB_FILE: {TEST_DB_FILE}
UPLOAD_FOLDER: {TEST_FILES}
API_SECRET: {TEST_API_SECRET}
SECRET_KEY: test-secret-key-for-flask
AUTH_ME: test@example.com
DEBUG: true
DOMAIN: http://localhost:5001
"""
with open(TEST_SETTINGS_FILE, "w") as _f:
    _f.write(_settings_content)
os.environ["SETTINGS"] = TEST_SETTINGS_FILE

from photolog.db import DB  # noqa: E402
from photolog.squeue import SqliteQueue  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_test_files():
    if os.path.exists(TEST_FILES):
        shutil.rmtree(TEST_FILES)
    os.makedirs(TEST_FILES)


def make_db(db_filename):
    db_file = os.path.join(TEST_FILES, db_filename)
    return DB(db_file)


def make_queue(name):
    return SqliteQueue(os.path.join(TEST_FILES, name))
