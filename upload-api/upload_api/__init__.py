import os
import sys
import logging

queue_logger = logging.getLogger('QUEUE')
api_logger = logging.getLogger('API')
web_logger = logging.getLogger('WEB')

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO
)
ALLOWED_FILES = {'jpg', 'jpeg', 'png', 'gif', 'raw'}

settings_file = os.environ.get('SETTINGS')
# settings = yaml.load(open(settings_file).read())
#
# PROJECT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '../..'))
#
# DEBUG = settings.get('DEBUG', True)
# UPLOAD_FOLDER = settings.get('UPLOAD_FOLDER', os.path.join(PROJECT_DIR, 'media'))
# DB_FILE = settings.get('DB_FILE', os.path.join(PROJECT_DIR, 'photos.db'))
#
# S3_ACCESS_KEY = settings['S3_ACCESS_KEY']
# S3_SECRET_KEY = settings['S3_SECRET_KEY']
# S3_BUCKET = settings['S3_BUCKET']
