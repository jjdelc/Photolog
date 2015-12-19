import math
from flask import Flask, render_template, request

from upload_api import web_logger as log, settings_file
from upload_api.db import DB
from upload_api.settings import Setting

settings = Setting.load(settings_file)
db = DB(settings.DB_FILE)
app = Flask(__name__)

PAGE_SIZE = 24


def human_size(size):
    size_name = ['B', 'KB', 'MB', 'GB']
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    if s > 0:
        return '%s%s' % (s, size_name[i])
    return '0B'


def get_paginator(total, page_size, current):
    total_pages = math.ceil(total / page_size)
    next_page = current + 1 if current < total_pages else None
    prev_page = current - 1 if current > 1 else None
    adjacent_size = 2
    page_start = current - adjacent_size
    page_start = page_start if page_start > 1 else 1
    page_end = page_start + 1 + adjacent_size * 2
    adjacent_pages = range(page_start, page_end)
    adjacent = [x for x in adjacent_pages if 0 < x <= total_pages]
    return {
        'current': current,
        'total_pages': total_pages,
        'next': next_page,
        'prev': prev_page,
        'adjacent': adjacent
    }


def pictures_for_page(db, page_num, tags=None):
    offset, limit = (page_num - 1) * PAGE_SIZE, PAGE_SIZE
    if not tags:
        db_pics = list(db.get_pictures(offset, limit))
    else:
        db_pics = list(db.get_tagged_pictures(tags, offset, limit))
    return db_pics


@app.route('/', methods=['GET'])
def index():
    page = int(request.args.get('page', '1'))
    pictures = pictures_for_page(db, page)
    db_total = db.total_pictures()
    paginator = get_paginator(db_total, PAGE_SIZE, page)
    all_tags = db.get_tags()
    ctx = {
        'pictures': pictures,
        'total': db_total,
        'paginator': paginator,
        'all_tags': all_tags,
    }
    return render_template('index.html', **ctx)


@app.route('/photo/<string:key>/')
def picture_detail(key):
    picture = db.get_picture(key)
    tags = db.tags_for_picture(picture['id'])
    return render_template('detail.html', **{
        'picture': picture,
        'tags': tags,
        'human_size': human_size(picture['size'])
    })


@app.route('/tags/<string:tag_list>/')
def view_tags(tag_list):
    page = int(request.args.get('page', '1'))
    tags = [t.lower() for t in tag_list.split(',') if t]
    pictures = pictures_for_page(db, page, tags)
    tagged_total = db.total_for_tags(tags)
    paginator = get_paginator(tagged_total, PAGE_SIZE, page)
    all_tags = db.get_tags()
    ctx = {
        'selected_tags': tags,
        'all_tags': all_tags,
        'pictures': pictures,
        'paginator': paginator,
        'total': tagged_total,
    }
    return render_template('index.html', **ctx)


def start():
    log.info('Starting WEB server')
    app.run(debug=settings.DEBUG, port=5001, host='0.0.0.0')


if __name__ == "__main__":
    start()

