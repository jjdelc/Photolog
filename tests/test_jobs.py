from datetime import datetime

from photolog.queue.jobs import prepare_job
from tests.conftest import make_db


def test_tag_day():
    db = make_db("test_tag_day.db")
    db.add_picture(
        {
            "original": "file1.jpg",
            "name": "name",
            "key": "1",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "file2.jpg",
            "name": "name",
            "key": "2",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "file3.jpg",
            "name": "name",
            "key": "3",
            "year": 2015,
            "month": 12,
            "day": 31,
        },
        ["phone", "travel"],
    )

    job = prepare_job(
        {
            "type": "tag-day",
            "key": "xxxxx",
            "year": 2015,
            "month": 12,
            "day": 25,
            "tags": ["tagged"],
            "attempt": 0,
        },
        db,
        {},
    )
    job.process()

    assert {p["key"] for p in db.tags.pictures_for_tag("tagged")} == {"1", "2"}
    assert {p["key"] for p in db.tags.pictures_for_tag("travel")} == {"3"}


def test_mass_tag():
    db = make_db("test_mass_tag.db")
    db.add_picture(
        {
            "original": "file1.jpg",
            "name": "name",
            "key": "1",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "file2.jpg",
            "name": "name",
            "key": "2",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "file3.jpg",
            "name": "name",
            "key": "3",
            "year": 2015,
            "month": 12,
            "day": 31,
        },
        ["phone", "travel"],
    )

    job = prepare_job(
        {
            "type": "mass-tag",
            "key": "xxxxx",
            "tags": ["tagged"],
            "keys": ["1", "3"],
            "attempt": 0,
        },
        db,
        {},
    )
    job.process()

    assert {p["key"] for p in db.tags.pictures_for_tag("tagged")} == {"1", "3"}
    assert {p["key"] for p in db.tags.pictures_for_tag("travel")} == {"2"}


def test_edit_picture_dates():
    db = make_db("test_edit_dates.db")
    db.add_picture(
        {
            "original": "file1.jpg",
            "name": "name",
            "key": "1",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        [],
    )
    db.add_picture(
        {
            "original": "file1.jpg",
            "name": "name",
            "key": "2",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        [],
    )
    db.add_picture(
        {
            "original": "file1.jpg",
            "name": "name",
            "key": "3",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        [],
    )

    job = prepare_job(
        {
            "type": "edit-dates",
            "key": "xxxx",
            "changes": [
                ("1", datetime(1999, 12, 31)),
                ("2", datetime(1998, 1, 1)),
            ],
            "attempt": 0,
        },
        db,
        {},
    )
    job.process()

    pictures = {p["key"]: p for p in db.pictures.by_keys(["1", "2", "3"])}

    assert pictures["1"]["date_taken"] == "1999-12-31"
    assert pictures["1"]["year"] == 1999
    assert pictures["1"]["month"] == 12
    assert pictures["1"]["day"] == 31

    assert pictures["2"]["date_taken"] == "1998-01-01"
    assert pictures["2"]["year"] == 1998
    assert pictures["2"]["month"] == 1
    assert pictures["2"]["day"] == 1

    assert pictures["3"]["year"] == 2015
    assert pictures["3"]["month"] == 12
    assert pictures["3"]["day"] == 25
