"""Actualiza la lista de acceso de QA de una app sin un nuevo deploy_qa.

Se ejecuta al hacer merge a main de un cambio "solo de accesos". Solo actúa si la huella
de la app coincide con la publicada en QA: es decir, si el contenido ya validado en QA es
el mismo y lo único que cambió es quién puede verlo.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app_schema import catalog_object_name, compute_fingerprint, load_app, read_html
from bucket_io import open_bucket, read_json, upload
from common import environment_config

LIMA = ZoneInfo("America/Lima")


def main(app_path: Path, sha: str, actor: str) -> int:
    """Sincroniza `acceso.qa` y `version` en el catálogo de QA.

    Args:
        app_path: Carpeta `apps/<dominio>/<app>`.
        sha: Commit de main que contiene el cambio.
        actor: Usuario de GitHub que hizo el merge.

    Returns:
        Exit code (0 también cuando no corresponde sincronizar: solo se avisa).
    """
    app = load_app(app_dir=app_path)
    config = environment_config(env="qa")
    bucket = open_bucket(
        bucket_name=config["bucket"]["nombre"], project=config["ambiente"]["proyecto"]
    )
    name = catalog_object_name(
        prefix=config["bucket"]["prefijo"], domain=app["dominio"], app_id=app["id"]
    )
    entry = read_json(bucket=bucket, name=name)
    if entry is None:
        sys.stdout.write(f"::warning::{app_path} no está publicada en QA: requiere deploy_qa.\n")
        return 0
    fingerprint = compute_fingerprint(app=app, html=read_html(app_dir=app_path))
    if entry.get("huella") != fingerprint:
        sys.stdout.write(
            f"::warning::{app_path}: el contenido difiere del publicado en QA; "
            "requiere deploy_qa.\n"
        )
        return 0
    entry.update(
        {
            "acceso": sorted(str(email) for email in app["acceso"]["qa"]),
            "version": str(app["version"]),
            "sha_commit": sha,
            "publicado_en": datetime.now(tz=LIMA).isoformat(timespec="seconds"),
            "publicado_por": actor,
        }
    )
    upload(
        bucket=bucket,
        name=name,
        data=json.dumps(entry, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
        metadata={"huella": fingerprint, "sha_commit": sha, "version": str(app["version"])},
    )
    sys.stdout.write(f"Accesos de QA sincronizados para {app['dominio']}/{app['id']}.\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-path", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--actor", required=True)
    args = parser.parse_args()
    sys.exit(main(app_path=Path(args.app_path), sha=args.sha, actor=args.actor))
