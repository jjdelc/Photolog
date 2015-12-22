import os
import re
import uuid
import binascii
import unicodedata
from datetime import datetime

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from photolog.squeue import SqliteQueue
from photolog.settings import Settings
from photolog.services.base import random_string
from photolog import api_logger as log, settings_file

ALLOWED_FILES = {'jpg', 'jpeg', 'png', 'gif', 'raw'}
settings = Settings.load(settings_file)
queue = SqliteQueue(settings.DB_FILE)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB


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


def slugify(text):
    """
    Slugify inspired in Django's slugify
    """
    text = unicodedata.normalize('NFKD', text)
    text = re.sub('[^\w\s-]', '', text).strip().lower()
    text = re.sub('[-\s]+', '-', text)
    return text


def filename_for_file(uploaded_file, filename, path):
    _crc = crc(uploaded_file)
    return unique_filename(secure_filename(filename), _crc, path)


def _add_photo(_settings, _queue, uploaded_file, base_filename, tags, skip):
    filename = filename_for_file(uploaded_file, base_filename,
                                 _settings.UPLOAD_FOLDER)

    uploaded_file.save(os.path.join(_settings.UPLOAD_FOLDER, filename))
    _queue.append({
        'key': uuid.uuid4().hex,
        'filename': filename,
        'tags': tags,
        'original_filename': uploaded_file.filename,
        'uploaded_at': datetime.now(),
        'step': 'upload_and_store',  # First thing to do to the pics,
        'data': {},  # Store additional parameters,
        'attempt': 0,  # Records how many times this step has been attempted
        'skip': skip,
    })
    return filename


@app.route('/photos/', methods=['GET'])
def get_photo():
    return jsonify({
        'last': queue.peek()
    }), 200


@app.route('/photos/', methods=['POST'])
def add_photo():
    uploaded_file = request.files.get('photo_file')
    if not uploaded_file:
        return jsonify({
            'error': 'Must send an `photo_file`'
        }), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({
            'error': 'Invalid file extension'
        }), 400

    tags = request.form.get('tags', '')
    tags = {slugify(t) for t in tags.split(',')}
    skip = request.form.get('skip', '')
    skip = {slugify(t) for t in skip.split(',')}
    tags = [t for t in tags if t]  # Strip empty
    filename = _add_photo(settings, queue, uploaded_file,
                          uploaded_file.filename, tags, skip)
    log.info('Queued file: %s' % filename)
    return '', 201


def start():
    log.info('Starting API server')
    app.run(debug=settings.DEBUG)

