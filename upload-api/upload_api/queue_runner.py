import os

from . import UPLOAD_FOLDER, DB_FILE
from .squeue import SqliteQueue

queue = SqliteQueue(DB_FILE)


def process(filename):
    print('Processing %s' % filename)


def daemon():
    while 1:
        _file = queue.popleft(100)
        filename = os.path.join(UPLOAD_FOLDER, _file)
        process(filename)

