# Photolog Modernization Strategy

## Executive Summary

This document outlines a phased approach to modernize the Photolog project from legacy tools and dependencies to current best practices. The strategy is designed as a series of small, deployable steps that maintain functionality while reducing technical debt.

**Current State**:
- Framework: Flask 2.2.3 (API & Web), Python 3.10
- Dependency Management: setup.py + requirements.txt (mixed approaches)
- Testing: Minimal (only basic DB unit tests)
- Dependencies: Mix of old and new versions; some are 5+ years outdated
- Deployment: Manual/unclear

**Target State**:
- Framework: Flask 2.2.3+ (or FastAPI alternative if desired)
- Python: 3.12+ (latest stable)
- Dependency Management: uv + pyproject.toml (modern standard)
- Testing: Comprehensive test suite (unit, integration, API tests)
- Dependencies: Latest stable versions
- Deployment: Clear, automated strategy

**Key Principles**:
1. **Incremental**: Each PR is independently deployable
2. **Tested**: Each step includes tests to ensure functionality
3. **Backwards Compatible**: Early steps don't break existing deployments
4. **Risk Isolated**: Changes are scoped to minimize blast radius

---

## Current State Analysis

### Framework & Language
- **Flask Version**: 2.2.3 (modern, well-maintained)
- **Python**: 3.10.12 (in venv, likely not declared in setup.py)
- **Setup Method**: `setup.py` with `install_requires` (deprecated in PEP 517/518)
- **Requirements**: `requirements.txt` with pinned versions (good)

### Critical Outdated Dependencies
| Package | Current | Latest | Status |
|---------|---------|--------|--------|
| Flask | 0.10.1 (setup.py) / 2.2.3 (requirements.txt) | 3.0+ | **Setup.py outdated** |
| Pillow | 3.0.0 | 11.0+ | 8 years old |
| boto | 2.38.0 | N/A (deprecated) | **Critical: Use boto3** |
| PyYAML | 3.11 / 6.0 | 6.0+ | **Fixed in requirements.txt** |
| ExifRead | 2.1.2 | 2.1.2 | Outdated but stable |

### Testing Status
- **Current**: Basic DB unit tests (test_db.py, test_jobs.py)
- **Missing**: API endpoint tests, integration tests, fixtures
- **Framework**: unittest (can be enhanced with pytest)

### Deployment Status
- **API**: `start_api` entry point
- **Queue**: `start_queue` entry point
- **Web**: `start_web` entry point
- **Unknown**: How these are currently deployed/orchestrated

---

## Migration Path: 4 Phases

Each phase results in a PR that can be deployed independently.

### Phase 1: Add Comprehensive Test Suite
**Goal**: Establish testing foundation  
**Effort**: Medium (1-2 days)  
**Risk**: Low (test-only, no production changes)  
**Deployment**: Non-blocking (can run in parallel with services)

**Changes**:
1. Add pytest & pytest-cov as dev dependencies (in requirements-dev.txt)
2. Add fixtures for common test setup
3. Add API endpoint tests (mocking where needed)
4. Add integration tests for queue processing
5. Document test running and coverage expectations
6. Add test GitHub Actions workflow

**Files to Create/Modify**:
- `requirements-dev.txt` - dev dependencies
- `tests/conftest.py` - pytest fixtures
- `tests/test_api.py` - API endpoint tests
- `tests/test_api_integration.py` - API + DB integration
- `tests/test_queue.py` - Queue job processing tests
- `.github/workflows/test.yml` - CI pipeline

**Success Criteria**:
- All endpoints have test coverage
- Tests can run in CI/CD
- Coverage > 70% for core API
- No changes to production code

**Deployment Strategy**: 
- Merge to master
- Run tests in CI but don't block deploys yet
- Validate tests pass in staging

**PR Checklist**:
- [ ] `pytest` runs successfully locally
- [ ] Coverage report generated
- [ ] GitHub Actions workflow passes
- [ ] Tests document expected API behavior

---

### Phase 2: Migrate to Modern Dependency Management (uv + pyproject.toml)
**Goal**: Use modern Python packaging standards  
**Effort**: Medium (1 day)  
**Risk**: Medium (dependency resolution; can affect runtime)  
**Deployment**: Requires testing in staging before production

**Changes**:
1. Install `uv` tooling
2. Create `pyproject.toml` with modern metadata
3. Keep `requirements.txt` for now (for safety, deploy current pinned versions)
4. Document uv workflow (install, add, lock)
5. Create `requirements-dev.txt` with test dependencies

**Files to Create/Modify**:
- `pyproject.toml` - metadata, dependencies, build info
- `requirements-dev.txt` - development tools (pytest, black, ruff)
- `.github/workflows/lock.yml` - auto-update lock file
- `Makefile` or `Justfile` - common commands (if desired)

**pyproject.toml Structure**:
```toml
[project]
name = "photolog"
version = "0.1"
description = "Personal photo management solution"
requires-python = ">=3.10"
dependencies = [
    "Flask==2.2.3",
    "piexif==1.0.2",
    "flickrapi==2.1.2",
    "boto==2.38.0",
    "PyYAML==6.0",
    "Pillow==3.0.0",
    "ExifRead==2.1.2",
    "Flask-Login==0.6.2",
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.0",
    "pytest-cov==4.1.0",
    "black==23.7.0",
    "ruff==0.0.280",
]

[project.scripts]
start_api = "photolog.api.main:start"
start_queue = "photolog.queue.main:start"
start_web = "photolog.web.main:start"
upload2photolog = "photolog.tools.uploader:run"
prep_folder = "photolog.tools.prep_folder:run"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Success Criteria**:
- `uv pip install -e .` works
- All entry points registered and callable
- Tests still pass
- Same dependency versions as before (no accidental upgrades)

**Deployment Strategy**:
- Test locally with uv
- Verify in staging environment
- Keep old setup.py for backwards compatibility during transition
- Deploy to production with same pinned versions

**PR Checklist**:
- [ ] `pyproject.toml` is valid (check with build tools)
- [ ] `uv pip install -e .` installs without errors
- [ ] All entry points callable
- [ ] Tests pass
- [ ] requirements.txt versions match pyproject.toml

---

### Phase 3: Upgrade Dependencies & Python Version
**Goal**: Modernize to Python 3.12, latest stable dependencies  
**Effort**: Medium-High (2-3 days due to testing)  
**Risk**: Medium-High (breaking changes possible; thorough testing required)  
**Deployment**: Staged rollout recommended

**Changes**:
1. Upgrade Python 3.10 → 3.12 (update pyproject.toml, venv, CI)
2. Upgrade boto 2.38 → boto3 3.26+ (API changes, needs testing)
3. Upgrade Pillow 3.0.0 → 11.0+ (likely breaking changes)
4. Verify Flickr/GPhotos APIs work with new versions
5. Test S3 operations with boto3
6. Update requirements with new versions

**Critical Changes**:
- **boto → boto3**: Complete API change; S3 code will need refactoring
  - Recommended approach: Create wrapper service layer (`services/s3_v3.py`)
  - Test against staging S3 bucket
  - Migrate old code gradually
  
- **Pillow 3.0 → 11.0**: May have breaking changes in image operations
  - Review thumbnail generation code
  - Test with sample images
  - Verify EXIF data handling

**Files to Modify**:
- `pyproject.toml` - update Python requirement and versions
- `photolog/services/s3.py` - refactor to boto3 (or create wrapper)
- `.github/workflows/test.yml` - test on Python 3.12
- `tests/` - ensure all tests pass on new versions

**Success Criteria**:
- Tests pass on Python 3.12
- All services (S3, Flickr, GPhotos) functional in staging
- No security warnings in dependency scan
- Performance: no regression in upload/processing speed

**Deployment Strategy**:
- Test extensively in staging environment first
- Deploy to production gradually (canary if possible)
- Monitor for errors post-deploy
- Keep rollback plan ready (easy: pin versions back)

**PR Checklist**:
- [ ] Tests pass on Python 3.12
- [ ] boto3 migration complete and tested
- [ ] Pillow upgrade tested with sample media
- [ ] All services tested in staging
- [ ] Security vulnerabilities checked (`pip audit`)
- [ ] Performance baseline compared

**Note on boto3 Migration**:
```python
# Old (boto):
from boto.s3.connection import S3Connection
conn = S3Connection(aws_access_key_id, aws_secret_access_key)

# New (boto3):
import boto3
s3 = boto3.client('s3', 
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key
)
s3.put_object(Bucket=bucket, Key=key, Body=data)
```

---

### Phase 4: Document Deployment Strategy & Final Polish
**Goal**: Clear runbook for production deployment  
**Effort**: Low-Medium (1 day)  
**Risk**: Low (documentation only)  
**Deployment**: Non-blocking

**Changes**:
1. Create DEPLOYMENT.md with runbook
2. Add Docker files (optional but recommended)
3. Add health checks / monitoring guidance
4. Clean up setup.py (can remove if no longer needed)
5. Update README with current version info

**DEPLOYMENT.md Contents**:
- Local development setup (using uv)
- Running each service locally (API, queue, web)
- Production deployment via Supervisor/Nginx
  - Supervisor config (autorestart, logging)
  - Nginx reverse proxy config
  - Health check endpoints
- Secrets management (environment variables)
- Monitoring logs at `/logs/` directory
- Graceful restarts and rollback procedures
- Troubleshooting guide for common issues

**Example Supervisor Config** (updated for modern setup):
```ini
[program:upload_api]
command=/home/jj/sites/photos.isgeek.net/venv/bin/gunicorn photolog.api.main:app -b 127.0.0.1:4002
directory=/home/jj/sites/photos.isgeek.net/
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/jj/sites/photos.isgeek.net/logs/upload_api.log
user=jj
environment=SETTINGS=/home/jj/sites/photos.isgeek.net/settings.conf,PYTHONUNBUFFERED=1

# Add health check monitoring
stopsignal=TERM
stopasgroup=true
```

**Optional Enhancements**:
- Dockerfile for containerized deployment
- docker-compose.yml for local dev
- systemd service files for Linux deployments
- GitHub Actions workflow for auto-deployment

**Success Criteria**:
- New developer can set up project in <30 minutes
- Production deployment is documented and repeatable
- All services can be monitored/debugged

**Deployment Strategy**: 
- Merge documentation changes anytime
- Optional: create release version tags

**PR Checklist**:
- [ ] DEPLOYMENT.md is complete and tested
- [ ] A new developer tested the setup guide
- [ ] Docker builds successfully (if included)
- [ ] Entry points and config validated

---

## Phase Timeline & Resource Planning

| Phase | Duration | Complexity | Blocking | Notes |
|-------|----------|-----------|----------|-------|
| 1: Testing | 1-2 days | Medium | No | Safe to merge anytime |
| 2: Packaging | 1 day | Medium | No | Backwards compatible |
| 3: Upgrade | 2-3 days | High | Yes | Needs staging test |
| 4: Deployment | 1 day | Low | No | Documentation |
| **Total** | **5-7 days** | **Medium** | **1 phase** | **1-2 week sprint** |

---

## Risk Mitigation

### Phase 1 (Testing)
- **Risk**: Tests may reveal bugs → Code bugs get exposed
- **Mitigation**: Fix bugs in same PR or separate bug-fix PR before merge
- **Rollback**: N/A (test-only)

### Phase 2 (Packaging)
- **Risk**: Dependency resolution fails → Services won't install
- **Mitigation**: Test in CI and staging; keep old setup.py as fallback
- **Rollback**: Keep old requirements.txt, revert pyproject.toml

### Phase 3 (Upgrade)
- **Risk**: Breaking changes in boto/Pillow → Features break
- **Mitigation**: Comprehensive testing in staging; monitor S3/image ops closely
- **Rollback**: Pin versions back in pyproject.toml; deploy again

### Phase 4 (Deployment)
- **Risk**: Documentation is incomplete → Hard to troubleshoot
- **Mitigation**: Have team member test runbook; iterate
- **Rollback**: N/A (documentation-only)

---

## Success Metrics

After all phases complete, you should have:

✅ **Testing**:
- API endpoint test coverage > 80%
- Integration tests for all services
- CI/CD pipeline runs on every push

✅ **Modernization**:
- Python 3.12 (latest stable)
- All dependencies on latest stable versions
- No security vulnerabilities (pip audit clean)
- Build/packaging using industry standard tools

✅ **Deployment**:
- New developers can set up in <30 minutes
- Clear runbook for production deployment
- Monitoring/observability guidance
- Rollback procedures documented

✅ **Code Quality**:
- Linting/formatting enforced (ruff, black)
- Type hints (optional, Phase 5)
- Clean git history with meaningful commits

---

## Optional Future Phases (Phase 5+)

These can be considered after core modernization:

### Phase 5: Type Hints & Static Analysis
- Add mypy for type checking
- Add type hints to core functions
- Catch bugs earlier

### Phase 6: Code Cleanup
- Use ruff/black for consistent formatting
- Remove dead code
- Refactor for readability

### Phase 7: Framework Modernization
- Consider FastAPI if API performance/features needed
- Consider async processing (Celery, RQ)
- Consider GraphQL API (optional)

### Phase 8: Observability
- Add structured logging
- Add metrics/monitoring
- Add distributed tracing

---

## Implementation Checklist

Use this as you work through each phase:

### Phase 1: Testing
- [ ] Create `tests/conftest.py` with fixtures
- [ ] Create `tests/test_api.py` with endpoint tests
- [ ] Create `tests/test_api_integration.py` with DB tests
- [ ] Create `tests/test_queue.py` with job tests
- [ ] Create `.github/workflows/test.yml` CI pipeline
- [ ] Verify `pytest` runs locally
- [ ] Verify CI passes in GitHub
- [ ] Create PR #1 with tests

### Phase 2: Packaging
- [ ] Create `pyproject.toml` with dependencies
- [ ] Create `requirements-dev.txt` with dev tools
- [ ] Test `uv pip install -e .`
- [ ] Verify all entry points work
- [ ] Run tests again to ensure nothing broke
- [ ] Create PR #2 with packaging changes

### Phase 3: Upgrade
- [ ] Update `pyproject.toml` Python version
- [ ] Create `services/s3_v3.py` wrapper for boto3
- [ ] Refactor boto calls to boto3
- [ ] Update Pillow usage if needed
- [ ] Test in staging environment
- [ ] Run full test suite
- [ ] Test S3 operations manually
- [ ] Test Flickr/GPhotos operations
- [ ] Create PR #3 with upgrades

### Phase 4: Deployment
**URGENT: Fix Security Issue First**
- [ ] Create `.env.template` with all required secrets
- [ ] Remove secrets from `settings.conf` in deployment repo
- [ ] Add `.env` to `.gitignore`
- [ ] Update Fabric/startup scripts to load `.env`
- [ ] Document how to set secrets in production

**Then proceed with documentation:**
- [ ] Create `DEPLOYMENT.md` runbook (Supervisor + Nginx focused)
- [ ] Test runbook with clean checkout
- [ ] Document Supervisor health checks
- [ ] Create optional `Dockerfile` (non-blocking)
- [ ] Create optional `docker-compose.yml` (non-blocking)
- [ ] Update `README.md` with Python version, modern setup info
- [ ] Create PR #4 with documentation

---

## References & Tools

**Key Tools**:
- **uv**: https://github.com/astral-sh/uv (fast package installer)
- **pytest**: https://pytest.org/ (testing framework)
- **boto3**: https://boto3.amazonaws.com/ (AWS SDK)

**Reading**:
- PEP 517: https://www.python.org/dev/peps/pep-0517/ (Python packaging)
- PEP 518: https://www.python.org/dev/peps/pep-0518/ (pyproject.toml)
- Flask 2.x migration: https://flask.palletsprojects.com/en/2.3.x/changes/

**Commands**:
```bash
# Install uv
pip install uv

# Create virtual environment with uv
uv venv

# Install dependencies
uv pip install -e .
uv pip install -r requirements-dev.txt

# Run tests
pytest
pytest --cov=photolog

# Check for security issues
pip audit

# Format code
black photolog/ tests/

# Lint code
ruff check photolog/ tests/
```

---

## Current Deployment Architecture

From the `photos.isgeek.net` deployment repo, the current setup is:

**Process Management**: Supervisor (supervisor.isgeek.net)
- **upload_api**: `gunicorn photolog.api.main:app -b 127.0.0.1:4002`
- **process_queue**: Direct start_queue executable
- **webend**: `gunicorn photolog.web.main:app -b 127.0.0.1:4000`

**Web Server**: Nginx (reverse proxy)
- `photos.isgeek.net` → web (port 4000, HTTP Basic Auth)
- `upload_photos.isgeek.net` → API (port 4002, no auth at nginx level)
- Client max upload size: 40MB

**Fabric Deployment**: `fab update` runs:
1. `git pull` in `/home/jj/sites/Photolog/`
2. `supervisorctl restart all`

**Storage**:
- SQLite database: `/home/jj/sites/photos.isgeek.net/photos.db`
- Upload folder: `/home/jj/sites/photos.isgeek.net/media/`
- Logs: `/home/jj/sites/photos.isgeek.net/logs/`

**🚨 CRITICAL SECURITY ISSUE**: 
Settings file (`settings.conf`) contains live AWS/Flickr/GPhotos credentials and is tracked in git. **This must be fixed immediately** — move to environment variables or secure secrets management before any deployment changes.

---

## Adjusted Deployment Strategy for Phase 4

Given the Supervisor + Nginx setup, Phase 4 should include:

1. **Keep Supervisor/Nginx** (proven, working well)
2. **Secrets Management**: Move credentials from git to environment variables
3. **Graceful Deployment**: Update Fabric script to run tests before restart
4. **Health Checks**: Add endpoints for Nginx to verify service health
5. **Optional Docker**: Provide Dockerfile for modern deployments, but not required

### Phase 4 Sub-Tasks:

**4a: Fix Security Issue** (MUST do first):
- Remove secrets from `settings.conf` 
- Create `.env` template with required variables
- Update Fabric script to source `.env` before starting services
- Document required environment variables

**4b: Add Health Checks** (improves reliability):
- Add `GET /health` endpoint to API and web
- Update Nginx config to use health check endpoints
- Enable Supervisor to restart unhealthy processes

**4c: Improve Deployment** (optional, for future):
- Provide Docker Compose for local dev (mirrors production)
- Provide optional Docker images for production
- Keep current Supervisor setup as primary (don't force Docker)

---

## Questions Answered

✅ **Current Deployment**: Supervisor + Nginx (solid setup)
- Autostart/autorestart configured
- Multiple independent services
- Gunicorn for both API and web

✅ **Database**: SQLite (sufficient; no migration needed unless scaling beyond single-user)

✅ **S3 Bucket**: AWS credentials in settings.conf — can test boto3 migration against live bucket

✅ **Monitoring**: Logs in `/home/jj/sites/photos.isgeek.net/logs/` (local only; optional: add Sentry/DataDog)

✅ **Load**: Single-user app, modest load; no scaling concerns now

---

## Next Steps

1. Review this plan with team
2. Adjust phases based on priorities/constraints
3. Start with Phase 1 (safest, highest confidence)
4. Track progress in GitHub issues
5. Iterate based on learnings from each phase

**Ready to start Phase 1?** → Create test fixtures and first test file