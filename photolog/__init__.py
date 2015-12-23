import os
import sys
import logging

queue_logger = logging.getLogger('QUEUE')
api_logger = logging.getLogger('API')
web_logger = logging.getLogger('WEB')
cli_logger = logging.getLogger('CLI')

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO
)

settings_file = os.environ.get('SETTINGS')


ALLOWED_FILES = {'jpg', 'jpeg', 'png', 'gif', 'raw'}
