#Photolog

This is my personal solution for photo management.

* Simple API server that receives picture uploads
* Simple processing queue that uploads pictures to S3, Flickr and GPhotos
* Basic web interface to browse S3 uploaded files
* Command line client to upload pictures


The idea is that I can upload my photos to a single endpoint and it will
upload them on popular services so I can use their excellent browsing and 
sharing interfaces while I still maintain an original copy on an S3 bucket 
that I control.

The solution consists of 3 main parts:
 * Upload API
 * Processing queue
 * Web interface
 
 
## Upload API
Exposes a single endpoint where to POST the photos. It will queue them for the
processing queue to handle. 
Will temporarily store files in local file system.

## Processing queue
Reads each file record from the queue and generates the thumbnails necessary
for the web interface to display.
Additionally it will upload the original file to S3 and to GPhotos and Flickr.
Will delete the temporary local file when done.

## Web interface
A very basic interface to browse through the uploaded files. This is just to
have a quick view on what's currently backed up.

# Setup

## Settings

You need to provide an environment variable `SETTINGS` that should point to
a Yaml file containing the needed settings:

The Yaml file should have the following keys:

```
UPLOAD_FOLDER: <directory for tmp uploads>
DB_FILE: <Sqlite db file>
API_SECRET: <arbitraty string of your choice>

S3_ACCESS_KEY: <AWS Access>
S3_SECRET_KEY: <AWS Secret>
S3_BUCKET: <Bucket name>

FLICKR_API_KEY: <API KEY>
FLICKR_API_SECRET: <API SECRET>
FLICKR_APP_TOKEN: <APP TOKEN>
FLICKR_APP_SECRET: <APP SECRET>

GPHOTOS_SECRET: <API SECRET>
GPHOTOS_CLIENT_ID: <CLIENT ID>
GPHOTOS_ACCESS_CODE: <PRISTINE ACCESS CODE>


```

### Flickr

To obtain the needed credentials you will need to create an app type 
"Desktop application" here http://www.flickr.com/services/api/keys/.
 That will provide you with `FLICKR_API_KEY` and `FLICKR_API_SECRET`

Then, open your python terminal

> SETTINGS=settings.conf python

```
>>> import os
>>> from upload_api.settings import Settings
>>> settings = Settings.load(os.environ['SETTINGS'])

>>> import flickrapi
>>> api = flickrapi.FlickrAPI(settings.FLICKR_API_KEY, settings.FLICKR_API_SECRET)
>>> api.get_request_token(oauth_callback='oob')
>>> auth_url = api.auth_url(perms='write')
>>> print(auth_url)
# Paste this in browser and put in settings
https://www.flickr.com/services/oauth/authorize?oauth_token=xxxxxx&perms=write
>>> verifier_code = ###-###-###
api.get_access_token(verifier_code)
# Store the following settings
FLICKR_APP_TOKEN = api.flickr_oauth.oauth.client.resource_owner_key
FLICKR_APP_SECRET = api.flickr_oauth.oauth.client.resource_owner_secret
```

### Google

From your Google developer console, create a new project and new credentials
for an "Oauth client ID".

That will provide with `GPHOTOS_SECRET` and `GPHOTOS_CLIENT_ID`

Then, open your python terminal

> SETTINGS=settings.conf python

```
>>> import os
>>> from upload_api.settings import Settings
>>> settings = Settings.load(os.environ['SETTINGS'])
>>> from upload_api.services.gphotos import get_access_code
>>> get_access_code(settings.GPHOTOS_CLIENT_ID)
```

Will print a url of the shape:

> https://accounts.google.com/o/oauth2/v2/auth?scope=https%3A%2F%2Fpicasaweb.google.com%2Fdata%2Fredirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&client_id={{YOUR_CLIENT_ID}}

Paste that in your browser, accept and you will see the app access code. You 
should put that in your `GPHOTOS_ACCESS_CODE` setting. 

# Uploading pictures

You can use the main `upload2photolog` command to get your pictures on your server.
It will handle many things.

## Configuration

The best way to have it ready is to create a file under `~/.photolog` with the 
following:

```
host: <http://upload.host.com>
halt: <boolean>
secret: <same secret from API settings>
```

* host: Should point to the host where the API is installed. Should not include
any path from the API. If you installed it under `photos.domain.com` then you 
should have `http://photos.domain.com`.
* halt: Boolean, if true, the upload command will not break in case of a failed 
upload due bad connection, but will wait for user input to resume or cancel. This 
is very useful when performing huge uploads.
* secret: Same string you used on your API settings configuration, just to prevent
bare HTTP calls from going through and avoid accidents in case you have many
endpoints configured (my case during development)

## Usage

Then, you can use it like so:

> upload2photolog dir1 dir2 file1 file2 --tags 'tag1,tag2' --skip 'google,flickr'

And it will do its thing.

## Raw HTTP usage

Upload a picture to the upload endpoint:
> curl -X POST -F "photo_file=@DSC00647.JPG" -F "secret={{md5(secret)}}" http://localhost:5000/photos/

Use the `tags` field to tag it:
> curl -X POST -F "photo_file=@DSC00647.JPG" -F "secret={{md5(secret)}}" -F "tags=vegas,travel" http://localhost:5000/photos/

Or skip steps of the processing, in case you don't want your phone pictures
uploaded to Gphotos again ("gphotos" or "flickr"):
> curl -X POST -F "photo_file=@DSC00647.JPG" -F "secret={{md5(secret)}}" -F "skip=gphotos" http://localhost:5000/photos/

They will be added to the queue and processed sequentially. Will be available
from your web interface.