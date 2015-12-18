from flask import Flask, render_template, request

from upload_api import web_logger as log, settings_file
from upload_api.db import DB
from upload_api.settings import Setting

settings = Setting.load(settings_file)
db = DB(settings.DB_FILE)
app = Flask(__name__)

PAGE_SIZE = 20


def pictures_for_page(db, page_num):
    start, end = 0, PAGE_SIZE
    db_pics = list(db.get_pictures(start, end))
    return db_pics


@app.route('/', methods=['GET'])
def index():
    page = int(request.form.get('page', '1'))
    pictures = pictures_for_page(db, page)
    ctx = {
        'pictures': pictures
    }
    return render_template('index.html', **ctx)


@app.route('/photo/<string:key>/')
def picture_detail(key):
    picture = db.get_picture(key)
    tags = db.tags_for_picture(picture['id'])
    return render_template('detail.html', **{
        'picture': picture,
        'tags': tags,
    })


def start():
    log.info('Starting WEB server')
    app.run(debug=settings.DEBUG, port=5001)


if __name__ == "__main__":
    start()

