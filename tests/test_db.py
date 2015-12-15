# coding: utf-8

import os
from upload_api.db import DB
from unittest import TestCase
from . import TEST_FILES


class TestDB(TestCase):
    def test_get_tags(self):
        db_file = os.path.join(TEST_FILES, 'test_get_tags.db')
        db = DB(db_file)
        db.add_tag('tag1')
        db.add_tag('tag2')
        self.assertEqual(db.get_tags(), {'tag1', 'tag2'})
