import os
import yaml
import requests
import argparse
from time import time
from hashlib import md5
from urllib.parse import urljoin
from photolog import cli_logger as log, ALLOWED_FILES


def read_local_conf(conf_file=None):
    if not conf_file:
        home = os.path.expanduser('~')
        conf_file = os.path.join(home, '.photolog')
    log.info('Reading config file: %s' % conf_file)
    conf = yaml.load(open(conf_file))
    return conf


def upload_directory(directory, endpoint, secret, tags):
    total_files = 0
    start = time()
    for file in os.listdir(directory):
        name, ext = os.path.splitext(file)
        ext = ext.lstrip('.')
        if ext.lower() not in ALLOWED_FILES:
            continue
        full_file = os.path.join(directory, file)
        requests.post(endpoint, data={
            'tags': tags,
            'secret': secret
        }, files={
            'photo_file': open(full_file, 'rb'),
        }, headers={
            'X-PHOTOLOG-SECRET': secret
        })
        log.info('Uploaded %s' % file)
        total_files += 1
    elapsed = time() - start
    log.info('Uploaded %s files in %.2fs' % (total_files, elapsed))


def run():
    config = read_local_conf()
    parser = argparse.ArgumentParser(
        description="Upload files or directories to Photolog"
    )
    parser.add_argument('directory', type=str, help="Directory to upload")
    parser.add_argument('--tags', metavar='T', nargs='?', type=str, help="Tags for this batch")
    parsed = parser.parse_args()
    directory = os.path.realpath(parsed.directory)
    endpoint = urljoin(config['host'], '/photos/')
    secret = md5(config['secret'].encode('utf-8')).hexdigest()
    tags = parsed.tags or ''
    upload_directory(directory, endpoint, secret, tags)


if __name__ == '__main__':
    run()
