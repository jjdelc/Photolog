# coding: utf-8

from unittest import TestCase

import os
import shutil
from photolog.db import DB
from . import TEST_FILES


class TestDB(TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TEST_FILES)
        os.makedirs(TEST_FILES)

    def test_get_tags(self):
        db_file = os.path.join(TEST_FILES, 'test_get_tags.db')
        db = DB(db_file)
        db.add_tag('tag1')
        db.add_tag('tag2')
        self.assertEqual(db.get_tags(), {'tag1', 'tag2'})

    def test_add_picture(self):
        db_file = os.path.join(TEST_FILES, 'test_add_picture.db')
        db = DB(db_file)
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
        db_file = os.path.join(TEST_FILES, 'test_update_picture.db')
        db = DB(db_file)
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
        db_file = os.path.join(TEST_FILES, 'test_find_picture.db')
        db = DB(db_file)
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
