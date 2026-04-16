"""
Admin-auth integration tests.

Cover the /admin/* gate: unauth redirects, bearer path for ops scripts,
cookie-based login, CSRF on mutating requests, host-scoped admin routing.

Google/Apple login is not covered here — both require mocking remote JWKS
clients and are tracked with the same follow-up as `/auth/google`/`/auth/apple`.
"""

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _grant_admin(db, user_id: str, is_admin: bool = True):
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET is_admin = %s WHERE id = %s",
            (is_admin, user_id),
        )
    db.commit()


@pytest.fixture
def admin_user(register_user, db):
    """Register a user and flip is_admin=true in the DB."""
    body = register_user(
        email="admin@example.com",
        password="correct-horse-battery-staple",
        display_name="Admin",
    )
    _grant_admin(db, body["user"]["id"], True)
    return body


def _admin_login(client, email: str, password: str, follow_redirects: bool = False):
    """POST /admin/login as a browser form submission."""
    return client.post(
        "/admin/login",
        data={"email": email, "password": password},
        follow_redirects=follow_redirects,
    )


def _admin_cookie(client, name: str):
    """Return the cookie object for `name` scoped to /admin, or None.

    Werkzeug 3.x identifies cookies by (domain, path, key). Our admin cookies
    are set with Path=/admin, so we must pass that explicitly.
    """
    return client.get_cookie(name, path="/admin")


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------

def test_admin_dashboard_unauth_html_redirects_to_login(client):
    resp = client.get("/admin/", headers={"Accept": "text/html"})
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]
    assert "next=" in resp.headers["Location"]


def test_admin_dashboard_unauth_json_returns_401(client):
    resp = client.get("/admin/", headers={"Accept": "application/json"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]


def test_admin_login_page_is_exempt_from_gate(client):
    resp = client.get("/admin/login")
    assert resp.status_code == 200
    # The page sets an admin_csrf cookie so JS on the page can echo it.
    assert _admin_cookie(client, "admin_csrf") is not None


# ---------------------------------------------------------------------------
# Password login
# ---------------------------------------------------------------------------

def test_password_login_bad_credentials_fails(client, admin_user):
    resp = _admin_login(client, "admin@example.com", "wrong-password")
    assert resp.status_code == 401
    assert _admin_cookie(client, "admin_session") is None


def test_password_login_non_admin_is_rejected(client, register_user, db):
    register_user(email="regular@example.com", password="password-xyz")
    resp = _admin_login(client, "regular@example.com", "password-xyz")
    assert resp.status_code == 403
    assert _admin_cookie(client, "admin_session") is None


def test_password_login_admin_sets_cookies_and_redirects(client, admin_user):
    resp = _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/")
    assert _admin_cookie(client, "admin_session") is not None
    assert _admin_cookie(client, "admin_csrf") is not None


def test_password_login_honours_safe_next(client, admin_user):
    resp = client.post(
        "/admin/login?next=/admin/orphans",
        data={
            "email": "admin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/orphans")


def test_password_login_rejects_unsafe_next(client, admin_user):
    resp = client.post(
        "/admin/login?next=https://evil.example.com/pwn",
        data={
            "email": "admin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 302
    # Open redirect got scrubbed back to /admin/
    assert resp.headers["Location"].endswith("/admin/")


# ---------------------------------------------------------------------------
# Cookie-authenticated access
# ---------------------------------------------------------------------------

def test_admin_cookie_grants_access(client, admin_user):
    _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    resp = client.get("/admin/", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.data


def test_admin_cookie_revoked_when_is_admin_flipped_false(
    client, admin_user, db,
):
    _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    assert client.get("/admin/", headers={"Accept": "text/html"}).status_code == 200

    _grant_admin(db, admin_user["user"]["id"], False)

    resp = client.get("/admin/", headers={"Accept": "application/json"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF on mutating admin requests
# ---------------------------------------------------------------------------

def test_admin_post_without_csrf_is_forbidden(client, admin_user):
    _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    resp = client.post(
        "/admin/orphans/00000000-0000-0000-0000-000000000000/status",
        json={"status": "approved"},
    )
    assert resp.status_code == 403


def test_admin_post_with_csrf_passes_gate(client, admin_user):
    """The gate should not reject a POST that carries a matching CSRF token.
    We expect the downstream handler to 404 or similar on a fake UUID — the
    important assertion is that it's NOT 403 (CSRF) or 401 (auth)."""
    _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    csrf = _admin_cookie(client, "admin_csrf").value
    resp = client.post(
        "/admin/orphans/00000000-0000-0000-0000-000000000000/status",
        json={"status": "approved"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Bearer-token path (ops scripts)
# ---------------------------------------------------------------------------

def test_bearer_admin_access_token_grants_access(client, admin_user):
    resp = client.get(
        "/admin/",
        headers={
            "Authorization": f"Bearer {admin_user['access_token']}",
            "Accept": "text/html",
        },
    )
    assert resp.status_code == 200


def test_bearer_non_admin_access_token_is_rejected(client, register_user):
    body = register_user(email="regular@example.com", password="password-xyz")
    resp = client.get(
        "/admin/",
        headers={
            "Authorization": f"Bearer {body['access_token']}",
            "Accept": "application/json",
        },
    )
    assert resp.status_code == 401


def test_bearer_admin_post_skips_csrf(client, admin_user):
    """Bearer-authed requests don't need CSRF — they can't be mounted from
    a victim browser session."""
    resp = client.post(
        "/admin/orphans/00000000-0000-0000-0000-000000000000/status",
        json={"status": "approved"},
        headers={
            "Authorization": f"Bearer {admin_user['access_token']}",
        },
    )
    # Pass the gate: anything but 401/403 proves the middleware let it through.
    assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_clears_cookies(client, admin_user):
    _admin_login(client, "admin@example.com", "correct-horse-battery-staple")
    csrf = _admin_cookie(client, "admin_csrf").value
    resp = client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    assert resp.status_code == 200
    # After logout, subsequent request should be unauthenticated.
    resp2 = client.get("/admin/", headers={"Accept": "application/json"})
    assert resp2.status_code == 401


# ---------------------------------------------------------------------------
# Host-scoped admin routing
# ---------------------------------------------------------------------------

def test_admin_not_served_from_public_web_host(client, admin_user):
    resp = client.get(
        "/admin/",
        headers={
            "Host": "approachnote.com",
            "Accept": "text/html",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Invalid admin-ish paths don't loop through login
# ---------------------------------------------------------------------------

def test_admin_prefix_near_miss_does_not_loop(client):
    """/admin= looks admin-ish but can never receive the admin_session cookie
    (Path=/admin won't match), so the gate must NOT intercept it — otherwise
    we'd loop back to login forever after a successful login."""
    resp = client.get("/admin=", headers={"Accept": "text/html"})
    # Should reach Flask routing and 404 instead of 302-ing to login.
    assert resp.status_code == 404


def test_adminfoo_does_not_hit_admin_gate(client):
    resp = client.get("/adminfoo", headers={"Accept": "text/html"})
    assert resp.status_code == 404
