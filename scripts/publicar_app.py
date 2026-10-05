"""Publica una app en el bucket de webapps de un ambiente (lo usan deploy_qa y deploy_prd).

Orden: primero el index.html (si es herramienta) y después la entrada de catálogo, para que
el catálogo nunca apunte a un HTML que todavía no existe.

Outputs: huella, objetos (lista separada por comas). Escribe además un JSON con el diff de
accesos respecto de la entrada anterior, que la bitácora de PRD registra.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app_schema import (
    access_diff,
    build_catalog_entry,
    catalog_object_name,
    compute_fingerprint,
    html_object_name,
    load_app,
    read_html,
    validate_app,
)
from bucket_io import open_bucket, read_json, upload
from common import CONFIG_DIR, environment_config, fail, write_github_output
from validar_apps import allowed_icons

from alejandria.email_policy import load_email_policy

LIMA = ZoneInfo("America/Lima")


def main(app_path: Path, env: str, sha: str, actor: str, diff_output: Path) -> int:
    """Valida y publica la app en el ambiente.

    Args:
        app_path: Carpeta `apps/<dominio>/<app>`.
        env: Ambiente destino (qa o prd).
        sha: Commit que se publica.
        actor: Usuario de GitHub que ejecuta el despliegue.
        diff_output: Archivo donde se escribe el diff de accesos (JSON).

    Returns:
        Exit code.
    """
    errors = validate_app(
        app_dir=app_path,
        policy=load_email_policy(path=CONFIG_DIR / "politica_correos.yaml"),
        icons=allowed_icons(config_dir=CONFIG_DIR),
    )
    if errors:
        for error in errors:
            sys.stderr.write(f"::error::{error}\n")
        return fail("La app no cumple el contrato; no se publica.")

    config = environment_config(env=env)
    prefix = config["bucket"]["prefijo"]
    bucket = open_bucket(
        bucket_name=config["bucket"]["nombre"], project=config["ambiente"]["proyecto"]
    )

    app = load_app(app_dir=app_path)
    html = read_html(app_dir=app_path)
    fingerprint = compute_fingerprint(app=app, html=html)
    published_at = datetime.now(tz=LIMA).isoformat(timespec="seconds")
    metadata = {"huella": fingerprint, "sha_commit": sha, "version": str(app["version"])}

    objects: list[str] = []
    if html is not None:
        name = html_object_name(prefix=prefix, domain=app["dominio"], app_id=app["id"])
        upload(
            bucket=bucket,
            name=name,
            data=html,
            content_type="text/html; charset=utf-8",
            metadata=metadata,
        )
        objects.append(name)

    catalog_name = catalog_object_name(prefix=prefix, domain=app["dominio"], app_id=app["id"])
    previous = read_json(bucket=bucket, name=catalog_name) or {}
    entry = build_catalog_entry(
        app=app, env=env, fingerprint=fingerprint, sha=sha, actor=actor, published_at=published_at
    )
    upload(
        bucket=bucket,
        name=catalog_name,
        data=json.dumps(entry, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
        metadata=metadata,
    )
    objects.append(catalog_name)

    diff = {
        **access_diff(previous=previous.get("acceso", []), current=entry["acceso"]),
        "version_anterior": previous.get("version", ""),
    }
    diff_output.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")

    write_github_output(name="huella", value=fingerprint)
    write_github_output(name="objetos", value=",".join(objects))
    sys.stdout.write(f"Publicada {app['dominio']}/{app['id']} ({env}): {', '.join(objects)}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-path", required=True)
    parser.add_argument("--env", required=True, choices=["qa", "prd"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--diff-output", required=True)
    args = parser.parse_args()
    sys.exit(
        main(
            app_path=Path(args.app_path),
            env=args.env,
            sha=args.sha,
            actor=args.actor,
            diff_output=Path(args.diff_output),
        )
    )
