"""Endpoints del portal.

| Ruta                                      | Sesión | Límite  |
|-------------------------------------------|--------|---------|
| GET  /api/salud                           | No     | —       |
| GET  /api/configuracion                   | No     | IP      |
| POST /api/ingreso/evento                  | No     | IP      |
| POST /api/sesion                          | No     | IP      |
| GET  /api/yo                              | Sí     | Usuario |
| GET  /api/apps/{dominio}/{app}/contenido  | Sí     | Usuario |
| POST /api/eventos                         | Sí     | Usuario |

Las rutas son síncronas a propósito: GCS y Firebase se llaman con clientes bloqueantes y
FastAPI las ejecuta en su pool de hilos.
"""

import gzip
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from alejandria.audit import AuditLogger
from alejandria.authorization import apps_for_email, find_app
from alejandria.catalog import AppEntry, CatalogStore
from alejandria.content import ContentStore
from alejandria.email_policy import evaluate_email, normalize_email
from alejandria.rate_limit import RateLimiter, client_ip
from alejandria.security_headers import CONTENT_CSP
from alejandria.session import SessionExpiredError, SessionInvalidError, SessionManager
from alejandria.settings import Settings

SESSION_COOKIE = "alejandria_sesion"

# Cabecera que solo envía el visor del portal. Una navegación directa a la URL de
# contenido no puede enviarla, así que el HTML nunca se ejecuta fuera del iframe.
VIEWER_HEADER = "x-alejandria-visor"

# Longitud máxima del user-agent que se guarda en la auditoría.
_MAX_USER_AGENT = 300


@dataclass
class Services:
    """Dependencias de las rutas, inyectables para tests.

    Attributes:
        settings: Configuración del portal.
        sessions: Manejo de sesiones.
        catalog: Catálogo de apps.
        content: HTML de las apps.
        user_limiter: Límite por correo.
        ip_limiter: Límite por IP.
        audit: Registrador de auditoría.
    """

    settings: Settings
    sessions: SessionManager
    catalog: CatalogStore
    content: ContentStore
    user_limiter: RateLimiter
    ip_limiter: RateLimiter
    audit: AuditLogger


@dataclass(frozen=True)
class RequestContext:
    """Metadatos de conexión de un request.

    Attributes:
        ip: IP del cliente.
        user_agent: User-agent recortado.
    """

    ip: str
    user_agent: str


@dataclass(frozen=True)
class User:
    """Usuario autenticado de un request.

    Attributes:
        email: Correo normalizado.
        session_id: Identificador de la sesión.
        context: Metadatos de conexión.
    """

    email: str
    session_id: str
    context: RequestContext


class LoginEventBody(BaseModel):
    """Evento de ingreso informado por el frontend antes de tener sesión."""

    tipo: Literal["enlace_solicitado", "enlace_rechazado_politica"]
    correo: str = Field(max_length=320)


class SessionBody(BaseModel):
    """ID token de Identity Platform para crear la sesión."""

    id_token: str = Field(min_length=1, max_length=8192)


class ViewerEventBody(BaseModel):
    """Evento del visor sobre una app."""

    tipo: Literal["app_abierta", "latido", "app_cerrada"]
    dominio: str = Field(max_length=100)
    app_id: str = Field(max_length=100)
    tiempo_carga_ms: int | None = Field(default=None, ge=0)
    duracion_s: int | None = Field(default=None, ge=0)
    generacion_html: str | None = Field(default=None, max_length=40)


def _app_payload(entry: AppEntry) -> dict:
    """Serializa una app para el frontend.

    Args:
        entry: Entrada del catálogo.

    Returns:
        Datos de tarjeta, capacidades y marca de agua.
    """
    return {
        "id": entry.app_id,
        "dominio": entry.domain,
        "version": entry.version,
        "titulo": entry.card.title,
        "descripcion": entry.card.description,
        "icono": entry.card.icon,
        "etiqueta": entry.card.tag,
        "capacidades": entry.capabilities,
        "marca_agua": entry.watermark,
    }


def build_router(services: Services) -> APIRouter:
    """Arma el router con todas las rutas del portal.

    Args:
        services: Dependencias de las rutas.

    Returns:
        El router de FastAPI.
    """
    router = APIRouter(prefix="/api")
    settings = services.settings
    audit = services.audit

    def request_context(request: Request) -> RequestContext:
        """Extrae IP y user-agent del request."""
        fallback = request.client.host if request.client else ""
        ip = client_ip(
            headers=request.headers,
            index_from_end=settings.environment.ip_index_from_end,
            fallback=fallback,
        )
        agent = request.headers.get("user-agent", "")[:_MAX_USER_AGENT]
        return RequestContext(ip=ip, user_agent=agent)

    def public_limit(context: RequestContext = Depends(request_context)) -> RequestContext:
        """Aplica el límite por IP de las rutas públicas."""
        if not services.ip_limiter.allow(key=context.ip):
            audit.emit(event_type="limite_excedido", fields={"ip": context.ip, "limite": "ip"})
            raise HTTPException(status_code=429, detail="demasiadas_solicitudes")
        return context

    def current_user(request: Request, context: RequestContext = Depends(request_context)) -> User:
        """Valida la cookie de sesión, la política y el límite por usuario."""
        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie:
            raise HTTPException(status_code=401, detail="sin_sesion")
        try:
            identity = services.sessions.verify(cookie=cookie)
        except SessionExpiredError:
            audit.emit(event_type="sesion_expirada", fields={"ip": context.ip})
            raise HTTPException(status_code=401, detail="sesion_expirada") from None
        except SessionInvalidError:
            raise HTTPException(status_code=401, detail="sesion_invalida") from None
        policy = evaluate_email(email=identity.email, policy=settings.email_policy)
        if not policy.allowed:
            raise HTTPException(status_code=403, detail="correo_no_permitido")
        if not services.user_limiter.allow(key=policy.email):
            audit.emit(
                event_type="limite_excedido",
                fields={"correo": policy.email, "ip": context.ip, "limite": "usuario"},
            )
            raise HTTPException(status_code=429, detail="demasiadas_solicitudes")
        return User(email=policy.email, session_id=identity.session_id, context=context)

    @router.get("/salud")
    def health() -> dict:
        """Health check de Cloud Run y del smoke test de los despliegues."""
        return {"estado": "ok", "version": settings.portal.version}

    @router.get("/configuracion")
    def public_config(context: RequestContext = Depends(public_limit)) -> dict:
        """Datos públicos que el frontend necesita antes de iniciar sesión."""
        policy = settings.email_policy
        return {
            "portal": {
                "nombre": settings.portal.name,
                "subtitulo": settings.portal.subtitle,
                "contacto": settings.portal.contact,
                "version": settings.portal.version,
            },
            "politica": {
                "dominios_permitidos": list(policy.allowed_domains),
                "prefijos_excluidos": list(policy.excluded_prefixes),
                "mensaje_rechazo": policy.rejection_message,
            },
            "identidad": {
                "api_key": settings.identity.api_key,
                "auth_domain": settings.identity.auth_domain,
            },
            "latido_segundos": settings.environment.heartbeat_seconds,
            "ambiente": settings.environment.name,
        }

    @router.post("/ingreso/evento", status_code=204)
    def login_event(
        body: LoginEventBody, context: RequestContext = Depends(public_limit)
    ) -> Response:
        """Registra que el frontend pidió un enlace o que la política rechazó el correo."""
        audit.emit(
            event_type=body.tipo,
            fields={
                "correo": normalize_email(email=body.correo),
                "ip": context.ip,
                "user_agent": context.user_agent,
            },
        )
        return Response(status_code=204)

    @router.post("/sesion")
    def create_session(
        body: SessionBody, context: RequestContext = Depends(public_limit)
    ) -> JSONResponse:
        """Cambia el ID token por la cookie de sesión, si el correo cumple la política."""
        base_fields = {"ip": context.ip, "user_agent": context.user_agent}
        try:
            new_session = services.sessions.create(id_token=body.id_token)
        except SessionInvalidError:
            audit.emit(
                event_type="login_rechazado", fields={**base_fields, "motivo": "token_invalido"}
            )
            raise HTTPException(status_code=401, detail="token_invalido") from None
        identity = new_session.identity
        policy = evaluate_email(email=identity.email, policy=settings.email_policy)
        if not identity.email_verified or not policy.allowed:
            reason = policy.reason or "correo_no_verificado"
            audit.emit(
                event_type="login_rechazado",
                fields={**base_fields, "correo": policy.email, "motivo": reason},
            )
            raise HTTPException(status_code=403, detail=settings.email_policy.rejection_message)
        apps = apps_for_email(entries=services.catalog.entries(), email=policy.email)
        user_fields = {**base_fields, "correo": policy.email, "id_sesion": identity.session_id}
        audit.emit(event_type="login_ok", fields={**user_fields, "cantidad_apps": len(apps)})
        if not apps:
            audit.emit(event_type="sin_apps", fields=user_fields)
        response = JSONResponse({"tiene_apps": bool(apps)})
        # Sin max_age: la cookie se borra al cerrar el navegador. El servidor además la
        # invalida al cumplirse las horas de sesión configuradas.
        response.set_cookie(
            key=SESSION_COOKIE,
            value=new_session.cookie,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return response

    @router.get("/yo")
    def me(user: User = Depends(current_user)) -> dict:
        """Correo del usuario y las apps habilitadas para él."""
        apps = apps_for_email(entries=services.catalog.entries(), email=user.email)
        return {"correo": user.email, "apps": [_app_payload(entry=entry) for entry in apps]}

    @router.get("/apps/{dominio}/{app_id}/contenido")
    def app_content(
        dominio: str, app_id: str, request: Request, user: User = Depends(current_user)
    ) -> Response:
        """Entrega el HTML de una app autorizada, comprimido y sin caché en el navegador."""
        if request.headers.get(VIEWER_HEADER) != "1":
            raise HTTPException(status_code=400, detail="solo_desde_el_visor")
        lookup = find_app(
            entries=services.catalog.entries(), email=user.email, domain=dominio, app_id=app_id
        )
        if lookup.entry is None or not lookup.authorized:
            audit.emit(
                event_type="acceso_denegado",
                fields={
                    "correo": user.email,
                    "id_sesion": user.session_id,
                    "dominio": dominio,
                    "app_id": app_id,
                    "ip": user.context.ip,
                },
            )
            raise HTTPException(status_code=403, detail="sin_acceso")
        content = services.content.get(domain=dominio, app_id=app_id)
        if content is None:
            raise HTTPException(status_code=404, detail="sin_publicar")
        headers = {
            "Cache-Control": "no-store",
            "Content-Security-Policy": CONTENT_CSP,
            "X-Generacion-Html": str(content.generation),
            "Vary": "Accept-Encoding",
        }
        media_type = "text/html; charset=utf-8"
        if "gzip" in request.headers.get("accept-encoding", ""):
            headers["Content-Encoding"] = "gzip"
            return Response(content=content.gzipped, media_type=media_type, headers=headers)
        return Response(
            content=gzip.decompress(content.gzipped), media_type=media_type, headers=headers
        )

    @router.post("/eventos", status_code=204)
    def viewer_event(body: ViewerEventBody, user: User = Depends(current_user)) -> Response:
        """Registra apertura, latido y cierre de una app en el visor."""
        lookup = find_app(
            entries=services.catalog.entries(),
            email=user.email,
            domain=body.dominio,
            app_id=body.app_id,
        )
        if lookup.entry is None or not lookup.authorized:
            raise HTTPException(status_code=403, detail="sin_acceso")
        audit.emit(
            event_type=body.tipo,
            fields={
                "correo": user.email,
                "id_sesion": user.session_id,
                "dominio": lookup.entry.domain,
                "app_id": lookup.entry.app_id,
                "version_app": lookup.entry.version,
                "labels_app": lookup.entry.labels,
                "generacion_html": body.generacion_html,
                "tiempo_carga_ms": body.tiempo_carga_ms,
                "duracion_s": body.duracion_s,
                "ip": user.context.ip,
                "user_agent": user.context.user_agent,
            },
        )
        return Response(status_code=204)

    return router
