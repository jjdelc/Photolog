import flickrapi
import flickrapi.shorturl

"""

Need to create an app type "Desktop application"
How to obtain the token:
Create an app from http://www.flickr.com/services/api/keys/ and get keys and
secret, Then:

import flickrapi
api = flickrapi.FlickrAPI(settings.FLICKR_API_KEY, settings.FLICKR_API_SECRET)
api.get_request_token(oauth_callback='oob')
auth_url = api.auth_url(perms='write')
print(auth_url)
# Pasete this in browser and put in settings
https://www.flickr.com/services/oauth/authorize?oauth_token=xxxxxx&perms=write
"""


def upload(settings, title, filename, tags):
    """
    Uploads the given file to Flickr and returns its url
    """
    api = flickrapi.FlickrAPI(settings.FLICKR_API_KEY,
        settings.FLICKR_API_SECRET)
    if api.token_valid(perms='write'):
        api.get_access_token(settings.FLICKR_APP_TOKEN)
        uploaded = api.upload(
            filename=filename,
            tags=' '.join(tags),
            is_public=0,
            is_family=0,
            is_friend=0,
            title=title,
        )
        # Understanding the response
        # https://secure.flickr.com/services/api/upload.api.html
        # https://secure.flickr.com/services/api/response.rest.html
        stat = dict(uploaded.items()).get('stat')
        if stat == 'ok':
            photo_id = uploaded.find('photoid').text
            return flickrapi.shorturl.url(photo_id), photo_id
        raise ValueError('Error uploading photo to Flickr')
    else:
        raise ValueError('Invalid Flickr API token')
