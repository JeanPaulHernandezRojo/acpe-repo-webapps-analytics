"""Normalización de correos y política de acceso por dominio y prefijo.

Es la única implementación de la política en Python: la usa el backend en cada ingreso y
en cada request, y la reutiliza `scripts/validar_apps.py` para validar los correos de los
app.yaml. El frontend replica la misma regla solo para dar un mensaje inmediato.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EmailPolicy:
    """Reglas de la política de correos.

    Attributes:
        allowed_domains: Dominios permitidos, en minúsculas.
        excluded_prefixes: Prefijos del usuario que se rechazan, en minúsculas.
        rejection_message: Mensaje para quien no cumple la política.
    """

    allowed_domains: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    rejection_message: str


@dataclass(frozen=True)
class PolicyResult:
    """Resultado de evaluar un correo contra la política.

    Attributes:
        allowed: True si el correo cumple la política.
        email: Correo normalizado.
        reason: Motivo del rechazo; vacío si se permite.
    """

    allowed: bool
    email: str
    reason: str


def normalize_email(email: str) -> str:
    """Normaliza un correo: sin espacios alrededor y en minúsculas.

    Args:
        email: Correo tal como lo escribió el usuario.

    Returns:
        El correo normalizado.
    """
    return email.strip().lower()


def load_email_policy(path: Path) -> EmailPolicy:
    """Carga la política desde `politica_correos.yaml`.

    Args:
        path: Ruta al archivo YAML.

    Returns:
        La política con dominios y prefijos ya normalizados.

    Raises:
        ValueError: si el archivo no declara dominios permitidos o mensaje de rechazo.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    section = raw.get("politica") or {}
    domains = tuple(normalize_email(str(d)) for d in section.get("dominios_permitidos") or [])
    prefixes = tuple(normalize_email(str(p)) for p in section.get("prefijos_excluidos") or [])
    message = str(section.get("mensaje_rechazo") or "").strip()
    if not domains:
        raise ValueError(f"{path}: politica.dominios_permitidos no puede estar vacío.")
    if not message:
        raise ValueError(f"{path}: politica.mensaje_rechazo es obligatorio.")
    return EmailPolicy(
        allowed_domains=domains, excluded_prefixes=prefixes, rejection_message=message
    )


def evaluate_email(email: str, policy: EmailPolicy) -> PolicyResult:
    """Evalúa un correo contra la política, después de normalizarlo.

    Args:
        email: Correo a evaluar.
        policy: Política vigente.

    Returns:
        El resultado con el correo normalizado y el motivo si se rechaza.
    """
    normalized = normalize_email(email)
    user, separator, domain = normalized.rpartition("@")
    if not separator or not user or not domain or " " in normalized:
        return PolicyResult(allowed=False, email=normalized, reason="formato_invalido")
    if domain not in policy.allowed_domains:
        return PolicyResult(allowed=False, email=normalized, reason="dominio_no_permitido")
    if any(user.startswith(prefix) for prefix in policy.excluded_prefixes):
        return PolicyResult(allowed=False, email=normalized, reason="prefijo_excluido")
    return PolicyResult(allowed=True, email=normalized, reason="")
