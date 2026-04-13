import os
import math
import json
import uuid
import requests
from urllib.parse import urljoin
from datetime import datetime, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    send_file,
)
from flask_login import (
    LoginManager,
    login_required,
    login_user,
    UserMixin,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect

from photolog import web_logger as log, settings_file
from photolog.db import DB
from photolog.settings import Settings
from photolog.squeue import SqliteQueue
from photolog.services.api import base
from photolog.services.web import main as web_service

INDIEAUTH_ENDPOINT = "https://indieauth.com/auth"
# INDIEAUTH_ENDPOINT = 'https://indielogin.com/auth'

settings = Settings.load(settings_file)
db = DB(settings.DB_FILE)
queue = SqliteQueue(settings.DB_FILE)
app = Flask(__name__)
app.secret_key = settings.SECRET_KEY

csrf = CSRFProtect()
csrf.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):
    """
    We need some User class to authenticate, Photolog is single user so we
    have this dummy.
    """

    def get_id(self):
        return settings.AUTH_ME


# This is our single user
user = User()


@login_manager.user_loader
def load_user(user_id):
    return user


PAGE_SIZE = 24


@app.route("/", methods=["GET"])
@login_required
def index():
    db_total = db.total_pictures()
    all_tags = db.tags.all()
    years = db.get_years()
    recent = list(db.pictures.recent(24, 0))
    ctx = {
        "recent": recent,
        "total": db_total,
        "all_tags": all_tags,
        "years": years,
        "total_pages": math.ceil(db_total / PAGE_SIZE),
    }
    return render_template("index.html", **ctx)


@app.route("/photo/", methods=["GET"])
@login_required
def photo_list():
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400)
    pictures = web_service.pictures_for_page(db, page, PAGE_SIZE)
    db_total = db.total_pictures()
    paginator = web_service.get_paginator(db_total, PAGE_SIZE, page)
    all_tags = db.tags.all()
    years = db.get_years()
    ctx = {
        "pictures": pictures,
        "total": db_total,
        "paginator": paginator,
        "all_tags": all_tags,
        "years": years,
    }
    return render_template("photo_list.html", **ctx)


def get_pic_nav(taken_time):
    prev_key, next_key = db.pictures.nav(taken_time)
    return {
        "prev": url_for("picture_detail", key=prev_key) if prev_key else "",
        "next": url_for("picture_detail", key=next_key) if next_key else "",
    }


@app.route("/photo/<string:key>/")
@login_required
def picture_detail(key):
    picture = db.pictures.by_key(key)
    tags = db.tags.for_picture(picture["id"])
    nav = get_pic_nav(picture["taken_time"])
    return render_template(
        "detail.html",
        **{
            "picture": picture,
            "tags": tags,
            "human_size": web_service.human_size(picture["size"]),
            "flickr": web_service.get_flickr_data(picture),
            "gphotos": web_service.get_gphotos_data(picture),
            "nav": nav,
            "month": "%02d" % picture["month"],
            "day": "%02d" % picture["day"],
        },
    )


@app.route("/photo/<string:key>/edit/tags/", methods=["GET", "POST"])
@login_required
def tag_picture(key):
    picture = db.pictures.by_key(key)
    if request.method == "GET":
        tags = db.tags.for_picture(picture["id"])
        return render_template(
            "edit_tags.html",
            **{
                "picture": picture,
                "tags": tags,
                "current_tags": ", ".join(tags),
            },
        )
    else:
        tags = request.form["tags"]
        new_tags = {base.slugify(t) for t in tags.split(",")}
        db.tags.change_for_picture(picture["id"], new_tags)
        return redirect(url_for("picture_detail", key=key))


@app.route("/photo/<string:key>/edit/attr/", methods=["GET", "POST"])
@login_required
def edit_attr(key):
    picture = db.pictures.by_key(key)
    allowed_attrs = {"tags"}
    if request.method == "GET":
        return render_template(
            "edit_attr.html",
            **{
                "picture": picture,
                "blob": json.dumps(picture, indent=2),
            },
        )
    else:
        attr = request.form["attr"]
        value = request.form["value"]
        confirm = request.form.get("confirm")
        if attr not in allowed_attrs:
            abort(400)  # Cannot edit just _any_ attribute, geez!
        if confirm and attr in picture:
            db.pictures.edit_attribute(key, attr, value)
            return redirect(url_for("picture_detail_blob", key=key))
        return redirect(url_for("picture_detail_blob", key=key))


@app.route("/photo/<string:key>/blob/")
@login_required
def picture_detail_blob(key):
    picture = db.pictures.by_key(key)
    return render_template(
        "detail_blob.html",
        **{
            "picture": picture,
            "blob": json.dumps(picture, indent=2),
        },
    )


@app.route("/edit/tags/", methods=["GET", "POST"])
@login_required
def mass_tag():
    if request.method == "GET":
        return render_template("mass_tag.html")
    else:
        keys = [web_service.get_key(k) for k in request.form["keys"].split()]
        tags = request.form["tags"]
        new_tags = {base.slugify(t) for t in tags.split(",") if t.strip()}
        if new_tags and keys:
            queue.append(
                {
                    "type": "mass-tag",
                    "key": uuid.uuid4().hex,
                    "keys": keys,
                    "tags": new_tags,
                    "attempt": 0,
                }
            )
        return redirect("/")


@app.route("/edit/dates/", methods=["GET", "POST"])
@login_required
def edit_dates():
    if request.method == "GET":
        return render_template("edit_dates.html")
    else:
        changes = []
        try:
            for field_n in range(1, 9):
                url = request.form.get("key_%s" % field_n)
                if not url:
                    continue
                url = url.strip()
                if not url:
                    continue
                key = web_service.get_key(url)
                date = request.form.get("date_%s" % field_n)
                if date:
                    date = date.strip()
                if key and date:
                    changes.append((key, datetime.strptime(date, "%Y-%m-%d")))

            multikey = request.form.get("multikeys")
            if multikey:
                keys = [web_service.get_key(k) for k in multikey.split()]
                multikeys_dates = request.form.get("multikeys_dates")
                if multikeys_dates:
                    dest_date = datetime.strptime(multikeys_dates, "%Y-%m-%d")
                    for key in keys:
                        changes.append((key, dest_date))
        except ValueError:
            abort(400)
        if changes:
            queue.append(
                {
                    "type": "edit-dates",
                    "key": uuid.uuid4().hex,
                    "changes": changes,
                    "attempt": 0,
                }
            )
        return redirect("/edit/dates/")


@app.route("/tags/dates/change/", methods=["POST"])
@login_required
def change_date():
    if request.method == "POST":
        origin = request.form.get("origin")
        target = request.form.get("target")
        if not origin or not target:
            abort(400)
        origin = origin.strip()
        target = target.strip()
        try:
            origin = datetime.strptime(origin, "%Y-%m-%d")
            target = datetime.strptime(target, "%Y-%m-%d")
        except ValueError:
            abort(400)
        queue.append(
            {
                "type": "change-date",
                "key": uuid.uuid4().hex,
                "origin": origin,
                "target": target,
                "attempt": 0,
            }
        )
        return redirect(url_for("view_day", year=target.year, month=target.month, day=target.day))


@app.route("/tags/<string:tag_list>/")
@login_required
def view_tags(tag_list):
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400)
    tags = [t.lower() for t in tag_list.split(",") if t]
    pictures = web_service.pictures_for_page(db, page, PAGE_SIZE, tags=tags)
    tagged_total = db.tags.total_for_tags(tags)
    paginator = web_service.get_paginator(tagged_total, PAGE_SIZE, page)
    all_tags = db.tags.all()
    years = db.get_years()
    ctx = {
        "selected_tags": tags,
        "all_tags": all_tags,
        "pictures": pictures,
        "paginator": paginator,
        "total": tagged_total,
        "years": years,
    }
    return render_template("photo_list.html", **ctx)


@app.route("/date/<int:year>/")
@login_required
def view_year(year):
    page = int(request.args.get("page", "1"))
    pictures = web_service.pictures_for_page(db, page, PAGE_SIZE, year=year)
    tagged_total = db.total_for_year(year)
    paginator = web_service.get_paginator(tagged_total, PAGE_SIZE, page)
    all_tags = db.tags.all()
    years = db.get_years()
    present_months = db.get_months(year)
    ctx = {
        "all_tags": all_tags,
        "pictures": pictures,
        "paginator": paginator,
        "total": tagged_total,
        "year": year,
        "months": web_service.months_tags(present_months, 0),
        "years": years,
    }
    return render_template("photo_list.html", **ctx)


@app.route("/date/<int:year>/<int:month>/")
@login_required
def view_month(year, month):
    page = int(request.args.get("page", "1"))
    params = {"year": year, "month": month}
    offset, limit = (page - 1) * PAGE_SIZE, PAGE_SIZE
    pictures = db.pictures.find(params, limit, offset)
    tagged_total = db.pictures.count(params)
    paginator = web_service.get_paginator(tagged_total, PAGE_SIZE, page)
    all_tags = db.tags.all()
    years = db.get_years()
    present_months = db.get_months(year)
    active_days = db.get_days(year, month)
    ctx = {
        "all_tags": all_tags,
        "pictures": pictures,
        "paginator": paginator,
        "total": tagged_total,
        "year": year,
        "month": "%02d" % month,
        "months": web_service.months_tags(present_months, month),
        "days": web_service.days_tags(active_days, 0),
        "years": years,
    }
    return render_template("photo_list.html", **ctx)


@app.route("/date/<int:year>/<int:month>/<int:day>/")
@login_required
def view_day(year, month, day):
    try:
        this_day = datetime(year, month, day)
    except ValueError:
        abort(404)
    page = int(request.args.get("page", "1"))
    params = {"year": year, "month": month, "day": day}
    offset, limit = (page - 1) * PAGE_SIZE, PAGE_SIZE
    pictures = db.pictures.find(params, limit, offset)
    tagged_total = db.pictures.count(params)
    paginator = web_service.get_paginator(tagged_total, PAGE_SIZE, page)
    all_tags = db.tags.all()
    years = db.get_years()
    present_months = db.get_months(year)
    active_days = db.get_days(year, month)
    yesterday = this_day + timedelta(-1)
    tomorrow = this_day + timedelta(1)
    ctx = {
        "all_tags": all_tags,
        "pictures": pictures,
        "paginator": paginator,
        "total": tagged_total,
        "year": year,
        "month": "%02d" % month,
        "day": "%02d" % day,
        "years": years,
        "months": web_service.months_tags(present_months, month),
        "days": web_service.days_tags(active_days, day),
        "tomorrow": tomorrow,
        "yesterday": yesterday,
    }
    return render_template("photo_list.html", **ctx)


@app.route("/date/<int:year>/<int:month>/<int:day>/tags/", methods=["GET", "POST"])
@login_required
def tag_day(year, month, day):
    month_str = "%02d" % month
    day_str = "%02d" % day
    year_str = str(year)
    params = {"year": year, "month": month, "day": day}
    total = db.pictures.count(params)
    if request.method == "GET":
        return render_template(
            "edit_day_tags.html",
            **{"total": total, "year": year_str, "month": month_str, "day": day_str},
        )
    else:
        tags = request.form["tags"]
        new_tags = {base.slugify(t) for t in tags.split(",") if t.strip()}
        if new_tags:
            web_service.tag_day_job(queue, year, month, day, new_tags)
        return redirect(url_for("view_day", year=year, month=month, day=day))


@app.route("/jobs/")
@login_required
def view_queue():
    result = queue.peek(200)
    size = len(queue)
    return render_template("jobs.html", jobs=result, size=size)


@app.route("/jobs/bad/", methods=["POST"])
@login_required
def retry_jobs():
    queue.retry_jobs()
    return redirect("/jobs/")


@app.route("/jobs/bad/", methods=["GET"])
@login_required
def bad_jobs():
    result = queue.get_bad_jobs()
    total_jobs = queue.total_bad_jobs()
    return render_template(
        "bad_jobs.html",
        bad_jobs=[
            (job, json.dumps(job, indent=2, default=web_service.serial_job))
            for job in result
        ],
        total_jobs=total_jobs,
    )


@app.route("/jobs/bad/purge/", methods=["GET"])
@login_required
def purge_form():
    return render_template("purge_jobs.html")


@app.route("/jobs/bad/purge/all/", methods=["POST"])
@login_required
def purge_all():
    queue.purge_all_bad()
    return redirect("/jobs/bad/")


@app.route("/jobs/bad/purge/", methods=["POST"])
@login_required
def purge_bad_job():
    key = request.form["job_key"]
    for bj in queue.get_bad_jobs_raw():
        if bj[1]["key"] == key:
            queue.purge_bad_job(bj[0])
            break
    return redirect("/jobs/bad/")


@app.route("/search/")
@login_required
def search():
    name = request.args.get("name")
    if name:
        pic = db.pictures.find_one({"name": name})
        return redirect(url_for("picture_detail", key=pic["key"]))
    return render_template("search.html")


@app.route("/backup/", methods=["GET", "POST"])
@login_required
def backup():
    if request.method == "POST":
        today = datetime.now().date()
        return send_file(
            settings.DB_FILE,
            as_attachment=True,
            download_name="backup-%s.db" % today,
        )
    db_size = web_service.human_size(os.stat(settings.DB_FILE).st_size)
    return render_template("backup.html", db_size=db_size)


@app.route("/login/", methods=["GET", "POST"])
def login():
    code = request.args.get("code") or request.form.get("code")
    me = request.args.get("me") or request.form.get("me")
    redirect_uri = urljoin(settings.DOMAIN, url_for("login"))
    client_id = settings.DOMAIN
    if code and me:
        r = requests.post(
            INDIEAUTH_ENDPOINT,
            data={
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
            },
        )
        if r.status_code == 200:
            # me = dict(parse_qsl(r.text)).get('me')
            me = r.json()["me"]
            if me == user.get_id():
                login_user(user)
                return redirect(url_for("index"))
            else:
                abort(401)
        else:
            abort(401)

    return render_template(
        "login.html",
        redirect_url=redirect_uri,
        auth_url=INDIEAUTH_ENDPOINT,
        client_id=client_id,
    )


@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


def start():
    log.info("Starting WEB server")
    app.run(debug=settings.DEBUG, port=5001, host="0.0.0.0")


if __name__ == "__main__":
    start()
