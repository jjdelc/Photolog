import os
from time import time, sleep
import xml.etree.ElementTree as etree

import requests
from photolog.db import TokensDB
from photolog import queue_logger as log

SERVICE = "gphotos"
UPLOAD_ENDPOINT = "https://photoslibrary.googleapis.com/v1/uploads"
ITEM_ENDPOINT = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"
EXCHANGE_TOKEN_ENDPOINT = "https://www.googleapis.com/oauth2/v4/token"

etree.register_namespace("", "http://www.w3.org/2005/Atom")
etree.register_namespace("gphoto", "http://schemas.google.com/photos/2007")
etree.register_namespace("media", "http://search.yahoo.com/mrss/")
etree.register_namespace("app", "http://www.w3.org/2007/app")
etree.register_namespace("gd", "http://schemas.google.com/g/2005")


def refresh_access_token(tokens, client_id, secret, refresh_token):
    response = requests.post(
        EXCHANGE_TOKEN_ENDPOINT,
        data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": secret,
            "grant_type": "refresh_token",
            "access_type": "offline",
        },
    ).json()
    if "access_token" in response:
        tokens.update_token(
            SERVICE,
            response["access_token"],
            response["token_type"],
            time() + response["expires_in"],
        )
        return response["access_token"]
    else:
        # Some error
        log.error("Error refreshing %s token: %s" % (SERVICE, response))
        raise ValueError("Error refreshing %s token: %s" % (SERVICE, response))


def _get_file_bytes(filename, fallback_s3_url):
    try:
        with open(filename, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        if not fallback_s3_url:
            log.error("Local file not found and no fallback URL available: %s" % filename)
            raise

        log.info("Local file not found, fetching from S3: %s" % fallback_s3_url)
        response = requests.get(fallback_s3_url)
        response.raise_for_status()
        return response.content


def _upload_photo(filename, name, access_token, token_type, fallback_s3_url):
    headers = {
        "Authorization": "%s %s" % (token_type, access_token),
        "Content-type": "application/octet-stream",
        # 'Content-Length': str(os.stat(filename).st_size),
        "X-Goog-Upload-File-Name": name,
        "X-Goog-Upload-Protocol": "raw",
    }
    files = _get_file_bytes(filename, fallback_s3_url)
    return do_upload(files, headers)


def _upload_video(filename, name, access_token, token_type, mime, fallback_s3_url):
    metadata = """<entry xmlns='http://www.w3.org/2005/Atom'>
      <title>%(name)s</title>
      <summary>%(name)s</summary>
      <category scheme="http://schemas.google.com/g/2005#kind"
        term="http://schemas.google.com/photos/2007#photo"/>
    </entry>""" % {"name": name}
    metadata = metadata.encode("utf-8")

    file_bytes = _get_file_bytes(filename, fallback_s3_url)
    file_size = len(file_bytes)

    headers = {
        "GData-Version": "2",
        "Slug": name,
        "Content-Type": "multipart/related",
        "Authorization": "%s %s" % (token_type, access_token),
        "Content-Length": str(file_size + len(metadata)),
        "MIME-version": "1.0",
    }
    files = [
        (None, (None, metadata, "application/atom+xml")),
        (None, (None, file_bytes, mime)),
    ]
    return do_upload(files, headers)


def do_upload(files, headers, retry=True):
    """
    Follows the steps described in:
        https://developers.google.com/photos/library/guides/upload-media
    :param files: The bytes to upload
    :param headers: dict of headers to upload containing the Authorization
    :param retry: Boolean to indicate if we should backoff/retry
    :return: media item ID
    """
    try:
        response = requests.post(UPLOAD_ENDPOINT, data=files, headers=headers)
    except Exception as err:
        log.exception(err)
        raise

    if response.status_code == 429:
        # RESOURCE_EXHAUSTED
        if retry:
            log.info("Sleeping for 60s")
            sleep(60)  # Wait a minute
            log.info("Retrying")
            return do_upload(files, headers, retry=False)
    elif response.status_code > 300:
        log.error("Failed obtain upload token: %s" % response.text)
        raise ValueError(response.text)
    upload_token = response.text

    new_items = {
        "newMediaItems": [
            {
                "description": "",
                "simpleMediaItem": {"uploadToken": upload_token},
            }
        ]
    }
    try:
        item_response = requests.post(
            ITEM_ENDPOINT,
            json=new_items,
            headers={
                "Authorization": headers["Authorization"],
                "Content-Type": "application/json",
            },
        )
    except Exception as err:
        log.exception(err)
        raise

    if item_response.status_code == 429:
        # RESOURCE_EXHAUSTED
        if retry:
            log.info("Sleeping for 60s")
            sleep(60)  # Wait a minute
            log.info("Retrying")
            return do_upload(files, headers, retry=False)
    elif item_response.status_code > 300:
        log.error("Failed to upload: %s" % item_response.text)
        raise ValueError(item_response.text)

    new_items_resp = item_response.json()
    return new_items_resp["newMediaItemResults"][0]["mediaItem"]


def get_token(settings):
    if not hasattr(settings, "GPHOTOS_REFRESH_TOKEN") or not settings.GPHOTOS_REFRESH_TOKEN:
        raise ValueError("GPHOTOS_REFRESH_TOKEN not configured")

    tokens = TokensDB(settings.DB_FILE)
    token = tokens.get_token(SERVICE)
    token_type = "Bearer"
    if token and not tokens.needs_refresh(SERVICE, token["access_token"]):
        return token["access_token"], token_type

    log.info("Refreshing Gphotos token...")
    access_token = refresh_access_token(
        tokens,
        settings.GPHOTOS_CLIENT_ID,
        settings.GPHOTOS_SECRET,
        settings.GPHOTOS_REFRESH_TOKEN,
    )
    log.info("Token refreshed")
    return access_token, token_type


def upload_photo(settings, filename, name, fallback_s3_url):
    """Uploads the given file to Google Photos and returns its url.
    If the local file is missing, falls back to fetching from the S3 URL."""
    access_token, token_type = get_token(settings)
    return _upload_photo(filename, name, access_token, token_type, fallback_s3_url)


def upload_video(settings, filename, name, mime, fallback_s3_url):
    """Uploads the given file to Google Photos and returns its url.
    If the local file is missing, falls back to fetching from the S3 URL."""
    access_token, token_type = get_token(settings)
    return _upload_video(filename, name, access_token, token_type, mime, fallback_s3_url)


album_meta = """<entry xmlns='http://www.w3.org/2005/Atom'
    xmlns:media='http://search.yahoo.com/mrss/'
    xmlns:gphoto='http://schemas.google.com/photos/2007'>
  <title type='text'>%s</title>
  <gphoto:access>private</gphoto:access>
  <category scheme='http://schemas.google.com/g/2005#kind'
    term='http://schemas.google.com/photos/2007#album'></category>
</entry>"""

link_tag = "{http://www.w3.org/2005/Atom}link"


def create_album(album_name, settings):
    access_token, token_type = get_token(settings)
    payload = album_meta % album_name
    headers = {
        "GData-Version": "2",
        "Authorization": "%s %s" % (token_type, access_token),
        "MIME-version": "1.0",
        "Content-length": str(len(payload.encode("ascii"))),
        "Content-Type": "application/atom+xml; charset=UTF-8",
    }
    session = requests.Session()
    request = requests.Request(
        "POST", UPLOAD_ENDPOINT, data=payload.encode("ascii"), headers=headers
    )
    response = session.send(request.prepare())
    if response.status_code == 201:
        xml = etree.fromstring(response.text)
        links = [t for t in xml.findall(link_tag) if t.get("rel") == "self"]
        if links:
            return links[0].get("href")
        raise ValueError("Malformed album response")
    else:
        raise ValueError("Failed to create album")


def delete_album(album_url, settings):
    access_token, token_type = get_token(settings)
    headers = {
        "GData-Version": "2",
        "Authorization": "%s %s" % (token_type, access_token),
        "MIME-version": "1.0",
        "If-Match": "*",
    }
    response = requests.delete(album_url, headers=headers)
    if response.status_code != 200:
        raise ValueError("Failed to delete album")


def clear_album(album_url, settings):
    """
    Removes all photos from an album
    """
    access_token, token_type = get_token(settings)
    response = requests.get(
        album_url,
        headers={
            "GData-Version": "2",
            "Authorization": "%s %s" % (token_type, access_token),
            "MIME-version": "1.0",
        },
    )
    if response.status_code != 200:
        raise ValueError("Error reading album")
    xml = etree.fromstring(response.text)
    groups = xml.findall("{http://search.yahoo.com/mrss/}group")
    # There should only be one group... but oh well
    for group in groups:
        while group:  # While it has children, remove it
            group.remove(group[0])
    empty_album = etree.tostring(xml)
    response = requests.put(
        album_url,
        data=empty_album,
        headers={
            "GData-Version": "2",
            "Authorization": "%s %s" % (token_type, access_token),
            "MIME-version": "1.0",
            "Content-length": str(len(empty_album)),
            "Content-Type": "application/atom+xml; charset=UTF-8",
            "If-Match": "*",
        },
    )
    if response.status_code > 300:
        raise ValueError("Error updating album")
