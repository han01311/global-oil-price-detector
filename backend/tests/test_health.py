"""
백엔드 테스트 설정
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """테스트 클라이언트"""
    return TestClient(app)


def test_health_check(client):
    """헬스체크 엔드포인트 테스트"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
