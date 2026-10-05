"""Constructores de apps de prueba para los tests de scripts/."""

from pathlib import Path
from typing import Any

import yaml

from alejandria.email_policy import EmailPolicy

ICONS = frozenset({"chart-line", "map", "table"})


def base_app(domain: str, app_id: str, app_type: str) -> dict[str, Any]:
    """App.yaml mínimo válido.

    Args:
        domain: Dominio (carpeta padre).
        app_id: Identificador (carpeta).
        app_type: pipeline o herramienta.

    Returns:
        El contenido del app.yaml.
    """
    return {
        "id": app_id,
        "dominio": domain,
        "version": "2026-10-01-01",
        "tipo": app_type,
        "tarjeta": {
            "titulo": "Simulador de precios",
            "descripcion": "Simula escenarios de precio por canal.",
            "icono": "chart-line",
            "etiqueta": "Comercial",
        },
        "acceso": {"qa": ["ana.perez@alicorp.com.pe"], "prd": ["ana.perez@alicorp.com.pe"]},
        "labels": {"ceco": "data-analytics", "managed_by": "jperez"},
    }


def write_app(root: Path, app: dict[str, Any], html: bytes | None) -> Path:
    """Escribe una carpeta de app en `root/apps/<dominio>/<id>`.

    Args:
        root: Raíz del repo de prueba.
        app: Contenido del app.yaml.
        html: Contenido del index.html, o None para no crearlo.

    Returns:
        La carpeta de la app.
    """
    folder = root / "apps" / str(app["dominio"]) / str(app["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "app.yaml").write_text(yaml.safe_dump(app, allow_unicode=True), encoding="utf-8")
    if html is not None:
        (folder / "index.html").write_bytes(html)
    return folder


def make_policy() -> EmailPolicy:
    """Política de correos equivalente a la de producción, con un prefijo excluido."""
    return EmailPolicy(
        allowed_domains=("alicorp.com.pe",),
        excluded_prefixes=("ext_",),
        rejection_message="Solo correos corporativos.",
    )
