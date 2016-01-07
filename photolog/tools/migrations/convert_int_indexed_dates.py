import os
from photolog.db import DB

DB_FILE = os.environ['DB_FILE']

SCRIPT = """
CREATE TABLE pictures_new (  
id INTEGER PRIMARY KEY AUTOINCREMENT,  
  name TEXT,
  filename TEXT,
  notes TEXT,
  key TEXT,
  checksum TEXT,
  original TEXT,
  thumb TEXT,
  medium TEXT,
  web TEXT,
  large TEXT,
  flickr TEXT,
  gphotos TEXT,
  year INTEGER,
  month INTEGER,
  day INTEGER,
  width INTEGER,
  height INTEGER,
  size INTEGER,
  camera TEXT,
  upload_date TEXT,
  format TEXT,
  taken_time INTEGER,
  upload_time INTEGER,
  exif_read INTEGER,
  date_taken TEXT
);


INSERT INTO pictures_new SELECT
 id, name, filename, notes, key, checksum, original, thumb, medium, web, large,
 flickr, gphotos, CAST(year as INTEGER), CAST(month as INTEGER),
 CAST(day as INTEGER), width, height, size, camera, upload_date, format,
 taken_time, upload_time, exif_read, date_taken FROM pictures;
DROP TABLE pictures;
ALTER TABLE pictures_new RENAME TO pictures;
CREATE INDEX year_idx ON pictures (year);
CREATE INDEX month_idx ON pictures (month);
CREATE INDEX day_idx ON pictures (day);
CREATE INDEX key_idx ON pictures (key);

"""


def migrate(conn):
    conn.executescript(SCRIPT)


if __name__ == '__main__':
    db = DB(DB_FILE)
    with db._get_conn() as conn:
        migrate(conn)
