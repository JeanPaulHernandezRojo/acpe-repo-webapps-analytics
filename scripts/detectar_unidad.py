"""Detecta qué unidad desplegable toca un cambio: el portal o una app.

Regla: una PR toca como máximo UNA unidad, `portal` o `apps/<dominio>/<app>`. Los cambios
a docs/, scripts/, .github/ o README acompañan a cualquier unidad (o van solos).

Salidas (GitHub Actions): unidad, tipo (portal | app | ninguna), dominio, app_id.
"""

import argparse
import re
import subprocess
import sys

from common import fail, write_github_output

# Archivos que definen la imagen del portal: un cambio en ellos es un cambio del portal.
PORTAL_PATHS = ("portal/", "pyproject.toml", "uv.lock", ".dockerignore")
APP_PATTERN = re.compile(r"^apps/([^/]+)/([^/]+)/")


def changed_files(base_ref: str, head_ref: str) -> list[str]:
    """Lista los archivos modificados entre dos refs.

    Args:
        base_ref: Ref base (ej. origin/main).
        head_ref: Ref head (ej. HEAD).

    Returns:
        Rutas modificadas.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def classify(paths: list[str]) -> set[str]:
    """Agrupa los archivos modificados en unidades desplegables.

    Args:
        paths: Rutas modificadas.

    Returns:
        Unidades tocadas: 'portal' y/o 'apps/<dominio>/<app>'.
    """
    units: set[str] = set()
    for path in paths:
        if path.startswith(PORTAL_PATHS[0]) or path in PORTAL_PATHS[1:]:
            units.add("portal")
            continue
        match = APP_PATTERN.match(path)
        if match:
            units.add(f"apps/{match.group(1)}/{match.group(2)}")
    return units


def main(base_ref: str, head_ref: str, require_unit: bool) -> int:
    """Detecta la unidad y publica los outputs.

    Args:
        base_ref: Ref base.
        head_ref: Ref head.
        require_unit: Si True, exige exactamente una unidad (deploy_qa).

    Returns:
        Exit code.
    """
    units = classify(paths=changed_files(base_ref=base_ref, head_ref=head_ref))
    if len(units) > 1:
        return fail(
            f"Una PR solo puede tocar una unidad (portal o una app). Encontradas: {sorted(units)}"
        )
    if require_unit and not units:
        return fail("No hay cambios en portal/ ni en apps/: no hay nada que desplegar.")

    unit = next(iter(units), "")
    kind = "ninguna" if not unit else ("portal" if unit == "portal" else "app")
    _, domain, app_id = unit.split("/") if kind == "app" else ("", "", "")
    sys.stdout.write(f"Unidad detectada: {unit or '<ninguna>'}\n")
    write_github_output(name="unidad", value=unit)
    write_github_output(name="tipo", value=kind)
    write_github_output(name="dominio", value=domain)
    write_github_output(name="app_id", value=app_id)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--require-unit", action="store_true")
    args = parser.parse_args()
    sys.exit(main(base_ref=args.base_ref, head_ref=args.head_ref, require_unit=args.require_unit))
