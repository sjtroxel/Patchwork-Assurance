from fastapi.testclient import TestClient

from patchwork_assurance.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "ok"
    assert isinstance(body["core"]["corpus_size"], int)
    assert body["core"]["corpus_size"] >= 0
