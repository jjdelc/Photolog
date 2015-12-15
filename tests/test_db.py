# coding: utf-8

import os, shutil
from upload_api.db import DB
from unittest import TestCase
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
