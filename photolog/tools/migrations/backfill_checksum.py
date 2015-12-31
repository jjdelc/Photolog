"""
This migration script will add and backfill a checksum(md5) for all files
on the database.

I ran this locally against my local backup of files. May not be useful in
other environments.
"""

import os
from os.path import join
from photolog.db import DB
from photolog.services.base import file_checksum


BASE_PATH = os.environ['BASE_PATH']
DB_FILE = os.environ['DB_FILE']


def migrate(conn):
    conn.execute('ALTER TABLE pictures ADD COLUMN checksum TEXT')

    total_ok, total_bad = 0, 0
    updates = []
    for picture in conn.execute('SELECT * FROM pictures'):
        local_path = join(BASE_PATH, picture['year'],
            '%s%s' % (picture['month'], picture['day']))
        name = picture['name']

        tries = [join(local_path, name), join(local_path, name.upper())]
        found, found_file, checksum = True, None, None
        for file in tries:
            try:
                checksum = file_checksum(file)
                found_file = file
                break
            except FileNotFoundError:
                pass
            found = False

        if found:
            total_ok += 1
            print("Checksum for: %s: %s" % (found_file, checksum))
            updates.append((picture['id'], checksum))
        else:
            print("File not found: %s" % local_path)
            total_bad += 1
    print('Total OK: %s - Bad: %s' % (total_ok, total_bad))

    for pic_id, checksum in updates:
        conn.execute('UPDATE pictures SET checksum =? WHERE id=?',
            [pic_id, checksum])


if __name__ == '__main__':
    db = DB(DB_FILE)
    with db._get_conn() as conn:
        migrate(conn)
