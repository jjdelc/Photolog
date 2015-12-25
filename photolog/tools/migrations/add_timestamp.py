from photolog.db import DB
from photolog import settings_file
from photolog.settings import Settings
from photolog.services.base import taken_timestamp


def migrate(db, settings):
    with db._get_conn() as conn:
        conn.execute('ALTER TABLE pictures ADD COLUMN format TEXT')
        conn.execute('ALTER TABLE pictures ADD COLUMN taken_time INTEGER')
        conn.execute('UPDATE pictures SET format="image"')

        for picture in conn.execute('SELECT * FROM pictures'):
            try:
                taken_time = taken_timestamp(picture['date_taken'], {
                    'year': int(picture['year']),
                    'month': int(picture['month']),
                    'day': int(picture['day']),
                })
                db.update_picture(picture['key'], 'taken_time', taken_time)
            except:
                pass


if __name__ == '__main__':
    settings = Settings.load(settings_file)
    db = DB(settings.DB_FILE)
    migrate(db, settings)
