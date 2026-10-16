from fastapi.testclient import TestClient

from app.main import app

def test_health_endpoint_reports_service_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "seatflow-api"}

def test_root_endpoint_returns_api_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "SeatFlow API"
    assert response.json()["status"] == "running"
