#Mediascream

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

You need to provide an environment variable `SETTINGS` that should point to
a Yaml file containing the needed settings:

## Settings

The Yaml file should have the following keys:

```
UPLOAD_FOLDER: <directory for tmp uploads>
DB_FILE: <Sqlite db file>
S3_ACCESS_KEY: <AWS Access>
S3_SECRET_KEY: <AWS Secret>
S3_BUCKET: <Bucket name>

```