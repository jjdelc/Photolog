import os
import sqlite3
from time import time

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


class BaseDB(object):
    _create = []

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


class TagManager:
    _tag_picture = 'INSERT INTO tagged_pics (tag_id, picture_id) VALUES (?, ?)'
    _get_tag = 'SELECT id, name FROM tags WHERE name=?'
    _add_tag = 'INSERT INTO tags (name) VALUES (?)'
    _clear_picture_tags = 'DELETE FROM tagged_pics WHERE picture_id=?'
    _pic_tags = ('SELECT name FROM tags WHERE id in '
                 '(SELECT tag_id from tagged_pics WHERE picture_id = ?)')
    _get_tags = 'SELECT name FROM tags'
    _tagged_pics = ('SELECT * from pictures where id in '
                    '(SELECT picture_id FROM tagged_pics WHERE tag_id = ?)')
    _get_tags_by_name = 'SELECT id, name FROM tags WHERE name in (?)'
    _get_tagged_pictures = ('SELECT * FROM pictures WHERE id in '
                            '(SELECT picture_id FROM tagged_pics WHERE tag_id in (?))'
                            ' ORDER BY taken_time DESC LIMIT ? OFFSET ?')
    _total_for_tags = 'SELECT COUNT(*) as count FROM tagged_pics WHERE tag_id in (?)'

    def __init__(self, db):
        self.db = db

    def add(self, name):
        with self.db._get_conn() as conn:
            conn.execute(self._add_tag, [name.lower()])

    def get(self, name):
        with self.db._get_conn() as conn:
            matches = list(conn.execute(self._get_tag, [name.lower()]))
            if not matches:
                self.add(name)
                matches = list(conn.execute(self._get_tag, [name.lower()]))
            return matches[0]

    def all(self):
        with self.db._get_conn() as conn:
            return sorted({r['name'] for r in conn.execute(self._get_tags)})

    def pictures_for_tag(self, name):
        tag = self.get(name)
        t_id = tag['id']
        with self.db._get_conn() as conn:
            return [r for r in conn.execute(self._tagged_pics, [t_id])]

    def change_for_picture(self, picture_id, tags):
        with self.db._get_conn() as conn:
            conn.execute(self._clear_picture_tags, [picture_id])
        self.tag_picture(picture_id, tags)

    def for_picture(self, picture_id):
        with self.db._get_conn() as conn:
            return [t['name'] for t in conn.execute(self._pic_tags, [picture_id])]

    def tag_picture(self, picture_id, tags):
        with self.db._get_conn() as conn:
            for tag in tags:
                tag = tag.strip()
                if not tag:
                    continue
                t = self.get(tag)
                t_id = t['id']
                conn.execute(self._tag_picture, [t_id, picture_id])

    def tagged_pictures(self, tags, limit, offset):
        with self.db._get_conn() as conn:
            tag_ids = [str(t['id'])
                       # This usage of IN statement is wrong, look at by_keys()
                       for t in conn.execute(self._get_tags_by_name, [', '.join(tags)])]
            return conn.execute(self._get_tagged_pictures,
                (', '.join(tag_ids), limit, offset))

    def total_for_tags(self, tags):
        with self.db._get_conn() as conn:
            tag_ids = [str(t['id'])
                       # This usage of IN statement is wrong, look at by_keys()
                       for t in conn.execute(self._get_tags_by_name, [', '.join(tags)])]
            return conn.execute(self._total_for_tags, [', '.join(tag_ids)]).fetchone()['count']


class PictureManager:
    _by_keys = 'SELECT * FROM pictures WHERE key IN (%s)'
    _change_date = 'UPDATE pictures SET year=?, month=?, day=?, taken_time=?,' \
                   ' date_taken=? WHERE key =?'
    _get_recent = 'SELECT * FROM pictures ORDER BY id DESC LIMIT ? OFFSET ?'
    _get_pictures = 'SELECT * FROM pictures ORDER BY taken_time DESC LIMIT ? ' \
                    'OFFSET ?'
    _get_picture = 'SELECT * FROM pictures WHERE key = ?'
    _find_picture = 'SELECT * FROM pictures WHERE %s'
    _find_pictures = 'SELECT * FROM pictures WHERE %s ORDER BY taken_time ' \
                     'DESC'
    _count_pictures = 'SELECT COUNT(*) count FROM pictures WHERE %s'
    _update_picture = 'UPDATE pictures SET %s = ? WHERE key = ?'

    def __init__(self, db):
        self.db = db

    def by_keys(self, keys):
        with self.db._get_conn() as conn:
            return conn.execute(self._by_keys % ','.join('?' * len(keys)),
                keys)

    def change_date(self, picture_key, date_struct):
        with self.db._get_conn() as conn:
            conn.execute(self._change_date, [date_struct['year'],
                                             date_struct['month'],
                                             date_struct['day'],
                                             date_struct['taken_time'],
                                             date_struct['date_taken'],
                                             picture_key])

    def recent(self, limit, offset):
        with self.db._get_conn() as conn:
            return conn.execute(self._get_recent, (limit, offset))

    def by_key(self, key):
        with self.db._get_conn() as conn:
            return conn.execute(self._get_picture, [key]).fetchone()

    def get_all(self, limit, offset):
        with self.db._get_conn() as conn:
            return conn.execute(self._get_pictures, (limit, offset))

    def find_one(self, params):
        with self.db._get_conn() as conn:
            fields, values = zip(*params.items())
            query = self._find_picture % ' AND '.join('%s = ?' % f for f in fields)
            return conn.execute(query, values).fetchone()

    def find(self, params, limit=None, offset=None):
        with self.db._get_conn() as conn:
            fields, values = zip(*params.items())
            query = self._find_pictures % ' AND '.join('%s = ?' % f for f in fields)
            params = []
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            if offset:
                query += ' OFFSET ?'
                params.append(offset)
            return conn.execute(query, list(values) + params)

    def count(self, params):
        with self.db._get_conn() as conn:
            fields, values = zip(*params.items())
            query = self._count_pictures % ' AND '.join('%s = ?' % f for f in fields)
            return conn.execute(query, values).fetchone()['count']

    def update(self, key, attr, value):
        with self.db._get_conn() as conn:
            return conn.execute(self._update_picture % attr, [value, key])


class DB(BaseDB):
    _create = (
            'CREATE TABLE IF NOT EXISTS pictures '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  name TEXT,'
            '  filename TEXT,'
            '  notes TEXT,'
            '  key TEXT,'
            '  checksum TEXT,'
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
            '  format TEXT,'
            '  taken_time INTEGER,'
            '  upload_time INTEGER,'
            '  exif_read INTEGER,'
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
    _total_pictures = 'SELECT COUNT(*) as count FROM pictures'
    _get_years = 'SELECT DISTINCT year from pictures ORDER BY year DESC'
    _get_months = 'SELECT DISTINCT month from pictures WHERE year = ? ORDER BY year DESC'
    _get_days = 'SELECT DISTINCT day from pictures WHERE year=? AND month=? ORDER BY year DESC'
    _get_pictures_by_year = ('SELECT * FROM pictures WHERE year = ? ORDER BY '
                             'taken_time DESC LIMIT ? OFFSET ?')
    _total_for_year = 'SELECT COUNT(*) count FROM pictures WHERE year = ?'
    _file_exists = 'SELECT COUNT(*) count FROM pictures WHERE name=? AND checksum=?'

    @property
    def tags(self):
        return TagManager(self)

    @property
    def pictures(self):
        return PictureManager(self)

    def add_picture(self, picture_data, tags):
        with self._get_conn() as conn:
            query = self._add_picture % {
                'fields': ', '.join(picture_data.keys()),
                'values': ', '.join([':%s' % k for k in picture_data.keys()]),
            }
            cur = conn.execute(query, picture_data)
            picture_id = cur.lastrowid
            self.tags.tag_picture(picture_id, tags)

    def total_pictures(self):
        with self._get_conn() as conn:
            return conn.execute(self._total_pictures).fetchone()['count']

    def tagged(self, name):
        return self.tags.pictures_for_tag(name)

    def get_years(self):
        with self._get_conn() as conn:
            return [y['year'] for y in conn.execute(self._get_years)]

    def get_months(self, year):
        with self._get_conn() as conn:
            return [y['month'] for y in conn.execute(self._get_months, [year])]

    def get_days(self, year, month):
        with self._get_conn() as conn:
            return [y['day'] for y in conn.execute(self._get_days, [year, month])]

    def get_pictures_for_year(self, year, limit, offset):
        with self._get_conn() as conn:
            return conn.execute(self._get_pictures_by_year, (year, limit, offset))

    def total_for_year(self, year):
        with self._get_conn() as conn:
            return conn.execute(self._total_for_year, [year]).fetchone()['count']

    def file_exists(self, name, checksum):
        with self._get_conn() as conn:
            return bool(conn.execute(self._file_exists, [name, checksum]).fetchone()['count'])


class TokensDB(BaseDB):
    EXPIRE_WINDOW = 60 * 30  # Half hour
    _create = ['CREATE TABLE IF NOT EXISTS tokens '
            '('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  service TEXT,'
            '  token_type TEXT,'
            '  access_token TEXT,'
            '  refresh_token TEXT,'
            '  expires INTEGER'
            ');']
    _save_token = ('INSERT INTO tokens (service, access_token, token_type, '
                   'refresh_token, expires) VALUES (?,?,?,?,?)')
    _update_token = ('UPDATE tokens SET access_token=?, token_type=?, '
                     'expires=? WHERE service=?')
    _get_token = 'SELECT * FROM tokens WHERE service = ?'
    _get_expires = 'SELECT expires FROM tokens WHERE service = ? AND access_token = ?'

    def save_token(self, service, token, token_type, refresh_token, expires):
        with self._get_conn() as conn:
            conn.execute(self._save_token, [service, token, token_type,
                                            refresh_token, expires])

    def update_token(self, service, token, token_type, expires):
        with self._get_conn() as conn:
            conn.execute(self._update_token, [token, token_type, expires,
                                              service])

    def needs_refresh(self, service, token):
        with self._get_conn() as conn:
            response = conn.execute(self._get_expires, [service, token]).fetchone()
            expires = response['expires']
            return (time() + self.EXPIRE_WINDOW) > expires

    def get_token(self, service):
        with self._get_conn() as conn:
            return conn.execute(self._get_token, [service]).fetchone()
