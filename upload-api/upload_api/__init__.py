import os
import sys
import logging

COMMON_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '../..'))

UPLOAD_FOLDER = os.path.join(COMMON_DIR, 'media')
DB_FILE = os.path.join(COMMON_DIR, 'photos.db')
ALLOWED_FILES = {'jpg', 'jpeg', 'png', 'gif', 'raw'}

queue_logger = logging.getLogger('QUEUE')
api_logger = logging.getLogger('API')

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG
)

