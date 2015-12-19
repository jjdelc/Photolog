import os
import random
import string
import exifread
from time import time
from PIL import Image
from os.path import splitext, basename, join


THUMBNAILS = {
    'thumb': 100,
    'medium': 320,
    'web': 1200,
    'large': 2048
}


def random_string():
    return ''.join([random.choice(string.ascii_letters) for _ in range(6)])


def generate_thumbnails(filename, thumbs_folder):
    generated = {
        'original': filename
    }
    base = basename(filename)
    name, ext = splitext(base)
    for thumb_name, dim in THUMBNAILS.items():
        orig = Image.open(filename)
        _hash = random_string()
        # I want each thumbnail have a different random string so you cannot
        # guess the other size from the URL
        out_name = join(thumbs_folder, '%s--%s-%s%s' % (name, thumb_name, _hash, ext))
        generated[thumb_name] = out_name
        orig.thumbnail((dim, dim))
        orig.save(out_name, format='JPEG', quality=85, progressive=True)
    return generated


def store_photo(db, key, name, s3_urls, tags, upload_date, exif):
    values = {
        'name': name,
        'filename': name,
        'notes': '',
        'key': key,
        'year': exif['year'],
        'month': exif['month'],
        'day': exif['day'],
        'date_taken': exif['timestamp'],
        'upload_date': str(upload_date),
        'upload_time': int(time() * 100),
        'camera': exif['camera'],
        'width': exif['width'],
        'height': exif['height'],
        'size': exif['size'],
        'original': s3_urls['original'],
        'thumb': s3_urls['thumb'],
        'medium': s3_urls['medium'],
        'web': s3_urls['web'],
        'large': s3_urls['large'],
    }
    db.add_picture(values, tags)


def delete_file(filename):
    pass


def read_exif(filename, upload_date):
    exif = exifread.process_file(open(filename, 'rb'))
    timestamp = None
    year, month, day = upload_date.year, upload_date.month, upload_date.day
    exif_read = bool(exif)
    if 'EXIF DateTimeOriginal' in exif:
        timestamp = str(exif['EXIF DateTimeOriginal'])  # fmt='2015:12:04 00:50:53'
        year, month, day = timestamp.split(' ')[0].split(':')
    dims = Image.open(filename).size
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

