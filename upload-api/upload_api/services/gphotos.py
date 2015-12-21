import os
from time import time
from urllib.parse import urlencode, urlunparse

import requests
from upload_api.db import TokensDB
from upload_api import queue_logger as log

"""
To obtain a bearer token you must:
Go to gogole developer console and create a new project
Grant "New Credentials" for an "Oauth client ID"
*important*
    The redirect_uri has to be "urn:ietf:wg:oauth:2.0:oob"
    scope has to point to https%3A%2F%2Fpicasaweb.google.com%2Fdata%2F

Construct the following URL and paste into browser:
https://accounts.google.com/o/oauth2/v2/auth?
    scope=https%3A%2F%2Fpicasaweb.google.com%2Fdata%2F
    redirect_uri=urn:ietf:wg:oauth:2.0:oob&
    response_type=code&
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
EXCHANGE_TOKEN_ENDPOINT = 'https://www.googleapis.com/oauth2/v4/token'
OOB_URL = "urn:ietf:wg:oauth:2.0:oob"
CODE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
PICASA_ENDPOINT = "https://picasaweb.google.com/data/feed/api/user/default"


def get_access_code(client_id):
    """
    Use this function to discover the URL you need to visit to get your
     one off code to exchange for an access token.
    """
    params = {
        'redirect_uri': "urn:ietf:wg:oauth:2.0:oob",
        'scope': "https://picasaweb.google.com/data/",
        'response_type': 'code',
        'client_id': client_id,
        'access_type': 'offline'
    }
    return urlunparse([
        'https',
        'accounts.google.com',
        '/o/oauth2/v2/auth',
        '',
        urlencode(params),
        ''
    ])


def exchange_token(tokens, client_id, secret, code):
    response = requests.post(EXCHANGE_TOKEN_ENDPOINT, data={
        'code': code,
        'client_id': client_id,
        'client_secret': secret,
        'grant_type': 'authorization_code',
        'redirect_uri': OOB_URL,
        'expires_in': 0
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
        raise ValueError('Error negotiating %s token: %s' % (SERVICE, response))


def refresh_access_token(tokens, client_id, secret, refresh_token):
    response = requests.post(EXCHANGE_TOKEN_ENDPOINT, data={
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': secret,
        'grant_type': 'refresh_token'
    }).json()
    tokens.update_token(
        SERVICE,
        response['access_token'],
        response['token_type'],
        time() + response['expires_in']
    )
    if 'access_token' in response:
        return response['access_token']
    else:
        # Some error
        raise ValueError('Error refreshing %s token: %s' % (SERVICE, response))


def do_upload(settings, filename, name, access_token, token_type):
    headers = {
        'GData-Version': 2,
        'Slug': name,
        'Content-Type': 'image/jpeg',
        'Authorization': '%s %s' % (token_type, access_token),
        'Content-Length': os.stat(filename).st_size,
        'MIME-version': '1.0'
    }
    session = requests.Session()
    # Uploads to "Drop Box" album
    request = requests.Request('POST', PICASA_ENDPOINT,
        data=open(filename, 'rb'), headers=headers)
    response = session.send(request.prepare())
    return response.text


def upload(settings, filename, name):
    """
    Uploads the given file to Google Photos and returns its url
    """
    tokens = TokensDB(settings.DB_FILE)
    token = tokens.get_token(SERVICE)
    token_type = 'Bearer'
    if token:
        log.info('Attempting to use existing token')
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
        access_token = exchange_token(tokens,
            settings.GPHOTOS_CLIENT_ID,
            settings.GPHOTOS_SECRET,
            settings.GPHOTOS_ACCESS_CODE)
        log.info("Token obtained")

    return do_upload(settings, filename, name, access_token, token_type)
