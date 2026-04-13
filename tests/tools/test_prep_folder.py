import os
from unittest.mock import patch


def run_prep_folder(args, tmp_path):
    """Helper: call prep_folder.run() with patched sys.argv, return output file contents."""
    output_file = str(tmp_path / "commands.sh")
    with patch("sys.argv", ["prep_folder"] + args + ["--output", output_file]):
        from photolog.tools import prep_folder

        prep_folder.run()
    if os.path.exists(output_file):
        with open(output_file) as fh:
            return fh.read()
    return ""


# --- file filtering ---


def test_only_allowed_files_included(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    (tmp_path / "document.txt").write_bytes(b"x")
    (tmp_path / "script.py").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "photo.jpg" in output
    assert "document.txt" not in output
    assert "script.py" not in output


def test_raw_files_included(tmp_path):
    (tmp_path / "image.arw").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "image.arw" in output


def test_video_files_excluded(tmp_path):
    # prep_folder only handles IMAGE_FILES and RAW_FILES, not VIDEO_FILES
    (tmp_path / "clip.mp4").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "clip.mp4" not in output


# --- command structure ---


def test_command_contains_base_command(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "upload2photolog" in output


def test_command_contains_full_file_path(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert str(tmp_path / "photo.jpg") in output


def test_tags_appended_when_provided(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path), "--tags", "vacation"], tmp_path)

    assert "--tags 'vacation'" in output


def test_skip_appended_when_provided(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path), "--skip", "gphotos"], tmp_path)

    assert "--skip 'gphotos'" in output


def test_host_appended_when_provided(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path), "--host", "http://myserver/"], tmp_path)

    assert "--host http://myserver/" in output


def test_no_tags_flag_when_not_provided(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "--tags" not in output


def test_no_skip_flag_when_not_provided(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert "--skip" not in output


# --- ordering ---


def test_images_before_raws(tmp_path):
    (tmp_path / "b_photo.jpg").write_bytes(b"x")
    (tmp_path / "a_raw.arw").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    jpg_pos = output.index("b_photo.jpg")
    arw_pos = output.index("a_raw.arw")
    assert jpg_pos < arw_pos


def test_files_sorted_within_batch(tmp_path):
    (tmp_path / "c.jpg").write_bytes(b"x")
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    pos_a = output.index("/a.jpg")
    pos_b = output.index("/b.jpg")
    pos_c = output.index("/c.jpg")
    assert pos_a < pos_b < pos_c


# --- output file format ---


def test_commands_joined_with_and_backslash(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert " &&\\\n" in output


def test_single_file_no_separator(tmp_path):
    (tmp_path / "only.jpg").write_bytes(b"x")

    output = run_prep_folder([str(tmp_path)], tmp_path)

    assert " &&\\\n" not in output


def test_empty_directory_produces_empty_output(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    output = run_prep_folder([str(source)], tmp_path)

    assert output == ""


# --- multiple directories ---


def test_multiple_directories(tmp_path):
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "a.jpg").write_bytes(b"x")
    (dir_b / "b.jpg").write_bytes(b"x")

    output = run_prep_folder([str(dir_a), str(dir_b)], tmp_path)

    assert "a.jpg" in output
    assert "b.jpg" in output
