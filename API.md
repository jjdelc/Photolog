# Photolog API Documentation

## Overview

Photolog API is a Flask-based REST API for managing photo uploads. It uses an MD5-hashed secret key for authentication and queues uploaded files for async processing.

**Framework**: Flask 2.2.3  
**Python Version**: Python 3.10 (current runtime)  
**Entry Point**: `photolog.api.main:start`

---

## Authentication

All API endpoints require authentication via the `X-PHOTOLOG-SECRET` header.

**Header**: `X-PHOTOLOG-SECRET`  
**Value**: MD5 hash of the `API_SECRET` configured in settings  

**Example**:
```bash
curl -H "X-PHOTOLOG-SECRET: $(echo -n 'your_secret' | md5sum | cut -d' ' -f1)" http://localhost:5000/photos/
```

---

## Endpoints

### 1. Get Photos Queue Status
**Endpoint**: `GET /photos/`  
**Authentication**: Required  
**Description**: Returns the current photos in the processing queue

**Response**:
```json
{
  "last": [
    {
      "type": "upload",
      "key": "uuid-hex-string",
      "filename": "photo-crc.jpg",
      "tags": ["tag1", "tag2"],
      "original_filename": "photo.jpg",
      "metadata_filename": "metadata-crc.json",
      "uploaded_at": "2023-03-21T10:30:00.000000",
      "target_date": "2023-03-21",
      "step": "upload_and_store",
      "data": {},
      "attempt": 0,
      "skip": [],
      "batch_id": "batch-uuid",
      "is_last": false
    }
  ]
}
```

**Status Code**: `200 OK`

---

### 2. Create Upload Batch
**Endpoint**: `POST /photos/batch/`  
**Authentication**: Required  
**Description**: Creates a new upload batch. Batches group multiple photo uploads together for coordinated processing.

**Request**: No body required

**Response**:
```json
{
  "batch_id": "uuid-hex-string"
}
```

**Status Code**: `201 Created`

**Notes**:
- Returns a batch ID that should be included in subsequent photo uploads
- Useful for grouping related uploads together
- Enables transactional handling of multiple photos

---

### 3. Finish Upload Batch
**Endpoint**: `DELETE /photos/batch/<string:batch_id>/`  
**Authentication**: Required  
**Parameters**:
- `batch_id` (path): The batch ID returned from batch creation

**Description**: Marks a batch as complete. Signals that all photos for this batch have been uploaded.

**Response**: No body (empty response)  
**Status Code**: `204 No Content`

**Notes**:
- Called after all photos in a batch have been uploaded
- Allows the processing queue to know when a batch is fully received
- Enables optimized batch processing

---

### 4. Verify Photo Existence
**Endpoint**: `GET /photos/verify/`  
**Authentication**: Required  
**Query Parameters**:
- `filename` (string): The filename to check
- `checksum` (string): The file checksum (CRC32) to verify

**Description**: Checks if a photo with the given filename and checksum already exists in the system.

**Response**: No body

**Status Codes**:
- `204 No Content` - Photo exists in the database
- `404 Not Found` - Photo does not exist

**Notes**:
- Used for deduplication checks before uploading
- Prevents duplicate uploads of the same file
- Client-side optimization to skip redundant uploads

---

### 5. Upload Photo
**Endpoint**: `POST /photos/`  
**Authentication**: Required  
**Content-Type**: `multipart/form-data`

**Description**: Uploads a photo and optional metadata file. Files are temporarily stored locally and queued for async processing.

**Form Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `photo_file` | file | Yes | The photo file to upload (JPG, PNG, GIF, WebP, RAW, MP4, AVI, OGV, MPG, MPEG, MKV) |
| `metadata_file` | file | No | Optional metadata file (sidecar file with additional info) |
| `batch_id` | string | No | Batch ID from `/photos/batch/` endpoint |
| `tags` | string | No | Comma-separated tags (e.g., "travel,vacation,2023") |
| `skip` | string | No | Comma-separated service names to skip (e.g., "gphotos,flickr") |
| `target_date` | string | No | Date to associate with the photo (format: YYYY-MM-DD) |
| `is_last` | boolean | No | If true, indicates this is the last photo in a batch |

**Allowed File Extensions**:
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- Raw: `.arw`, `.raw`
- Video: `.mp4`, `.avi`, `.ogv`, `.mpg`, `.mpeg`, `.mkv`

**Response**: No body  
**Status Code**: `202 Accepted`

**Error Responses**:

```json
{
  "error": "Must send an `photo_file`"
}
```
**Status Code**: `400 Bad Request` - Missing photo_file

```json
{
  "error": "Invalid file extension"
}
```
**Status Code**: `400 Bad Request` - File type not allowed

```json
{
  "error": "Invalid request"
}
```
**Status Code**: `400 Bad Request` - Authentication failed

**Notes**:
- Files are renamed with CRC32 checksum appended for uniqueness
- Max upload size: 64MB (configured in `app.config['MAX_CONTENT_LENGTH']`)
- Processing happens asynchronously via the queue
- Tags and skip parameters are automatically slugified (lowercased, stripped)
- Metadata files follow the same file existence checks as photo files

**Example Usage**:
```bash
# Create a batch
BATCH_ID=$(curl -X POST \
  -H "X-PHOTOLOG-SECRET: your_secret_hash" \
  http://localhost:5000/photos/batch/ | jq -r '.batch_id')

# Upload a photo
curl -X POST \
  -H "X-PHOTOLOG-SECRET: your_secret_hash" \
  -F "photo_file=@DSC_0001.jpg" \
  -F "tags=vacation,beach" \
  -F "batch_id=$BATCH_ID" \
  http://localhost:5000/photos/

# Upload another photo with is_last flag
curl -X POST \
  -H "X-PHOTOLOG-SECRET: your_secret_hash" \
  -F "photo_file=@DSC_0002.jpg" \
  -F "tags=vacation,beach" \
  -F "batch_id=$BATCH_ID" \
  -F "is_last=true" \
  http://localhost:5000/photos/

# Finish the batch
curl -X DELETE \
  -H "X-PHOTOLOG-SECRET: your_secret_hash" \
  http://localhost:5000/photos/batch/$BATCH_ID/
```

---

## Configuration

The API requires a YAML configuration file specified via the `SETTINGS` environment variable.

**Required Settings**:
```yaml
# File storage
UPLOAD_FOLDER: /path/to/temp/uploads
DB_FILE: /path/to/photos.db

# API authentication
API_SECRET: your_secret_string

# AWS S3 (for storage)
S3_ACCESS_KEY: your_access_key
S3_SECRET_KEY: your_secret_key
S3_BUCKET: your_bucket_name

# Flickr (optional service)
FLICKR_API_KEY: your_api_key
FLICKR_API_SECRET: your_api_secret
FLICKR_APP_TOKEN: your_app_token
FLICKR_APP_SECRET: your_app_secret

# Google Photos (optional service)
GPHOTOS_CLIENT_ID: your_client_id
GPHOTOS_SECRET: your_secret
GPHOTOS_ACCESS_CODE: your_access_code

# Web interface
DOMAIN: https://your-domain.com
AUTH_ME: https://your-domain.com  # For Indieauth
SECRET_KEY: your_session_secret
```

---

## Running the API

```bash
export SETTINGS=/path/to/settings.yaml
python -m photolog.api.main
# or using entry point:
start_api
```

The API will start on `http://localhost:5000/` by default.

---

## Processing Queue

After upload (`202 Accepted`), files are queued for async processing with these steps:

1. **upload_and_store**: Transfer to permanent storage (S3)
2. **thumbnail_generation**: Create thumbnail and web-sized versions
3. **service_upload**: Upload to configured services (Flickr, Google Photos)
4. **cleanup**: Remove temporary local files

Each job record stores:
- `attempt`: Number of retry attempts (max 3)
- `step`: Current processing step
- `skip`: Services to skip for this upload
- `data`: Additional processing parameters
- `batch_id`: Associated batch for coordinated processing
