"""Control C3: la versión del issue coincide con la declarada en el código del release.

La versión vive en portal/config/portal.yaml (portal.version) o en el app.yaml (version).
"""

import argparse
import sys
from pathlib import Path

from common import fail, load_yaml


def declared_version(repo_root: Path, unit: str) -> str:
    """Lee la versión declarada de una unidad.

    Args:
        repo_root: Raíz del checkout del release.
        unit: 'portal' o 'apps/<dominio>/<app>'.

    Returns:
        La versión CalVer declarada.
    """
    if unit == "portal":
        return str(load_yaml(repo_root / "portal" / "config" / "portal.yaml")["portal"]["version"])
    return str(load_yaml(repo_root / unit / "app.yaml")["version"])


def main(repo_root: Path, unit: str, expected: str) -> int:
    """Compara la versión declarada con la esperada.

    Args:
        repo_root: Raíz del checkout del release.
        unit: Unidad desplegada.
        expected: Versión indicada en el issue.

    Returns:
        Exit code.
    """
    actual = declared_version(repo_root=repo_root, unit=unit)
    if actual != expected:
        return fail(f"C3: {unit} declara la versión '{actual}' pero el issue indica '{expected}'.")
    sys.stdout.write(f"Versión validada: {actual}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--unidad", required=True)
    parser.add_argument("--version-esperada", required=True)
    args = parser.parse_args()
    sys.exit(main(repo_root=Path(args.repo_root), unit=args.unidad, expected=args.version_esperada))
