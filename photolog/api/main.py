import os
import uuid
import binascii
from hashlib import md5
from datetime import datetime

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect

from photolog.db import DB
from photolog.squeue import SqliteQueue
from photolog.settings import Settings
from photolog import api_logger as log, settings_file, ALLOWED_FILES
from photolog.services.base import random_string, start_batch, end_batch, \
    slugify

settings = Settings.load(settings_file)
queue = SqliteQueue(settings.DB_FILE)
db = DB(settings.DB_FILE)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB  # Raw files

# Initialize CSRF protection; API routes exempt (they use X-PHOTOLOG-SECRET instead)
csrf = CSRFProtect()
csrf.init_app(app)


# Expected MIME types for file extensions
MIME_TYPES = {
    'jpg': {'image/jpeg'},
    'jpeg': {'image/jpeg'},
    'png': {'image/png'},
    'gif': {'image/gif'},
    'arw': {'application/octet-stream', 'image/x-sony-arw'},
    'raw': {'application/octet-stream', 'image/x-raw'},
    'mp4': {'video/mp4'},
    'avi': {'video/x-msvideo', 'video/avi'},
    'ogv': {'video/ogg'},
    'mpg': {'video/mpeg'},
    'mpeg': {'video/mpeg'},
    'mkv': {'video/x-matroska'},
}


def allowed_file(filename, file_obj=None):
    """Check if file extension is allowed and MIME type matches (if file_obj provided)."""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_FILES:
        return False

    # If file object provided, validate MIME type
    if file_obj and hasattr(file_obj, 'content_type'):
        mime_type = file_obj.content_type or ''
        allowed_mimes = MIME_TYPES.get(ext, set())
        # Extract base MIME type (without charset or other params)
        base_mime = mime_type.split(';')[0].strip()
        if allowed_mimes and base_mime not in allowed_mimes:
            return False

    return True


def unique_filename(filename, salt, path):
    existing = {f.lower() for f in os.listdir(path)}
    # Season with hash initially anyway. This is to prevent file guesses
    # if the public URL leaks.
    name, ext = os.path.splitext(filename)
    final_filename = '%s-%s%s' % (name, salt, ext)
    while final_filename.lower() in existing:
        secret = random_string()
        final_filename = '%s-%s-%s%s' % (name, salt, secret, ext)
    return final_filename


def crc(file):
    buf = file.read()
    file.seek(0)
    return '%08X' % (binascii.crc32(buf) & 0xFFFFFFFF)


def filename_for_file(uploaded_file, filename, path):
    _crc = crc(uploaded_file)
    return unique_filename(secure_filename(filename), _crc, path)


def queue_file(_settings, _queue, uploaded_file, metadata_file, tags, skip,
        batch_id, is_last, target_date):
    filename = filename_for_file(uploaded_file, uploaded_file.filename,
                                 _settings.UPLOAD_FOLDER)
    uploaded_file.save(os.path.join(_settings.UPLOAD_FOLDER, filename))

    if metadata_file:
        metadata_filename = filename_for_file(metadata_file, metadata_file.filename,
            _settings.UPLOAD_FOLDER)
        metadata_file.save(os.path.join(_settings.UPLOAD_FOLDER, metadata_filename))
    _queue.append({
        'type': 'upload',
        'key': uuid.uuid4().hex,
        'filename': filename,
        'tags': tags,
        'original_filename': uploaded_file.filename,
        'metadata_filename': metadata_filename if metadata_file else None,
        'uploaded_at': datetime.now(),
        'target_date': target_date,
        'step': 'upload_and_store',  # First thing to do to the pics,
        'data': {},  # Store additional parameters,
        'attempt': 0,  # Records how many times this step has been attempted
        'skip': skip,
        'batch_id': batch_id,
        'is_last': bool(is_last)
    })
    return filename


def valid_secret():
    secret = request.headers.get('X-PHOTOLOG-SECRET', '')
    return secret == md5(settings.API_SECRET.encode('utf-8')).hexdigest()


@app.route('/photos/', methods=['GET'])
@csrf.exempt
def get_photo():
    return jsonify({
        'last': list(queue.peek())
    }), 200


@app.route('/photos/batch/', methods=['POST'])
@csrf.exempt
def new_batch():
    if not valid_secret():
        return jsonify({
            'error': 'Invalid request'
        }), 400
    batch_id = start_batch(settings)
    return jsonify({
        'batch_id': batch_id
    })


@app.route('/photos/batch/<string:batch_id>/', methods=['DELETE'])
@csrf.exempt
def finish_batch(batch_id):
    if not valid_secret():
        return jsonify({
            'error': 'Invalid request'
        }), 400
    end_batch(batch_id, settings)
    return '', 204


@app.route('/photos/verify/', methods=['GET'])
@csrf.exempt
def verify_photo():
    if not valid_secret():
        return jsonify({
            'error': 'Invalid request'
        }), 400

    filename = request.args.get('filename', '')
    checksum = request.args.get('checksum', '')
    exists = db.file_exists(filename, checksum)
    return '', 204 if exists else 404


@app.route('/photos/', methods=['POST'])
@csrf.exempt
def add_photo():
    uploaded_file = request.files.get('photo_file')
    metadata_file = request.files.get('metadata_file', None)
    if not uploaded_file:
        return jsonify({
            'error': 'Must send an `photo_file`'
        }), 400

    if not allowed_file(uploaded_file.filename, uploaded_file):
        return jsonify({
            'error': 'Invalid file type or extension'
        }), 400

    if not valid_secret():
        return jsonify({
            'error': 'Invalid request'
        }), 400

    batch_id = request.form.get('batch_id', '')
    is_last = request.form.get('is_last', False)
    tags = request.form.get('tags', '')
    tags = [t for t in (slugify(t) for t in tags.split(',')) if t.strip()]
    skip = request.form.get('skip', '')
    skip = [t for t in (slugify(t) for t in skip.split(',')) if t.strip()]
    target_date = request.form.get('target_date')
    filename = queue_file(settings, queue, uploaded_file, metadata_file,
        tags, skip, batch_id, is_last, target_date)
    log.info('Queued file: %s' % filename)
    return '', 202


def start():
    log.info('Starting API server')
    app.run(debug=settings.DEBUG)

