import os
import yaml
import requests
import argparse
from time import time
from hashlib import md5
from urllib.parse import urljoin
from photolog.services.base import file_checksum
from photolog import cli_logger as log, ALLOWED_FILES, IMAGE_FILES, RAW_FILES, VIDEO_FILES

BATCH_SIZE = 1999  # Max Gphotos album is 2000
UPLOAD_ATTEMPTS = 3


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


def verify_exists(host, full_filepath, secret):
    verification = urljoin(host, '/photos/verify/')
    checksum = file_checksum(full_filepath)
    filename = os.path.basename(full_filepath)
    response = requests.get(verification, params={
        'filename': filename,
        'checksum': checksum
    }, headers={
        'X-PHOTOLOG-SECRET': secret
    })
    return response.status_code == 204


def validate_file(filename):
    if os.stat(filename).st_size < 1024:  # Too small for a valid photo
        raise OSError('Invalid file')


def find_metadata_file(full_filename):
    """
    Looks for a .THM file on the same directory as the video file
    :param filename:
    :return:
    """
    filename = os.path.basename(full_filename)
    name, ext = os.path.splitext(filename)
    if ext.lstrip('.').lower() not in VIDEO_FILES:
        return False

    dirname = os.path.dirname(full_filename)
    metadata_extensions = ['.THM', '_1.THM', '_2.THM']
    dirlist = set(os.listdir(dirname))
    for suffix in metadata_extensions:
        target = '%s%s' % (name, suffix)
        if target in dirlist:
            log.info('Found metadata file %s for %s' % (target, filename))
            return os.path.join(dirname, target)
    assert False


def handle_file(host, full_file, secret, tags, skip, halt, target_date):
    """
    :param host: Host to upload data to
    :param full_file: Full file path in local machine
    :param secret: API secret
    :param tags: Tags to use for file
    :param skip: Steps for job to skip
    :param halt: If True, will wait for user input to resume after attempts
    :return: Returns if the file was uploaded or not
    """

    answer = 'Y'
    while answer == 'Y':
        attempt = 1
        while attempt < UPLOAD_ATTEMPTS:
            try:
                validate_file(full_file)
                file_exists = verify_exists(host, full_file, secret)
                endpoint = urljoin(host, '/photos/')
                if file_exists:
                    log.info('File %s already uploaded' % full_file)
                    return False
                else:
                    post_data = {
                        'tags': tags,
                        'skip': skip,
                        # 'batch_id': None,
                        # 'is_last': False,  # n == total_files
                    }
                    files = {
                        'photo_file': open(full_file, 'rb'),
                    }
                    if target_date:
                        post_data['target_date'] = target_date
                    else:
                        metadata_file = find_metadata_file(full_file)
                        if metadata_file:
                            files['metadata_file'] = open(metadata_file, 'rb')
                    response = requests.post(endpoint, data=post_data, files=files, headers={
                        'X-PHOTOLOG-SECRET': secret
                    })
                    return response.status_code == 201
            except requests.ConnectionError:
                attempt += 1
                log.warning("Attempt %s. Failed to connect. Retrying" % attempt)
            except OSError:
                log.warning("Invalid file: %s - Skipping" % full_file)
                return False

        if halt:
            answer = input("Problem connecting, Continue? [Y, n]") or 'Y'
        else:
            answer = 'n'
    raise requests.ConnectionError('Could not connect to %s' % host)


def upload_directories(targets, filelist, host, secret, tags, skip, halt, target_date):
    start = time()
    first_batch, second_batch, third_batch = [], [], []
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
                elif ext in VIDEO_FILES:
                    third_batch.append((file, full_file))
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
            elif ext in VIDEO_FILES:
                third_batch.append((target, full_file))

    for target in filelist:
        name, ext = os.path.splitext(target)
        ext = ext.lstrip('.').lower()
        full_file = os.path.abspath(target)
        if ext not in ALLOWED_FILES:
            continue
        if ext in IMAGE_FILES:
            first_batch.append((target, full_file))
        elif ext in RAW_FILES:
            second_batch.append((target, full_file))
        elif ext in VIDEO_FILES:
            third_batch.append((target, full_file))

    n, skipped = 1, 0
    total_files = len(first_batch) + len(second_batch) + len(third_batch)
    log.info('Found %s files' % total_files)
    for batch in chunks(sorted(first_batch) + sorted(second_batch) + sorted(third_batch), BATCH_SIZE):
        #batch_id = start_batch(endpoint, secret)
        for file, full_file in batch:
            log.info('Uploading %s [%s/%s]' % (full_file, n, total_files))
            file_start = time()
            uploaded = handle_file(host, full_file, secret, tags, skip, halt, target_date)
            skipped += 1 if not uploaded else 0
            pct = 100 * n / total_files
            log.info("Done in %0.2fs [%0.1f%%]" % (time() - file_start, pct))
            n += 1
    elapsed = time() - start
    log.info('Skipped files: %s' % skipped)
    log.info('Uploaded %s files in %.2fs' % (total_files, elapsed))


def read_filelist(filelist):
    if not filelist:
        return []

    with open(filelist) as fl:
        return [line.strip() for line in fl if os.path.isfile(line.strip())]


def run():
    config = read_local_conf()
    parser = argparse.ArgumentParser(
        description="Upload files or directories to Photolog"
    )
    parser.add_argument('directories', type=str, nargs='+',
        help="Directory to upload")
    parser.add_argument('--filelist', metavar='T', nargs='?', type=str,
        help="Tags for this batch")
    parser.add_argument('--tags', metavar='T', nargs='?', type=str,
        help="Tags for this batch")
    parser.add_argument('--host', metavar='H', nargs='?', type=str,
        help="Host to upload")
    parser.add_argument('--skip', nargs='?', type=str,
        help="steps to skip")
    parser.add_argument('--target_date', nargs='?', type=str,
        help="Media date")
    parsed = parser.parse_args()
    directories = [os.path.realpath(d) for d in (parsed.directories or [])]
    halt = config.get('halt', False)
    host = parsed.host or config['host']
    secret = md5(config['secret'].encode('utf-8')).hexdigest()
    tags = parsed.tags or ''
    skip = parsed.skip or ''
    target_date = parsed.target_date or None
    filelist = read_filelist(parsed.filelist)
    upload_directories(directories, filelist, host, secret, tags, skip, halt, target_date)


if __name__ == '__main__':
    run()
