import os
import exifread
from PIL import Image
from os.path import splitext, basename, join


THUMBNAILS = {
    'thumb': 100,
    'medium': 320,
    'web': 1200,
    'large': 2048
}


def generate_thumbnails(filename, thumbs_folder):
    generated = {
        'original': filename
    }
    base = basename(filename)
    name, ext = splitext(base)
    for thumb_name, dim in THUMBNAILS.items():
        orig = Image.open(filename)
        out_name = join(thumbs_folder, '%s--%s-%s' % (name, thumb_name, ext))
        generated[thumb_name] = out_name
        orig.thumbnail((dim, dim))
        orig.save(out_name, format='JPEG', quality=85, progressive=True)
    return generated


def store_photo(s3_urls, flickr_url, gphotos_url, tags, upload_date, exif):
    values = {
        'year': exif['year'],
        'month': exif['month'],
        'day': exif['day'],
        'date_taken': exif['timestamp'],
        'upload_date': str(upload_date),
        'camera': exif['camera'],
        'width': exif['width'],
        'height': exif['height'],
        'size': exif['size'],
        'original': s3_urls['original'],
        'thumb': s3_urls['thumb'],
        'medium': s3_urls['medium'],
        'web': s3_urls['web'],
        'large': s3_urls['large'],
        'flickr': flickr_url,
        'gphotos': gphotos_url
    }
    pass


def delete_file(filename):
    pass


def read_exif(filename):
    exif = exifread.process_file(open(filename, 'rb'))
    timestamp = str(exif['EXIF DateTimeOriginal'])  # fmt='2015:12:04 00:50:53'
    year, month, day = timestamp.split(' ')[0].split(':')
    dims = Image.open(filename).size
    brand = str(exif['Image Make'])
    model = str(exif['Image Model'])
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
    }

