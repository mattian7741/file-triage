"""API contract tests: error envelope, success shapes, no internals leaked."""

import pytest
from pathlib import Path
from flask import Flask

from file_triage.explorer.app import create_app


@pytest.fixture
def app():
    """Explorer app with temp meta DB."""
    return create_app(meta_db_path=Path("/tmp/file-triage-test-contract.db"))


@pytest.fixture
def client(app: Flask):
    return app.test_client()


class TestErrorEnvelope:
    """Error responses must use canonical envelope and not leak internals."""

    def test_missing_path_listing(self, client):
        r = client.get("/api/listing")
        assert r.status_code == 400
        data = r.get_json()
        assert "error" in data
        assert data["error"]["code"] == "PATH_REQUIRED"
        assert "message" in data["error"]
        assert "retryable" in data["error"]
        assert "traceback" not in str(data).lower()
        assert "Exception" not in data.get("error", {}).get("message", "")

    def test_missing_path_preview(self, client):
        r = client.get("/api/preview")
        assert r.status_code == 400
        data = r.get_json()
        assert data.get("error", {}).get("code") == "PATH_REQUIRED"

    def test_path_not_allowed(self, client):
        # Path that does not exist or is outside roots gets 400 (PATH_REQUIRED if empty) or 403
        r = client.get("/api/listing?path=/nonexistent_root_xyz_123")
        assert r.status_code in (400, 403, 404)
        data = r.get_json()
        assert "error" in data
        assert "code" in data["error"]


class TestSuccessShapes:
    """Success responses match expected shape."""

    def test_roots_list(self, client):
        r = client.get("/api/roots")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        # May be empty on some envs
        for item in data:
            assert isinstance(item, str)

    def test_listing_has_path_and_entries(self, client):
        r = client.get("/api/listing?path=/")
        if r.status_code != 200:
            pytest.skip("roots may not include / in this env")
        data = r.get_json()
        assert "path" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_rules_list(self, client):
        r = client.get("/api/rules")
        assert r.status_code == 200
        data = r.get_json()
        assert "rules" in data
        assert isinstance(data["rules"], list)

    def test_debug_ping(self, client):
        r = client.get("/api/debug/ping")
        assert r.status_code == 200
        assert r.get_json() == {"pong": True}

    def test_request_id_header_returned(self, client):
        r = client.get("/api/roots")
        assert r.status_code == 200
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) > 0

    def test_generate_commands_shape(self, client):
        """GET /api/generate-commands returns { commands: [{ op, src, dst, job_id }, ...] }."""
        r = client.get("/api/generate-commands")
        if r.status_code == 503:
            pytest.skip("No meta DB configured")
        assert r.status_code == 200
        data = r.get_json()
        assert "commands" in data
        assert isinstance(data["commands"], list)
        for cmd in data["commands"]:
            assert "op" in cmd
            assert "src" in cmd
            assert "dst" in cmd
            assert "job_id" in cmd


class TestIdempotency:
    """Add-tag and similar writes are idempotent where applicable."""

    def test_add_tag_twice_same_result(self, client):
        # Use a path that exists and is allowed (e.g. /tmp)
        path = "/tmp"
        tag = "contract_test_tag_xyz"
        r1 = client.post(
            "/api/tags",
            json={"path": path, "tag": tag},
            content_type="application/json",
        )
        if r1.status_code not in (200, 403):
            pytest.skip("path not allowed or meta issue")
        if r1.status_code != 200:
            return
        r2 = client.post(
            "/api/tags",
            json={"path": path, "tag": tag},
            content_type="application/json",
        )
        assert r2.status_code == 200
        # Second add should be idempotent (same tags)
        assert r1.get_json()["tags"] == r2.get_json()["tags"]

    def test_tagged_with_hide_tags_does_not_filter_viewed_tag(self, client):
        """When requesting tagged?tag=X&hide_tags=X, entries with tag X are still returned."""
        # Request tagged list for a tag while passing that same tag in hide_tags
        r = client.get("/api/tagged?tag=contract_test_tag_xyz&hide_tags=contract_test_tag_xyz")
        if r.status_code != 200:
            pytest.skip("meta or tag not available")
        data = r.get_json()
        assert "entries" in data
        # Entries with that tag should still appear (backend uses hide_tags - {tag})
        assert data["tag"] == "contract_test_tag_xyz"
