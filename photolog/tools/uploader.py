import os
import yaml
import requests
import argparse
from time import time
from hashlib import md5
from urllib.parse import urljoin
from photolog import cli_logger as log, ALLOWED_FILES, IMAGE_FILES, RAW_FILES


def read_local_conf(conf_file=None):
    if not conf_file:
        home = os.path.expanduser('~')
        conf_file = os.path.join(home, '.photolog')
    log.info('Reading config file: %s' % conf_file)
    conf = yaml.load(open(conf_file))
    return conf


def upload_directory(directory, endpoint, secret, tags, skip):
    total_files = 0
    start = time()
    first_batch, second_batch = [], []
    for file in os.listdir(directory):
        name, ext = os.path.splitext(file)
        ext = ext.lstrip('.').lower()
        if ext not in ALLOWED_FILES:
            continue
        full_file = os.path.join(directory, file)
        if ext in IMAGE_FILES:
            first_batch.append((file, full_file))
        elif ext in RAW_FILES:
            second_batch.append((file, full_file))

    for file, full_file in first_batch + second_batch:
        requests.post(endpoint, data={
            'tags': tags,
            'skip': skip,
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
    parser.add_argument('--tags', metavar='T', nargs='?', type=str,
        help="Tags for this batch")
    parser.add_argument('--host', metavar='H', nargs='?', type=str,
        help="Host to upload")
    parser.add_argument('--skip', nargs='?', type=str,
        help="steps to skip")
    parsed = parser.parse_args()
    directory = os.path.realpath(parsed.directory)
    endpoint = urljoin(parsed.host or config['host'], '/photos/')
    secret = md5(config['secret'].encode('utf-8')).hexdigest()
    tags = parsed.tags or ''
    skip = parsed.skip or ''
    upload_directory(directory, endpoint, secret, tags, skip)


if __name__ == '__main__':
    run()
