import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from desktop.server import desktop_app


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<h1>SmartFlow</h1>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("ok", encoding="utf-8")
    app = FastAPI()

    @app.post("/api/example")
    def example():
        return {"ok": True}

    @app.websocket("/ws")
    async def socket(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("ready")
        await websocket.close()

    return TestClient(desktop_app(app, tmp_path, "http://127.0.0.1:18321"), base_url="http://127.0.0.1:18321")


def test_spa_and_api_boundaries(client):
    assert client.get("/dashboard").text == "<h1>SmartFlow</h1>"
    assert client.get("/assets/app.js").text == "ok"
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/missing").status_code == 404
    assert client.get("/unknown.png").status_code == 404
    assert client.post("/api/example").status_code == 403
    assert client.post("/api/example", headers={"origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/example", headers={"origin": "http://127.0.0.1:18321"}).json() == {"ok": True}
    assert client.get("/", headers={"host": "evil.example"}).status_code == 403


def test_websocket_requires_same_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("ws://127.0.0.1:18321/ws", headers={"origin": "http://evil.example"}):
            pass
    with client.websocket_connect("ws://127.0.0.1:18321/ws", headers={"origin": "http://127.0.0.1:18321"}) as websocket:
        assert websocket.receive_text() == "ready"


@pytest.mark.parametrize("origin", ["http://localhost:1234", "https://127.0.0.1:1234", "http://127.0.0.1:1234/path"])
def test_rejects_non_loopback_desktop_origins(tmp_path, origin):
    (tmp_path / "index.html").write_text("ok")
    with pytest.raises(ValueError):
        desktop_app(FastAPI(), tmp_path, origin)


def test_preferences_survive_port_change_and_reject_unrelated_keys(tmp_path):
    (tmp_path / "index.html").write_text("ok", encoding="utf-8")
    storage = tmp_path / "user data" / "preferences.json"
    first_origin, second_origin = "http://127.0.0.1:18321", "http://127.0.0.1:18322"
    first = TestClient(desktop_app(FastAPI(), tmp_path, first_origin, storage), base_url=first_origin)
    second = TestClient(desktop_app(FastAPI(), tmp_path, second_origin, storage), base_url=second_origin)
    assert first.get("/api/desktop/preferences").json() == {}
    for key, value in (("smartflow-theme", "light"), ("smartflow-view-7", "2d")):
        assert first.post("/api/desktop/preferences", headers={"origin": first_origin}, json={"key": key, "value": value}).status_code == 200
    assert second.get("/api/desktop/preferences").json() == {"smartflow-theme": "light", "smartflow-view-7": "2d"}
    assert second.post("/api/desktop/preferences", headers={"origin": "http://evil.example"}, json={"key": "smartflow-theme", "value": "dark"}).status_code == 403
    assert second.post("/api/desktop/preferences", headers={"origin": second_origin}, json={"key": "password", "value": "bad"}).status_code == 400
    assert second.post("/api/desktop/preferences", headers={"origin": second_origin}, json={"key": "smartflow-theme", "value": None}).status_code == 200
    assert first.get("/api/desktop/preferences").json() == {"smartflow-view-7": "2d"}
