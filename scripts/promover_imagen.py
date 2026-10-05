"""Promueve por digest la imagen del portal validada en QA al Artifact Registry de PRD.

Recibe el tag inmutable <version>-<sha> que el control C4 identificó, resuelve su digest en
QA y publica ese mismo digest en PRD (sin reconstruir) con los tags <version> y
<version>-<sha>. Outputs: image_uri (tag), image_ref (por digest, para desplegar), digest.
"""

import argparse
import subprocess
import sys

from common import write_github_output


def resolve_digest(image: str, tag: str) -> str:
    """Resuelve el digest sha256 de un tag.

    Args:
        image: Ruta de la imagen sin tag.
        tag: Tag a resolver.

    Returns:
        El digest (sha256:...).
    """
    result = subprocess.run(
        [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            f"{image}:{tag}",
            "--format=value(image_summary.digest)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main(qa_image: str, prd_image: str, source_tag: str, version: str, registry_host: str) -> int:
    """Copia la imagen de QA a PRD por digest.

    Args:
        qa_image: Imagen de QA sin tag.
        prd_image: Imagen de PRD sin tag.
        source_tag: Tag inmutable validado en QA (<version>-<sha>).
        version: Versión CalVer (tag móvil en PRD).
        registry_host: Host de Artifact Registry (ej. us-east1-docker.pkg.dev).

    Returns:
        Exit code.
    """
    digest = resolve_digest(image=qa_image, tag=source_tag)
    source = f"{qa_image}@{digest}"
    subprocess.run(["gcloud", "auth", "configure-docker", registry_host, "--quiet"], check=True)
    subprocess.run(["docker", "pull", source], check=True)
    for tag in (version, source_tag):
        destination = f"{prd_image}:{tag}"
        subprocess.run(["docker", "tag", source, destination], check=True)
        subprocess.run(["docker", "push", destination], check=True)

    write_github_output(name="image_uri", value=f"{prd_image}:{version}")
    write_github_output(name="image_ref", value=f"{prd_image}@{digest}")
    write_github_output(name="digest", value=digest)
    sys.stdout.write(f"Promovida {source} -> {prd_image}:{version}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-image", required=True)
    parser.add_argument("--prd-image", required=True)
    parser.add_argument("--source-tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--registry-host", required=True)
    args = parser.parse_args()
    sys.exit(
        main(
            qa_image=args.qa_image,
            prd_image=args.prd_image,
            source_tag=args.source_tag,
            version=args.version,
            registry_host=args.registry_host,
        )
    )
