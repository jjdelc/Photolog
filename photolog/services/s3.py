# coding: utf-8

import os
import math
import boto3
from os.path import basename

from photolog import queue_logger as log


def upload_thumbs(settings, thumbs, path):
    """
    Receives an object with a list of thumbnails, uploads them to s3 and returns
     another object with the s3 urls of those files
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    uploaded = {}
    for thumb_name, full_filename in thumbs.items():
        filename = basename(full_filename)
        key = f"{path}/{filename}"

        with open(full_filename, "rb") as f:
            s3_client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=f, ACL="public-read")

        # Generate public URL
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=0,
        )
        uploaded[thumb_name] = url
    return uploaded


CHUNK_SIZE = int(5e3 * 2**20)


def upload_video(settings, video_full_filename, path):
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    video_filename = basename(video_full_filename)
    key = f"{path}/{video_filename}"

    source_size = os.stat(video_full_filename).st_size
    chunks_count = int(math.ceil(source_size / float(CHUNK_SIZE)))

    # Initiate multipart upload
    response = s3_client.create_multipart_upload(Bucket=settings.S3_BUCKET, Key=key)
    upload_id = response["UploadId"]

    parts = []
    for i in range(chunks_count):
        offset = int(i * CHUNK_SIZE)
        remaining_bytes = source_size - offset
        bytes_to_read = min([CHUNK_SIZE, remaining_bytes])
        part_num = i + 1

        log.info("Uploading part " + str(part_num) + " of " + str(chunks_count))
        with open(video_full_filename, "rb") as fp:
            fp.seek(offset)
            part_data = fp.read(bytes_to_read)
            part_response = s3_client.upload_part(
                Bucket=settings.S3_BUCKET,
                Key=key,
                PartNumber=part_num,
                UploadId=upload_id,
                Body=part_data,
            )
            parts.append({"ETag": part_response["ETag"], "PartNumber": part_num})
            log.info("Done part " + str(part_num) + " of " + str(chunks_count))

    # Complete multipart upload
    if len(parts) == chunks_count:
        s3_client.complete_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        # Set public-read ACL
        s3_client.put_object_acl(Bucket=settings.S3_BUCKET, Key=key, ACL="public-read")
        log.info("upload_video done")
    else:
        s3_client.abort_multipart_upload(Bucket=settings.S3_BUCKET, Key=key, UploadId=upload_id)
        log.error("upload_file failed")

    # Generate public URL
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=0,
    )
    return url
