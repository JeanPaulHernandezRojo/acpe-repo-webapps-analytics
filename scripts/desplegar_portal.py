"""Despliega la imagen del portal en Cloud Run y hace el smoke test (deploy_qa y deploy_prd).

Todos los parámetros del servicio salen de `portal/config/env_<env>.yaml` y los labels de
`portal/config/portal.yaml`; el workflow solo aporta la imagen y los datos de Identity
Platform. El smoke test exige que `/api/salud` responda con la versión desplegada.

Output: url (URL del servicio).
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from common import CONFIG_DIR, environment_config, fail, load_yaml, write_github_output

# Smoke test: intentos y espera entre intentos (la revisión nueva puede tardar en servir).
SMOKE_ATTEMPTS = 10
SMOKE_WAIT_SECONDS = 6


def deploy_args(
    config: dict[str, Any],
    labels: dict[str, str],
    image_ref: str,
    identity_api_key: str,
    identity_auth_domain: str,
) -> list[str]:
    """Arma los argumentos de `gcloud run deploy`.

    Args:
        config: Contenido de env_<env>.yaml.
        labels: Labels finales del servicio.
        image_ref: Imagen por digest (repo/imagen@sha256:...).
        identity_api_key: API key web de Identity Platform.
        identity_auth_domain: Dominio de autenticación de Identity Platform.

    Returns:
        Argumentos para gcloud.
    """
    run = config["cloud_run"]
    environment = config["ambiente"]
    env_vars = {
        "APP_ENV": environment["nombre"],
        "GCP_PROJECT_ID": environment["proyecto"],
        "IDENTITY_API_KEY": identity_api_key,
        "IDENTITY_AUTH_DOMAIN": identity_auth_domain,
    }
    return [
        "run",
        "deploy",
        run["servicio"],
        f"--project={environment['proyecto']}",
        f"--region={environment['region']}",
        f"--image={image_ref}",
        f"--service-account={run['cuenta_runtime']}",
        f"--min-instances={run['min_instances']}",
        f"--max-instances={run['max_instances']}",
        f"--cpu={run['cpu']}",
        f"--memory={run['memoria']}",
        f"--concurrency={run['concurrencia']}",
        "--port=8080",
        "--cpu-boost",
        # El portal se abre desde internet: la seguridad está en el login de Identity
        # Platform y en la autorización por app del backend.
        "--allow-unauthenticated",
        "--set-env-vars=" + ",".join(f"{key}={value}" for key, value in env_vars.items()),
        "--labels=" + ",".join(f"{key}={value}" for key, value in labels.items()),
        "--quiet",
    ]


def service_labels(portal: dict[str, Any], env_name: str, version: str) -> dict[str, str]:
    """Combina los labels de portal.yaml con el ambiente y la versión.

    Args:
        portal: Contenido de portal.yaml.
        env_name: Nombre del ambiente (qa o prd).
        version: Versión CalVer desplegada.

    Returns:
        Labels del servicio.
    """
    return {
        **{str(k): str(v) for k, v in portal["labels"].items()},
        "env": env_name,
        "version": version,
    }


def smoke_test(url: str, version: str) -> bool:
    """Verifica que el servicio responda con la versión esperada.

    Args:
        url: URL base del servicio.
        version: Versión que debe informar /api/salud.

    Returns:
        True si respondió correctamente dentro de los intentos.
    """
    for attempt in range(1, SMOKE_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(f"{url}/api/salud", timeout=10) as response:
                body = json.loads(response.read())
                if body.get("version") == version:
                    return True
                sys.stdout.write(f"Intento {attempt}: versión {body.get('version')!r}\n")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            sys.stdout.write(f"Intento {attempt}: {error}\n")
        time.sleep(SMOKE_WAIT_SECONDS)
    return False


def main(
    env: str, image_ref: str, version: str, identity_api_key: str, identity_auth_domain: str
) -> int:
    """Despliega y verifica el portal.

    Args:
        env: Ambiente (qa o prd).
        image_ref: Imagen por digest.
        version: Versión CalVer (debe coincidir con portal.yaml).
        identity_api_key: API key web de Identity Platform.
        identity_auth_domain: Dominio de autenticación de Identity Platform.

    Returns:
        Exit code.
    """
    config = environment_config(env=env)
    portal = load_yaml(CONFIG_DIR / "portal.yaml")
    if str(portal["portal"]["version"]) != version:
        return fail(f"portal.yaml declara {portal['portal']['version']} y se despliega {version}.")

    labels = service_labels(portal=portal, env_name=config["ambiente"]["nombre"], version=version)
    subprocess.run(
        [
            "gcloud",
            *deploy_args(
                config=config,
                labels=labels,
                image_ref=image_ref,
                identity_api_key=identity_api_key,
                identity_auth_domain=identity_auth_domain,
            ),
        ],
        check=True,
    )
    url = subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            config["cloud_run"]["servicio"],
            f"--project={config['ambiente']['proyecto']}",
            f"--region={config['ambiente']['region']}",
            "--format=value(status.url)",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    write_github_output(name="url", value=url)

    if not smoke_test(url=url, version=version):
        return fail(f"El smoke test de {url}/api/salud no respondió con la versión {version}.")
    sys.stdout.write(f"Portal {version} desplegado en {url}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=["qa", "prd"])
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--identity-api-key", required=True)
    parser.add_argument("--identity-auth-domain", required=True)
    args = parser.parse_args()
    sys.exit(
        main(
            env=args.env,
            image_ref=args.image_ref,
            version=args.version,
            identity_api_key=args.identity_api_key,
            identity_auth_domain=args.identity_auth_domain,
        )
    )
