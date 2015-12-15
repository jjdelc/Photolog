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
    pass


def delete_file(filename):
    pass


def read_exif(filename):
    return {
        'year': '',
        'month': '',
        'day': '',
        'camera': '',
        'orientation': '',
        'width': 0,
        'height': 0,
        'size': 0,
    }

