# Photolog API Reference

## Overview

The Photolog Upload API is a Flask application that receives photo uploads and queues them for background processing (S3 upload, Flickr, Google Photos, thumbnail generation).

- **Default port:** 5000
- **Max upload size:** 64 MB
- **Authentication:** MD5-hashed shared secret via `X-PHOTOLOG-SECRET` header

## Authentication

All write endpoints require the `X-PHOTOLOG-SECRET` header set to the MD5 hash of the configured `API_SECRET`.

```
X-PHOTOLOG-SECRET: md5(settings.API_SECRET)
```

## Endpoints

### GET /photos/

Returns recently queued photos.

**Auth required:** No

**Response:** JSON list of recent queue entries.

---

### POST /photos/

Upload a photo or video for processing.

**Auth required:** Yes (`X-PHOTOLOG-SECRET` header or `secret` form field)

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `photo_file` | file | Yes | The photo/video file to upload. Supported image formats: `jpg`, `jpeg`, `png`, `gif`. Video: `mp4`, `avi`, `ogv`, `mpg`, `mpeg`, `mkv`. Raw: `arw`, `raw`. |
| `metadata_file` | file | No | Companion metadata file for videos (e.g. `.THM` thumbnail file from cameras). |
| `tags` | string | No | Comma-separated list of tags to apply to the photo. |
| `skip` | string | No | Comma-separated list of upload targets to skip. Valid values: `flickr`, `gphotos`. |
| `batch_id` | string | No | UUID of an open batch. If provided, groups this upload with others in the same Google Photos album. |
| `is_last` | string | No | Set to `"true"` if this is the last photo in a batch. Triggers batch finalization. |
| `target_date` | string | No | Override the date for this photo. Format: `YYYY-MM-DD`. Useful when EXIF data is missing or wrong. |

**Response:**

```json
{
  "key": "<uuid>",
  "queued": true
}
```

**Error response (duplicate detected):**

```json
{
  "key": "<existing_uuid>",
  "queued": false,
  "reason": "duplicate"
}
```

---

### POST /photos/batch/

Start a new batch upload session. Returns a `batch_id` to use in subsequent `/photos/` uploads.

**Auth required:** Yes (`X-PHOTOLOG-SECRET` header)

**Request body:** None

**Response:**

```json
{
  "batch_id": "<uuid>"
}
```

---

### DELETE /photos/batch/<batch_id>/

Finalize and close a batch. Triggers any pending batch-level processing (e.g. Google Photos album creation).

**Auth required:** Yes (`X-PHOTOLOG-SECRET` header)

**URL Parameters:**

| Parameter | Description |
|-----------|-------------|
| `batch_id` | UUID of the batch to close. |

**Response:**

```json
{
  "closed": true
}
```

---

### GET /photos/verify/

Check whether a file has already been uploaded, by filename and checksum.

**Auth required:** Yes (`X-PHOTOLOG-SECRET` header)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Original filename of the photo. |
| `checksum` | string | Yes | MD5 checksum of the file contents. |

**Response (file exists):**

```json
{
  "exists": true,
  "key": "<uuid>"
}
```

**Response (file not found):**

```json
{
  "exists": false
}
```

---

## Processing Pipeline

After a successful upload, the file is placed in a SQLite-backed job queue. A separate queue worker daemon processes jobs asynchronously.

### Image job steps

1. Read EXIF metadata (date taken, camera, dimensions, orientation)
2. Generate thumbnails at 4 sizes: `thumb` (100px), `medium` (320px), `web` (1200px), `large` (2048px)
3. Upload original and all thumbnails to S3
4. Upload to Flickr (unless skipped)
5. Upload to Google Photos (unless skipped)
6. Write final record to the database

### Video job steps

1. Extract thumbnail frame from center of video using FFmpeg
2. Upload video and thumbnail to S3
3. Upload to Google Photos (unless skipped)
4. Write final record to the database

### Raw file job steps

1. Upload original file to S3
2. Write record to database

### Failure handling

Jobs are retried up to 3 times on failure. After that, the job is moved to the `bad_jobs` table. Failed jobs can be retried or permanently deleted via the web interface at `/jobs/bad/`.

---

## Client Configuration

The `upload2photolog` CLI tool reads `~/.photolog` (YAML):

```yaml
host: https://upload.example.com
secret: <same_value_as_API_SECRET_in_settings.conf>
halt: false   # if true, pause and wait for input on upload failure
```

### CLI usage

```bash
upload2photolog photo1.jpg photo2.jpg some_folder/ \
  --tags "vacation,2024" \
  --skip "flickr" \
  --host "https://upload.example.com"
```

The client:
- Checks each file via `/photos/verify/` before uploading (deduplication)
- Opens a batch before multi-file uploads and closes it when done
- Retries failed uploads up to 3 times
- Automatically detects `.THM` sidecar files for videos

---

## Supported File Types

| Category | Extensions |
|----------|-----------|
| Image | `jpg`, `jpeg`, `png`, `gif` |
| Video | `mp4`, `avi`, `ogv`, `mpg`, `mpeg`, `mkv` |
| Raw | `arw`, `raw` |