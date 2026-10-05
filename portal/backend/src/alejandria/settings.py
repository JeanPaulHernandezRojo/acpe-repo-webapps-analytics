"""Carga de la configuración del portal: YAML del repo + variables de entorno de Cloud Run.

Composición:
  - portal/config/portal.yaml          identidad del portal (igual en todos los ambientes)
  - portal/config/env_<APP_ENV>.yaml   parámetros del ambiente
  - portal/config/politica_correos.yaml
  - portal/config/csp_allowlist.yaml
  - Variables de entorno: APP_ENV, GCP_PROJECT_ID, IDENTITY_API_KEY, IDENTITY_AUTH_DOMAIN,
    CONFIG_DIR y FRONTEND_DIST (las dos últimas las fija el Dockerfile).

Falla al arrancar si falta cualquier valor: un portal mal configurado no debe levantar.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alejandria.email_policy import EmailPolicy, load_email_policy

VALID_ENVIRONMENTS = ("qa", "prd")

REQUIRED_ENV_VARS = (
    "APP_ENV",
    "GCP_PROJECT_ID",
    "IDENTITY_API_KEY",
    "IDENTITY_AUTH_DOMAIN",
    "CONFIG_DIR",
    "FRONTEND_DIST",
)


@dataclass(frozen=True)
class PortalIdentity:
    """Identidad visible del portal.

    Attributes:
        name: Nombre del portal.
        subtitle: Subtítulo.
        contact: Texto de contacto de la página "sin herramientas".
        version: Versión CalVer del portal.
    """

    name: str
    subtitle: str
    contact: str
    version: str


@dataclass(frozen=True)
class EnvironmentConfig:
    """Parámetros del ambiente que usa el backend.

    Attributes:
        name: Nombre corto del ambiente (qa o prd).
        project: Project ID de GCP.
        bucket: Bucket de webapps.
        bucket_prefix: Carpeta del ambiente dentro del bucket.
        session_hours: Vigencia máxima de la sesión.
        heartbeat_seconds: Intervalo del latido del visor.
        catalog_ttl_seconds: Segundos de caché del catálogo.
        user_limit_per_minute: Límite de requests por correo.
        ip_limit_per_minute: Límite de requests por IP en rutas públicas.
        ip_index_from_end: Posición de la IP del cliente en X-Forwarded-For, desde el final.
    """

    name: str
    project: str
    bucket: str
    bucket_prefix: str
    session_hours: int
    heartbeat_seconds: int
    catalog_ttl_seconds: int
    user_limit_per_minute: int
    ip_limit_per_minute: int
    ip_index_from_end: int


@dataclass(frozen=True)
class CspAllowlist:
    """Dominios externos permitidos para los HTML.

    Attributes:
        maps: Orígenes de teselas de mapas.
        cdn: Orígenes de CDN de librerías.
    """

    maps: tuple[str, ...]
    cdn: tuple[str, ...]


@dataclass(frozen=True)
class IdentityConfig:
    """Datos públicos de Identity Platform para el frontend.

    Attributes:
        api_key: API key web (pública por diseño, restringida al dominio del portal).
        auth_domain: Dominio de autenticación del proyecto.
    """

    api_key: str
    auth_domain: str


@dataclass(frozen=True)
class Settings:
    """Configuración completa del backend.

    Attributes:
        portal: Identidad del portal.
        environment: Parámetros del ambiente.
        email_policy: Política de correos.
        csp: Lista blanca de dominios.
        identity: Datos públicos de Identity Platform.
        gcp_project_id: Proyecto de Identity Platform y de GCS.
        frontend_dist: Carpeta con el build de React.
    """

    portal: PortalIdentity
    environment: EnvironmentConfig
    email_policy: EmailPolicy
    csp: CspAllowlist
    identity: IdentityConfig
    gcp_project_id: str
    frontend_dist: Path


def _read_yaml(path: Path) -> dict[str, Any]:
    """Lee un YAML y exige que sea un mapeo.

    Args:
        path: Ruta al archivo.

    Returns:
        El contenido como diccionario.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el contenido no es un mapeo.
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuración requerida no encontrada: {path}")
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError(f"{path}: se esperaba un mapeo YAML.")
    return content


def _require(section: Mapping[str, Any], key: str, source: str) -> Any:
    """Devuelve una clave obligatoria de una sección de configuración.

    Args:
        section: Sección del YAML.
        key: Clave requerida.
        source: Referencia legible del origen, para el mensaje de error.

    Returns:
        El valor de la clave.

    Raises:
        ValueError: si la clave falta o está vacía.
    """
    value = section.get(key)
    if value is None or value == "":
        raise ValueError(f"Falta la clave obligatoria '{key}' en {source}.")
    return value


def load_portal_identity(config_dir: Path) -> PortalIdentity:
    """Carga la identidad del portal desde portal.yaml.

    Args:
        config_dir: Carpeta portal/config.

    Returns:
        La identidad del portal.
    """
    raw = _read_yaml(config_dir / "portal.yaml")
    section = raw.get("portal") or {}
    source = "portal.yaml:portal"
    return PortalIdentity(
        name=str(_require(section, "nombre", source)),
        subtitle=str(_require(section, "subtitulo", source)),
        contact=str(_require(section, "contacto", source)),
        version=str(_require(section, "version", source)),
    )


def load_environment(config_dir: Path, app_env: str) -> EnvironmentConfig:
    """Carga los parámetros del ambiente desde env_<app_env>.yaml.

    Args:
        config_dir: Carpeta portal/config.
        app_env: Ambiente (qa o prd).

    Returns:
        Los parámetros del ambiente.

    Raises:
        ValueError: si el ambiente no es válido o falta alguna clave.
    """
    if app_env not in VALID_ENVIRONMENTS:
        raise ValueError(f"APP_ENV debe ser uno de {VALID_ENVIRONMENTS}; recibido: {app_env!r}")
    raw = _read_yaml(config_dir / f"env_{app_env}.yaml")
    source = f"env_{app_env}.yaml"
    environment = raw.get("ambiente") or {}
    bucket = raw.get("bucket") or {}
    session = raw.get("sesion") or {}
    audit = raw.get("auditoria") or {}
    catalog = raw.get("catalogo") or {}
    limits = raw.get("limites") or {}
    return EnvironmentConfig(
        name=str(_require(environment, "nombre", f"{source}:ambiente")),
        project=str(_require(environment, "proyecto", f"{source}:ambiente")),
        bucket=str(_require(bucket, "nombre", f"{source}:bucket")),
        bucket_prefix=str(_require(bucket, "prefijo", f"{source}:bucket")),
        session_hours=int(_require(session, "horas", f"{source}:sesion")),
        heartbeat_seconds=int(_require(audit, "latido_segundos", f"{source}:auditoria")),
        catalog_ttl_seconds=int(_require(catalog, "ttl_segundos", f"{source}:catalogo")),
        user_limit_per_minute=int(_require(limits, "usuario_por_minuto", f"{source}:limites")),
        ip_limit_per_minute=int(_require(limits, "ip_por_minuto", f"{source}:limites")),
        ip_index_from_end=int(_require(limits, "ip_indice_desde_final", f"{source}:limites")),
    )


def load_csp_allowlist(config_dir: Path) -> CspAllowlist:
    """Carga la lista blanca de dominios desde csp_allowlist.yaml.

    Args:
        config_dir: Carpeta portal/config.

    Returns:
        La lista blanca.

    Raises:
        ValueError: si algún origen no empieza con https://.
    """
    raw = _read_yaml(config_dir / "csp_allowlist.yaml")
    section = raw.get("csp") or {}
    maps = tuple(str(origin).strip() for origin in section.get("mapas") or [])
    cdn = tuple(str(origin).strip() for origin in section.get("cdn") or [])
    invalid = [origin for origin in (*maps, *cdn) if not origin.startswith("https://")]
    if invalid:
        raise ValueError(f"csp_allowlist.yaml: orígenes sin https:// {invalid}")
    return CspAllowlist(maps=maps, cdn=cdn)


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Arma la configuración completa a partir de las variables de entorno.

    Args:
        environ: Variables de entorno (os.environ en producción).

    Returns:
        La configuración validada.

    Raises:
        ValueError: si falta alguna variable de entorno o alguna clave de configuración.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not environ.get(name)]
    if missing:
        raise ValueError(f"Variables de entorno faltantes: {missing}")
    config_dir = Path(environ["CONFIG_DIR"])
    return Settings(
        portal=load_portal_identity(config_dir=config_dir),
        environment=load_environment(config_dir=config_dir, app_env=environ["APP_ENV"]),
        email_policy=load_email_policy(path=config_dir / "politica_correos.yaml"),
        csp=load_csp_allowlist(config_dir=config_dir),
        identity=IdentityConfig(
            api_key=environ["IDENTITY_API_KEY"], auth_domain=environ["IDENTITY_AUTH_DOMAIN"]
        ),
        gcp_project_id=environ["GCP_PROJECT_ID"],
        frontend_dist=Path(environ["FRONTEND_DIST"]),
    )
