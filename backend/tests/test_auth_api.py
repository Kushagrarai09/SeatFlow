"""Authentication API tests against an isolated SQLite database."""

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-seatflow")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth import hash_password, verify_password


def test_password_hash_uses_salt_and_verifies():
    first = hash_password("a-good-password")
    second = hash_password("a-good-password")
    assert first != second
    assert verify_password("a-good-password", first)
    assert not verify_password("bad-password", first)


def make_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine


def test_register_login_profile_refresh_and_logout():
    client, engine = make_client()
    try:
        registered = client.post("/api/v1/auth/register", json={
            "email": "attendee@example.test", "full_name": "Test Attendee", "password": "correct-horse-123"
        })
        assert registered.status_code == 201
        assert registered.json()["role"] == "attendee"
        assert "password_hash" not in registered.json()

        attempted_escalation = client.post("/api/v1/auth/register", json={
            "email": "admin@example.test", "full_name": "Admin User", "password": "correct-horse-123", "role": "admin"
        })
        assert attempted_escalation.status_code == 422
        assert client.post("/api/v1/auth/register", json={
            "email": "attendee@example.test", "full_name": "Test Attendee", "password": "correct-horse-123"
        }).status_code == 409

        bad_login = client.post("/api/v1/auth/login", json={
            "email": "attendee@example.test", "password": "incorrect-password"
        })
        assert bad_login.status_code == 401

        response = client.post("/api/v1/auth/login", json={
            "email": "ATTENDEE@example.test", "password": "correct-horse-123"
        })
        assert response.status_code == 200
        tokens = response.json()
        headers = {"Authorization": "Bearer " + tokens["access_token"]}
        profile = client.get("/api/v1/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["email"] == "attendee@example.test"
        assert client.get("/api/v1/auth/me").status_code == 401

        rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert rotated.status_code == 200
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

        logout = client.post("/api/v1/auth/logout", json={"refresh_token": rotated.json()["refresh_token"]},
                             headers={"Authorization": "Bearer " + rotated.json()["access_token"]})
        assert logout.status_code == 204
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}).status_code == 401
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_admin_can_promote_organizer_but_attendee_cannot_assign_roles():
    client, engine = make_client()
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        admin_user = client.post("/api/v1/auth/register", json={
            "email": "admin@example.test", "full_name": "Admin User", "password": "correct-horse-123"
        })
        attendee = client.post("/api/v1/auth/register", json={
            "email": "new-organizer@example.test", "full_name": "New Organizer", "password": "correct-horse-123"
        })
        assert admin_user.status_code == attendee.status_code == 201
        with testing_session() as db:
            from app.models import User
            administrator = db.get(User, admin_user.json()["id"])
            administrator.role = "admin"  # trusted bootstrap simulation in the test only
            db.commit()

        admin_tokens = client.post("/api/v1/auth/login", json={
            "email": "admin@example.test", "password": "correct-horse-123"
        }).json()
        attendee_tokens = client.post("/api/v1/auth/login", json={
            "email": "new-organizer@example.test", "password": "correct-horse-123"
        }).json()
        target_id = attendee.json()["id"]

        denied = client.patch(
            f"/api/v1/admin/users/{target_id}/role",
            json={"role": "organizer"},
            headers={"Authorization": "Bearer " + attendee_tokens["access_token"]},
        )
        assert denied.status_code == 403

        promoted = client.patch(
            f"/api/v1/admin/users/{target_id}/role",
            json={"role": "organizer"},
            headers={"Authorization": "Bearer " + admin_tokens["access_token"]},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "organizer"

        deactivated = client.patch(
            f"/api/v1/admin/users/{target_id}/active",
            json={"is_active": False},
            headers={"Authorization": "Bearer " + admin_tokens["access_token"]},
        )
        assert deactivated.status_code == 200
        assert client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer " + attendee_tokens["access_token"]},
        ).status_code == 401
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
