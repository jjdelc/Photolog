"""
Integration tests for the job queue pipeline.

External services (S3, Flickr, GPhotos) are mocked; the real DB and queue are used.
"""

from datetime import datetime
from unittest.mock import patch

from photolog.queue.jobs import prepare_job
from tests.conftest import make_db, make_queue, TEST_FILES


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

FAKE_EXIF = {
    "year": 2020,
    "month": 6,
    "day": 15,
    "timestamp": None,
    "camera": "TestCam",
    "width": 800,
    "height": 600,
    "size": 204800,
    "mime": "video/mp4",
}

FAKE_THUMBS = {
    "original": "/tmp/fake-orig.jpg",
    "thumb": "/tmp/fake-thumb.jpg",
    "medium": "/tmp/fake-medium.jpg",
    "web": "/tmp/fake-web.jpg",
    "large": "/tmp/fake-large.jpg",
}

FAKE_S3_URLS = {
    "original": "https://s3.example.com/orig.jpg",
    "thumb": "https://s3.example.com/thumb.jpg",
    "medium": "https://s3.example.com/medium.jpg",
    "web": "https://s3.example.com/web.jpg",
    "large": "https://s3.example.com/large.jpg",
    "video": "https://s3.example.com/video.mp4",
}


class FakeSettings:
    UPLOAD_FOLDER = TEST_FILES
    THUMBS_FOLDER = TEST_FILES
    FLICKR_ENABLED = True
    GPHOTOS_ENABLED = True
    MAX_QUEUE_ATTEMPTS = 3


def _make_upload_job(key, filename, original_filename=None):
    return {
        "type": "upload",
        "key": key,
        "filename": filename,
        "original_filename": original_filename or filename,
        "metadata_filename": None,
        "uploaded_at": datetime(2020, 6, 15, 12, 0, 0),
        "target_date": None,
        "step": "upload_and_store",
        "data": {},
        "attempt": 0,
        "skip": [],
        "batch_id": "",
        "is_last": False,
        "tags": ["vacation"],
    }


def _run_to_completion(job_data, db, settings):
    """Drive a job through every step until process() returns None."""
    job = job_data
    while job:
        job = prepare_job(job, db, settings).process()


# ---------------------------------------------------------------------------
# ImageJob full pipeline
# ---------------------------------------------------------------------------


def test_image_job_full_pipeline():
    db = make_db("test_img_pipeline.db")
    settings = FakeSettings()
    job_data = _make_upload_job("imgkey001", "photo.jpg")

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch(
            "photolog.services.base.generate_thumbnails",
            return_value=FAKE_THUMBS,
        ),
        patch("photolog.services.s3.upload_thumbs", return_value=FAKE_S3_URLS),
        patch("photolog.services.base.file_checksum", return_value="deadbeef"),
        patch("photolog.services.base.delete_file"),
        patch(
            "photolog.services.flickr.upload",
            return_value=("https://flickr.com/photo/42", "42"),
        ),
        patch(
            "photolog.services.gphotos.upload_photo",
            return_value={"url": "https://photos.google.com/photo/1"},
        ),
    ):
        _run_to_completion(job_data, db, settings)

    pic = db.pictures.by_key("imgkey001")
    assert pic is not None
    assert pic["year"] == 2020
    assert pic["month"] == 6
    assert pic["format"] == "image"
    assert pic["checksum"] == "deadbeef"
    assert "vacation" in {t for t in db.tags.for_picture(pic["id"])}


def test_image_job_skips_flickr_when_disabled():
    db = make_db("test_img_no_flickr.db")
    settings = FakeSettings()
    settings.FLICKR_ENABLED = False
    job_data = _make_upload_job("imgkey002", "photo2.jpg")

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch(
            "photolog.services.base.generate_thumbnails",
            return_value=FAKE_THUMBS,
        ),
        patch("photolog.services.s3.upload_thumbs", return_value=FAKE_S3_URLS),
        patch("photolog.services.base.file_checksum", return_value="abc"),
        patch("photolog.services.base.delete_file"),
        patch("photolog.services.flickr.upload") as mock_flickr,
        patch("photolog.services.gphotos.upload_photo", return_value={}),
    ):
        _run_to_completion(job_data, db, settings)
        mock_flickr.assert_not_called()

    assert db.pictures.by_key("imgkey002") is not None


def test_image_job_skip_field_bypasses_step():
    db = make_db("test_img_skip.db")
    settings = FakeSettings()
    job_data = _make_upload_job("imgkey003", "photo3.jpg")
    job_data["skip"] = ["flickr", "gphotos"]

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch(
            "photolog.services.base.generate_thumbnails",
            return_value=FAKE_THUMBS,
        ),
        patch("photolog.services.s3.upload_thumbs", return_value=FAKE_S3_URLS),
        patch("photolog.services.base.file_checksum", return_value="abc"),
        patch("photolog.services.base.delete_file"),
        patch("photolog.services.flickr.upload") as mock_flickr,
        patch("photolog.services.gphotos.upload_photo") as mock_gphotos,
    ):
        _run_to_completion(job_data, db, settings)
        mock_flickr.assert_not_called()
        mock_gphotos.assert_not_called()

    assert db.pictures.by_key("imgkey003") is not None


# ---------------------------------------------------------------------------
# VideoJob full pipeline
# ---------------------------------------------------------------------------


def test_video_job_full_pipeline():
    db = make_db("test_video_pipeline.db")
    settings = FakeSettings()
    job_data = _make_upload_job("vidkey001", "clip.mp4")

    with (
        patch(
            "photolog.services.base.get_video_thumbnail",
            return_value=(FAKE_THUMBS, "/tmp/fake_caps/"),
        ),
        patch("photolog.services.base.video_exif", return_value=FAKE_EXIF),
        patch("photolog.services.s3.upload_thumbs", return_value=FAKE_S3_URLS),
        patch(
            "photolog.services.s3.upload_video",
            return_value="https://s3.example.com/clip.mp4",
        ),
        patch("photolog.services.base.file_checksum", return_value="vidcsum"),
        patch("photolog.services.base.delete_file"),
        patch("photolog.services.base.delete_dir"),
        patch(
            "photolog.services.gphotos.upload_video",
            return_value={"xml": "<feed/>"},
        ),
    ):
        _run_to_completion(job_data, db, settings)

    pic = db.pictures.by_key("vidkey001")
    assert pic is not None
    assert pic["format"] == "video"
    assert pic["year"] == 2020


# ---------------------------------------------------------------------------
# RawFileJob full pipeline
# ---------------------------------------------------------------------------


def test_raw_file_job_full_pipeline():
    db = make_db("test_raw_pipeline.db")
    settings = FakeSettings()
    job_data = _make_upload_job("rawkey001", "shot.arw")
    raw_s3_urls = {"original": "https://s3.example.com/shot.arw"}

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch("photolog.services.s3.upload_thumbs", return_value=raw_s3_urls),
        patch("photolog.services.base.file_checksum", return_value="rawcsum"),
        patch("photolog.services.base.delete_file"),
    ):
        _run_to_completion(job_data, db, settings)

    pic = db.pictures.by_key("rawkey001")
    assert pic is not None
    assert pic["format"] == "raw"
    assert pic["original"] == "https://s3.example.com/shot.arw"


def test_raw_file_job_copies_thumbs_from_sister_jpeg():
    db = make_db("test_raw_sister.db")
    settings = FakeSettings()
    # Add a sister JPEG in the DB
    db.add_picture(
        {
            "key": "sister",
            "name": "shot.jpg",
            "year": 2020,
            "month": 6,
            "day": 15,
            "thumb": "https://s3/sister-thumb.jpg",
            "web": "https://s3/sister-web.jpg",
            "large": "https://s3/sister-large.jpg",
            "medium": "https://s3/sister-medium.jpg",
        },
        [],
    )

    job_data = _make_upload_job("rawkey002", "shot.arw")
    raw_s3_urls = {"original": "https://s3.example.com/shot.arw"}

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch("photolog.services.s3.upload_thumbs", return_value=raw_s3_urls),
        patch("photolog.services.base.file_checksum", return_value="rawcsum2"),
        patch("photolog.services.base.delete_file"),
    ):
        _run_to_completion(job_data, db, settings)

    pic = db.pictures.by_key("rawkey002")
    assert pic["thumb"] == "https://s3/sister-thumb.jpg"
    assert pic["web"] == "https://s3/sister-web.jpg"


# ---------------------------------------------------------------------------
# ChangeDateJob — DB-only
# ---------------------------------------------------------------------------


def test_change_date_job_moves_all_pictures_on_day():
    db = make_db("test_change_date_job.db")
    db.add_picture({"key": "p1", "name": "a.jpg", "year": 2020, "month": 6, "day": 15}, [])
    db.add_picture({"key": "p2", "name": "b.jpg", "year": 2020, "month": 6, "day": 15}, [])
    db.add_picture({"key": "p3", "name": "c.jpg", "year": 2021, "month": 1, "day": 1}, [])

    job_data = {
        "type": "change-date",
        "key": "changejob1",
        "origin": datetime(2020, 6, 15),
        "target": datetime(2020, 7, 4),
        "attempt": 0,
    }
    prepare_job(job_data, db, {}).process()

    p1 = db.pictures.by_key("p1")
    p2 = db.pictures.by_key("p2")
    p3 = db.pictures.by_key("p3")
    assert p1["year"] == 2020 and p1["month"] == 7 and p1["day"] == 4
    assert p2["year"] == 2020 and p2["month"] == 7 and p2["day"] == 4
    assert p3["year"] == 2021 and p3["month"] == 1  # unchanged


def test_change_date_job_no_pictures_on_day():
    db = make_db("test_change_date_empty.db")
    db.add_picture({"key": "p1", "name": "a.jpg", "year": 2020, "month": 1, "day": 1}, [])

    job_data = {
        "type": "change-date",
        "key": "changejob2",
        "origin": datetime(2019, 12, 31),
        "target": datetime(2020, 1, 1),
        "attempt": 0,
    }
    prepare_job(job_data, db, {}).process()

    # p1 unaffected — it's on a different date
    p1 = db.pictures.by_key("p1")
    assert p1["year"] == 2020 and p1["month"] == 1 and p1["day"] == 1


# ---------------------------------------------------------------------------
# Retry / failure integration
# ---------------------------------------------------------------------------


def _simulate_daemon(queue, db, settings):
    """Process the queue exactly as the daemon does, without blocking."""
    while True:
        job = queue.popleft(sleep_wait=False)
        if job is None:
            break
        try:
            next_job = prepare_job(job, db, settings).process()
        except Exception:
            if job["attempt"] <= settings.MAX_QUEUE_ATTEMPTS:
                job["attempt"] += 1
                queue.append(job)
            else:
                queue.append_bad(job)
        else:
            if next_job:
                queue.append(next_job)


def test_failed_job_exceeds_max_attempts_goes_to_bad_jobs():
    db = make_db("test_retry_integ.db")
    queue = make_queue("test_retry_integ_q.db")
    settings = FakeSettings()
    settings.MAX_QUEUE_ATTEMPTS = 1  # allow one retry

    # This job will always fail: file doesn't exist → read_exif raises FileNotFoundError
    job_data = _make_upload_job("failkey", "nonexistent_file.jpg")
    queue.append(job_data)

    _simulate_daemon(queue, db, settings)

    assert len(queue) == 0
    assert queue.total_bad_jobs() == 1
    bad = queue.get_bad_jobs()[0]
    assert bad["key"] == "failkey"


def test_successful_job_does_not_land_in_bad_jobs():
    db = make_db("test_success_nobad.db")
    queue = make_queue("test_success_nobad_q.db")
    settings = FakeSettings()
    job_data = _make_upload_job("successkey", "photo_ok.jpg")
    queue.append(job_data)

    with (
        patch("photolog.services.base.read_exif", return_value=FAKE_EXIF),
        patch(
            "photolog.services.base.generate_thumbnails",
            return_value=FAKE_THUMBS,
        ),
        patch("photolog.services.s3.upload_thumbs", return_value=FAKE_S3_URLS),
        patch("photolog.services.base.file_checksum", return_value="ok"),
        patch("photolog.services.base.delete_file"),
        patch("photolog.services.flickr.upload", return_value=("url", "1")),
        patch("photolog.services.gphotos.upload_photo", return_value={}),
    ):
        _simulate_daemon(queue, db, settings)

    assert len(queue) == 0
    assert queue.total_bad_jobs() == 0
    assert db.pictures.by_key("successkey") is not None


def test_retry_jobs_requeues_bad_job_for_processing():
    db = make_db("test_retry_requeue.db")
    queue = make_queue("test_retry_requeue_q.db")
    settings = FakeSettings()
    settings.MAX_QUEUE_ATTEMPTS = 0  # fail immediately to bad_jobs

    job_data = _make_upload_job("requeue_key", "nonexistent2.jpg")
    queue.append(job_data)
    _simulate_daemon(queue, db, settings)

    assert queue.total_bad_jobs() == 1
    assert len(queue) == 0

    # Now retry and confirm job is back in queue
    queue.retry_jobs()
    assert queue.total_bad_jobs() == 0
    assert len(queue) == 1
    requeued = queue.popleft(sleep_wait=False)
    assert requeued["key"] == "requeue_key"
