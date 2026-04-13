import math
import json
import uuid
import xml.etree.ElementTree as etree
from io import StringIO
from datetime import datetime


def human_size(size):
    size_name = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    if s > 0:
        return "%s%s" % (s, size_name[i])
    return "0B"


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
        "current": current,
        "total_pages": total_pages,
        "next": next_page,
        "prev": prev_page,
        "adjacent": adjacent,
    }


def pictures_for_page(db, page_num, page_size, tags=None, year=None):
    offset, limit = (page_num - 1) * page_size, page_size
    if tags:
        db_pics = list(db.tags.tagged_pictures(tags, limit, offset))
    elif year:
        db_pics = list(db.get_pictures_for_year(year, limit, offset))
    else:
        db_pics = list(db.pictures.get_all(limit, offset))
    return db_pics


def get_flickr_data(picture):
    data = picture.get("flickr")
    flickr = {"id": "", "url": ""}
    if data:
        try:
            flickr = json.loads(data)
        except ValueError:
            # Bad Json?
            pass
    return flickr


def get_gphotos_data(picture):
    picture_data = picture.get("gphotos")
    photo_id, url = "", ""
    if picture_data:
        try:
            picture_data = json.loads(picture_data)
        except ValueError:
            # Bad Json?
            pass
        else:
            xml_str = picture_data.get("xml")
            json_data = picture_data.get("json")
            if json_data:
                # Gphotos API (2019)
                photo_id = json_data["id"]
                url = json_data["productUrl"]
            elif xml_str:
                # For old photos where it returned XML, Picasa API
                xml = etree.parse(StringIO(xml_str))
                root = xml.getroot()
                links = root.findall("{http://www.w3.org/2005/Atom}link")
                rel = "http://schemas.google.com/photos/2007#canonical"
                matching = [link.attrib["href"] for link in links if link.attrib["rel"] == rel]
                id_node = "{http://schemas.google.com/photos/2007}id"
                photo_ids = root.findall(id_node)
                photo_id = photo_ids[0].text if photo_ids else ""
                url = matching[0] if matching else ""
    return {"url": url, "id": photo_id}


def get_key(url):
    return url.strip().split("/")[-2]


def months_tags(months, month):
    return [
        {"month": "%02d" % m, "has_data": m in months, "current": m == month} for m in range(1, 13)
    ]


def days_tags(days, current):
    return [
        {"day": "%02d" % d, "has_data": d in days, "current": d == current} for d in range(1, 32)
    ]


def tag_day_job(queue, year: int, month: int, day: int, tags):
    queue.append(
        {
            "type": "tag-day",
            "key": uuid.uuid4().hex,
            "year": year,
            "month": month,
            "day": day,
            "tags": tags,
            "attempt": 0,
        }
    )


def serial_job(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
