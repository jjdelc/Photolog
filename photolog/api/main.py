import os
import sys
import uuid
import binascii
from hashlib import md5
from datetime import datetime

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from photolog.db import DB
from photolog.squeue import SqliteQueue
from photolog.settings import Settings
from photolog import api_logger as log, settings_file, ALLOWED_FILES
from photolog.services.base import random_string, start_batch, end_batch, \
    slugify

if not settings_file:
    print("Provide a SETTINGS env variable pointing to the settings.yaml file")
    sys.exit(1)

settings = Settings.load(settings_file)
queue = SqliteQueue(settings.DB_FILE)
db = DB(settings.DB_FILE)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB  # Raw files


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_FILES


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


def invalid_secret():
    secret = request.headers.get('X-PHOTOLOG-SECRET', '')
    return secret != md5(settings.API_SECRET.encode('utf-8')).hexdigest()


def require_secret(view_fun):
    def __inner(*args, **kwargs):
        if invalid_secret():
            return jsonify({'error': 'Invalid request'}), 400
        return view_fun(*args, **kwargs)

    return __inner


@require_secret
@app.route('/photos/', methods=['GET'])
def get_photo():
    return jsonify({
        'last': list(queue.peek())
    }), 200


@require_secret
@app.route('/photos/batch/', methods=['POST'])
def new_batch():
    batch_id = start_batch(settings)
    return jsonify({
        'batch_id': batch_id
    })


@require_secret
@app.route('/photos/batch/<string:batch_id>/', methods=['DELETE'])
def finish_batch(batch_id):
    end_batch(batch_id, settings)
    return '', 204


@require_secret
@app.route('/photos/verify/', methods=['GET'])
def verify_photo():
    filename = request.args.get('filename', '')
    checksum = request.args.get('checksum', '')
    exists = db.file_exists(filename, checksum)
    return '', 204 if exists else 404


@require_secret
@app.route('/photos/', methods=['POST'])
def add_photo():
    uploaded_file = request.files.get('photo_file')
    metadata_file = request.files.get('metadata_file', None)
    if not uploaded_file:
        return jsonify({
            'error': 'Must send an `photo_file`'
        }), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({
            'error': 'Invalid file extension'
        }), 400

    batch_id = request.form.get('batch_id', '')
    is_last = request.form.get('is_last', False)
    tags = request.form.get('tags', '')
    tags = {slugify(t) for t in tags.split(',')}
    skip = request.form.get('skip', '')
    skip = {slugify(t) for t in skip.split(',')}
    tags = [t for t in tags if t]  # Strip empty
    target_date = request.form.get('target_date')
    filename = queue_file(settings, queue, uploaded_file, metadata_file,
        tags, skip, batch_id, is_last, target_date)
    log.info('Queued file: %s' % filename)
    return '', 202


def start():
    log.info('Starting API server')
    app.run(debug=settings.DEBUG)

