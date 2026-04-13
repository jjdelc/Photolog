import os
from time import time

from photolog.db import TokensDB
from tests.conftest import make_db, TEST_FILES


def make_tokens_db(name):
    return TokensDB(os.path.join(TEST_FILES, name))


def test_get_tags():
    db = make_db("test_get_tags.db")
    db.tags.add("tag1")
    db.tags.add("tag2")
    assert db.tags.all() == ["tag1", "tag2"]


def test_add_picture():
    db = make_db("test_add_picture.db")
    db.add_picture({"original": "original.jpg"}, ["phone", "travel"])
    db.add_picture({"original": "original2.jpg"}, ["phone", "not travel"])

    travel = db.tagged("travel")
    assert len(travel) == 1
    assert travel[0]["original"] == "original.jpg"

    phone = db.tagged("phone")
    assert len(phone) == 2
    assert {p["original"] for p in phone} == {"original.jpg", "original2.jpg"}


def test_update_picture():
    db = make_db("test_update_picture.db")
    key = "test_update_picture"
    attr = "flickr"
    value = "http://flickr/url"
    db.add_picture({"key": key, "original": "original.jpg"}, [])
    db.pictures.update(key, attr, value)
    pic = db.pictures.by_key(key)
    assert pic[attr] == value


def test_find_picture():
    db = make_db("test_find_picture.db")
    db.add_picture(
        {
            "original": "original.jpg",
            "name": "name",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "not original.jpg",
            "name": "not name",
            "year": 2015,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )
    db.add_picture(
        {
            "original": "other original.jpg",
            "name": "name",
            "year": 2012,
            "month": 12,
            "day": 25,
        },
        ["phone", "travel"],
    )

    found = db.pictures.find_one({"name": "name", "year": 2015})
    assert found["original"] == "original.jpg"

    found = db.pictures.find_one({"name": "name", "year": 2012})
    assert found["original"] == "other original.jpg"

    found = db.pictures.find_one({"name": "name", "year": 2020})
    assert found is None


def test_file_exists():
    db = make_db("test_file_exists.db")
    db.add_picture(
        {"original": "original.jpg", "checksum": "checksum", "name": "name"},
        ["phone", "travel"],
    )
    assert db.file_exists("name", "checksum")
    assert not db.file_exists("name", "not checksum")


def test_by_keys():
    db = make_db("test_by_keys.db")
    db.add_picture({"key": "1", "name": "one"}, [])
    db.add_picture({"key": "2", "name": "two"}, [])
    db.add_picture({"key": "3", "name": "three"}, [])
    assert {p["name"] for p in db.pictures.by_keys(["1", "2"])} == {
        "one",
        "two",
    }


# TagManager additional coverage


def test_tag_manager_for_picture():
    db = make_db("test_for_picture.db")
    db.add_picture({"key": "p1", "name": "a.jpg"}, ["beach", "summer"])
    p1 = db.pictures.by_key("p1")
    tags = db.tags.for_picture(p1["id"])
    assert set(tags) == {"beach", "summer"}


def test_tag_manager_for_picture_no_tags():
    db = make_db("test_for_picture_none.db")
    db.add_picture({"key": "p1", "name": "a.jpg"}, [])
    p1 = db.pictures.by_key("p1")
    assert db.tags.for_picture(p1["id"]) == []


def test_tag_manager_total_for_tags_single():
    db = make_db("test_total_for_tags.db")
    db.add_picture({"key": "p1", "name": "a.jpg"}, ["nature"])
    db.add_picture({"key": "p2", "name": "b.jpg"}, ["nature"])
    db.add_picture({"key": "p3", "name": "c.jpg"}, ["city"])
    assert db.tags.total_for_tags(["nature"]) == 2


def test_tag_manager_tagged_pictures_single_tag():
    db = make_db("test_tagged_pictures.db")
    db.add_picture({"key": "p1", "name": "a.jpg", "taken_time": 100}, ["food"])
    db.add_picture({"key": "p2", "name": "b.jpg", "taken_time": 200}, ["food"])
    db.add_picture({"key": "p3", "name": "c.jpg", "taken_time": 300}, ["other"])
    results = list(db.tags.tagged_pictures(["food"], limit=10, offset=0))
    assert {r["key"] for r in results} == {"p1", "p2"}


# PictureManager additional coverage


def test_picture_manager_recent():
    db = make_db("test_recent.db")
    for i in range(5):
        db.add_picture({"key": str(i), "name": f"pic{i}.jpg"}, [])
    recent = list(db.pictures.recent(limit=3, offset=0))
    assert len(recent) == 3
    # recent returns newest by id DESC
    assert recent[0]["key"] == "4"


def test_picture_manager_get_all():
    db = make_db("test_get_all.db")
    db.add_picture({"key": "a", "name": "a.jpg", "taken_time": 1}, [])
    db.add_picture({"key": "b", "name": "b.jpg", "taken_time": 2}, [])
    db.add_picture({"key": "c", "name": "c.jpg", "taken_time": 3}, [])
    all_pics = list(db.pictures.get_all(limit=2, offset=0))
    assert len(all_pics) == 2
    assert all_pics[0]["key"] == "c"  # ORDER BY taken_time DESC


def test_picture_manager_count():
    db = make_db("test_count.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2020, "month": 6}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020, "month": 6}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2021, "month": 1}, [])
    assert db.pictures.count({"year": 2020}) == 2
    assert db.pictures.count({"year": 2021}) == 1
    assert db.pictures.count({"year": 2020, "month": 6}) == 2


def test_picture_manager_nav():
    db = make_db("test_nav.db")
    db.add_picture({"key": "early", "name": "a.jpg", "taken_time": 100}, [])
    db.add_picture({"key": "middle", "name": "b.jpg", "taken_time": 200}, [])
    db.add_picture({"key": "late", "name": "c.jpg", "taken_time": 300}, [])
    prev_key, next_key = db.pictures.nav(200)
    assert prev_key == "early"
    assert next_key == "late"


def test_picture_manager_nav_at_edges():
    db = make_db("test_nav_edges.db")
    db.add_picture({"key": "first", "name": "a.jpg", "taken_time": 100}, [])
    db.add_picture({"key": "last", "name": "b.jpg", "taken_time": 200}, [])
    prev_key, next_key = db.pictures.nav(100)
    assert prev_key is None
    assert next_key == "last"


def test_picture_manager_change_date():
    db = make_db("test_change_date.db")
    db.add_picture({"key": "p1", "name": "a.jpg", "year": 2020, "month": 6, "day": 15}, [])
    db.pictures.change_date(
        "p1",
        {
            "year": 2021,
            "month": 1,
            "day": 1,
            "taken_time": 1000000,
            "date_taken": "2021-01-01",
        },
    )
    pic = db.pictures.by_key("p1")
    assert pic["year"] == 2021
    assert pic["month"] == 1
    assert pic["day"] == 1
    assert pic["date_taken"] == "2021-01-01"


def test_picture_manager_edit_attribute():
    db = make_db("test_edit_attr.db")
    db.add_picture({"key": "p1", "name": "a.jpg", "notes": "old note"}, [])
    db.pictures.edit_attribute("p1", "notes", "new note")
    pic = db.pictures.by_key("p1")
    assert pic["notes"] == "new note"


# DB top-level additional coverage


def test_db_total_pictures():
    db = make_db("test_total_pictures.db")
    assert db.total_pictures() == 0
    db.add_picture({"key": "1", "name": "a.jpg"}, [])
    db.add_picture({"key": "2", "name": "b.jpg"}, [])
    assert db.total_pictures() == 2


def test_db_get_years():
    db = make_db("test_get_years.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2019}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2020}, [])
    years = db.get_years()
    assert years == [2020, 2019]  # ORDER BY year DESC


def test_db_get_months():
    db = make_db("test_get_months.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2020, "month": 3}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020, "month": 7}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2021, "month": 1}, [])
    assert set(db.get_months(2020)) == {3, 7}
    assert db.get_months(2021) == [1]


def test_db_get_days():
    db = make_db("test_get_days.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2020, "month": 6, "day": 10}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020, "month": 6, "day": 20}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2020, "month": 7, "day": 1}, [])
    assert set(db.get_days(2020, 6)) == {10, 20}
    assert db.get_days(2020, 7) == [1]


def test_db_get_pictures_for_year():
    db = make_db("test_pics_for_year.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2020, "taken_time": 100}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020, "taken_time": 200}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2021, "taken_time": 300}, [])
    results = list(db.get_pictures_for_year(2020, limit=10, offset=0))
    assert {r["key"] for r in results} == {"1", "2"}


def test_db_total_for_year():
    db = make_db("test_total_for_year.db")
    db.add_picture({"key": "1", "name": "a.jpg", "year": 2020}, [])
    db.add_picture({"key": "2", "name": "b.jpg", "year": 2020}, [])
    db.add_picture({"key": "3", "name": "c.jpg", "year": 2021}, [])
    assert db.total_for_year(2020) == 2
    assert db.total_for_year(2021) == 1
    assert db.total_for_year(1900) == 0


# TokensDB coverage


def test_tokens_db_save_and_get():
    tdb = make_tokens_db("test_tokens_save.db")
    tdb.save_token("gphotos", "access_abc", "Bearer", "refresh_xyz", int(time()) + 3600)
    token = tdb.get_token("gphotos")
    assert token is not None
    assert token["service"] == "gphotos"
    assert token["access_token"] == "access_abc"
    assert token["refresh_token"] == "refresh_xyz"
    assert token["token_type"] == "Bearer"


def test_tokens_db_get_missing_returns_none():
    tdb = make_tokens_db("test_tokens_missing.db")
    assert tdb.get_token("nonexistent") is None


def test_tokens_db_update_token():
    tdb = make_tokens_db("test_tokens_update.db")
    future = int(time()) + 3600
    tdb.save_token("flickr", "old_token", "Bearer", "refresh", future)
    tdb.update_token("flickr", "new_token", "Bearer", future + 1000)
    token = tdb.get_token("flickr")
    assert token["access_token"] == "new_token"


def test_tokens_db_needs_refresh_expired():
    tdb = make_tokens_db("test_tokens_expired.db")
    tdb.save_token("s3", "tok", "Bearer", "ref", 0)  # expires in the past
    assert tdb.needs_refresh("s3", "tok") is True


def test_tokens_db_needs_refresh_fresh():
    tdb = make_tokens_db("test_tokens_fresh.db")
    far_future = int(time()) + 999999
    tdb.save_token("s3", "tok", "Bearer", "ref", far_future)
    assert tdb.needs_refresh("s3", "tok") is False
