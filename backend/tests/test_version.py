"""
Tests for GET /api/version — build metadata for the version label shown in
the CPO sidebar and the admin header.
"""
import main

# Fixtures from conftest.py: client, seeded_config, cpo_headers, admin_headers


def _stamp(monkeypatch, version="9.9", commit="abc1234"):
    """Pin the module-level build vars main.py read from the environment at
    import time, so the assertions below test the plumbing rather than the
    "dev"/"unknown" defaults."""
    monkeypatch.setattr(main, "_version", version)
    monkeypatch.setattr(main, "_commit", commit)


def test_version_returns_build_metadata_for_cpo(client, seeded_config, cpo_headers, monkeypatch):
    _stamp(monkeypatch)
    r = client.get("/api/version", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json() == {"version": "9.9", "commit": "abc1234"}


def test_version_returns_build_metadata_for_admin(client, seeded_config, admin_headers, monkeypatch):
    """Same endpoint serves both roles — it is not gated on admin or cpo."""
    _stamp(monkeypatch)
    r = client.get("/api/version", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"version": "9.9", "commit": "abc1234"}


def test_version_requires_auth(client, seeded_config, monkeypatch):
    """The commit SHA must not be readable anonymously."""
    _stamp(monkeypatch)
    r = client.get("/api/version")
    assert r.status_code == 401


def test_version_rejects_an_invalid_token(client, seeded_config, monkeypatch):
    _stamp(monkeypatch)
    r = client.get("/api/version", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_version_reports_unstamped_build_as_unknown(client, seeded_config, cpo_headers, monkeypatch):
    """An image built without --build-arg GIT_COMMIT still answers; the
    frontend suppresses the tooltip for this value."""
    _stamp(monkeypatch, version="1.0", commit="unknown")
    r = client.get("/api/version", headers=cpo_headers)
    assert r.json() == {"version": "1.0", "commit": "unknown"}
