import os

from . import UPLOAD_FOLDER, DB_FILE, queue_logger as log
from .db import DB
from .squeue import SqliteQueue
from .services import s3, gphotos, flickr, base

queue = SqliteQueue(DB_FILE)
db = DB(DB_FILE)

THUMBS_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
MAX_ATTEMPTS = 3

if not os.path.exists(THUMBS_FOLDER):
    os.makedirs(THUMBS_FOLDER)


def process_task(job):
    step = job['step']
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    base_file = os.path.basename(filename)
    tags = job['tags']
    upload_date = job['uploaded_at']
    key = job['key']

    log.info('Processing %s - Step: %s (%s)' % (key, step, base_file))
    if step == 'read_exif':
        exif = base.read_exif(filename, upload_date)
        job['data']['exif'] = exif
        job['step'] = 'thumbs'
    elif step == 'thumbs':
        thumbs = base.generate_thumbnails(filename, THUMBS_FOLDER)
        job['data']['thumbs'] = thumbs
        job['step'] = 's3_upload'
    elif step == 's3_upload':
        exif = job['data']['exif']
        thumbs = job['data']['thumbs']
        path = '%s/%s' % (exif['year'], exif['month'])
        s3_urls = s3.upload_thumbs(thumbs, path)
        job['data']['s3_urls'] = s3_urls
        job['step'] = 'flickr'
    elif step == 'flickr':
        flickr_url = flickr.upload(filename, tags)
        job['data']['flickr_url'] = flickr_url
        job['step'] = 'gphotos'
    elif step == 'gphotos':
        gphotos_url = gphotos.upload(filename)
        job['data']['gphotos_url'] = gphotos_url
        job['step'] = 'local_store'
    elif step == 'local_store':
        exif = job['data']['exif']
        s3_urls = job['data']['s3_urls']
        flickr_url = job['data']['flickr_url']
        gphotos_url = job['data']['gphotos_url']
        base.store_photo(db, s3_urls, flickr_url, gphotos_url, tags,
            upload_date, exif)
        job['step'] = 'finish'
    elif step == 'finish':
        base.delete_file(filename)
        log.info('Finished %s (%s)' % (key, base_file))
        return None
    return job


def daemon():
    log.info('Starting daemon')
    daemon_started = True
    while daemon_started:
        task = queue.popleft(100)
        try:
            next_task = process_task(task)
        except KeyboardInterrupt as inter:
            log.info('Daemon interrupted')
            daemon_started = False
        except SystemExit as inter:
            log.info('Daemon interrupted')
            daemon_started = False
        except Exception:
            if task['attempt'] <= MAX_ATTEMPTS:
                task['attempt'] += 1
                queue.append(task)
            else:
                # What should it do? Send a notification, record an error?
                # Don't loose the task
                pass
        else:
            if next_task:
                queue.append(next_task)

    log.info("Closing daemon")

