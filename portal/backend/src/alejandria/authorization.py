"""Autorización por app: un correo ve una app solo si figura en su lista de acceso."""

from dataclasses import dataclass

from alejandria.catalog import AppEntry


@dataclass(frozen=True)
class AppLookup:
    """Resultado de buscar una app para un usuario.

    Attributes:
        entry: La app, si existe en el catálogo.
        authorized: True si el usuario tiene acceso.
    """

    entry: AppEntry | None
    authorized: bool


def apps_for_email(entries: list[AppEntry], email: str) -> list[AppEntry]:
    """Filtra las apps a las que tiene acceso un correo.

    Args:
        entries: Catálogo del ambiente.
        email: Correo normalizado del usuario.

    Returns:
        Las apps habilitadas para el correo, en el orden del catálogo.
    """
    return [entry for entry in entries if email in entry.access]


def find_app(entries: list[AppEntry], email: str, domain: str, app_id: str) -> AppLookup:
    """Busca una app y decide si el correo puede verla.

    Args:
        entries: Catálogo del ambiente.
        email: Correo normalizado del usuario.
        domain: Dominio de la app pedida.
        app_id: Identificador de la app pedida.

    Returns:
        La app encontrada (o None) y si el usuario está autorizado.
    """
    for entry in entries:
        if entry.domain == domain and entry.app_id == app_id:
            return AppLookup(entry=entry, authorized=email in entry.access)
    return AppLookup(entry=None, authorized=False)
