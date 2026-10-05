"""Valida todos los `apps/<dominio>/<app>/app.yaml` contra el contrato (lo usa pr_checks).

Reporta todos los errores juntos para no obligar a corregir de a uno.
"""

import argparse
import sys
from pathlib import Path

from app_schema import app_dirs, validate_app
from common import CONFIG_DIR, fail, load_yaml

from alejandria.email_policy import load_email_policy


def allowed_icons(config_dir: Path) -> frozenset[str]:
    """Lee los íconos permitidos.

    Args:
        config_dir: Carpeta portal/config.

    Returns:
        Nombres de íconos permitidos.
    """
    return frozenset(
        str(icon) for icon in load_yaml(config_dir / "iconos_permitidos.yaml")["iconos"]
    )


def main(repo_root: Path) -> int:
    """Valida todas las apps del repo.

    Args:
        repo_root: Raíz del repo.

    Returns:
        Exit code (0 si todas son válidas).
    """
    policy = load_email_policy(path=CONFIG_DIR / "politica_correos.yaml")
    icons = allowed_icons(config_dir=CONFIG_DIR)
    folders = app_dirs(repo_root=repo_root)
    errors = [
        error
        for folder in folders
        for error in validate_app(app_dir=folder, policy=policy, icons=icons)
    ]
    for error in errors:
        sys.stderr.write(f"::error::{error}\n")
    if errors:
        return fail(f"{len(errors)} error(es) en los app.yaml.")
    sys.stdout.write(f"Apps válidas: {len(folders)}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    sys.exit(main(repo_root=Path(args.repo_root)))
