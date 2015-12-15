import os, sqlite3

try:
    from _thread import get_ident
except ImportError:
    from _dummy_thread import get_ident


class DB(object):
    _create = (
            'CREATE TABLE IF NOT EXISTS pictures '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  original TEXT,'
            '  thumb TEXT,'
            '  medium TEXT,'
            '  web TEXT,'
            '  large TEXT,'
            '  flickr TEXT,'
            '  gphotos TEXT,'
            '  year TEXT,'
            '  month TEXT,'
            '  day TEXT,'
            '  width INTEGER,'
            '  height INTEGER,'
            '  size INTEGER,'
            '  camera TEXT,'
            '  upload_date TEXT,'
            '  date_taken TEXT'
            ');',
            'CREATE TABLE IF NOT EXISTS tags '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  name TEXT'
            ');',
            'CREATE TABLE IF NOT EXISTS tagged_pics '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  tag_id INTEGER,'
            '  picture_id INTEGER,'
            '  FOREIGN KEY(tag_id) REFERENCES tags(id),'
            '  FOREIGN KEY(picture_id) REFERENCES pictures(id)'
            ');'
            )
    _append = 'INSERT INTO pictures (item) VALUES (?)'
    _get_tags = 'SELECT name from tags'
    _add_tag = 'INSERT INTO tags (name) VALUES (?)'

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._connection_cache = {}
        with self._get_conn() as conn:
            for table in self._create:
                conn.execute(table)

    def _get_conn(self):
        _id = get_ident()
        if _id not in self._connection_cache:
            self._connection_cache[_id] = sqlite3.Connection(self.path,
                                                             timeout=60)
        return self._connection_cache[_id]

    def add(self, obj):
        with self._get_conn() as conn:
            conn.execute(self._append, [])

    def by_year_month(self, year, month):
        pass

    def get_tags(self):
        with self._get_conn() as conn:
            return {r[0] for r in conn.execute(self._get_tags)}

    def add_tag(self, name):
        with self._get_conn() as conn:
            conn.execute(self._add_tag, [name])
