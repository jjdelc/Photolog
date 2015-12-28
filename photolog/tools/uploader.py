import os
import yaml
import requests
import argparse
from time import time
from hashlib import md5
from urllib.parse import urljoin
from photolog import cli_logger as log, ALLOWED_FILES, IMAGE_FILES, RAW_FILES

BATCH_SIZE = 1999  # Max Gphotos album is 2000


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def read_local_conf(conf_file=None):
    if not conf_file:
        home = os.path.expanduser('~')
        conf_file = os.path.join(home, '.photolog')
    log.info('Reading config file: %s' % conf_file)
    conf = yaml.load(open(conf_file))
    return conf


def start_batch(endpoint, secret):
    batch_endpoint = urljoin(endpoint, 'batch/')
    response = requests.post(batch_endpoint, headers={
        'X-PHOTOLOG-SECRET': secret
    })
    batch_id = response.json()['batch_id']
    return batch_id


def upload_directories(targets, endpoint, secret, tags, skip):
    start = time()
    first_batch, second_batch = [], []
    for target in targets:
        if os.path.isdir(target):
            for file in os.listdir(target):
                name, ext = os.path.splitext(file)
                ext = ext.lstrip('.').lower()
                if ext not in ALLOWED_FILES:
                    continue
                full_file = os.path.join(target, file)
                if ext in IMAGE_FILES:
                    first_batch.append((file, full_file))
                elif ext in RAW_FILES:
                    second_batch.append((file, full_file))
        else:
            name, ext = os.path.splitext(target)
            ext = ext.lstrip('.').lower()
            full_file = os.path.abspath(target)
            if ext not in ALLOWED_FILES:
                continue
            if ext in IMAGE_FILES:
                first_batch.append((target, full_file))
            elif ext in RAW_FILES:
                second_batch.append((target, full_file))

    n = 1
    total_files = len(first_batch) + len(second_batch)
    log.info('Found %s files' % total_files)
    for batch in chunks(sorted(first_batch) + sorted(second_batch), BATCH_SIZE):
        #batch_id = start_batch(endpoint, secret)
        for file, full_file in batch:
            log.info('Uploading %s [%s/%s]' % (full_file, n, total_files))
            file_start = time()
            requests.post(endpoint, data={
                'tags': tags,
                'skip': skip,
                #'batch_id': batch_id,
                #'is_last': n == total_files
            }, files={
                'photo_file': open(full_file, 'rb'),
            }, headers={
                'X-PHOTOLOG-SECRET': secret
            })
            pct = 100 * n / total_files
            log.info("Done in %0.2fs [%0.1f%%]" % (time() - file_start, pct))
            n += 1
    elapsed = time() - start
    log.info('Uploaded %s files in %.2fs' % (total_files, elapsed))


def run():
    config = read_local_conf()
    parser = argparse.ArgumentParser(
        description="Upload files or directories to Photolog"
    )
    parser.add_argument('directories', type=str, nargs='+',
        help="Directory to upload")
    parser.add_argument('--tags', metavar='T', nargs='?', type=str,
        help="Tags for this batch")
    parser.add_argument('--host', metavar='H', nargs='?', type=str,
        help="Host to upload")
    parser.add_argument('--skip', nargs='?', type=str,
        help="steps to skip")
    parsed = parser.parse_args()
    directories = [os.path.realpath(d) for d in parsed.directories]
    endpoint = urljoin(parsed.host or config['host'], '/photos/')
    secret = md5(config['secret'].encode('utf-8')).hexdigest()
    tags = parsed.tags or ''
    skip = parsed.skip or ''
    upload_directories(directories, endpoint, secret, tags, skip)


if __name__ == '__main__':
    run()
