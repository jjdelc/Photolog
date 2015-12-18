import os
import yaml


class Setting(object):
    PROJECT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '../..'))
    DEBUG = True
    DB_FILE = os.path.join(PROJECT_DIR, 'photos.db')
    UPLOAD_FOLDER = os.path.join(PROJECT_DIR, 'media')
    THUMBS_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
    MAX_QUEUE_ATTEMPTS = 3

    @classmethod
    def load(cls, settings_file):
        settings = yaml.load(open(settings_file).read())
        return cls(**settings)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
