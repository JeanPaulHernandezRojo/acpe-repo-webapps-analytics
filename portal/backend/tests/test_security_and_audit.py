import io
import json

import pytest

from alejandria.audit import AuditLogger
from alejandria.security_headers import build_portal_csp
from alejandria.session import _identity_from_claims, session_id_for
from alejandria.settings import CspAllowlist


def test_portal_csp_includes_allowlist_and_blocks_framing():
    csp = build_portal_csp(
        csp=CspAllowlist(maps=("https://*.tile.openstreetmap.org",), cdn=("https://cdn.plot.ly",))
    )
    directives = {d.split(" ")[0]: d for d in csp.split("; ")}
    assert "https://*.tile.openstreetmap.org" in directives["img-src"]
    assert "https://cdn.plot.ly" in directives["script-src"]
    assert "https://identitytoolkit.googleapis.com" in directives["connect-src"]
    assert directives["frame-ancestors"] == "frame-ancestors 'none'"
    assert directives["frame-src"] == "frame-src blob:"
    assert "  " not in csp


def test_audit_event_schema():
    stream = io.StringIO()
    logger = AuditLogger(stream=stream, environment="qa", portal_version="2026-10-01-01")
    logger.emit(event_type="app_abierta", fields={"correo": "a@alicorp.com.pe", "duracion_s": None})
    record = json.loads(stream.getvalue())
    assert record["tipo_registro"] == "auditoria"
    assert record["tipo_evento"] == "app_abierta"
    assert record["severity"] == "INFO"
    assert record["ambiente"] == "qa"
    assert "duracion_s" not in record


def test_audit_rejects_unknown_event():
    logger = AuditLogger(stream=io.StringIO(), environment="qa", portal_version="v")
    with pytest.raises(ValueError):
        logger.emit(event_type="logout", fields={})


def test_denied_events_are_warnings():
    stream = io.StringIO()
    AuditLogger(stream=stream, environment="qa", portal_version="v").emit(
        event_type="acceso_denegado", fields={}
    )
    assert json.loads(stream.getvalue())["severity"] == "WARNING"


def test_session_identity_from_claims():
    identity = _identity_from_claims(
        claims={"uid": "u1", "email": "A@alicorp.com.pe", "email_verified": True, "auth_time": 10}
    )
    assert identity.email == "A@alicorp.com.pe"
    assert identity.session_id == session_id_for(uid="u1", auth_time=10)
    assert len(identity.session_id) == 16
