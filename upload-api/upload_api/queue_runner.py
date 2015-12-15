import os

from . import UPLOAD_FOLDER, DB_FILE, queue_logger as log
from .squeue import SqliteQueue
from .services import s3, gphotos, flickr, base

queue = SqliteQueue(DB_FILE)
THUMBS_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')

if not os.path.exists(THUMBS_FOLDER):
    os.makedirs(THUMBS_FOLDER)


def process(filename, tags, upload_date):
    log.info('Processing %s' % filename)
    exif = base.read_exif(filename, upload_date)
    thumbs = base.generate_thumbnails(filename, THUMBS_FOLDER)

    path = '%s/%s' % (exif['year'], exif['month'])
    s3_urls = s3.upload_thumbs(thumbs, path)
    flickr_url = flickr.upload(filename, tags)
    gphotos_url = gphotos.upload(filename)
    base.store_photo(s3_urls, flickr_url, gphotos_url, tags, upload_date, exif)
    base.delete_file(filename)
    log.info("Finished processing %s" % filename)


def daemon():
    log.info('Starting daemon')
    daemon_started = True
    while daemon_started:
        try:
            data = queue.popleft(100)
            filename = os.path.join(UPLOAD_FOLDER, data['filename'])
            tags = data['tags']
            upload_date = data['uploaded_at']
            process(filename, tags, upload_date)
        except KeyboardInterrupt as inter:
            log.info('Daemon interrupted')
            daemon_started = False
        except SystemExit as inter:
            log.info('Daemon interrupted')
            daemon_started = False
    log.info("Closing daemon")

