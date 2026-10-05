import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from alejandria.audit import AuditLogger
from alejandria.catalog import CatalogStore
from alejandria.content import ContentStore
from alejandria.rate_limit import RateLimiter
from alejandria.routes import Services
from alejandria.session import (
    Identity,
    NewSession,
    SessionExpiredError,
    SessionInvalidError,
)
from alejandria.settings import load_settings
from alejandria.storage import ObjectData

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "portal" / "config"


class FakeObjectStore:
    """Bucket en memoria: nombre -> (bytes, generación)."""

    def __init__(self):
        self.objects: dict[str, ObjectData] = {}
        self.reads = 0

    def put(self, name: str, data: bytes):
        previous = self.objects.get(name)
        generation = previous.generation + 1 if previous else 1
        self.objects[name] = ObjectData(data=data, generation=generation)

    def list_objects(self, prefix: str) -> list[str]:
        return sorted(name for name in self.objects if name.startswith(prefix))

    def get_generation(self, name: str) -> int | None:
        obj = self.objects.get(name)
        return None if obj is None else obj.generation

    def read(self, name: str) -> ObjectData | None:
        self.reads += 1
        return self.objects.get(name)


@dataclass
class FakeSessions:
    """Sesiones simuladas: token -> identidad y cookie -> identidad."""

    tokens: dict[str, Identity] = field(default_factory=dict)
    cookies: dict[str, Identity] = field(default_factory=dict)
    expired: set[str] = field(default_factory=set)

    def create(self, id_token: str) -> NewSession:
        if id_token not in self.tokens:
            raise SessionInvalidError("token desconocido")
        identity = self.tokens[id_token]
        cookie = f"cookie-{id_token}"
        self.cookies[cookie] = identity
        return NewSession(cookie=cookie, identity=identity)

    def verify(self, cookie: str) -> Identity:
        if cookie in self.expired:
            raise SessionExpiredError("vencida")
        if cookie not in self.cookies:
            raise SessionInvalidError("cookie desconocida")
        return self.cookies[cookie]


class ManualClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def catalog_entry(app_id: str, domain: str, access: list[str], **overrides) -> dict:
    entry = {
        "id": app_id,
        "dominio": domain,
        "version": "2026-10-01-01",
        "tipo": "herramienta",
        "tarjeta": {
            "titulo": f"Título {app_id}",
            "descripcion": "Descripción",
            "icono": "boxes",
            "etiqueta": domain.capitalize(),
        },
        "acceso": access,
        "capacidades": {"descargas": True, "ventanas": True, "dialogos": True, "formularios": True},
        "marca_agua": "patron_suave",
        "labels": {"ceco": "data-analytics", "managed_by": "jhernandezr"},
        "huella": "abc123",
    }
    entry.update(overrides)
    return entry


def put_entry(store: FakeObjectStore, prefix: str, entry: dict):
    name = f"{prefix}/_catalogo/{entry['dominio']}/{entry['id']}.json"
    store.put(name, json.dumps(entry).encode())


@pytest.fixture
def frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    (dist / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "logo.svg").write_text("<svg/>", encoding="utf-8")
    return dist


@pytest.fixture
def settings(frontend_dist: Path):
    return load_settings(
        environ={
            "APP_ENV": "qa",
            "GCP_PROJECT_ID": "acpe-qa-uc-ml",
            "IDENTITY_API_KEY": "clave-publica",
            "IDENTITY_AUTH_DOMAIN": "acpe-qa-uc-ml.firebaseapp.com",
            "CONFIG_DIR": str(CONFIG_DIR),
            "FRONTEND_DIST": str(frontend_dist),
        }
    )


@dataclass
class Harness:
    services: Services
    store: FakeObjectStore
    sessions: FakeSessions
    audit_stream: io.StringIO
    clock: ManualClock

    def audit_events(self) -> list[dict]:
        return [json.loads(line) for line in self.audit_stream.getvalue().splitlines()]


@pytest.fixture
def harness(settings) -> Harness:
    store = FakeObjectStore()
    sessions = FakeSessions()
    stream = io.StringIO()
    clock = ManualClock()
    prefix = settings.environment.bucket_prefix
    services = Services(
        settings=settings,
        sessions=sessions,
        catalog=CatalogStore(object_store=store, bucket_prefix=prefix, ttl_seconds=0, clock=clock),
        content=ContentStore(object_store=store, bucket_prefix=prefix),
        user_limiter=RateLimiter(limit=100, window_seconds=60, clock=clock),
        ip_limiter=RateLimiter(limit=100, window_seconds=60, clock=clock),
        audit=AuditLogger(stream=stream, environment="qa", portal_version="2026-10-01-01"),
    )
    return Harness(
        services=services, store=store, sessions=sessions, audit_stream=stream, clock=clock
    )
