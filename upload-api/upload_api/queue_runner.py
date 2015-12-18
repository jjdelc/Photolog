import os
import traceback

from . import UPLOAD_FOLDER, DB_FILE, queue_logger as log
from .db import DB
from .squeue import SqliteQueue
from .services import s3, gphotos, flickr, base

queue = SqliteQueue(DB_FILE)

THUMBS_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
MAX_ATTEMPTS = 3

if not os.path.exists(THUMBS_FOLDER):
    os.makedirs(THUMBS_FOLDER)


def read_exif(db, settings, job):
    upload_date = job['uploaded_at']
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    exif = base.read_exif(filename, upload_date)
    job['data']['exif'] = exif
    return job


def local_store(db, settings, job):
    upload_date = job['uploaded_at']
    exif = job['data']['exif']
    s3_urls = job['data']['s3_urls']
    flickr_url = job['data']['flickr_url']
    gphotos_url = job['data']['gphotos_url']
    name = job['original_filename']
    key = job['key']
    tags = job['tags']
    base.store_photo(db, key, name, s3_urls, flickr_url, gphotos_url, tags,
        upload_date, exif)
    return job


def generate_thumbs(db, settings, job):
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    thumbs = base.generate_thumbnails(filename, THUMBS_FOLDER)
    job['data']['thumbs'] = thumbs
    return job


def s3_upload(db, settings, job):
    exif = job['data']['exif']
    thumbs = job['data']['thumbs']
    path = '%s/%s' % (exif['year'], exif['month'])
    s3_urls = s3.upload_thumbs(thumbs, path)
    job['data']['s3_urls'] = s3_urls
    return job


def flickr_upload(db, settings, job):
    tags = job['tags']
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    flickr_url = flickr.upload(filename, tags)
    job['data']['flickr_url'] = flickr_url
    return job


def gphotos_upload(db, settings, job):
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    gphotos_url = gphotos.upload(filename)
    job['data']['gphotos_url'] = gphotos_url
    return job


def finish_job(db, settings, job):
    key = job['key']
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    base_file = os.path.basename(filename)
    base.delete_file(filename)
    return None


steps = {
    'read_exif': (read_exif, 'thumbs'),
    'thumbs': (generate_thumbs, 's3_upload'),
    's3_upload': (s3_upload, 'flickr'),
    'flickr': (flickr_upload, 'gphotos'),
    'gphotos': (gphotos_upload, 'local_store'),
    'local_store': (local_store, 'finish'),
    'finish': (finish_job, None)
}


def process_task(db, settings, job):
    step = job['step']
    filename = os.path.join(UPLOAD_FOLDER, job['filename'])
    base_file = os.path.basename(filename)
    key = job['key']
    settings = None

    log.info('Processing %s - Step: %s (%s)' % (key, step, base_file))
    if job['attempt'] > 0:
        log.info('Attempt %s for %s - %s' % (job['attempt'], step, key))

    step_func, next_step = steps[step]
    job = step_func(db, settings, job)
    if job:
        job['step'] = next_step
        job['attempt'] = 0  # Step completed. Start next job fresh
    else:
        log.info('Finished %s (%s)' % (key, base_file))

    return job


def daemon(db, settings):
    log.info('Starting daemon')
    daemon_started = True
    while daemon_started:
        job = queue.popleft(100)
        try:
            next_job = process_task(db, settings, job)
        except KeyboardInterrupt as inter:
            log.info('Daemon interrupted')
            daemon_started = False
        except SystemExit as inter:
            log.info('Daemon interrupted')
            daemon_started = False
        except Exception as exc:
            traceback.print_exc(exc)
            if job['attempt'] <= MAX_ATTEMPTS:
                job['attempt'] += 1
                queue.append(job)
            else:
                # What should it do? Send a notification, record an error?
                # Don't loose the task
                pass
        else:
            if next_job:
                queue.append(next_job)

    log.info("Closing daemon")


def start_daemon():
    db = DB(DB_FILE)
    settings = None
    daemon(db, settings)