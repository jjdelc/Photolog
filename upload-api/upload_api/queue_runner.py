import os

from . import UPLOAD_FOLDER, DB_FILE, queue_logger as log
from .squeue import SqliteQueue

queue = SqliteQueue(DB_FILE)


def process(filename):
    log.info('Processing %s' % filename)


def daemon():
    log.info('Starting daemon')
    while 1:
        _file = queue.popleft(100)
        filename = os.path.join(UPLOAD_FOLDER, _file)
        process(filename)

