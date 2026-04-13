import os
from unittest.mock import patch, MagicMock

import pytest
import requests

from photolog.tools.uploader import (
    chunks,
    read_filelist,
    validate_file,
    find_metadata_file,
    verify_exists,
    handle_file,
    upload_directories,
)


# --- chunks ---


def test_chunks_even():
    result = list(chunks([1, 2, 3, 4], 2))
    assert result == [[1, 2], [3, 4]]


def test_chunks_uneven():
    result = list(chunks([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]


def test_chunks_larger_than_list():
    result = list(chunks([1, 2], 10))
    assert result == [[1, 2]]


def test_chunks_empty():
    result = list(chunks([], 5))
    assert result == []


# --- read_filelist ---


def test_read_filelist_none():
    assert read_filelist(None) == []


def test_read_filelist_reads_existing_files(tmp_path):
    real_file = tmp_path / "photo.jpg"
    real_file.write_bytes(b"x" * 2048)
    missing = tmp_path / "missing.jpg"

    filelist = tmp_path / "files.txt"
    filelist.write_text("%s\n%s\n" % (real_file, missing))

    result = read_filelist(str(filelist))
    assert result == [str(real_file)]


def test_read_filelist_empty_file(tmp_path):
    filelist = tmp_path / "empty.txt"
    filelist.write_text("")
    assert read_filelist(str(filelist)) == []


# --- validate_file ---


def test_validate_file_too_small(tmp_path):
    f = tmp_path / "tiny.jpg"
    f.write_bytes(b"x" * 100)
    with pytest.raises(OSError):
        validate_file(str(f))


def test_validate_file_ok(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)
    validate_file(str(f))  # should not raise


# --- find_metadata_file ---


def test_find_metadata_file_not_video(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x")
    assert find_metadata_file(str(f)) is False


def test_find_metadata_file_found(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    thm = tmp_path / "clip.THM"
    thm.write_bytes(b"x")

    result = find_metadata_file(str(video))
    assert result == str(thm)


def test_find_metadata_file_numbered_suffix(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    thm = tmp_path / "clip_1.THM"
    thm.write_bytes(b"x")

    result = find_metadata_file(str(video))
    assert result == str(thm)


def test_find_metadata_file_missing_raises(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    # No .THM file present
    with pytest.raises(AssertionError):
        find_metadata_file(str(video))


# --- verify_exists ---


def test_verify_exists_true(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("photolog.tools.uploader.requests.get", return_value=mock_response) as mock_get:
        result = verify_exists("http://localhost/", str(f), "secret")

    assert result is True
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["filename"] == "photo.jpg"


def test_verify_exists_false(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("photolog.tools.uploader.requests.get", return_value=mock_response):
        result = verify_exists("http://localhost/", str(f), "secret")

    assert result is False


# --- handle_file ---


def test_handle_file_already_uploaded(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    with patch("photolog.tools.uploader.verify_exists", return_value=True):
        result = handle_file("http://localhost/", str(f), "secret", "", "", False, None)

    assert result is False


def test_handle_file_upload_success(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    mock_response = MagicMock()
    mock_response.status_code = 201

    with (
        patch("photolog.tools.uploader.verify_exists", return_value=False),
        patch("photolog.tools.uploader.find_metadata_file", return_value=False),
        patch("photolog.tools.uploader.requests.post", return_value=mock_response),
    ):
        result = handle_file("http://localhost/", str(f), "secret", "", "", False, None)

    assert result is True


def test_handle_file_invalid_file_skipped(tmp_path):
    f = tmp_path / "tiny.jpg"
    f.write_bytes(b"x" * 10)

    result = handle_file("http://localhost/", str(f), "secret", "", "", False, None)
    assert result is False


def test_handle_file_connection_error_raises(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    with (
        patch(
            "photolog.tools.uploader.verify_exists",
            side_effect=requests.ConnectionError,
        ),
        pytest.raises(requests.ConnectionError),
    ):
        handle_file("http://localhost/", str(f), "secret", "", "", False, None)


def test_handle_file_with_target_date(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    mock_response = MagicMock()
    mock_response.status_code = 201

    with (
        patch("photolog.tools.uploader.verify_exists", return_value=False),
        patch("photolog.tools.uploader.requests.post", return_value=mock_response) as mock_post,
    ):
        result = handle_file("http://localhost/", str(f), "secret", "", "", False, "2024-01-01")

    assert result is True
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["target_date"] == "2024-01-01"


# --- upload_directories ---


def test_upload_directories_filters_allowed_files(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x" * 2048)
    (tmp_path / "document.txt").write_bytes(b"x" * 2048)

    uploaded = []

    def fake_handle(host, full_file, secret, tags, skip, halt, target_date):
        uploaded.append(full_file)
        return True

    with patch("photolog.tools.uploader.handle_file", side_effect=fake_handle):
        upload_directories(
            [str(tmp_path)],
            [],
            "http://localhost/",
            "secret",
            "",
            "",
            False,
            None,
        )

    assert len(uploaded) == 1
    assert uploaded[0].endswith("photo.jpg")


def test_upload_directories_images_before_raws(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x" * 2048)
    (tmp_path / "raw.arw").write_bytes(b"x" * 2048)

    order = []

    def fake_handle(host, full_file, *args, **kwargs):
        order.append(os.path.basename(full_file))
        return True

    with patch("photolog.tools.uploader.handle_file", side_effect=fake_handle):
        upload_directories(
            [str(tmp_path)],
            [],
            "http://localhost/",
            "secret",
            "",
            "",
            False,
            None,
        )

    assert order.index("photo.jpg") < order.index("raw.arw")


def test_upload_directories_single_file(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 2048)

    uploaded = []

    def fake_handle(host, full_file, *args, **kwargs):
        uploaded.append(full_file)
        return True

    with patch("photolog.tools.uploader.handle_file", side_effect=fake_handle):
        upload_directories([str(f)], [], "http://localhost/", "secret", "", "", False, None)

    assert len(uploaded) == 1


def test_upload_directories_filelist(tmp_path):
    f = tmp_path / "listed.jpg"
    f.write_bytes(b"x" * 2048)

    uploaded = []

    def fake_handle(host, full_file, *args, **kwargs):
        uploaded.append(full_file)
        return True

    with patch("photolog.tools.uploader.handle_file", side_effect=fake_handle):
        upload_directories([], [str(f)], "http://localhost/", "secret", "", "", False, None)

    assert len(uploaded) == 1
