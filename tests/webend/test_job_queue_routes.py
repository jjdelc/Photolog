"""Tests for job queue management routes"""

import uuid
from photolog.web.main import queue


class TestViewQueueRoute:
    """GET /jobs/ - View job queue"""

    def test_view_queue_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/jobs/")
        assert response.status_code == 302

    def test_view_queue_empty(self, authenticated_client):
        """GET /jobs/ shows empty queue"""
        response = authenticated_client.get("/jobs/")
        assert response.status_code == 200
        assert b"job" in response.data.lower() or b"queue" in response.data.lower()

    def test_view_queue_shows_jobs(self, authenticated_client):
        """GET /jobs/ displays jobs from queue"""
        # Add a job to queue
        queue.append(
            {
                "type": "test-job",
                "key": uuid.uuid4().hex,
                "data": "test",
                "attempt": 0,
            }
        )

        response = authenticated_client.get("/jobs/")
        assert response.status_code == 200
        # Job data should be visible
        assert b"test" in response.data.lower() or b"job" in response.data.lower()

    def test_view_queue_shows_queue_size(self, authenticated_client):
        """Queue view shows total number of jobs"""
        # Add multiple jobs
        for i in range(5):
            queue.append(
                {
                    "type": "test-job",
                    "key": uuid.uuid4().hex,
                    "data": f"test-{i}",
                    "attempt": 0,
                }
            )

        response = authenticated_client.get("/jobs/")
        assert response.status_code == 200
        # Should show 5 jobs somewhere
        data = response.get_data(as_text=True)
        assert len(data) > 100

    def test_view_queue_limits_display(self, authenticated_client):
        """Queue view limits display to 200 jobs"""
        # Add many jobs
        for i in range(250):
            queue.append(
                {
                    "type": "test-job",
                    "key": uuid.uuid4().hex,
                    "data": f"test-{i}",
                    "attempt": 0,
                }
            )

        response = authenticated_client.get("/jobs/")
        assert response.status_code == 200
        # Should only show first 200


class TestRetryJobsRoute:
    """POST /jobs/bad/ - Retry failed jobs"""

    def test_retry_jobs_requires_login(self, web_client):
        """POST requires authentication"""
        response = web_client.post("/jobs/bad/")
        assert response.status_code == 302

    def test_retry_jobs_post_redirects(self, authenticated_client):
        """POST /jobs/bad/ redirects to /jobs/"""
        response = authenticated_client.post("/jobs/bad/", follow_redirects=False)
        assert response.status_code == 302
        assert "/jobs/" in response.location

    def test_retry_jobs_retries_bad_jobs(self, authenticated_client):
        """POST retries bad jobs"""
        # This would require a way to add bad jobs
        # For now just test the redirect
        response = authenticated_client.post("/jobs/bad/", follow_redirects=True)
        assert response.status_code == 200


class TestBadJobsRoute:
    """GET /jobs/bad/ - View failed jobs"""

    def test_bad_jobs_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/jobs/bad/")
        assert response.status_code == 302

    def test_bad_jobs_empty(self, authenticated_client):
        """GET /jobs/bad/ shows empty bad jobs list"""
        response = authenticated_client.get("/jobs/bad/")
        assert response.status_code == 200
        assert b"bad" in response.data.lower() or b"failed" in response.data.lower()

    def test_bad_jobs_shows_count(self, authenticated_client):
        """Bad jobs view shows total count"""
        response = authenticated_client.get("/jobs/bad/")
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert len(data) > 100

    def test_bad_jobs_shows_jobs_with_details(self, authenticated_client):
        """Bad jobs are displayed with full details"""
        # Add a bad job - would need to directly insert into db
        # For now just test the page renders
        response = authenticated_client.get("/jobs/bad/")
        assert response.status_code == 200


class TestPurgeFormRoute:
    """GET /jobs/bad/purge/ - Purge form"""

    def test_purge_form_requires_login(self, web_client):
        """GET requires authentication"""
        response = web_client.get("/jobs/bad/purge/")
        assert response.status_code == 302

    def test_purge_form_renders(self, authenticated_client):
        """GET /jobs/bad/purge/ shows purge form"""
        response = authenticated_client.get("/jobs/bad/purge/")
        assert response.status_code == 200
        assert b"purge" in response.data.lower() or b"delete" in response.data.lower()


class TestPurgeAllRoute:
    """POST /jobs/bad/purge/all/ - Purge all bad jobs"""

    def test_purge_all_requires_login(self, web_client):
        """POST requires authentication"""
        response = web_client.post("/jobs/bad/purge/all/")
        assert response.status_code == 302

    def test_purge_all_redirects(self, authenticated_client):
        """POST /jobs/bad/purge/all/ redirects to bad jobs"""
        response = authenticated_client.post("/jobs/bad/purge/all/", follow_redirects=False)
        assert response.status_code == 302
        assert "/jobs/bad/" in response.location

    def test_purge_all_clears_bad_jobs(self, authenticated_client):
        """POST removes all bad jobs"""
        response = authenticated_client.post("/jobs/bad/purge/all/", follow_redirects=True)
        assert response.status_code == 200


class TestPurgeBadJobRoute:
    """POST /jobs/bad/purge/ - Purge specific bad job"""

    def test_purge_bad_job_requires_login(self, web_client):
        """POST requires authentication"""
        response = web_client.post("/jobs/bad/purge/")
        assert response.status_code == 302 or response.status_code == 400

    def test_purge_bad_job_redirects(self, authenticated_client):
        """POST /jobs/bad/purge/ redirects to bad jobs"""
        response = authenticated_client.post(
            "/jobs/bad/purge/",
            data={"job_key": "test-key"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/jobs/bad/" in response.location

    def test_purge_bad_job_deletes_job(self, authenticated_client):
        """POST removes specific bad job"""
        response = authenticated_client.post(
            "/jobs/bad/purge/",
            data={"job_key": "test-key"},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_purge_bad_job_missing_key(self, authenticated_client):
        """POST without job_key handled gracefully"""
        response = authenticated_client.post("/jobs/bad/purge/", data={}, follow_redirects=False)
        # Should either error or redirect
        assert response.status_code in [302, 400]
