from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.security import ALGORITHM, SECRET_KEY, create_access_token
from app.models import OfficerProfile, User
from app.core.security import password_hash


REGISTER_DATA = {
    "full_name": "Test Student",
    "email": "student@example.com",
    "password": "StrongPassword123!",
    "phone": "9876543210",
}


def register_student(client, email="student@example.com"):
    data = {**REGISTER_DATA, "email": email}
    return client.post("/api/auth/register", json=data)


def login(client, email="student@example.com", password="StrongPassword123!"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_successful_registration(client):
    response = register_student(client)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == REGISTER_DATA["email"]
    assert body["user_id"] > 0
    assert "password_hash" not in body


def test_duplicate_email_registration(client):
    register_student(client)

    response = register_student(client)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_successful_login(client):
    register_student(client)

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "STUDENT"
    assert body["access_token"]
    assert "password_hash" not in body


def test_incorrect_password(client):
    register_student(client)

    response = login(client, password="WrongPassword123!")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_missing_authentication_token(client):
    response = client.get("/api/test-protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials are required"


def test_invalid_jwt(client):
    response = client.get(
        "/api/test-protected",
        headers=bearer("not-a-valid-token"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_expired_jwt(client):
    token = jwt.encode(
        {
            "user_id": 1,
            "role": "STUDENT",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get("/api/test-protected", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_student_can_access_student_endpoint(client):
    register_student(client)
    token = login(client).json()["access_token"]

    response = client.get("/api/students/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["full_name"] == "Test Student"


def test_student_cannot_access_officer_endpoint(client):
    register_student(client)
    token = login(client).json()["access_token"]

    response = client.get("/api/officers/applications", headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Only officer users can access this resource"


def test_officer_cannot_access_student_endpoint(client, db_session):
    officer = User(
        email="officer@example.com",
        password_hash=password_hash.hash("OfficerPassword123!"),
        role="OFFICER",
    )
    db_session.add(officer)
    db_session.flush()
    db_session.add(OfficerProfile(user_id=officer.id, full_name="Test Officer"))
    db_session.commit()

    token = create_access_token({"user_id": officer.id, "role": "OFFICER"})
    response = client.get("/api/students/me", headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Only student users can access this resource"
