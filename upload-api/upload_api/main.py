import os
import uuid
import random
import string
import binascii
from datetime import datetime

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from .squeue import SqliteQueue
from . import UPLOAD_FOLDER, DB_FILE, ALLOWED_FILES, api_logger as log

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB


queue = SqliteQueue(DB_FILE)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_FILES


def random_string():
    return ''.join([random.choice(string.ascii_letters) for _ in range(6)])


def unique_filename(filename, salt, path):
    existing = {f.lower() for f in os.listdir(path)}
    # Season with hash initially anyway. This is to prevent file guesses
    # if the public URL leaks.
    name, ext = os.path.splitext(filename)
    _hash = random_string()
    final_filename = '%s-%s-%s%s' % (name, salt, _hash, ext)
    while final_filename.lower() in existing:
        _hash = random_string()
        final_filename = '%s-%s-%s%s' % (name, salt, _hash, ext)
    return final_filename


def crc(file):
    buf = file.read()
    file.seek(0)
    return '%08X' % (binascii.crc32(buf) & 0xFFFFFFFF)


def filename_for_file(uploaded_file, path):
    _crc = crc(uploaded_file)
    return unique_filename(secure_filename(uploaded_file.filename), _crc, path)


@app.route('/photos/', methods=['GET'])
def get_photos():
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
    tags = [t.strip().lower() for t in tags.split(',')]
    filename = filename_for_file(uploaded_file, app.config['UPLOAD_FOLDER'])

    uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    queue.append({
        'key': uuid.uuid4(),
        'filename': filename,
        'tags': tags,
        'uploaded_at': datetime.now(),
        'step': 'read_exif',  # read_exif is the first thing to do to the pics,
        'data': {},  # Store additional parameters,
        'attempt': 0,  # Records how many times this step has been attempted
    })
    log.info('Queued file: %s' % filename)
    return '', 201


def start():
    log.info('Starting API server')
    app.run(debug=True)


if __name__ == "__main__":
    start()

