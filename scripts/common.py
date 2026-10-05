"""Utilidades compartidas por los scripts de CI."""

import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "portal" / "config"


def load_yaml(path: Path) -> dict[str, Any]:
    """Lee un YAML y exige que sea un mapeo.

    Args:
        path: Ruta al archivo.

    Returns:
        El contenido como diccionario.

    Raises:
        ValueError: si el contenido no es un mapeo.
    """
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError(f"{path}: se esperaba un mapeo YAML.")
    return content


def write_github_output(name: str, value: str) -> None:
    """Publica un output del step actual de GitHub Actions (si corre en Actions).

    Args:
        name: Nombre del output.
        value: Valor del output (una sola línea).
    """
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination:
        with open(destination, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def fail(message: str) -> int:
    """Reporta un error con el formato de anotación de GitHub Actions.

    Args:
        message: Mensaje del error.

    Returns:
        Exit code 1, para usar como `return fail(...)`.
    """
    sys.stderr.write(f"::error::{message}\n")
    return 1


def environment_config(env: str) -> dict[str, Any]:
    """Lee `portal/config/env_<env>.yaml`.

    Args:
        env: Ambiente (qa o prd).

    Returns:
        El contenido del archivo.

    Raises:
        ValueError: si el ambiente no es válido.
    """
    if env not in ("qa", "prd"):
        raise ValueError(f"Ambiente inválido: {env!r}")
    return load_yaml(CONFIG_DIR / f"env_{env}.yaml")
