"""Calcula la huella de contenido de una app y la publica como output `huella`."""

import argparse
import sys
from pathlib import Path

from app_schema import compute_fingerprint, load_app, read_html
from common import write_github_output


def fingerprint_for(app_dir: Path) -> str:
    """Calcula la huella a partir de los archivos de una carpeta de app.

    Args:
        app_dir: Carpeta `apps/<dominio>/<app>`.

    Returns:
        La huella (SHA-256).
    """
    return compute_fingerprint(app=load_app(app_dir=app_dir), html=read_html(app_dir=app_dir))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-path", required=True)
    args = parser.parse_args()
    fingerprint = fingerprint_for(app_dir=Path(args.app_path))
    write_github_output(name="huella", value=fingerprint)
    sys.stdout.write(f"{fingerprint}\n")
