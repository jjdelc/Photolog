from . import TestDbBase


class TestDB(TestDbBase):
    def test_get_tags(self):
        db = self.get_db('test_get_tags.db')
        db.tags.add('tag1')
        db.tags.add('tag2')
        self.assertEqual(db.tags.all(), ['tag1', 'tag2'])

    def test_add_picture(self):
        db = self.get_db('test_add_picture.db')
        db.add_picture({
            'original': 'original.jpg'
        }, ['phone', 'travel'])
        db.add_picture({
            'original': 'original2.jpg'
        }, ['phone', 'not travel'])

        travel = db.tagged('travel')
        self.assertEqual(len(travel), 1)
        self.assertEqual(travel[0]['original'], 'original.jpg')

        phone = db.tagged('phone')
        self.assertEqual(len(phone), 2)
        self.assertEqual({p['original'] for p in phone}, {
            'original.jpg', 'original2.jpg'
        })

    def test_update_picture(self):
        db = self.get_db('test_update_picture.db')
        key = 'test_update_picture'

        attr = 'flickr'
        value = 'http://flickr/url'
        db.add_picture({
            'key': key,
            'original': 'original.jpg'
        }, [])
        db.update_picture(key, attr, value)
        pic = db.get_picture(key)
        self.assertEqual(pic[attr], value)

    def test_find_picture(self):
        db = self.get_db('test_find_picture.db')
        db.add_picture({
            'original': 'original.jpg',
            'name': 'name',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])
        db.add_picture({
            'original': 'not original.jpg',
            'name': 'not name',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])
        db.add_picture({
            'original': 'other original.jpg',
            'name': 'name',
            'year': 2012,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])
        found = db.find_picture({
            'name': 'name',
            'year': 2015
        })
        self.assertEqual(found['original'], 'original.jpg')
        found = db.find_picture({
            'name': 'name',
            'year': 2012
        })
        self.assertEqual(found['original'], 'other original.jpg')
        found = db.find_picture({
            'name': 'name',
            'year': 2020  # Doesn't exist
        })
        self.assertIsNone(found)

    def test_file_exists(self):
        db = self.get_db('test_file_exists.db')
        db.add_picture({
            'original': 'original.jpg',
            'checksum': 'checksum',
            'name': 'name',
        }, ['phone', 'travel'])
        self.assertTrue(db.file_exists('name', 'checksum'))
        self.assertFalse(db.file_exists('name', 'not checksum'))

    def test_by_keys(self):
        db = self.get_db('test_by_keys.db')
        db.add_picture({
            'key': '1',
            'name': 'one',
        }, [])
        db.add_picture({
            'key': '2',
            'name': 'two',
        }, [])
        db.add_picture({
            'key': '3',
            'name': 'three',
        }, [])
        self.assertEqual({p['name'] for p in db.pictures.by_keys(['1', '2'])},
            {'one', 'two'})
