"""Decide si el cambio de una app entre dos commits es "solo de accesos".

Es solo de accesos cuando la app ya existía en la base y su huella de contenido no cambió
(solo cambiaron `acceso` y/o `version`). En ese caso no hace falta un nuevo deploy_qa.
Output: solo_accesos (true | false).
"""

import argparse
import subprocess
import sys

import yaml
from app_schema import APP_FILE, HTML_FILE, compute_fingerprint
from common import write_github_output


def file_at(ref: str, path: str) -> bytes | None:
    """Lee un archivo tal como estaba en un commit.

    Args:
        ref: Commit o ref.
        path: Ruta relativa a la raíz del repo.

    Returns:
        El contenido, o None si el archivo no existía en ese commit.
    """
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=False)
    return result.stdout if result.returncode == 0 else None


def fingerprint_at(ref: str, app_path: str) -> str | None:
    """Calcula la huella de una app en un commit.

    Args:
        ref: Commit o ref.
        app_path: Carpeta de la app (apps/<dominio>/<app>).

    Returns:
        La huella, o None si la app no existía en ese commit.
    """
    raw_app = file_at(ref=ref, path=f"{app_path}/{APP_FILE}")
    if raw_app is None:
        return None
    app = yaml.safe_load(raw_app)
    return compute_fingerprint(app=app, html=file_at(ref=ref, path=f"{app_path}/{HTML_FILE}"))


def is_access_only(base_ref: str, head_ref: str, app_path: str) -> bool:
    """Compara la huella de la app entre base y head.

    Args:
        base_ref: Commit base.
        head_ref: Commit head.
        app_path: Carpeta de la app.

    Returns:
        True si el contenido no cambió (solo accesos y/o versión).
    """
    base = fingerprint_at(ref=base_ref, app_path=app_path)
    head = fingerprint_at(ref=head_ref, app_path=app_path)
    return base is not None and head is not None and base == head


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--app-path", required=True)
    args = parser.parse_args()
    result = is_access_only(base_ref=args.base_ref, head_ref=args.head_ref, app_path=args.app_path)
    write_github_output(name="solo_accesos", value=str(result).lower())
    sys.stdout.write(f"{args.app_path}: solo_accesos={str(result).lower()}\n")
