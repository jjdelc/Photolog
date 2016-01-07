import os
from photolog.db import DB

DB_FILE = os.environ['DB_FILE']

SCRIPT = """
DELETE FROM tagged_pics WHERE tag_id IN (SELECT id FROM tags WHERE name = '');
DELETE FROM tags WHERE name = '';
"""

def migrate(conn):
    conn.executescript(SCRIPT)


if __name__ == '__main__':
    db = DB(DB_FILE)
    with db._get_conn() as conn:
        migrate(conn)
