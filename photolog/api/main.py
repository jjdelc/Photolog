from flask import Flask, request, jsonify
from flask_wtf.csrf import CSRFProtect

from photolog.db import DB
from photolog.squeue import SqliteQueue
from photolog.settings import Settings
from photolog import api_logger as log, settings_file, ALLOWED_FILES
from photolog.services.base import start_batch, end_batch, slugify
from photolog.services.main import allowed_file, queue_file, valid_secret

settings = Settings.load(settings_file)
queue = SqliteQueue(settings.DB_FILE)
db = DB(settings.DB_FILE)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB  # Raw files

# Initialize CSRF protection; API routes exempt (they use X-PHOTOLOG-SECRET instead)
csrf = CSRFProtect()
csrf.init_app(app)


@app.route("/photos/", methods=["GET"])
@csrf.exempt
def get_photo():
    return jsonify({"last": list(queue.peek())}), 200


@app.route("/photos/batch/", methods=["POST"])
@csrf.exempt
def new_batch():
    secret = request.headers.get("X-PHOTOLOG-SECRET", "")
    if not valid_secret(secret, settings.API_SECRET):
        return jsonify({"error": "Invalid request"}), 400
    batch_id = start_batch(settings)
    return jsonify({"batch_id": batch_id})


@app.route("/photos/batch/<string:batch_id>/", methods=["DELETE"])
@csrf.exempt
def finish_batch(batch_id):
    secret = request.headers.get("X-PHOTOLOG-SECRET", "")
    if not valid_secret(secret, settings.API_SECRET):
        return jsonify({"error": "Invalid request"}), 400
    end_batch(batch_id, settings)
    return "", 204


@app.route("/photos/verify/", methods=["GET"])
@csrf.exempt
def verify_photo():
    secret = request.headers.get("X-PHOTOLOG-SECRET", "")
    if not valid_secret(secret, settings.API_SECRET):
        return jsonify({"error": "Invalid request"}), 400

    filename = request.args.get("filename", "")
    checksum = request.args.get("checksum", "")
    exists = db.file_exists(filename, checksum)
    return "", 204 if exists else 404


@app.route("/photos/", methods=["POST"])
@csrf.exempt
def add_photo():
    uploaded_file = request.files.get("photo_file")
    metadata_file = request.files.get("metadata_file", None)
    if not uploaded_file:
        return jsonify({"error": "Must send an `photo_file`"}), 400

    if not allowed_file(uploaded_file.filename, uploaded_file, ALLOWED_FILES):
        return jsonify({"error": "Invalid file type or extension"}), 400

    secret = request.headers.get("X-PHOTOLOG-SECRET", "")
    if not valid_secret(secret, settings.API_SECRET):
        return jsonify({"error": "Invalid request"}), 400

    batch_id = request.form.get("batch_id", "")
    is_last = request.form.get("is_last", False)
    tags = request.form.get("tags", "")
    tags = [t for t in (slugify(t) for t in tags.split(",")) if t.strip()]
    skip = request.form.get("skip", "")
    skip = [t for t in (slugify(t) for t in skip.split(",")) if t.strip()]
    target_date = request.form.get("target_date")
    filename = queue_file(
        settings,
        queue,
        uploaded_file,
        metadata_file,
        tags,
        skip,
        batch_id,
        is_last,
        target_date,
    )
    log.info("Queued file: %s" % filename)
    return "", 202


def start():
    log.info("Starting API server")
    app.run(debug=settings.DEBUG)
