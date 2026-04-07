# Photolog Migration Plan

## Current State

| Aspect | Current |
|--------|---------|
| Framework | Flask 0.10.1 (released 2014) |
| Python | 3.6 |
| Packaging | `setup.py` (legacy) |
| AWS SDK | `boto==2.38.0` (superseded by boto3 in 2015) |
| Image lib | `Pillow==3.0.0` (2015) |
| Auth | MD5-hashed shared secret; Indieauth for web |
| Deployment | Presumably Supervisor + Nginx (see memory notes) |
| Tests | `unittest`, partial coverage, no CI |

## Goals

1. Full test coverage so every change is validated before deploy
2. Modern packaging (`uv` + `pyproject.toml`)
3. Recent Python version (3.12+)
4. Up-to-date, maintained dependencies
5. Deployment strategy confirmed adequate (or improved)

---

## Strategy: Incremental, Always-Deployable Steps

Each step below is a standalone branch that can be deployed independently. Later steps build on earlier ones but are not blocked on them. Steps are ordered to de-risk the most impactful changes first.

---

## Step 1 — Baseline Test Suite (deploy this first)

**Goal:** Establish a passing test suite against the current codebase so every 
subsequent step has a safety net.

**Why first:** Without tests, every later change is flying blind. This step adds
no functional change, so it's safe to deploy immediately (the new test files are
not executed in production).

**Current Test Coverage:**

Existing test suite in `tests/` is minimal:
- `test_db.py`: 6 tests covering `TagManager` and `PictureManager` basic operations (add, update, find, file_exists)
- `test_jobs.py`: 3 tests covering `TagDayJob`, `MassTagJob`, `EditDatesJob` (DB-only jobs, no external services)
- Test framework: `unittest.TestCase` (stdlib), no pytest, no mocking (all tests use real SQLite files)
- No test runner config (no `Makefile`, `tox.ini`, `conftest.py`)

**Coverage Gaps (what needs tests):**

| Component | Status | Notes |
|-----------|--------|-------|
| **API endpoints** | ✅ Done | `tests/test_api.py` — all routes covered |
| **Auth** | ✅ Done | valid/invalid/missing header cases in `test_api.py` |
| **File upload** | ✅ Done | happy path, invalid extension, auth rejection, with metadata/target_date; duplicate detection not yet tested |
| **SqliteQueue** | ✅ Done | `tests/test_squeue.py` — append, popleft, peek, bad_jobs, retry, purge, __len__ |
| **Job retry (unit)** | ✅ Done | `test_retry_jobs_moves_bad_to_queue` in `test_squeue.py` |
| **tools/uploader** | ✅ Done (bonus) | `tests/tools/test_uploader.py` — chunks, validate_file, handle_file, upload_directories |
| **tools/prep_folder** | ✅ Done (bonus) | `tests/tools/test_prep_folder.py` |
| **Makefile** | ✅ Done | `make test` runs full suite |
| **ImageJob** | ❌ Missing | Full pipeline: upload → EXIF → thumbnails → S3 → Flickr → GPhotos → cleanup |
| **VideoJob** | ❌ Missing | Full pipeline: upload → thumbnail → EXIF → S3 video + thumbs → GPhotos → cleanup |
| **RawFileJob** | ❌ Missing | Full pipeline: upload → S3 → borrow sister JPEG thumbs → cleanup |
| **ChangeDateJob** | ❌ Missing | DB-only job: find by date → change all to new date |
| **Job retry (integration)** | ❌ Missing | End-to-end: job fails → lands in `bad_jobs` → `retry_jobs()` re-queues |
| **DB methods** | ⚠️ Partial | `by_keys` added; still missing: `TagManager` (for_picture, tagged_pictures, total_for_tags), `PictureManager` (recent, get_all, count, nav, change_date, edit_attribute), `DB` (get_years/months/days, get_pictures_for_year, total_pictures), `TokensDB` |

**Work:**

- ✅ Audit existing tests in `tests/` — documented above
- ✅ Add tests for all API endpoints (`tests/test_api.py`)
  - ✅ `POST /photos/` — happy path, auth rejection, unsupported file type, with metadata/target_date
  - ✅ `GET /photos/verify/` — found / not found
  - ✅ `POST /photos/batch/`, `DELETE /photos/batch/<id>/`
  - ✅ Auth error cases (missing header, invalid secret)
  - ❌ `POST /photos/` — duplicate detection (file already exists)
- ✅ Add unit tests for `SqliteQueue` operations (`tests/test_squeue.py`)
- ✅ Add a `Makefile` so tests run with one command
- ❌ Add integration tests for the job queue (enqueue → process → assert DB state)
  - ❌ `ImageJob` full pipeline with mocked S3/Flickr/GPhotos
  - ❌ `VideoJob`, `RawFileJob`
  - ❌ Retry and failure path (job ends up in `bad_jobs`) — integration level
  - ❌ `ChangeDateJob` DB-only pipeline
- ❌ Fill remaining DB method gaps (`TagManager`, `PictureManager`, `TokensDB` coverage)

**Deployable:** Yes — only test files added, no production code changed.

---

## Step 2 — Modernize Packaging (`uv` + `pyproject.toml`)

**Goal:** Replace `setup.py` with `pyproject.toml` managed by `uv`. Remove the committed `venv/` directory.

**Why second:** Packaging is a pre-requisite for cleanly pinning and upgrading dependencies. It touches no runtime logic.

**Work:**

- Add `pyproject.toml` with:
  - `[project]` metadata (name, version, dependencies)
  - `[project.scripts]` replacing `setup.py` entry points
  - `requires-python = ">=3.6"` (matches current runtime, upgraded in Step 3)
- Pin exact dependency versions in `uv.lock`
- Add `.python-version` file
- Remove `venv/` from repo, add to `.gitignore`
- Update README with `uv sync` setup instructions
- Update CI to use `uv run`

**Deployable:** Yes — same dependencies, same code, just a different install mechanism. Update deploy scripts to use `uv run` instead of `venv/bin/`.

---

## Step 3 — Upgrade Python to 3.12

**Goal:** Pin Python to 3.12 (current stable), remove any Python 2 compatibility shims.

**Why third:** Python version is a runtime concern; packaging must be modernized first (Step 2) to make this clean.

**Work:**

- Set `requires-python = ">=3.12"` in `pyproject.toml`
- Remove `_dummy_thread` / `_thread` compatibility import in `db.py` (Python 3.12 has `_thread` always)
- Run full test suite (from Step 1) under 3.12 and fix any failures
- Update CI to test on 3.12

**Deployable:** Yes — update server Python version and redeploy.

---

## Step 4 — Upgrade Dependencies

**Goal:** Replace all outdated dependencies with current maintained versions.

**Why fourth:** Python 3.12 (Step 3) may already break old packages, so this step resolves those conflicts. The test suite (Step 1) validates nothing breaks.

**Key upgrades:**

| Old | New | Notes |
|-----|-----|-------|
| `Flask==0.10.1` | `Flask>=3.0` | Major version bump; review `Blueprint`, `before_request` changes |
| `Flask-Login==0.4.0` | `Flask-Login>=0.6` | Minor API differences |
| `boto==2.38.0` | `boto3>=1.34` | Complete API rewrite — see below |
| `Pillow==3.0.0` | `Pillow>=10.0` | Review deprecated APIs |
| `PyYAML==3.11` | `PyYAML>=6.0` | Safe loader required by default |
| `flickrapi==2.1.2` | `flickrapi>=2.4` | Check if maintained; may need replacement |
| `piexif==1.0.2` | `piexif>=1.1` | Or switch to `Pillow` built-in EXIF |
| `ExifRead==2.1.2` | `exifread>=3.0` | |

**boto → boto3 migration** (largest change):
- `s3.py` uses `boto.connect_s3()` — rewrite to use `boto3.client('s3')`
- Multipart upload API is different
- Test thoroughly — S3 is the primary storage

**Work:**

- Upgrade one dependency at a time in a sub-branch
- Run tests after each upgrade
- Update `uv.lock` with final pinned versions

**Deployable:** Yes — functionally equivalent but on maintained libraries.

---

## Step 5 — Security Hardening

**Goal:** Fix known security issues without changing functionality.

**Work:**

- **API secret:** Replace MD5 hash with HMAC-SHA256 (`hmac.compare_digest` for timing-safe comparison)
- **Settings file:** Move secrets to environment variables; keep `settings.conf` for non-secret config. Document which keys must be env vars.
- **CSRF protection:** Add Flask-WTF CSRF tokens to all web forms
- **File upload:** Add MIME type validation alongside extension check
- **SQL queries:** Audit `db.py` for raw string concatenation; use parameterized queries throughout

**Deployable:** Yes — requires updating deploy environment to set env vars, then deploy.

---

## Step 6 — Deployment Review

**Goal:** Confirm Supervisor + Nginx setup is adequate, or improve it.

**Current setup (from memory):** Supervisor manages the three processes (`start_api`, `start_web`, `start_queue`); Nginx as reverse proxy.

**Work:**

- Document current Supervisor and Nginx configs in the repo (e.g. `deploy/supervisor/`, `deploy/nginx/`)
- Evaluate whether current setup still meets needs:
  - Is SQLite sufficient for the expected load? (Single-writer limitation)
  - Is Nginx config current (TLS 1.3, HSTS, etc.)?
  - Are Supervisor configs using the new `uv run` entry points?
- Add a `deploy/README.md` with setup steps
- Optionally: add a `Dockerfile` for local development parity (not required for production if Supervisor works well)

**Deployable:** Yes — documentation and config changes only unless issues found.

---

## Step Order Summary

```
Step 1  →  Tests + CI                (safe, no prod change)
Step 2  →  uv + pyproject.toml      (packaging only)
Step 3  →  Python 3.12              (runtime upgrade)
Step 4  →  Dependency upgrades      (boto3, Flask 3, etc.)
Step 5  →  Security hardening       (secrets, CSRF, HMAC)
Step 6  →  Deployment review        (docs + config)
```

Each step is independently deployable. Steps 2–4 have a natural dependency order (packaging → Python → deps) but each is a clean branch with no half-finished work.

---

## What Is Not In Scope

- Migrating from SQLite to PostgreSQL (significant operational complexity, not needed at current scale)
- Rewriting the queue system (the SQLite queue works; improvement can come later)
- Removing Flickr or Google Photos integrations (that's a feature decision, not a migration concern)
- Breaking API changes (the CLI client is deployed separately and must stay compatible)
