from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_index_is_revalidated():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_frontend_asset_is_revalidated():
    response = client.get("/js/app.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_unchanged_asset_returns_not_modified():
    etag = client.get("/js/app.js").headers["etag"]
    response = client.get("/js/app.js", headers={"If-None-Match": etag})
    assert response.status_code == 304
