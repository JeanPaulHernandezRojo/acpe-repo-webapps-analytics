"""Lee valores de un YAML de configuración y los publica como outputs de GitHub Actions.

Ejemplo:
    --archivo portal/config/env_qa.yaml \
    --valor repositorio=imagen.repositorio --valor nombre=imagen.nombre

Un valor que sea un mapeo se publica como `k=v,k=v` (el formato de labels de gcloud).
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from common import fail, load_yaml, write_github_output


def read_key(content: dict[str, Any], dotted_key: str) -> Any:
    """Obtiene un valor por su clave con puntos.

    Args:
        content: YAML ya cargado.
        dotted_key: Clave, por ejemplo "cloud_run.max_instances".

    Returns:
        El valor.

    Raises:
        KeyError: si alguna parte de la clave no existe.
    """
    value: Any = content
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted_key)
        value = value[part]
    return value


def render(value: Any) -> str:
    """Convierte un valor del YAML en texto de una línea.

    Args:
        value: Valor leído.

    Returns:
        El texto; los mapeos quedan como `k=v,k=v`.
    """
    if isinstance(value, dict):
        return ",".join(f"{key}={item}" for key, item in value.items())
    return str(value)


def main(file: Path, pairs: list[str]) -> int:
    """Publica cada valor pedido como output.

    Args:
        file: Archivo YAML.
        pairs: Pares `salida=clave.con.puntos`.

    Returns:
        Exit code.
    """
    content = load_yaml(file)
    for pair in pairs:
        output, _, key = pair.partition("=")
        if not output or not key:
            return fail(f"Formato inválido '{pair}': usar salida=clave.con.puntos.")
        try:
            value = render(read_key(content=content, dotted_key=key))
        except KeyError:
            return fail(f"No existe la clave '{key}' en {file}.")
        write_github_output(name=output, value=value)
        sys.stdout.write(f"{output}={value}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archivo", required=True)
    parser.add_argument("--valor", required=True, action="append")
    args = parser.parse_args()
    sys.exit(main(file=Path(args.archivo), pairs=args.valor))
