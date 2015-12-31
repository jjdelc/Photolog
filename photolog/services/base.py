import os
import random
import string
import piexif
import shutil
import exifread
from hashlib import md5
from functools import partial
from datetime import datetime
from time import time, mktime
from PIL import Image, ExifTags
from urllib.parse import urlparse, urljoin
from os.path import splitext, basename, join

from .gphotos import create_album, delete_album, clear_album


THUMBNAILS = {
    'thumb': 100,
    'medium': 320,
    'web': 1200,
    'large': 2048
}
KEEP_EXIF = {'large'}  # Keep exif data on these sizes

THUMB_QUALITY = 85
ORIENTATION_EXIF = 274  # Default
# Lookup the right orientation exif tag
for orientation in ExifTags.TAGS.keys():
    if ExifTags.TAGS[orientation] == 'Orientation':
        ORIENTATION_EXIF = orientation
        break


def random_string(size=6):
    return ''.join([random.choice(string.ascii_letters) for _ in range(size)])


def read_rotation(img_data):
    try:
        exif = dict(img_data._getexif().items())
    except ZeroDivisionError:
        # Error reading Exif :(
        return 0
    img_orient_exif = exif[ORIENTATION_EXIF]
    if img_orient_exif == 3:
        return 180
    elif img_orient_exif == 6:
        return 270
    elif img_orient_exif == 8:
        return 90
    return 0


def generate_thumbnails(filename, thumbs_folder):
    base = basename(filename)
    name, ext = splitext(base)
    secret = random_string()
    # Also add random to original
    new_original = join(thumbs_folder, '%s-%s%s' % (name, secret, ext))
    shutil.copyfile(filename, new_original)
    generated = {
        'original': new_original
    }
    for thumb_name, dim in THUMBNAILS.items():
        secret = random_string()
        # I want each thumbnail have a different random string so you cannot
        # guess the other size from the URL
        out_name = join(thumbs_folder, '%s--%s-%s%s' % (name, thumb_name,
                                                        secret, ext))

        orig = Image.open(new_original)
        rotation = read_rotation(orig)
        orig.thumbnail((dim, dim))
        if thumb_name not in KEEP_EXIF:
            # Only rotate those that don't have exif copied
            orig = orig.rotate(rotation, expand=True)

        orig.save(out_name, format='JPEG', quality=THUMB_QUALITY,
            progressive=True)
        generated[thumb_name] = out_name
        if thumb_name in KEEP_EXIF:
            try:
                piexif.transplant(new_original, out_name)
            except ValueError:
                # Original did not have EXIF to transplant
                pass
    return generated


TIME_FORMAT = '%Y:%m:%d %H:%M:%S'


def taken_timestamp(time_string, exif):
    try:
        dt = datetime.strptime(time_string, TIME_FORMAT)
    except ValueError:
        # Could not get a date... then what? Use base day
        dt = datetime(exif['year'], exif['month'], exif['day'])
    return mktime(dt.timetuple())


def store_photo(db, key, name, s3_urls, tags, upload_date, exif, format,
        checksum, notes=''):
    taken_time = taken_timestamp(exif['timestamp'], exif)
    values = {
        'name': name,
        'filename': name,
        'notes': notes,
        'key': key,
        'year': exif['year'],
        'month': exif['month'],
        'checksum': checksum,
        'day': exif['day'],
        'date_taken': exif['timestamp'],
        'upload_date': str(upload_date),
        'upload_time': int(time() * 100),
        'camera': exif['camera'],
        'width': exif['width'],
        'height': exif['height'],
        'size': exif['size'],
        'original': s3_urls['original'],
        'thumb': s3_urls.get('thumb', ''),
        'medium': s3_urls.get('medium', ''),
        'web': s3_urls.get('web', ''),
        'format': format,
        'large': s3_urls.get('large', ''),
        'taken_time': taken_time,
    }
    db.add_picture(values, tags)


def delete_file(filename, thumbs):
    os.remove(filename)
    for thumb_file in thumbs.values():
        os.remove(thumb_file)


def read_exif(filename, upload_date, is_image):
    exif = exifread.process_file(open(filename, 'rb'))
    timestamp = None
    year, month, day = upload_date.year, upload_date.month, upload_date.day
    exif_read = bool(exif)
    if 'EXIF DateTimeOriginal' in exif:
        timestamp = str(exif['EXIF DateTimeOriginal'])
        # fmt='2015:12:04 00:50:53'
        year, month, day = timestamp.split(' ')[0].split(':')
    if is_image:
        dims = Image.open(filename).size
    else:
        dims = None, None
    brand = str(exif.get('Image Make', 'Unknown camera'))
    model = str(exif.get('Image Model', ''))
    return {
        'year': year,
        'month': month,
        'day': day,
        'timestamp': timestamp,
        'camera': '%s %s' % (brand, model),
        'orientation': str(exif.get('Image Orientation', 'Horizontal (normal)')),
        'width': dims[0],
        'height': dims[1],
        'size': os.stat(filename).st_size,
        'exif_read': exif_read
    }


def start_batch(settings):
    """
    For now, we only need batches to handle GPhotos uploads. The default folder
     has a limit of 2000 pictures so we need to create a new folder per batch
     and delete it at the end of the batch.
     The batch_id returned will be the Gphotos folder ID
    """
    name = random_string(6) + str(time())
    album_url = create_album(name, settings)
    print('Created album %s' % album_url)
    parsed = urlparse(album_url)
    path = parsed.path
    chunks = path.split('/')
    return '%s:%s' % (chunks[5], chunks[7])


ALBUM_HOST = 'https://picasaweb.google.com/'


def batch_2_album(batch_id, settings, section='entry'):
    user_id, album_id = batch_id.split(':')
    path = ['', 'data', section, 'api', 'user', user_id, 'albumid', album_id]
    path = '/'.join(path)
    album_url = urljoin(ALBUM_HOST, path)
    return album_url


def end_batch(batch_id, settings):
    album_url = batch_2_album(batch_id, settings)
    clear_album(album_url, settings)
    #delete_album(album_url, settings)


# http://stackoverflow.com/a/7829658/43490
def file_checksum(filename):
    with open(filename, 'rb') as fh:
        d = md5()
        for buf in iter(partial(fh.read, 1024), b''):
            d.update(buf)
    return d.hexdigest()

