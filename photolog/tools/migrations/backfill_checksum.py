"""
This migration script will add and backfill a checksum(md5) for all files
on the database.

I ran this locally against my local backup of files. May not be useful in
other environments.
"""

import os
from os.path import join
from photolog.db import DB
from photolog import settings_file
from photolog.settings import Settings
from photolog.services.base import file_checksum


BASE_PATH = os.environ['BASE_PATH']


def migrate(db, settings):
    with db._get_conn() as conn:
        conn.execute('ALTER TABLE pictures ADD COLUMN checksum TEXT')

    total_ok, total_bad = 0, 0
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
        else:
            print("File not found: %s" % local_path)
            total_bad += 1

    print('Total OK: %s - Bad: %s' % (total_ok, total_bad))

if __name__ == '__main__':
    settings = Settings.load(settings_file)
    db = DB(settings.DB_FILE)
    migrate(db, settings)
