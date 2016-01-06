from datetime import datetime

from . import TestDbBase
from photolog.queue.jobs import prepare_job


class TestTagDay(TestDbBase):
    def test_process(self):
        db = self.get_db('test_process.db')
        db.add_picture({
            'original': 'file1.jpg',
            'name': 'name',
            'key': '1',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])
        db.add_picture({
            'original': 'file2.jpg',
            'name': 'name',
            'key': '2',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])

        db.add_picture({
            'original': 'file3.jpg',
            'name': 'name',
            'key': '3',
            'year': 2015,
            'month': 12,
            'day': 31
        }, ['phone', 'travel'])
        job = prepare_job({
            'type': 'tag-day',
            'key': 'xxxxx',
            'year': 2015,
            'month': 12,
            'day': 25,
            'tags': ['tagged'],
            'attempt': 0
        }, db, {})
        job.process()
        result = db.tags.pictures_for_tag('tagged')
        self.assertEqual({'1', '2'}, {p['key'] for p in result})
        result = db.tags.pictures_for_tag('travel')
        self.assertEqual({'3'}, {p['key'] for p in result})


class TestMassTag(TestDbBase):
    def test_process(self):
        db = self.get_db('test_process.db')
        db.add_picture({
            'original': 'file1.jpg',
            'name': 'name',
            'key': '1',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])
        db.add_picture({
            'original': 'file2.jpg',
            'name': 'name',
            'key': '2',
            'year': 2015,
            'month': 12,
            'day': 25
        }, ['phone', 'travel'])

        db.add_picture({
            'original': 'file3.jpg',
            'name': 'name',
            'key': '3',
            'year': 2015,
            'month': 12,
            'day': 31
        }, ['phone', 'travel'])
        job = prepare_job({
            'type': 'mass-tag',
            'key': 'xxxxx',
            'tags': ['tagged'],
            'keys': ['1', '3'],
            'attempt': 0
        }, db, {})
        job.process()

        result = db.tags.pictures_for_tag('tagged')
        self.assertEqual({'1', '3'}, {p['key'] for p in result})
        result = db.tags.pictures_for_tag('travel')
        self.assertEqual({'2'}, {p['key'] for p in result})


class TestEditPictureJob(TestDbBase):
    def test_process(self):
        db = self.get_db('test_process.db')
        db.add_picture({
            'original': 'file1.jpg',
            'name': 'name',
            'key': '1',
            'year': 2015,
            'month': 12,
            'day': 25
        }, [])
        db.add_picture({
            'original': 'file1.jpg',
            'name': 'name',
            'key': '2',
            'year': 2015,
            'month': 12,
            'day': 25
        }, [])
        db.add_picture({
            'original': 'file1.jpg',
            'name': 'name',
            'key': '3',
            'year': 2015,
            'month': 12,
            'day': 25
        }, [])
        job = prepare_job({
            'type': 'edit-dates',
            'key': 'xxxx',
            'changes': [
                ('1', datetime(1999, 12, 31)),
                ('2', datetime(1998, 1, 1))
            ],
            'attempt': 0
        }, db, {})
        job.process()

        pictures = {p['key']: p for p in db.pictures.by_keys(['1', '2', '3'])}
        self.assertEqual(pictures['1']['date_taken'], '1999-12-31')
        self.assertEqual(pictures['1']['year'], '1999')
        self.assertEqual(pictures['1']['month'], '12')
        self.assertEqual(pictures['1']['day'], '31')

        self.assertEqual(pictures['2']['date_taken'], '1998-01-01')
        self.assertEqual(pictures['2']['year'], '1998')
        self.assertEqual(pictures['2']['month'], '01')
        self.assertEqual(pictures['2']['day'], '01')

        self.assertEqual(pictures['3']['year'], '2015')
        self.assertEqual(pictures['3']['month'], '12')
        self.assertEqual(pictures['3']['day'], '25')
