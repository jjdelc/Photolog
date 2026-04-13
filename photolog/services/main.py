import os
import uuid
import binascii
from hashlib import md5
from datetime import datetime

from werkzeug.utils import secure_filename

from photolog.services.base import random_string


# Expected MIME types for file extensions
MIME_TYPES = {
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "gif": {"image/gif"},
    "arw": {"application/octet-stream", "image/x-sony-arw"},
    "raw": {"application/octet-stream", "image/x-raw"},
    "mp4": {"video/mp4"},
    "avi": {"video/x-msvideo", "video/avi"},
    "ogv": {"video/ogg"},
    "mpg": {"video/mpeg"},
    "mpeg": {"video/mpeg"},
    "mkv": {"video/x-matroska"},
}


def allowed_file(filename, file_obj=None, allowed_files=None):
    """
    Check if file extension is allowed and MIME type matches (if file_obj
    provided).
    """
    if "." not in filename:
        return False

    ext = filename.rsplit(".", 1)[1].lower()
    if allowed_files and ext not in allowed_files:
        return False

    # If file object provided, validate MIME type
    if file_obj and hasattr(file_obj, "content_type"):
        mime_type = file_obj.content_type or ""
        allowed_mimes = MIME_TYPES.get(ext, set())
        # Extract base MIME type (without charset or other params)
        base_mime = mime_type.split(";")[0].strip()
        if allowed_mimes and base_mime not in allowed_mimes:
            return False

    return True


def unique_filename(filename, salt, path):
    existing = {f.lower() for f in os.listdir(path)}
    # Season with hash initially anyway. This is to prevent file guesses
    # if the public URL leaks.
    name, ext = os.path.splitext(filename)
    final_filename = "%s-%s%s" % (name, salt, ext)
    while final_filename.lower() in existing:
        secret = random_string()
        final_filename = "%s-%s-%s%s" % (name, salt, secret, ext)
    return final_filename


def crc(file):
    buf = file.read()
    file.seek(0)
    return "%08X" % (binascii.crc32(buf) & 0xFFFFFFFF)


def filename_for_file(uploaded_file, filename, path):
    _crc = crc(uploaded_file)
    return unique_filename(secure_filename(filename), _crc, path)


def queue_file(
    _settings,
    _queue,
    uploaded_file,
    metadata_file,
    tags,
    skip,
    batch_id,
    is_last,
    target_date,
):
    filename = filename_for_file(uploaded_file, uploaded_file.filename, _settings.UPLOAD_FOLDER)
    uploaded_file.save(os.path.join(_settings.UPLOAD_FOLDER, filename))

    if metadata_file:
        metadata_filename = filename_for_file(
            metadata_file, metadata_file.filename, _settings.UPLOAD_FOLDER
        )
        metadata_file.save(os.path.join(_settings.UPLOAD_FOLDER, metadata_filename))
    _queue.append(
        {
            "type": "upload",
            "key": uuid.uuid4().hex,
            "filename": filename,
            "tags": tags,
            "original_filename": uploaded_file.filename,
            "metadata_filename": metadata_filename if metadata_file else None,
            "uploaded_at": datetime.now(),
            "target_date": target_date,
            "step": "upload_and_store",  # First thing to do to the pics,
            "data": {},  # Store additional parameters,
            "attempt": 0,  # Records how many times this step has been attempted
            "skip": skip,
            "batch_id": batch_id,
            "is_last": bool(is_last),
        }
    )
    return filename


def valid_secret(secret_from_header, api_secret):
    """
    Validate the X-PHOTOLOG-SECRET header against the configured API secret.
    """
    return secret_from_header == md5(api_secret.encode("utf-8")).hexdigest()
