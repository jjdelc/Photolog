# coding: utf-8

import os
from unittest import TestCase

import shutil
from photolog.db import DB
from photolog.squeue import SqliteQueue

TESTS_DIR = os.path.dirname(__file__)

TEST_FILES = os.path.join(TESTS_DIR, 'files')


class TestDbBase(TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TEST_FILES)
        os.makedirs(TEST_FILES)

    def get_db(self, db_filename):
        db_file = os.path.join(TEST_FILES, db_filename)
        db = DB(db_file)
        return db


class QueueMixin:
    def get_queue(self, name):
        queue = SqliteQueue(os.path.join(TEST_FILES, name))
        return queue
