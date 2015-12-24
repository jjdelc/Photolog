import os
import json
from photolog import queue_logger as log
from photolog.services import s3, gphotos, flickr, base


def job_fname(job, settings):
    return os.path.join(settings.UPLOAD_FOLDER, job['filename'])


class BaseJob(object):
    steps = {}
    raw = False

    def __init__(self, job_data, db, settings):
        self.data = job_data
        self.key = job_data['key']
        self.filename = job_data['filename']
        self.original_filename = job_data['original_filename']
        self.full_filepath = job_fname(job_data, settings)
        self.base_file = os.path.basename(job_data['filename'])
        self.settings = settings
        self.db = db

    def _read_exif(self):
        upload_date = self.data['uploaded_at']
        exif = base.read_exif(self.filename, upload_date, raw=self.raw)
        self.data['data']['exif'] = exif

    def _s3_upload(self):
        job = self.data
        exif = job['data']['exif']
        thumbs = job['data']['thumbs']
        path = '%s/%s' % (exif['year'], exif['month'])
        s3_urls = s3.upload_thumbs(self.settings, thumbs, path)
        job['data']['s3_urls'] = s3_urls

    def finish_job(self):
        thumbs = self.data['data']['thumbs']
        base.delete_file(self.full_filepath, thumbs)
        return None  # This ends the processing

    def process(self):
        step = self.data['step']
        task_name, next_step = self.steps[step]
        job = self.data
        if step in self.data['skip']:
            job['step'] = next_step
            job['attempt'] = 0  # Step completed. Start next job fresh
            log.info('Skipping %s - Step: %s (%s)' % (self.key, step,
                                                      self.base_file))
        else:
            log.info('Processing %s - Step: %s (%s)' % (self.key, step,
                                                        self.base_file))
            if job['attempt'] > 0:
                log.info('Attempt %s for %s - %s' % (job['attempt'], step,
                                                     self.key))
            task = getattr(self, task_name)
            job = task()
            if job:
                job['step'] = next_step
                job['attempt'] = 0  # Step completed. Start next job fresh
            else:
                log.info('Finished %s (%s)' % (self.key, self.base_file))

        return job


class ImageJob(BaseJob):
    steps = {  # Step function, Next job
        'upload_and_store': ('local_process', 'flickr'),
        'flickr': ('flickr_upload', 'gphotos'),
        'gphotos': ('gphotos_upload', 'finish'),
        'finish': ('finish_job', None)
    }

    def _local_store(self):
        job = self.data
        upload_date = job['uploaded_at']
        exif = job['data']['exif']
        s3_urls = job['data']['s3_urls']
        tags = job['tags']
        base.store_photo(
            self.db,
            self.key,
            self.original_filename,
            s3_urls, tags, upload_date, exif)

    def _generate_thumbs(self):
        thumbs = base.generate_thumbnails(self.full_filepath,
            self.settings.THUMBS_FOLDER)
        self.data['data']['thumbs'] = thumbs

    def flickr_upload(self):
        tags = self.data['tags']
        key = self.key
        flickr_url, photo_id = flickr.upload(self.settings, self.filename,
            self.full_filepath, tags)
        self.db.update_picture(key, 'flickr', json.dumps({
            'url': flickr_url,
            'id': photo_id
        }))
        log.info("Uploaded %s to Flickr" % key)
        return self.data

    def gphotos_upload(db, settings, job):
        key = job['key']
        filename = job_fname(job, settings)
        gphotos_data = gphotos.upload(settings, filename, job['filename'])
        db.update_picture(key, 'gphotos', json.dumps({
            'xml': gphotos_data
        }))
        log.info("Uploaded %s to Gphotos" % key)
        return job

    def local_process(self):
        """
        Collapses quick jobs so each picture doesn't get queued up in case of
        long batches
        """
        base_file = self.base_file
        key = self.key
        log.info('Processing %s - Step: read_exif (%s)' % (key, base_file))
        self._read_exif()
        log.info('Processing %s - Step: thumbs (%s)' % (key, base_file))
        self._generate_thumbs()
        log.info('Processing %s - Step: s3_upload (%s)' % (key, base_file))
        self._s3_upload()
        log.info('Processing %s - Step: local_store (%s)' % (key, base_file))
        self._local_store()
        return self.data


class RawFileJob(BaseJob):
    steps = {  # Step function, Next job
        'upload_and_store': ('local_process', 'finish'),
        'finish': ('finish_job', None)
    }
    raw = True

    def local_process(self):
        """
        Collapses quick jobs so each picture doesn't get queued up in case of
        long batches
        """
        base_file = self.base_file
        key = self.key
        log.info('Processing %s - Step: read_exif (%s)' % (key, base_file))
        self._read_exif()
        log.info('Processing %s - Step: s3_upload (%s)' % (key, base_file))
        self.data['data']['thumbs'] = {}
        self._s3_upload()
        log.info('Processing %s - Step: local_store (%s)' % (key, base_file))
        self._local_store()
        return self.data

