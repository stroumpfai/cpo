"""
Tests for request-size protections:
  - body larger than MAX_BODY_BYTES → 413
  - menu import capped at 500 dishes → 422
"""
from config import MAX_BODY_BYTES

# Fixtures from conftest.py: client, seeded_config, cpo_headers


def test_oversized_body_rejected_with_413(client, seeded_config):
    body = b"x" * (MAX_BODY_BYTES + 1)
    r = client.post(
        "/api/orders/somelink/submit",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_body_at_limit_not_rejected_by_middleware(client, seeded_config):
    # Invalid JSON of exactly MAX_BODY_BYTES passes the size gate (422, not 413)
    body = b"x" * MAX_BODY_BYTES
    r = client.post(
        "/api/orders/somelink/submit",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_menu_import_rejects_more_than_500_dishes(client, seeded_config, seeded_menu, cpo_headers):
    dishes = [{"name": f"Pizza {i}", "price": 1.0} for i in range(501)]
    r = client.post(f"/api/cpo/menus/{seeded_menu.id}/import", headers=cpo_headers, json={"dishes": dishes})
    assert r.status_code == 422


def test_menu_import_accepts_500_dishes(client, seeded_config, seeded_menu, cpo_headers):
    dishes = [{"name": f"Pizza {i}", "price": 1.0} for i in range(500)]
    r = client.post(f"/api/cpo/menus/{seeded_menu.id}/import", headers=cpo_headers, json={"dishes": dishes})
    assert r.status_code == 204
