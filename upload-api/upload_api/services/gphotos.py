from urllib.parse import urlencode, urlunparse

import requests
from time import time
from upload_api.db import TokensDB

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

code=4/v6xr77ewYqhvHSyW6UJ1w7jKwAzu&
client_id=8819981768.apps.googleusercontent.com&
client_secret=your_client_secret&
redirect_uri=https://oauth2-login-demo.appspot.com/code&
grant_type=authorization_code

"""

SERVICE = 'gphotos'
EXCHANGE_TOKEN_ENDPOINT = 'https://www.googleapis.com/oauth2/v4/token'
OOB_URL = "urn:ietf:wg:oauth:2.0:oob"
CODE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
PICASA_ENDPOINT = "https://picasaweb.google.com/data/feed/api/user/%(user)s/default"


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
        'redirect_uri': OOB_URL
    }).json()
    tokens.save_token(
        SERVICE,
        response['access_token'],
        response['refresh_token'],
        time() + response['expires_in']
    )
    return response['access_token']


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
        response['access_token'],
        time() + response['expires_in']
    )
    return response['access_token']


def do_upload(settings, filename, name, access_token, token_type):
    headers = {
        'GData-Version': 2,
        'Slug': name,
        'Content-Type': 'image/jpeg',
        'Authorization': '%s %s' % (token_type, access_token)

    }
    response = requests.post(PICASA_ENDPOINT % {
        'user': settings.GPHOTOS_USER
    }, files={
        'photo': open(filename, 'rb'),

    }, headers=headers)
    return response


def upload(settings, filename, name):
    """
    Uploads the given file to Google Photos and returns its url
    """
    tokens = TokensDB(settings.DB_FILE)
    token = tokens.get_token(SERVICE)
    access_token = token['access_token']
    if tokens.needs_refresh(SERVICE, access_token):
        access_token = refresh_access_token(tokens,
            settings.GPHOTOS_CLIENT_ID,
            settings.GPHOTOS_SECRET,
            token['refresh_token']
        )
    response = do_upload(filename, token['access_token'], token['token_type'])
    print(response)
    return filename
