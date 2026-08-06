# tests/test_main.py
import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# httpx 0.28 removed the `app=` shortcut; ASGITransport is the supported way to
# drive an ASGI app in-process.


async def test_health_check():
    """
    Tests the public health check endpoint.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.skipif(
    os.getenv("AUTH_BYPASS", "false").lower() == "true",
    reason="AUTH_BYPASS is on, so every request is authenticated as the dev user",
)
async def test_unauthorized_access():
    """
    Tests that protected endpoints require authentication.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/test")
    assert response.status_code == 401


# Additional tests would include:
# - Database integration tests
# - Authorization engine tests
# - API endpoint tests with mocked authentication
# - Model validation tests
