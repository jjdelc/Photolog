import flickrapi
import flickrapi.shorturl

"""
How to obtain the token:
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
    api.get_access_token(settings.FLICKR_APP_TOKEN)
    uploaded = api.upload(
        filename=filename,
        tags=tags,
        is_public=0,
        is_family=0,
        is_friend=0,
        title=title,
    )
    if dict(uploaded.items()).get('stat') == 'ok':
        photo_id = list(uploaded[0].iter())[0].text
        return flickrapi.shorturl.url(photo_id), photo_id
    return None, None
