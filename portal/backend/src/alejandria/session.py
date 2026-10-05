"""Sesión del usuario sobre Identity Platform (Firebase Authentication).

Flujo: el frontend completa el enlace de acceso con el SDK web, obtiene un ID token y lo
envía una sola vez a `POST /api/sesion`. El backend lo verifica y lo cambia por una cookie
de sesión firmada por Google (httpOnly), que es lo único que el navegador conserva.

El protocolo `SessionManager` permite probar las rutas sin Identity Platform.
"""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

import firebase_admin
from firebase_admin import auth, credentials

# Nombre de la app de firebase_admin, para no chocar con otra inicialización en el proceso.
_FIREBASE_APP_NAME = "alejandria"


class SessionExpiredError(Exception):
    """La cookie de sesión es válida pero ya venció."""


class SessionInvalidError(Exception):
    """La cookie o el token no son válidos."""


@dataclass(frozen=True)
class Identity:
    """Identidad autenticada.

    Attributes:
        uid: Identificador del usuario en Identity Platform.
        email: Correo tal como lo entrega Identity Platform (sin normalizar).
        email_verified: True si el correo está verificado (siempre, con enlace de acceso).
        session_id: Identificador de la sesión para la auditoría.
    """

    uid: str
    email: str
    email_verified: bool
    session_id: str


@dataclass(frozen=True)
class NewSession:
    """Sesión recién creada.

    Attributes:
        cookie: Valor de la cookie de sesión.
        identity: Identidad del usuario.
    """

    cookie: str
    identity: Identity


class SessionManager(Protocol):
    """Operaciones de sesión que usan las rutas."""

    def create(self, id_token: str) -> NewSession:
        """Verifica un ID token y crea la cookie de sesión."""
        ...

    def verify(self, cookie: str) -> Identity:
        """Verifica una cookie de sesión."""
        ...


def session_id_for(uid: str, auth_time: int) -> str:
    """Deriva un identificador estable de sesión sin exponer el uid.

    Args:
        uid: Identificador del usuario.
        auth_time: Instante (epoch) en que el usuario se autenticó.

    Returns:
        Hash corto que identifica la sesión en la auditoría.
    """
    return hashlib.sha256(f"{uid}:{auth_time}".encode()).hexdigest()[:16]


def _identity_from_claims(claims: dict) -> Identity:
    """Convierte los claims de un token o cookie en una identidad.

    Args:
        claims: Claims decodificados.

    Returns:
        La identidad correspondiente.

    Raises:
        SessionInvalidError: si falta el correo.
    """
    email = claims.get("email")
    if not email:
        raise SessionInvalidError("El token no trae correo.")
    return Identity(
        uid=str(claims["uid"]),
        email=str(email),
        email_verified=bool(claims.get("email_verified", False)),
        session_id=session_id_for(uid=str(claims["uid"]), auth_time=int(claims["auth_time"])),
    )


class FirebaseSessionManager:
    """Implementación de `SessionManager` con firebase_admin y ADC de Cloud Run."""

    def __init__(self, project_id: str, session_hours: int):
        """Inicializa firebase_admin con las credenciales de la cuenta runtime.

        Args:
            project_id: Proyecto de GCP con Identity Platform.
            session_hours: Vigencia de la cookie de sesión en el servidor.
        """
        try:
            self._app = firebase_admin.get_app(name=_FIREBASE_APP_NAME)
        except ValueError:
            self._app = firebase_admin.initialize_app(
                credential=credentials.ApplicationDefault(),
                options={"projectId": project_id},
                name=_FIREBASE_APP_NAME,
            )
        self._expires_in = timedelta(hours=session_hours)

    def create(self, id_token: str) -> NewSession:
        """Verifica el ID token y lo cambia por una cookie de sesión.

        Args:
            id_token: ID token emitido por Identity Platform al completar el enlace.

        Returns:
            La cookie y la identidad.

        Raises:
            SessionInvalidError: si el token no es válido.
        """
        try:
            claims = auth.verify_id_token(id_token, app=self._app)
            cookie = auth.create_session_cookie(
                id_token, expires_in=self._expires_in, app=self._app
            )
        except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, ValueError) as error:
            raise SessionInvalidError(str(error)) from error
        return NewSession(cookie=cookie, identity=_identity_from_claims(claims=claims))

    def verify(self, cookie: str) -> Identity:
        """Verifica la cookie de sesión.

        Args:
            cookie: Valor de la cookie.

        Returns:
            La identidad del usuario.

        Raises:
            SessionExpiredError: si la cookie venció.
            SessionInvalidError: si la cookie no es válida.
        """
        try:
            claims = auth.verify_session_cookie(cookie, check_revoked=False, app=self._app)
        except auth.ExpiredSessionCookieError as error:
            raise SessionExpiredError(str(error)) from error
        except (auth.InvalidSessionCookieError, ValueError) as error:
            raise SessionInvalidError(str(error)) from error
        return _identity_from_claims(claims=claims)
