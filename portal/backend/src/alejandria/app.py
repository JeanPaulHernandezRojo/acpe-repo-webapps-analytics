"""Aplicación FastAPI: API + build de React (SPA) en un solo servicio de Cloud Run.

Punto de entrada en producción (ver Dockerfile):
    uvicorn alejandria.app:create_app_from_env --factory --host 0.0.0.0 --port 8080
"""

import logging
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from google.cloud import storage

from alejandria.audit import AuditLogger
from alejandria.catalog import CatalogStore
from alejandria.content import ContentStore
from alejandria.rate_limit import WINDOW_SECONDS, RateLimiter
from alejandria.routes import Services, build_router
from alejandria.security_headers import build_portal_csp, common_headers
from alejandria.session import FirebaseSessionManager
from alejandria.settings import load_settings
from alejandria.storage import GcsObjectStore

# Los assets de Vite llevan hash en el nombre: se pueden cachear sin riesgo.
_ASSETS_CACHE = "public, max-age=31536000, immutable"


def _spa_file(frontend_dist: Path, path: str) -> Path | None:
    """Resuelve un archivo estático del build de React, sin salir de la carpeta.

    Args:
        frontend_dist: Carpeta del build de React.
        path: Ruta pedida, relativa a la raíz.

    Returns:
        El archivo si existe dentro del build, o None.
    """
    if not path:
        return None
    root = frontend_dist.resolve()
    candidate = (root / path).resolve()
    if root in candidate.parents and candidate.is_file():
        return candidate
    return None


def create_app(services: Services) -> FastAPI:
    """Crea la aplicación con sus rutas, cabeceras de seguridad y la SPA.

    Args:
        services: Dependencias ya construidas.

    Returns:
        La aplicación FastAPI.
    """
    app = FastAPI(
        title=services.settings.portal.name, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.include_router(build_router(services=services))

    portal_csp = build_portal_csp(csp=services.settings.csp)
    security = common_headers()

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # noqa: ANN001, ANN202
        """Agrega las cabeceras de seguridad sin pisar las que fijó cada ruta."""
        response = await call_next(request)
        for name, value in security.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Content-Security-Policy", portal_csp)
        return response

    frontend_dist = services.settings.frontend_dist
    index_file = frontend_dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """Sirve los archivos del build y, para cualquier otra ruta, el index de la SPA."""
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="no_encontrado")
        static = _spa_file(frontend_dist=frontend_dist, path=path)
        if static is not None:
            cache = _ASSETS_CACHE if path.startswith("assets/") else "no-cache"
            return FileResponse(static, headers={"Cache-Control": cache})
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    return app


def create_app_from_env() -> FastAPI:
    """Construye la aplicación con los servicios reales a partir del entorno de Cloud Run.

    Returns:
        La aplicación lista para uvicorn.
    """
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s %(message)s"
    )
    settings = load_settings(environ=os.environ)
    environment = settings.environment
    object_store = GcsObjectStore(
        client=storage.Client(project=settings.gcp_project_id), bucket_name=environment.bucket
    )
    services = Services(
        settings=settings,
        sessions=FirebaseSessionManager(
            project_id=settings.gcp_project_id, session_hours=environment.session_hours
        ),
        catalog=CatalogStore(
            object_store=object_store,
            bucket_prefix=environment.bucket_prefix,
            ttl_seconds=environment.catalog_ttl_seconds,
            clock=time.monotonic,
        ),
        content=ContentStore(object_store=object_store, bucket_prefix=environment.bucket_prefix),
        user_limiter=RateLimiter(
            limit=environment.user_limit_per_minute,
            window_seconds=WINDOW_SECONDS,
            clock=time.monotonic,
        ),
        ip_limiter=RateLimiter(
            limit=environment.ip_limit_per_minute,
            window_seconds=WINDOW_SECONDS,
            clock=time.monotonic,
        ),
        audit=AuditLogger(
            stream=sys.stdout,
            environment=environment.name,
            portal_version=settings.portal.version,
        ),
    )
    return create_app(services=services)
