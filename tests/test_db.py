from tests.conftest import make_db


def test_get_tags():
    db = make_db('test_get_tags.db')
    db.tags.add('tag1')
    db.tags.add('tag2')
    assert db.tags.all() == ['tag1', 'tag2']


def test_add_picture():
    db = make_db('test_add_picture.db')
    db.add_picture({'original': 'original.jpg'}, ['phone', 'travel'])
    db.add_picture({'original': 'original2.jpg'}, ['phone', 'not travel'])

    travel = db.tagged('travel')
    assert len(travel) == 1
    assert travel[0]['original'] == 'original.jpg'

    phone = db.tagged('phone')
    assert len(phone) == 2
    assert {p['original'] for p in phone} == {'original.jpg', 'original2.jpg'}


def test_update_picture():
    db = make_db('test_update_picture.db')
    key = 'test_update_picture'
    attr = 'flickr'
    value = 'http://flickr/url'
    db.add_picture({'key': key, 'original': 'original.jpg'}, [])
    db.pictures.update(key, attr, value)
    pic = db.pictures.by_key(key)
    assert pic[attr] == value


def test_find_picture():
    db = make_db('test_find_picture.db')
    db.add_picture({'original': 'original.jpg', 'name': 'name', 'year': 2015, 'month': 12, 'day': 25}, ['phone', 'travel'])
    db.add_picture({'original': 'not original.jpg', 'name': 'not name', 'year': 2015, 'month': 12, 'day': 25}, ['phone', 'travel'])
    db.add_picture({'original': 'other original.jpg', 'name': 'name', 'year': 2012, 'month': 12, 'day': 25}, ['phone', 'travel'])

    found = db.pictures.find_one({'name': 'name', 'year': 2015})
    assert found['original'] == 'original.jpg'

    found = db.pictures.find_one({'name': 'name', 'year': 2012})
    assert found['original'] == 'other original.jpg'

    found = db.pictures.find_one({'name': 'name', 'year': 2020})
    assert found is None


def test_file_exists():
    db = make_db('test_file_exists.db')
    db.add_picture({'original': 'original.jpg', 'checksum': 'checksum', 'name': 'name'}, ['phone', 'travel'])
    assert db.file_exists('name', 'checksum')
    assert not db.file_exists('name', 'not checksum')


def test_by_keys():
    db = make_db('test_by_keys.db')
    db.add_picture({'key': '1', 'name': 'one'}, [])
    db.add_picture({'key': '2', 'name': 'two'}, [])
    db.add_picture({'key': '3', 'name': 'three'}, [])
    assert {p['name'] for p in db.pictures.by_keys(['1', '2'])} == {'one', 'two'}
