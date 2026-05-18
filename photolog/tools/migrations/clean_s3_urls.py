"""
Migration to clean up presigned S3 URLs by removing query parameters.

This strips AWS authentication parameters (AWSAccessKeyId, Signature, Expires)
from stored S3 URLs, replacing them with direct public URLs.

Example:
  Before: https://bucket.s3.amazonaws.com/path?AWSAccessKeyId=...&Signature=...
  After:  https://bucket.s3.amazonaws.com/path
"""

from photolog.db import DB
import os


DB_FILE = os.environ.get("DB_FILE", "photos.db")
URL_FIELDS = ["original", "thumb", "medium", "web", "large"]


def clean_url(url):
    """Remove query parameters from URL if present."""
    if url is None:
        return None
    if "?" in url:
        return url.split("?")[0]
    return url


def migrate(conn):
    total_updated = 0
    total_entries = 0

    for picture in conn.execute("SELECT id, key FROM pictures"):
        pic_id = picture["id"]
        pic_key = picture["key"]
        total_entries += 1

        updated_fields = {}
        needs_update = False

        for field in URL_FIELDS:
            current_url = conn.execute(
                f"SELECT {field} FROM pictures WHERE id=?", [pic_id]
            ).fetchone()[field]

            if current_url:
                cleaned_url = clean_url(current_url)
                if cleaned_url != current_url:
                    updated_fields[field] = cleaned_url
                    needs_update = True
                    print(f"  [{pic_key}] {field}: {current_url[:80]}... -> {cleaned_url}")

        if needs_update:
            total_updated += 1
            print(f"✓ Updated [{pic_key}]")
            for field, cleaned_url in updated_fields.items():
                conn.execute(
                    f"UPDATE pictures SET {field} = ? WHERE id=?",
                    [cleaned_url, pic_id]
                )

    print(f"\nMigration complete!")
    print(f"Total entries processed: {total_entries}")
    print(f"Entries updated: {total_updated}")


if __name__ == "__main__":
    db = DB(DB_FILE)
    with db._get_conn() as conn:
        migrate(conn)
