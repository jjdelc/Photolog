def generate_thumbnails(filename, thumbs_folder):
    return {
        'original': filename
    }


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

