import json
import sys
import traceback

import os
from photolog.db import DB
from photolog.settings import Settings
from photolog.squeue import SqliteQueue
from photolog.services import s3, gphotos, flickr, base
from photolog import queue_logger as log, settings_file, RAW_FILES


def job_fname(job, settings):
    return os.path.join(settings.UPLOAD_FOLDER, job['filename'])


def is_raw_file(filename):
    name, ext = os.path.splitext(filename)
    ext = ext.lstrip('.').lower()
    return ext in RAW_FILES


def read_exif(db, settings, job):
    upload_date = job['uploaded_at']
    filename = job_fname(job, settings)
    exif = base.read_exif(filename, upload_date, is_raw_file(filename))
    job['data']['exif'] = exif
    return job


def generate_thumbs(db, settings, job):
    filename = job_fname(job, settings)
    thumbs = base.generate_thumbnails(filename, settings.THUMBS_FOLDER)
    job['data']['thumbs'] = thumbs
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


def s3_upload(db, settings, job):
    exif = job['data']['exif']
    thumbs = job['data']['thumbs']
    path = '%s/%s' % (exif['year'], exif['month'])
    s3_urls = s3.upload_thumbs(settings, thumbs, path)
    job['data']['s3_urls'] = s3_urls
    return job


def local_process(db, settings, job):
    """
    Collapses quick jobs so each picture doesn't get queued up in case of
    long batches
    """
    filename = job_fname(job, settings)
    base_file = os.path.basename(filename)
    key = job['key']
    log.info('Processing %s - Step: read_exif (%s)' % (key, base_file))
    job = read_exif(db, settings, job)
    log.info('Processing %s - Step: thumbs (%s)' % (key, base_file))
    job = generate_thumbs(db, settings, job)
    log.info('Processing %s - Step: s3_upload (%s)' % (key, base_file))
    job = s3_upload(db, settings, job)
    log.info('Processing %s - Step: local_store (%s)' % (key, base_file))
    job = local_store(db, settings, job)
    return job


def flickr_upload(db, settings, job):
    tags = job['tags']
    key = job['key']
    full_filename = job_fname(job, settings)
    flickr_url, photo_id = flickr.upload(settings, job['filename'],
        full_filename, tags)
    db.update_picture(key, 'flickr', json.dumps({
        'url': flickr_url,
        'id': photo_id
    }))
    log.info("Uploaded %s to Flickr" % key)
    return job


def gphotos_upload(db, settings, job):
    key = job['key']
    filename = job_fname(job, settings)
    gphotos_data = gphotos.upload(settings, filename, job['filename'])
    db.update_picture(key, 'gphotos', json.dumps({
        'xml': gphotos_data
    }))
    log.info("Uploaded %s to Gphotos" % key)
    return job


def finish_job(db, settings, job):
    filename = job_fname(job, settings)
    thumbs = job['data']['thumbs']
    base.delete_file(filename, thumbs)
    return None


steps = {  # Step function, Next job
    'upload_and_store': (local_process, 'flickr'),
    'flickr': (flickr_upload, 'gphotos'),
    'gphotos': (gphotos_upload, 'finish'),
    'finish': (finish_job, None)
}


def process_task(db, settings, job):
    step = job['step']
    filename = job_fname(job, settings)
    base_file = os.path.basename(filename)
    key = job['key']
    skip = job['skip']

    step_func, next_step = steps[step]
    if step in skip:
        job['step'] = next_step
        job['attempt'] = 0  # Step completed. Start next job fresh
        log.info('Skipping %s - Step: %s (%s)' % (key, step, base_file))
        return job

    log.info('Processing %s - Step: %s (%s)' % (key, step, base_file))
    if job['attempt'] > 0:
        log.info('Attempt %s for %s - %s' % (job['attempt'], step, key))

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
            queue.append(job)
            daemon_started = False
        except SystemExit as inter:
            # If job was interrupted, don't toss job.
            queue.append(job)
            log.info('Daemon interrupted')
            daemon_started = False
        except Exception as exc:
            ex_type, ex, tb = sys.exc_info()
            traceback.print_tb(tb)
            if job['attempt'] <= settings.MAX_QUEUE_ATTEMPTS:
                job['attempt'] += 1
                queue.append(job)
            else:
                # What should it do? Send a notification, record an error?
                # Don't loose the task
                log.info('Adding job %s to bad jobs' % job['key'])
                queue.append_bad(job)
        else:
            if next_job:
                queue.append(next_job)

    log.info("Finishing daemon")


def start():
    settings = Settings.load(settings_file)
    db = DB(settings.DB_FILE)
    queue = SqliteQueue(settings.DB_FILE)
    ensure_thumbs_folder(settings)
    daemon(db, settings, queue)


def ensure_thumbs_folder(settings):
    if not os.path.exists(settings.THUMBS_FOLDER):
        os.makedirs(settings.THUMBS_FOLDER)
