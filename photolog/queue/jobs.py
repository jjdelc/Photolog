import os
import json
from time import mktime
from photolog.services import s3, gphotos, flickr, base
from photolog import queue_logger as log, RAW_FILES, IMAGE_FILES, VIDEO_FILES


def job_fname(filename, settings):
    return os.path.join(settings.UPLOAD_FOLDER, filename)


class BaseJob(object):
    steps = {}

    def __init__(self, job_data, db, settings):
        self.data = job_data
        self.key = job_data['key']
        self.settings = settings
        self.db = db

    def process(self):
        raise NotImplemented


class BaseUploadJob(BaseJob):
    format = 'image'

    def __init__(self, job_data, db, settings):
        super(BaseUploadJob, self).__init__(job_data, db, settings)
        # Contains only name/extension with unique hash - Refers to file on disk
        self.filename = job_data['filename']
        # Original filename of the file uploaded on remove system
        self.original_filename = job_data['original_filename']
        # Metadata file if any (for videos)
        self.metadata_filename = self.data['metadata_filename']
        # Full file path of uploaded original file locally
        self.full_filepath = job_fname(job_data['filename'], settings)
        if self.metadata_filename:
            self.metadata_full_filepath = job_fname(job_data['metadata_filename'], settings)
        else:
            self.metadata_full_filepath = None

    def _read_exif(self):
        upload_date = self.data['uploaded_at']
        exif = base.read_exif(self.full_filepath, upload_date,
            self.format == 'image')
        self.data['data']['exif'] = exif

    def _s3_upload(self):
        job = self.data
        exif = job['data']['exif']
        thumbs = job['data']['thumbs']
        path = '%s/%s' % (exif['year'], exif['month'])
        s3_urls = s3.upload_thumbs(self.settings, thumbs, path)
        job['data']['s3_urls'] = s3_urls

    def _get_notes(self):
        return ''

    def _get_checksum(self):
        return base.file_checksum(self.full_filepath)

    def _local_store(self):
        job = self.data
        upload_date = job['uploaded_at']
        exif = job['data']['exif']
        s3_urls = job['data']['s3_urls']
        tags = job['tags']
        checksum = self._get_checksum()
        base.store_photo(
            self.db,
            self.key,
            self.original_filename,
            s3_urls, tags, upload_date, exif, self.format,
            checksum, notes=self._get_notes())

    def finish_job(self):
        thumbs = self.data['data'].get('thumbs', {})
        base.delete_file(self.full_filepath, thumbs)
        return None  # This ends the processing

    def process(self):
        job = self.data
        step = job['step']
        task_name, next_step = self.steps[step]
        if step in job.get('skip', []):
            job['step'] = next_step
            job['attempt'] = 0  # Step completed. Start next job fresh
            log.info('Skipping %s - Step: %s (%s)' % (self.key, step,
                                                      self.filename))
        else:
            log.info('Processing %s - Step: %s (%s)' % (self.key, step,
                                                        self.filename))
            if job['attempt'] > 0:
                log.info('Attempt %s for %s - %s' % (job['attempt'], step,
                                                     self.key))
            task = getattr(self, task_name)
            job = task()
            if job:
                job['step'] = next_step
                job['attempt'] = 0  # Step completed. Start next job fresh
            else:
                log.info('Finished %s (%s)' % (self.key, self.filename))
                # if self.data['is_last']:
                #     batch_id = self.data['batch_id']
                #     base.end_batch(batch_id, self.settings)
                #     log.info("Batch %s ended" % batch_id)
        return job


class ImageJob(BaseUploadJob):
    steps = {  # Step function, Next job
        'upload_and_store': ('local_process', 'flickr'),
        'flickr': ('flickr_upload', 'gphotos'),
        'gphotos': ('gphotos_upload', 'finish'),
        'finish': ('finish_job', None)
    }

    def _generate_thumbs(self):
        thumbs = base.generate_thumbnails(self.full_filepath,
            self.settings.THUMBS_FOLDER)
        self.data['data']['thumbs'] = thumbs

    def flickr_upload(self):
        if not self.settings.FLICKR_ENABLED:
            return self.data
        tags = self.data['tags']
        key = self.key
        flickr_url, photo_id = flickr.upload(self.settings, self.filename,
            self.full_filepath, tags)
        self.db.pictures.update(key, 'flickr', json.dumps({
            'url': flickr_url,
            'id': photo_id
        }))
        log.info("Uploaded %s to Flickr" % key)
        return self.data

    def gphotos_upload(self):
        batch_id = self.data['batch_id']
        album_url = None
        if batch_id:
            album_url = base.batch_2_album(batch_id, self.settings,
                section='feed')
        gphotos_data = gphotos.upload_photo(self.settings, self.full_filepath,
            self.filename, album_url)
        self.db.pictures.update(self.key, 'gphotos', json.dumps({
            'xml': gphotos_data
        }))
        log.info("Uploaded %s to Gphotos" % self.key)
        return self.data

    def local_process(self):
        """
        Collapses quick jobs so each picture doesn't get queued up in case of
        long batches
        """
        base_file = self.original_filename
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


class VideoJob(BaseUploadJob):
    format = 'video'
    steps = {
        'upload_and_store': ('local_process', 'gphotos'),
        'gphotos': ('gphotos_upload', 'finish'),
        'finish': ('finish_job', None)
    }

    def _generate_thumbnail(self):
        thumbs, output_dir = base.get_video_thumbnail(self.settings,
            self.full_filepath, self.filename, self.key)
        self.data['output_dir'] = output_dir
        self.data['data']['thumbs'] = thumbs

    def _s3_video_upload(self):
        job = self.data
        exif = job['data']['exif']
        path = '%s/%s' % (exif['year'], exif['month'])
        thumbs = self.data['data']['thumbs']
        uploaded_thumbs = s3.upload_thumbs(self.settings, thumbs, path)
        video = s3.upload_video(self.settings, self.full_filepath, path)
        uploaded_thumbs['video'] = video
        job['data']['s3_urls'] = uploaded_thumbs

    def _local_store(self):
        job = self.data
        upload_date = job['uploaded_at']
        s3_urls = job['data']['s3_urls']
        tags = job['tags']
        checksum = self._get_checksum()
        exif = job['data']['exif']
        base.store_video(
            self.db,
            self.key,
            self.original_filename,
            s3_urls, tags, upload_date, exif, self.format,
            checksum, notes=self._get_notes())

    def _read_exif(self):
        upload_date = self.data['target_date'] or self.data['uploaded_at']
        upload_date = base.ensure_datetime(upload_date)
        thumbnail = self.data['data']['thumbs']['original']
        exif = base.video_exif(self.settings, self.full_filepath, upload_date,
            self.metadata_full_filepath, thumbnail)
        self.data['data']['exif'] = exif

    def gphotos_upload(self):
        batch_id = self.data['batch_id']
        album_url = None
        if batch_id:
            album_url = base.batch_2_album(batch_id, self.settings,
                section='feed')
        mime = self.data['data']['exif']['mime']
        gphotos_data = gphotos.upload_video(self.settings, self.full_filepath,
            self.filename, album_url, mime)
        self.db.pictures.update(self.key, 'gphotos', json.dumps({
            'xml': gphotos_data
        }))
        log.info("Uploaded %s to Gphotos" % self.key)
        return self.data

    def finish_job(self):
        # Delete thumbnails from selected thumb
        thumbs = self.data['data'].get('thumbs', {})
        base.delete_file(self.full_filepath, thumbs)
        # Delete metadata file if any
        if self.metadata_filename:
            base.delete_file(self.metadata_filename, {})
        # Delete directory with video screen caps
        base.delete_dir(self.data['output_dir'])
        return None  # This ends the processing

    def local_process(self):
        """
        Generate thumbnails and upload raw video to S3
        """
        base_file = self.original_filename
        key = self.key
        log.info('Processing %s - Obtaining thumbnail (%s)' % (key, base_file))
        self._generate_thumbnail()
        log.info('Processing %s - Read metadata (%s)' % (key, base_file))
        self._read_exif()
        log.info('Processing %s - Upload file (%s)' % (key, base_file))
        self._s3_video_upload()
        log.info('Processing %s - local_store (%s)' % (key, base_file))
        self._local_store()
        log.info('Processing %s - Stored (%s)' % (key, base_file))
        return self.data


class RawFileJob(BaseUploadJob):
    steps = {  # Step function, Next job
        'upload_and_store': ('local_process', 'finish'),
        'finish': ('finish_job', None)
    }
    format = 'raw'

    def _get_reference_file(self):
        name, ext = os.path.splitext(self.original_filename)
        # We hope that the raw file came with a sister JPEG file
        # it should have the sane name in JPG extension
        possibilities = [p % name for p in [
            '%s_ARW_embedded.jpg',
            '%s.jpg',
            '%s.JPG',
            '%s.JPEG',
            '%s.jpeg',
        ]]
        exif = self.data['data']['exif']
        for pos in possibilities:
            result = self.db.pictures.find_one({
                'name': pos,
                'year': exif['year'],
                'month': exif['month'],
                'day': exif['day'],
            })
            if result:
                return result

    def _get_notes(self):
        reference = self._get_reference_file()
        if reference:
            return 'REFERENCE: %s' % reference['key']
        return ''

    def _s3_upload(self):
        job = self.data
        exif = job['data']['exif']
        path = '%s/%s' % (exif['year'], exif['month'])
        s3_urls = s3.upload_thumbs(self.settings, {
            'original': self.full_filepath
        }, path)
        job['data']['s3_urls'] = s3_urls

    def _copy_thumbs(self):
        # Will use thumbnail from reference file
        reference = self._get_reference_file()
        if reference:
            self.data['data']['s3_urls'].update({
                'thumb': reference['thumb'],
                'web': reference['web'],
                'large': reference['large'],
                'medium': reference['medium'],
            })

    def local_process(self):
        """
        Collapses quick jobs so each picture doesn't get queued up in case of
        long batches
        """
        base_file = self.original_filename
        key = self.key
        log.info('Processing %s - Step: read_exif (%s)' % (key, base_file))
        self._read_exif()
        # We don't generate thumbnails for RAW files
        log.info('Processing %s - Step: s3_upload (%s)' % (key, base_file))
        self._s3_upload()
        self._copy_thumbs()
        log.info('Processing %s - Step: local_store (%s)' % (key, base_file))
        self._local_store()
        return self.data


class TagDayJob(BaseJob):
    """
    This job will receive a year/month/day and change the tags
    of all pictures on that date for the new ones.
    """
    def process(self):
        data = self.data
        pictures = list(self.db.pictures.find({
            'year': data['year'],
            'month': data['month'],
            'day': data['day']
        }))
        log.info("Tagging day: %s-%s-%s (%s pictures)" % (data['year'],
            data['month'], data['day'], len(pictures)))
        tags = data['tags']
        for picture in pictures:
            self.db.tags.change_for_picture(picture['id'], tags)
        log.info("Done")


class MassTagJob(BaseJob):
    """
    Will receive a list of picture keys and change tags for each of them.
    """
    def process(self):
        data = self.data
        pictures = list(self.db.pictures.by_keys(data['keys']))
        log.info("Tagging %s pictures" % len(pictures))
        tags = data['tags']
        for picture in pictures:
            self.db.tags.change_for_picture(picture['id'], tags)
        log.info("Done")


class EditDatesJob(BaseJob):
    """
    Will receive a list of picture keys and change tags for each of them.
    """
    def process(self):
        changes = self.data['changes']
        keys, dates = zip(*changes)
        pictures = {p['key']: p for p in self.db.pictures.by_keys(keys)}
        log.info("Changing dates for %s pictures" % len(pictures))
        for key, date in changes:
            self.db.pictures.change_date(key, {
                'year': date.year,
                'month': date.month,
                'day': date.day,
                'taken_time': mktime(date.timetuple()),
                'date_taken': date.strftime('%Y-%m-%d')
            })
        log.info("Done")


class ChangeDateJob(BaseJob):
    """
    Changes the date of all pictures in one day
    """
    def process(self):
        origin = self.data['origin']
        target = self.data['target']
        params = {
            'year': origin.year,
            'month': origin.month,
            'day': origin.day
        }
        pictures = list(self.db.pictures.find(params))
        for pic in pictures:
            self.db.pictures.change_date(pic['key'], {
                'year': target.year,
                'month': target.month,
                'day': target.day,
                'taken_time': mktime(target.timetuple()),
                'date_taken': target.strftime('%Y-%m-%d')
            })
        log.info("Done")

upload_formats = [
    (ImageJob, IMAGE_FILES),
    (RawFileJob, RAW_FILES),
    (VideoJob, VIDEO_FILES)
]

job_types = {
    'tag-day': TagDayJob,
    'mass-tag': MassTagJob,
    'edit-dates': EditDatesJob,
    'change-date': ChangeDateJob,
}


def prepare_job(job, db, settings):
    if job.get('type', 'upload') == 'upload':
        filename = job_fname(job['filename'], settings)
        name, ext = os.path.splitext(filename)
        ext = ext.lstrip('.').lower()
        for cls, types in upload_formats:
            if ext in types:
                return cls(job, db, settings)

    cls = job_types[job['type']]
    return cls(job, db, settings)
