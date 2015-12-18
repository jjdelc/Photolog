import os, sqlite3

try:
    from _thread import get_ident
except ImportError:
    from _dummy_thread import get_ident


# http://stackoverflow.com/a/3300514/43490
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class DB(object):
    _create = (
            'CREATE TABLE IF NOT EXISTS pictures '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  name TEXT,'
            '  key TEXT,'
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
    _add_picture = 'INSERT INTO pictures (%(fields)s) VALUES (%(values)s)'
    _get_pictures = 'SELECT * FROM pictures LIMIT ? OFFSET ?'
    _get_picture = 'SELECT * FROM pictures WHERE key = ?'
    _update_picture = 'UPDATE pictures SET %s = ? WHERE key = ?'
    _get_tags = 'SELECT name FROM tags'
    _get_tag = 'SELECT id, name FROM tags WHERE name=?'
    _add_tag = 'INSERT INTO tags (name) VALUES (?)'
    _tag_picture = 'INSERT INTO tagged_pics (tag_id, picture_id) VALUES (?, ?)'
    _tagged_pics = ('SELECT * from pictures where id in '
                    '(SELECT picture_id FROM tagged_pics WHERE tag_id = ?)')
    _pic_tags = ('SELECT name FROM tags WHERE id in '
                 '(SELECT tag_id from tagged_pics WHERE picture_id = ?)')

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._connection_cache = {}
        with self._get_conn() as conn:
            for table in self._create:
                conn.execute(table)

    def _get_conn(self):
        _id = get_ident()
        if _id not in self._connection_cache:
            conn = sqlite3.Connection(self.path, timeout=60)
            conn.row_factory = dict_factory
            self._connection_cache[_id] = conn
        return self._connection_cache[_id]

    def add_picture(self, picture_data, tags):
        with self._get_conn() as conn:
            query = self._add_picture % {
                'fields': ', '.join(picture_data.keys()),
                'values': ', '.join([':%s' % k for k in picture_data.keys()]),
            }
            cur = conn.execute(query, picture_data)
            picture_id = cur.lastrowid
            for tag in tags:
                t = self.get_tag(tag)
                t_id = t['id']
                conn.execute(self._tag_picture, [t_id, picture_id])

    def get_pictures(self, offset, limit):
        with self._get_conn() as conn:
            return conn.execute(self._get_pictures, (limit, offset))

    def get_picture(self, key):
        with self._get_conn() as conn:
            return conn.execute(self._get_picture, [key]).fetchone()

    def update_picture(self, key, attr, value):
        with self._get_conn() as conn:
            return conn.execute(self._update_picture % attr, [value, key])

    def get_tags(self):
        with self._get_conn() as conn:
            return {r['name'] for r in conn.execute(self._get_tags)}

    def add_tag(self, name):
        with self._get_conn() as conn:
            conn.execute(self._add_tag, [name.lower()])

    def get_tag(self, name):
        with self._get_conn() as conn:
            matches = list(conn.execute(self._get_tag, [name.lower()]))
            if not matches:
                self.add_tag(name)
                matches = list(conn.execute(self._get_tag, [name.lower()]))
            return matches[0]

    def tagged(self, name):
        tag = self.get_tag(name)
        t_id = tag['id']
        with self._get_conn() as conn:
            return [r for r in conn.execute(self._tagged_pics, [t_id])]

    def tags_for_picture(self, picture_id):
        with self._get_conn() as conn:
            return [t['name'] for t in conn.execute(self._pic_tags, [picture_id])]