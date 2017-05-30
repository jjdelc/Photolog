# coding: utf-8

import os
import math
from boto.s3.key import Key
from os.path import basename
from boto.s3.connection import S3Connection

from photolog import queue_logger as log


def upload_thumbs(settings, thumbs, path):
    """
    Receives an object with a list of thumbnails, uploads them to s3 and returns
     another object with the s3 urls of those files
    """
    conn = S3Connection(settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(settings.S3_BUCKET, validate=False)
    uploaded = {}
    for thumb_name, full_filename in thumbs.items():
        filename = basename(full_filename)
        key = Key(bucket)
        key.key = '%s/%s' % (path, filename)
        key.set_contents_from_filename(full_filename)
        key.set_acl('public-read')
        uploaded[thumb_name] = key.generate_url(expires_in=0, query_auth=False)
    return uploaded


CHUNK_SIZE = int(5e3 * 2 ** 20)


def upload_video(settings, video_full_filename, path):
    conn = S3Connection(settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(settings.S3_BUCKET, validate=False)
    video_filename = basename(video_full_filename)
    video_key = Key(bucket)
    video_key.key = '%s/%s' % (path, video_filename)

    source_size = os.stat(video_full_filename).st_size
    chunks_count = int(math.ceil(source_size / float(CHUNK_SIZE)))
    mp = bucket.initiate_multipart_upload(video_key.key)

    for i in range(chunks_count):
        offset = int(i * CHUNK_SIZE)
        remaining_bytes = source_size - offset
        bytes = min([CHUNK_SIZE, remaining_bytes])
        part_num = i + 1

        log.info("Uploading part " + str(part_num) + " of " + str(chunks_count))
        with open(video_full_filename, 'rb') as fp:
            fp.seek(offset)
            mp.upload_part_from_file(fp=fp, part_num=part_num, size=bytes)
            log.info("Done part " + str(part_num) + " of " + str(chunks_count))

    if len(mp.get_all_parts()) == chunks_count:
        mp.complete_upload()
        video_key.set_acl('public-read')
        log.info("upload_video done")
    else:
        mp.cancel_upload()
        log.error("upload_file failed")

    return video_key.generate_url(expires_in=0, query_auth=False)
