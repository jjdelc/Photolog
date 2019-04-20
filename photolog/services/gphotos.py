import os
from time import time, sleep
import xml.etree.ElementTree as etree
from urllib.parse import urlencode, urlunparse

import requests
from photolog.db import TokensDB
from photolog import queue_logger as log

"""
To obtain a bearer token you must:
Go to google developer console and create a new project
Grant "New Credentials" for an "Oauth client ID"
*important*
    The redirect_uri has to be "urn:ietf:wg:oauth:2.0:oob"
    scope has to point to https://www.googleapis.com/auth/photoslibrary.appendonly

Construct the following URL and paste into browser:
https://accounts.google.com/o/oauth2/v2/auth?
    scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fphotoslibrary&
    redirect_uri=urn:ietf:wg:oauth:2.0:oob&
    response_type=code&
    access_type=offline&
    client_id={{YOUR_CLIENT_ID}}

Copy the provided code as the GPHOTOS_ACCESS_CODE setting.

https://www.googleapis.com/oauth2/v4/token

code=YOUR_CODE
client_id=YOUR_CLIENT&
client_secret=your_client_secret&
redirect_uri=https://oauth2-login-demo.appspot.com/code&
grant_type=authorization_code

"""

SERVICE = 'gphotos'
# https://developers.google.com/api-client-library/python/auth/installed-app
# This value signals to the Google Authorization Server that the
# authorization code should be returned in the title bar of the browser,
OOB_URL = "urn:ietf:wg:oauth:2.0:oob"
#EXCHANGE_TOKEN_ENDPOINT = 'https://www.googleapis.com/oauth2/v4/token'
CODE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD_ENDPOINT = "https://photoslibrary.googleapis.com/v1/uploads"
ITEM_ENDPOINT = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
#EXCHANGE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
EXCHANGE_TOKEN_ENDPOINT = "https://www.googleapis.com/oauth2/v4/token"

# For Gphotos/Atom XML parsing
etree.register_namespace('', 'http://www.w3.org/2005/Atom')
etree.register_namespace('gphoto', 'http://schemas.google.com/photos/2007')
etree.register_namespace('media', 'http://search.yahoo.com/mrss/')
etree.register_namespace('app', 'http://www.w3.org/2007/app')
etree.register_namespace('gd', 'http://schemas.google.com/g/2005')

# https://developers.google.com/photos/library/guides/authentication-authorization
SCOPE = "https://www.googleapis.com/auth/photoslibrary"
GACCOUNT_HOST = "accounts.google.com"
GACCOUNT_PATH = "/o/oauth2/v2/auth"


def get_access_code(client_id):
    """
    Use this function to discover the URL you need to visit to get your
     one off code to exchange for an access token.
    https://developers.google.com/identity/protocols/OAuth2WebServer
    """
    params = {
        'redirect_uri': OOB_URL,
        'scope': SCOPE,
        'client_id': client_id,
        'response_type': 'code',
        'access_type': 'offline',
    }
    return urlunparse([
        'https', GACCOUNT_HOST, GACCOUNT_PATH, '', urlencode(params), ''
    ])


def exchange_token(tokens, client_id, secret, code):
    response = requests.post(EXCHANGE_TOKEN_ENDPOINT, data={
        'code': code,
        'client_id': client_id,
        'client_secret': secret,
        'grant_type': 'authorization_code',
        'redirect_uri': OOB_URL,
        'expires_in': '86400'  # 1 day in seconds
    }).json()
    if 'access_token' in response:
        tokens.save_token(
            SERVICE,
            response['access_token'],
            response['token_type'],
            response['refresh_token'],
            time() + response['expires_in']
        )
        return response['access_token']
    else:
        # Some error
        log.error('Error negotiating %s token: %s' % (SERVICE, response))
        raise ValueError('Error negotiating %s token: %s' % (SERVICE, response))


def refresh_access_token(tokens, client_id, secret, refresh_token):
    response = requests.post(EXCHANGE_TOKEN_ENDPOINT, data={
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': secret,
        'grant_type': 'refresh_token',
        'access_type': 'offline'
    }).json()
    if 'access_token' in response:
        tokens.update_token(
            SERVICE,
            response['access_token'],
            response['token_type'],
            time() + response['expires_in']
        )
        return response['access_token']
    else:
        # Some error
        log.error('Error refreshing %s token: %s' % (SERVICE, response))
        raise ValueError('Error refreshing %s token: %s' % (SERVICE, response))


def _upload_photo(filename, name, access_token, token_type):
    headers = {
        'Authorization': '%s %s' % (token_type, access_token),
        'Content-type': 'application/octet-stream',
        # 'Content-Length': str(os.stat(filename).st_size),
        'X-Goog-Upload-File-Name': name,
        'X-Goog-Upload-Protocol': 'raw',
    }
    files = open(filename, 'rb').read()
    return do_upload(files, headers)


def _upload_video(filename, name, access_token, token_type, mime):
    metadata = """<entry xmlns='http://www.w3.org/2005/Atom'>
      <title>%(name)s</title>
      <summary>%(name)s</summary>
      <category scheme="http://schemas.google.com/g/2005#kind"
        term="http://schemas.google.com/photos/2007#photo"/>
    </entry>""" % {
        'name': name
    }
    metadata = metadata.encode('utf-8')
    headers = {
        'GData-Version': '2',
        'Slug': name,
        'Content-Type': 'multipart/related',
        'Authorization': '%s %s' % (token_type, access_token),
        'Content-Length': str(os.stat(filename).st_size + len(metadata)),
        'MIME-version': '1.0'
    }
    files = [
        (None, (None, metadata, 'application/atom+xml')),
        (None, (None, open(filename, 'rb'), mime))
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
        log.error('Failed obtain upload token: %s' % response.text)
        raise ValueError(response.text)
    upload_token = response.text

    new_items = {
        "newMediaItems": [
            {
                "description": "",
                "simpleMediaItem": {
                    "uploadToken": upload_token
                }
            }
        ]
    }
    try:
        item_response = requests.post(ITEM_ENDPOINT, json=new_items, headers={
            "Authorization": headers["Authorization"],
            "Content-Type": "application/json"
        })
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
        log.error('Failed to upload: %s' % item_response.text)
        raise ValueError(item_response.text)

    new_items_resp = item_response.json()
    return new_items_resp["newMediaItemResults"][0]["mediaItem"]


def get_token(settings):
    tokens = TokensDB(settings.DB_FILE)
    token = tokens.get_token(SERVICE)
    token_type = 'Bearer'
    if token:
        access_token = token['access_token']
        token_type = token['token_type']
        if tokens.needs_refresh(SERVICE, access_token):
            log.info('Refreshing Gphotos token...')
            access_token = refresh_access_token(tokens,
                settings.GPHOTOS_CLIENT_ID,
                settings.GPHOTOS_SECRET,
                token['refresh_token']
            )
            log.info("Token refreshed")
    else:
        log.info('Obtaining Gphotos token')
        #access_token = gphotos.exchange_token(tokens,
        access_token = exchange_token(tokens,
            settings.GPHOTOS_CLIENT_ID,
            settings.GPHOTOS_SECRET,
            settings.GPHOTOS_ACCESS_CODE)
        log.info("Token obtained")
    return access_token, token_type


def upload_photo(settings, filename, name):
    """Uploads the given file to Google Photos and returns its url"""
    access_token, token_type = get_token(settings)
    return _upload_photo(filename, name, access_token, token_type)


def upload_video(settings, filename, name, mime):
    """Uploads the given file to Google Photos and returns its url"""
    access_token, token_type = get_token(settings)
    return _upload_video(filename, name, access_token, token_type, mime)


album_meta = """<entry xmlns='http://www.w3.org/2005/Atom'
    xmlns:media='http://search.yahoo.com/mrss/'
    xmlns:gphoto='http://schemas.google.com/photos/2007'>
  <title type='text'>%s</title>
  <gphoto:access>private</gphoto:access>
  <category scheme='http://schemas.google.com/g/2005#kind'
    term='http://schemas.google.com/photos/2007#album'></category>
</entry>"""

link_tag = '{http://www.w3.org/2005/Atom}link'


def create_album(album_name, settings):
    access_token, token_type = get_token(settings)
    payload = album_meta % album_name
    headers = {
        'GData-Version': '2',
        'Authorization': '%s %s' % (token_type, access_token),
        'MIME-version': '1.0',
        'Content-length': str(len(payload.encode('ascii'))),
        'Content-Type': 'application/atom+xml; charset=UTF-8'
    }
    session = requests.Session()
    request = requests.Request('POST', UPLOAD_ENDPOINT,
        data=payload.encode('ascii'), headers=headers)
    response = session.send(request.prepare())
    if response.status_code == 201:
        xml = etree.fromstring(response.text)
        links = [t for t in xml.findall(link_tag) if t.get('rel') == 'self']
        if links:
            return links[0].get('href')
        raise ValueError('Malformed album response')
    else:
        raise ValueError('Failed to create album')


def delete_album(album_url, settings):
    access_token, token_type = get_token(settings)
    headers = {
        'GData-Version': '2',
        'Authorization': '%s %s' % (token_type, access_token),
        'MIME-version': '1.0',
        'If-Match': '*'
    }
    response = requests.delete(album_url, headers=headers)
    if response.status_code != 200:
        raise ValueError('Failed to delete album')


def clear_album(album_url, settings):
    """
    Removes all photos from an album
    """
    access_token, token_type = get_token(settings)
    response = requests.get(album_url, headers={
        'GData-Version': '2',
        'Authorization': '%s %s' % (token_type, access_token),
        'MIME-version': '1.0',
    })
    if response.status_code != 200:
        raise ValueError('Error reading album')
    xml = etree.fromstring(response.text)
    groups = xml.findall('{http://search.yahoo.com/mrss/}group')
    # There should only be one group... but oh well
    for group in groups:
        while group:  # While it has children, remove it
            group.remove(group[0])
    empty_album = etree.tostring(xml)
    response = requests.put(album_url, data=empty_album, headers={
        'GData-Version': '2',
        'Authorization': '%s %s' % (token_type, access_token),
        'MIME-version': '1.0',
        'Content-length': str(len(empty_album)),
        'Content-Type': 'application/atom+xml; charset=UTF-8',
        'If-Match': '*'
    })
    if response.status_code > 300:
        raise ValueError('Error updating album')
