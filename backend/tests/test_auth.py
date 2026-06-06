"""Auth routes + get_current_user dependency."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.routes import auth
from api.schemas import UserProfile
from api.security import create_access_token, decode_token
from config.settings import settings

ACTIVATE = "/auth/activate"
LOGIN = "/auth/login"
# E101 / E105 are seeded un-activated by the fresh_db fixture.
RAHUL = {"employee_id": "E101", "email": "rahul@company.com", "password": "hunter2pass"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth.router)

    @app.get("/me")
    def me(user: UserProfile = Depends(get_current_user)):
        return {"employee_id": user.employee_id, "name": user.name, "band": user.band}

    return TestClient(app)


# --- activation ------------------------------------------------------------

def test_activate_returns_token_and_logs_in(client):
    r = client.post(ACTIVATE, json=RAHUL)
    assert r.status_code == 200
    assert decode_token(r.json()["access_token"]) == "E101"


def test_activate_email_is_case_insensitive(client):
    r = client.post(ACTIVATE, json={**RAHUL, "email": "RAHUL@Company.com"})
    assert r.status_code == 200


def test_activate_wrong_email_is_generic_400(client):
    r = client.post(ACTIVATE, json={**RAHUL, "email": "wrong@company.com"})
    assert r.status_code == 400


def test_activate_unknown_id_is_generic_400(client):
    r = client.post(
        ACTIVATE,
        json={"employee_id": "E999", "email": "x@company.com", "password": "longenough"},
    )
    assert r.status_code == 400


def test_activate_twice_conflicts(client):
    assert client.post(ACTIVATE, json=RAHUL).status_code == 200
    assert client.post(ACTIVATE, json=RAHUL).status_code == 409


def test_activate_short_password_is_422(client):
    assert client.post(ACTIVATE, json={**RAHUL, "password": "short"}).status_code == 422


# --- login -----------------------------------------------------------------

def test_login_before_activation_401(client):
    r = client.post(LOGIN, json={"employee_id": "E101", "password": "whatever"})
    assert r.status_code == 401


def test_login_success_after_activation(client):
    client.post(ACTIVATE, json=RAHUL)
    r = client.post(LOGIN, json={"employee_id": "E101", "password": "hunter2pass"})
    assert r.status_code == 200
    assert decode_token(r.json()["access_token"]) == "E101"


def test_login_wrong_password_401(client):
    client.post(ACTIVATE, json=RAHUL)
    r = client.post(LOGIN, json={"employee_id": "E101", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user_401(client):
    # Exercises the dummy_verify (timing-equalizing) path.
    r = client.post(LOGIN, json={"employee_id": "E000", "password": "whatever"})
    assert r.status_code == 401


# --- get_current_user ------------------------------------------------------

def test_me_no_token_401(client):
    assert client.get("/me").status_code == 401


def test_me_garbage_token_401(client):
    assert client.get("/me", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_me_valid_token_reads_band_from_db(client):
    tok = client.post(
        ACTIVATE,
        json={"employee_id": "E105", "email": "kunal@company.com", "password": "kunalpass1"},
    ).json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    # The token carries only sub; band MUST come from the DB lookup.
    assert r.json()["band"] == 10


def test_me_unknown_user_token_401(client):
    tok = create_access_token("E999")  # valid signature, no such user
    assert client.get("/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_me_expired_token_401(client):
    expired = jwt.encode(
        {"sub": "E105", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


# --- GET /auth/me ----------------------------------------------------------

def test_auth_me_returns_own_profile(client):
    tok = client.post(
        ACTIVATE,
        json={"employee_id": "E105", "email": "kunal@company.com", "password": "kunalpass1"},
    ).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {
        "employee_id": "E105",
        "name": "Kunal",
        "band": 10,
        "role": "employee",
    }


def test_auth_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


# --- rate limiting ---------------------------------------------------------

def test_login_rate_limited_after_max_attempts(client):
    for _ in range(settings.login_rate_max_attempts):
        assert client.post(LOGIN, json={"employee_id": "E101", "password": "bad"}).status_code == 401
    r = client.post(LOGIN, json={"employee_id": "E101", "password": "bad"})
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}
