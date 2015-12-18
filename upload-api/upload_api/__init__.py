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

settings_file = os.environ.get('SETTINGS')
