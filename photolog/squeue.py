# Snippet from: http://flask.pocoo.org/snippets/88/

import os, sqlite3
from pickle import loads, dumps
from time import sleep
try:
    from _thread import get_ident
except ImportError:
    from _dummy_thread import get_ident


class SqliteQueue(object):

    _create = [(
            'CREATE TABLE IF NOT EXISTS queue ' 
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  item BLOB'
            ')'
            ), (
            'CREATE TABLE IF NOT EXISTS bad_jobs '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  item BLOB'
            ')'
            )]
    _count = 'SELECT COUNT(*) count FROM queue'
    _iterate = 'SELECT id, item FROM queue'
    _append = 'INSERT INTO queue (item) VALUES (?)'
    _append_bad = 'INSERT INTO bad_jobs (item) VALUES (?)'
    _bad_jobs = 'SELECT item FROM bad_jobs ORDER BY id DESC LIMIT ?'
    _write_lock = 'BEGIN IMMEDIATE'
    _popleft_get = (
            'SELECT id, item FROM queue '
            'ORDER BY id LIMIT 1'
            )
    _popleft_del = 'DELETE FROM queue WHERE id = ?'
    _peek = 'SELECT item FROM queue ORDER BY id LIMIT ?'
    _retry = 'INSERT INTO queue(item) SELECT item FROM bad_jobs'
    _clear_bad_jobs = 'DELETE FROM bad_jobs'

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._connection_cache = {}
        with self._get_conn() as conn:
            for table in self._create:
                conn.execute(table)

    def __len__(self):
        with self._get_conn() as conn:
            l = conn.execute(self._count).fetchone()[0]
        return l

    def __iter__(self):
        with self._get_conn() as conn:
            for id, obj_buffer in conn.execute(self._iterate):
                yield loads(str(obj_buffer))

    def _get_conn(self):
        _id = get_ident()
        if _id not in self._connection_cache:
            self._connection_cache[_id] = sqlite3.Connection(self.path,
                                                             timeout=60)
        return self._connection_cache[_id]

    def append(self, obj):
        obj_buffer = memoryview(dumps(obj, 2))
        with self._get_conn() as conn:
            conn.execute(self._append, (obj_buffer,))

    def append_bad(self, obj):
        obj_buffer = memoryview(dumps(obj, 2))
        with self._get_conn() as conn:
            conn.execute(self._append_bad, (obj_buffer,))

    def get_bad_jobs(self, limit=20):
        with self._get_conn() as conn:
            return [loads(obj_buffer[0])
                    for obj_buffer in conn.execute(self._bad_jobs, [limit])]

    def popleft(self, sleep_wait=True):
        keep_pooling = True
        wait = 0.1
        max_wait = 2
        tries = 0
        with self._get_conn() as conn:
            _id = None
            while keep_pooling:
                conn.execute(self._write_lock)
                cursor = conn.execute(self._popleft_get)
                try:
                    _id, obj_buffer = next(cursor)
                    keep_pooling = False
                except StopIteration:
                    conn.commit()  # unlock the database
                    if not sleep_wait:
                        keep_pooling = False
                        continue
                    tries += 1
                    sleep(wait)
                    wait = min(max_wait, tries/10 + wait)
            if _id:
                conn.execute(self._popleft_del, (_id,))
                return loads(obj_buffer)
        return None

    def peek(self, size=1):
        with self._get_conn() as conn:
            cursor = conn.execute(self._peek, [size])
            try:
                for row in cursor:
                    yield loads(row[0])
            except StopIteration:
                return None

    def retry_jobs(self):
        bad_jobs = self.get_bad_jobs()
        with self._get_conn() as conn:
            for bad in bad_jobs:
                bad['attempt'] = 0
                obj_buffer = memoryview(dumps(bad, 2))
                conn.execute(self._append, (obj_buffer,))
