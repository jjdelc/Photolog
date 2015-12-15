# coding: utf-8

from boto.s3.key import Key
from os.path import basename
from boto.s3.connection import S3Connection
from upload_api import S3_ACCESS_KEY, S3_BUCKET, S3_SECRET_KEY


def upload_thumbs(thumbs, path):
    """
    Receives an object with a list of thumbnails, uploads them to s3 and returns
     another object with the s3 urls of those files
    """
    conn = S3Connection(S3_ACCESS_KEY, S3_SECRET_KEY)
    bucket = conn.get_bucket(S3_BUCKET, validate=False)
    uploaded = {}
    for thumb_name, full_filename in thumbs.items():
        filename = basename(full_filename)
        key = Key(bucket)
        key.key = '%s/%s' % (path, filename)
        key.set_contents_from_filename(full_filename)
        key.set_acl('public-read')
        uploaded[thumb_name] = key.generate_url(expires_in=0, query_auth=False)
    return uploaded
