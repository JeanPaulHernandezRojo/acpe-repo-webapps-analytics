"""Contrato de `apps/<dominio>/<app>/app.yaml`: validación, valores por defecto y huella.

Lo usan validar_apps.py (pr_checks), publicar_app.py (deploy_qa / deploy_prd),
solo_accesos.py y sincronizar_accesos_qa.py. Es la única definición del contrato.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import load_yaml

from alejandria.email_policy import EmailPolicy, evaluate_email, normalize_email

APPS_DIR = "apps"
APP_FILE = "app.yaml"
HTML_FILE = "index.html"

APP_TYPES = ("pipeline", "herramienta")
CAPABILITIES = ("descargas", "ventanas", "dialogos", "formularios")
WATERMARK_LEVELS = ("patron_suave", "esquina", "franja", "patron")
DEFAULT_WATERMARK = "patron_suave"
ENVIRONMENTS = ("qa", "prd")

TOP_LEVEL_KEYS = frozenset(
    {"id", "dominio", "version", "tipo", "tarjeta", "acceso", "capacidades", "marca_agua", "labels"}
)
CARD_KEYS = ("titulo", "descripcion", "icono", "etiqueta")
REQUIRED_LABELS = ("ceco", "managed_by")

# Carpetas reservadas: evitan choques con las ramas release del portal.
RESERVED_DOMAINS = frozenset({"portal"})

# Campos que no cambian "lo que el usuario ve": un cambio solo en estos no exige un nuevo QA.
FINGERPRINT_EXCLUDED = ("acceso", "version")

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
CALVER = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}$")
LABEL_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
LABEL_VALUE = re.compile(r"^[a-z0-9_-]{1,63}$")


def app_dirs(repo_root: Path) -> list[Path]:
    """Lista las carpetas de app (`apps/<dominio>/<app>`).

    Args:
        repo_root: Raíz del repo.

    Returns:
        Carpetas de app ordenadas.
    """
    base = repo_root / APPS_DIR
    if not base.is_dir():
        return []
    return sorted(
        app
        for domain in base.iterdir()
        if domain.is_dir()
        for app in domain.iterdir()
        if app.is_dir()
    )


def load_app(app_dir: Path) -> dict[str, Any]:
    """Lee el app.yaml de una carpeta de app.

    Args:
        app_dir: Carpeta de la app.

    Returns:
        El contenido del app.yaml.
    """
    return load_yaml(app_dir / APP_FILE)


def read_html(app_dir: Path) -> bytes | None:
    """Lee el index.html de una herramienta, si existe.

    Args:
        app_dir: Carpeta de la app.

    Returns:
        Los bytes del HTML, o None si la carpeta no tiene index.html.
    """
    path = app_dir / HTML_FILE
    return path.read_bytes() if path.is_file() else None


def resolve_capabilities(raw: dict[str, Any] | None) -> dict[str, bool]:
    """Completa las capacidades: las omitidas quedan activadas.

    Args:
        raw: Bloque `capacidades` del app.yaml, o None.

    Returns:
        Las cuatro capacidades con su valor final.
    """
    raw = raw or {}
    return {name: bool(raw.get(name, True)) for name in CAPABILITIES}


def resolve_watermark(raw: str | None) -> str:
    """Devuelve el nivel de marca de agua, con el valor por defecto si se omite.

    Args:
        raw: Valor de `marca_agua`, o None.

    Returns:
        El nivel final.
    """
    return raw or DEFAULT_WATERMARK


def compute_fingerprint(app: dict[str, Any], html: bytes | None) -> str:
    """Calcula la huella de contenido de una app.

    La huella resume lo que el usuario ve y cómo funciona la app (HTML + app.yaml sin
    accesos ni versión). Si solo cambian los accesos, la huella no cambia.

    Args:
        app: Contenido del app.yaml.
        html: Bytes del index.html, o None si la app es de tipo pipeline.

    Returns:
        SHA-256 en hexadecimal.
    """
    content = {key: value for key, value in app.items() if key not in FINGERPRINT_EXCLUDED}
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8"))
    digest.update(b"\x00")
    if html is not None:
        digest.update(html)
    return digest.hexdigest()


def _validate_emails(emails: Any, env: str, policy: EmailPolicy) -> list[str]:
    """Valida la lista de correos de un ambiente.

    Args:
        emails: Valor de `acceso.<env>`.
        env: Ambiente, para los mensajes.
        policy: Política de correos.

    Returns:
        Errores encontrados.
    """
    if not isinstance(emails, list):
        return [f"acceso.{env} debe ser una lista (puede estar vacía)."]
    errors: list[str] = []
    seen: set[str] = set()
    for email in emails:
        text = str(email)
        if text != normalize_email(text):
            errors.append(f"acceso.{env}: '{text}' debe escribirse en minúsculas y sin espacios.")
            continue
        result = evaluate_email(email=text, policy=policy)
        if not result.allowed:
            errors.append(f"acceso.{env}: '{text}' no cumple la política ({result.reason}).")
        if text in seen:
            errors.append(f"acceso.{env}: '{text}' está repetido.")
        seen.add(text)
    return errors


def validate_app(app_dir: Path, policy: EmailPolicy, icons: frozenset[str]) -> list[str]:
    """Valida una carpeta de app contra el contrato.

    Args:
        app_dir: Carpeta `apps/<dominio>/<app>`.
        policy: Política de correos.
        icons: Íconos permitidos.

    Returns:
        Errores encontrados (vacío si la app es válida).
    """
    label = f"{app_dir.parent.name}/{app_dir.name}"
    if not (app_dir / APP_FILE).is_file():
        return [f"{label}: falta {APP_FILE}."]
    try:
        app = load_app(app_dir=app_dir)
    except (ValueError, OSError) as error:
        return [f"{label}: {error}"]

    errors: list[str] = []
    unknown = sorted(set(app) - TOP_LEVEL_KEYS)
    if unknown:
        errors.append(f"claves desconocidas {unknown}.")

    if app.get("id") != app_dir.name or not SNAKE_CASE.match(app_dir.name):
        errors.append(f"id debe ser igual a la carpeta y en snake_case ('{app_dir.name}').")
    domain = app_dir.parent.name
    if app.get("dominio") != domain or not SNAKE_CASE.match(domain):
        errors.append(f"dominio debe ser igual a la carpeta padre y en snake_case ('{domain}').")
    if domain in RESERVED_DOMAINS:
        errors.append(f"el dominio '{domain}' está reservado.")
    if not CALVER.match(str(app.get("version", ""))):
        errors.append("version debe tener el formato AAAA-MM-DD-NN.")

    app_type = app.get("tipo")
    has_html = (app_dir / HTML_FILE).is_file()
    if app_type not in APP_TYPES:
        errors.append(f"tipo debe ser uno de {APP_TYPES}.")
    elif app_type == "herramienta" and not has_html:
        errors.append("una herramienta debe incluir index.html en su carpeta.")
    elif app_type == "pipeline" and has_html:
        errors.append(
            "una app de pipeline no lleva index.html: lo escribe el pipeline en el bucket."
        )

    card = app.get("tarjeta")
    if not isinstance(card, dict):
        errors.append(f"tarjeta debe declarar {CARD_KEYS}.")
    else:
        missing = [key for key in CARD_KEYS if not str(card.get(key, "")).strip()]
        if missing:
            errors.append(f"tarjeta sin {missing}.")
        extra = sorted(set(card) - set(CARD_KEYS))
        if extra:
            errors.append(f"tarjeta tiene claves desconocidas {extra}.")
        if card.get("icono") and card["icono"] not in icons:
            errors.append(f"tarjeta.icono '{card['icono']}' no está en iconos_permitidos.yaml.")

    access = app.get("acceso")
    if not isinstance(access, dict) or set(access) != set(ENVIRONMENTS):
        errors.append("acceso debe declarar exactamente las listas 'qa' y 'prd'.")
    else:
        for env in ENVIRONMENTS:
            errors.extend(_validate_emails(emails=access[env], env=env, policy=policy))

    capabilities = app.get("capacidades")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            errors.append("capacidades debe ser un mapeo.")
        else:
            unknown_caps = sorted(set(capabilities) - set(CAPABILITIES))
            if unknown_caps:
                errors.append(f"capacidades desconocidas {unknown_caps}; válidas: {CAPABILITIES}.")
            if any(not isinstance(value, bool) for value in capabilities.values()):
                errors.append("cada capacidad debe ser true o false.")

    watermark = app.get("marca_agua")
    if watermark is not None and watermark not in WATERMARK_LEVELS:
        errors.append(f"marca_agua debe ser uno de {WATERMARK_LEVELS}.")

    labels = app.get("labels")
    if not isinstance(labels, dict):
        errors.append(f"labels debe declarar {REQUIRED_LABELS}.")
    else:
        for required in REQUIRED_LABELS:
            if not labels.get(required):
                errors.append(f"falta el label '{required}'.")
        for key, value in labels.items():
            if not LABEL_KEY.match(str(key)) or not LABEL_VALUE.match(str(value)):
                errors.append(f"label inválido {key}={value} (minúsculas, dígitos, '_' y '-').")

    return [f"{label}: {error}" for error in errors]


def build_catalog_entry(
    app: dict[str, Any],
    env: str,
    fingerprint: str,
    sha: str,
    actor: str,
    published_at: str,
) -> dict[str, Any]:
    """Arma la entrada de catálogo que lee el portal para un ambiente.

    Args:
        app: Contenido del app.yaml.
        env: Ambiente (qa o prd): define qué lista de acceso se publica.
        fingerprint: Huella de contenido.
        sha: Commit publicado.
        actor: Usuario de GitHub que ejecutó el despliegue.
        published_at: Fecha y hora de publicación (ISO 8601).

    Returns:
        La entrada de catálogo.
    """
    return {
        "id": app["id"],
        "dominio": app["dominio"],
        "version": str(app["version"]),
        "tipo": app["tipo"],
        "tarjeta": {key: str(app["tarjeta"][key]) for key in CARD_KEYS},
        "acceso": sorted(str(email) for email in app["acceso"][env]),
        "capacidades": resolve_capabilities(raw=app.get("capacidades")),
        "marca_agua": resolve_watermark(raw=app.get("marca_agua")),
        "labels": {str(k): str(v) for k, v in app["labels"].items()},
        "huella": fingerprint,
        "sha_commit": sha,
        "publicado_en": published_at,
        "publicado_por": actor,
    }


def catalog_object_name(prefix: str, domain: str, app_id: str) -> str:
    """Nombre del objeto de catálogo de una app.

    Args:
        prefix: Carpeta del ambiente en el bucket (qa o prd).
        domain: Dominio de la app.
        app_id: Identificador de la app.

    Returns:
        Nombre completo del objeto.
    """
    return f"{prefix}/_catalogo/{domain}/{app_id}.json"


def html_object_name(prefix: str, domain: str, app_id: str) -> str:
    """Nombre del objeto index.html de una app.

    Args:
        prefix: Carpeta del ambiente en el bucket (qa o prd).
        domain: Dominio de la app.
        app_id: Identificador de la app.

    Returns:
        Nombre completo del objeto.
    """
    return f"{prefix}/{domain}/{app_id}/{HTML_FILE}"


def access_diff(previous: list[str], current: list[str]) -> dict[str, list[str]]:
    """Compara dos listas de acceso.

    Args:
        previous: Correos antes del cambio.
        current: Correos después del cambio.

    Returns:
        Correos agregados y quitados, ordenados.
    """
    return {
        "agregados": sorted(set(current) - set(previous)),
        "quitados": sorted(set(previous) - set(current)),
    }
