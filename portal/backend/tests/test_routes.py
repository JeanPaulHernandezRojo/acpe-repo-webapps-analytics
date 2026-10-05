import pytest
from conftest import catalog_entry, put_entry
from fastapi.testclient import TestClient

from alejandria.app import create_app
from alejandria.routes import SESSION_COOKIE
from alejandria.session import Identity

ANA = Identity(uid="u-ana", email="Ana@Alicorp.com.pe", email_verified=True, session_id="s-ana")
BETO = Identity(uid="u-beto", email="beto@alicorp.com.pe", email_verified=True, session_id="s-beto")
EXTERNO = Identity(uid="u-ext", email="x@gmail.com", email_verified=True, session_id="s-ext")
VIEWER = {"X-Alejandria-Visor": "1"}


@pytest.fixture
def client(harness):
    harness.sessions.tokens.update({"tok-ana": ANA, "tok-beto": BETO, "tok-ext": EXTERNO})
    put_entry(harness.store, "qa", catalog_entry("stock", "supply", ["ana@alicorp.com.pe"]))
    harness.store.put("qa/supply/stock/index.html", b"<html>stock</html>")
    put_entry(harness.store, "qa", catalog_entry("churn", "clientes", ["ana@alicorp.com.pe"]))
    return TestClient(create_app(services=harness.services), base_url="https://testserver")


def login(client: TestClient, token: str):
    return client.post("/api/sesion", json={"id_token": token})


def test_health(client):
    assert client.get("/api/salud").json()["estado"] == "ok"


def test_public_config(client):
    body = client.get("/api/configuracion").json()
    assert body["portal"]["nombre"] == "ALEJANDRÍA"
    assert body["politica"]["dominios_permitidos"] == ["alicorp.com.pe"]
    assert body["identidad"]["api_key"] == "clave-publica"
    assert body["latido_segundos"] == 300


def test_login_sets_session_cookie_and_normalizes_email(client, harness):
    response = login(client, "tok-ana")
    assert response.status_code == 200
    assert response.json() == {"tiene_apps": True}
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "Max-Age" not in cookie and "expires" not in cookie.lower()
    login_event = harness.audit_events()[-1]
    assert login_event["tipo_evento"] == "login_ok"
    assert login_event["correo"] == "ana@alicorp.com.pe"


def test_login_without_apps_is_logged(client, harness):
    response = login(client, "tok-beto")
    assert response.json() == {"tiene_apps": False}
    assert [e["tipo_evento"] for e in harness.audit_events()] == ["login_ok", "sin_apps"]


def test_login_rejected_by_policy(client, harness):
    response = login(client, "tok-ext")
    assert response.status_code == 403
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")
    event = harness.audit_events()[-1]
    assert event["tipo_evento"] == "login_rechazado"
    assert event["motivo"] == "dominio_no_permitido"


def test_login_invalid_token(client, harness):
    assert login(client, "tok-falso").status_code == 401
    assert harness.audit_events()[-1]["motivo"] == "token_invalido"


def test_me_requires_session(client):
    assert client.get("/api/yo").status_code == 401


def test_me_lists_only_authorized_apps(client):
    login(client, "tok-ana")
    body = client.get("/api/yo").json()
    assert body["correo"] == "ana@alicorp.com.pe"
    assert {app["id"] for app in body["apps"]} == {"stock", "churn"}
    assert body["apps"][0]["capacidades"]["descargas"] is True


def test_expired_session(client, harness):
    login(client, "tok-ana")
    harness.sessions.expired.add("cookie-tok-ana")
    response = client.get("/api/yo")
    assert response.status_code == 401
    assert response.json()["detail"] == "sesion_expirada"
    assert harness.audit_events()[-1]["tipo_evento"] == "sesion_expirada"


def test_content_requires_viewer_header(client):
    login(client, "tok-ana")
    assert client.get("/api/apps/supply/stock/contenido").status_code == 400


def test_content_delivered_gzipped_with_sandbox_csp(client):
    login(client, "tok-ana")
    response = client.get(
        "/api/apps/supply/stock/contenido", headers={**VIEWER, "Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    assert response.text == "<html>stock</html>"
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-generacion-html"] == "1"


def test_content_without_gzip_support(client, harness):
    login(client, "tok-ana")
    response = client.get(
        "/api/apps/supply/stock/contenido", headers={**VIEWER, "Accept-Encoding": "identity"}
    )
    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert response.content == b"<html>stock</html>"


def test_content_forbidden_is_audited(client, harness):
    login(client, "tok-beto")
    response = client.get("/api/apps/supply/stock/contenido", headers=VIEWER)
    assert response.status_code == 403
    event = harness.audit_events()[-1]
    assert event["tipo_evento"] == "acceso_denegado"
    assert event["app_id"] == "stock"


def test_content_not_published_yet(client):
    login(client, "tok-ana")
    response = client.get("/api/apps/clientes/churn/contenido", headers=VIEWER)
    assert response.status_code == 404
    assert response.json()["detail"] == "sin_publicar"


def test_viewer_event_is_audited_with_app_metadata(client, harness):
    login(client, "tok-ana")
    response = client.post(
        "/api/eventos",
        json={
            "tipo": "app_abierta",
            "dominio": "supply",
            "app_id": "stock",
            "tiempo_carga_ms": 850,
        },
    )
    assert response.status_code == 204
    event = harness.audit_events()[-1]
    assert event["tipo_evento"] == "app_abierta"
    assert event["tiempo_carga_ms"] == 850
    assert event["labels_app"]["ceco"] == "data-analytics"


def test_viewer_event_for_unauthorized_app(client):
    login(client, "tok-beto")
    response = client.post(
        "/api/eventos", json={"tipo": "latido", "dominio": "supply", "app_id": "stock"}
    )
    assert response.status_code == 403


def test_login_event_endpoint(client, harness):
    response = client.post(
        "/api/ingreso/evento", json={"tipo": "enlace_solicitado", "correo": " Ana@Alicorp.com.pe "}
    )
    assert response.status_code == 204
    assert harness.audit_events()[-1]["correo"] == "ana@alicorp.com.pe"


def test_user_rate_limit(client, harness):
    harness.services.user_limiter._limit = 2
    login(client, "tok-ana")
    assert client.get("/api/yo").status_code == 200
    assert client.get("/api/yo").status_code == 200
    assert client.get("/api/yo").status_code == 429
    assert harness.audit_events()[-1]["tipo_evento"] == "limite_excedido"


def test_ip_rate_limit_on_public_routes(client, harness):
    harness.services.ip_limiter._limit = 1
    assert client.get("/api/configuracion").status_code == 200
    assert client.get("/api/configuracion").status_code == 429


def test_spa_fallback_and_static_files(client):
    index = client.get("/herramientas/supply/stock")
    assert index.text == "<html>spa</html>"
    assert "frame-ancestors 'none'" in index.headers["content-security-policy"]
    assert index.headers["x-frame-options"] == "DENY"
    asset = client.get("/assets/app-123.js")
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/logo.svg").text == "<svg/>"


def test_unknown_api_route_is_404_not_spa(client):
    assert client.get("/api/no-existe").status_code == 404


def test_path_traversal_returns_spa_index(client):
    assert client.get("/../../etc/passwd").text == "<html>spa</html>"
