import os
import traceback

from . import queue_logger as log, settings_file
from .db import DB
from .squeue import SqliteQueue
from .services import s3, gphotos, flickr, base
from .settings import Setting


def job_fname(job, settings):
    return os.path.join(settings.UPLOAD_FOLDER, job['filename'])


def read_exif(db, settings, job):
    upload_date = job['uploaded_at']
    filename = job_fname(job, settings)
    exif = base.read_exif(filename, upload_date)
    job['data']['exif'] = exif
    return job


def local_store(db, settings, job):
    upload_date = job['uploaded_at']
    exif = job['data']['exif']
    s3_urls = job['data']['s3_urls']
    name = job['original_filename']
    key = job['key']
    tags = job['tags']
    base.store_photo(db, key, name, s3_urls, tags, upload_date, exif)
    return job


def generate_thumbs(db, settings, job):
    filename = job_fname(job, settings)
    thumbs = base.generate_thumbnails(filename, settings.THUMBS_FOLDER)
    job['data']['thumbs'] = thumbs
    return job


def s3_upload(db, settings, job):
    exif = job['data']['exif']
    thumbs = job['data']['thumbs']
    path = '%s/%s' % (exif['year'], exif['month'])
    s3_urls = s3.upload_thumbs(settings, thumbs, path)
    job['data']['s3_urls'] = s3_urls
    return job


def flickr_upload(db, settings, job):
    tags = job['tags']
    key = job['key']
    filename = job_fname(job, settings)
    flickr_url = flickr.upload(filename, tags)
    db.update_picture(key, 'flickr', flickr_url)
    job['data']['flickr_url'] = flickr_url
    return job


def gphotos_upload(db, settings, job):
    key = job['key']
    filename = job_fname(job, settings)
    gphotos_url = gphotos.upload(filename)
    db.update_picture(key, 'gphotos', gphotos_url)
    job['data']['gphotos_url'] = gphotos_url
    return job


def finish_job(db, settings, job):
    filename = job_fname(job, settings)
    base.delete_file(filename)
    return None


steps = {
    'read_exif': (read_exif, 'thumbs'),
    'thumbs': (generate_thumbs, 's3_upload'),
    's3_upload': (s3_upload, 'local_store'),
    'local_store': (local_store, 'flickr'),
    'flickr': (flickr_upload, 'gphotos'),
    'gphotos': (gphotos_upload, 'finish'),
    'finish': (finish_job, None)
}


def process_task(db, settings, job):
    step = job['step']
    filename = os.path.join(settings.UPLOAD_FOLDER, job['filename'])
    base_file = os.path.basename(filename)
    key = job['key']

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


def daemon(db, settings, queue):
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
            # If job was interrupted, don't toss job.
            queue.append(job)
            log.info('Daemon interrupted')
            daemon_started = False
        except Exception as exc:
            traceback.print_exc(exc)
            if job['attempt'] <= settings.MAX_QUEUE_ATTEMPTS:
                job['attempt'] += 1
                queue.append(job)
            else:
                # What should it do? Send a notification, record an error?
                # Don't loose the task
                queue.append_bad(job)
                pass
        else:
            if next_job:
                queue.append(next_job)

    log.info("Closing daemon")


def start_daemon():
    settings = Setting.load(settings_file)
    db = DB(settings.DB_FILE)
    queue = SqliteQueue(settings.DB_FILE)
    ensure_thumbs_folder(settings)
    daemon(db, settings, queue)


def ensure_thumbs_folder(settings):
    if not os.path.exists(settings.THUMBS_FOLDER):
        os.makedirs(settings.THUMBS_FOLDER)
