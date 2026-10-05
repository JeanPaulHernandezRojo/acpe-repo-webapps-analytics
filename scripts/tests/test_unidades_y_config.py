from pathlib import Path

import pytest
import yaml
from common import CONFIG_DIR, environment_config, load_yaml
from desplegar_portal import deploy_args, service_labels
from detectar_unidad import classify
from leer_config import read_key, render
from verificar_version import declared_version
from verificar_version import main as verify_version


def test_classify_portal_paths() -> None:
    assert classify(paths=["portal/backend/src/alejandria/app.py"]) == {"portal"}
    assert classify(paths=["uv.lock", "pyproject.toml", ".dockerignore"]) == {"portal"}


def test_classify_app_and_neutral_paths() -> None:
    units = classify(
        paths=["apps/comercial/simulador/app.yaml", "docs/guia_data_scientist.md", "README.md"]
    )
    assert units == {"apps/comercial/simulador"}
    assert classify(paths=[".github/workflows/pr_checks.yml", "scripts/common.py"]) == set()


def test_classify_detects_multiple_units() -> None:
    units = classify(paths=["apps/a/x/app.yaml", "apps/b/y/index.html", "portal/Dockerfile"])
    assert units == {"apps/a/x", "apps/b/y", "portal"}


def test_classify_ignores_files_at_domain_level() -> None:
    assert classify(paths=["apps/.gitkeep", "apps/comercial/README.md"]) == set()


def test_read_key() -> None:
    content = {"cloud_run": {"max_instances": 1}}
    assert read_key(content=content, dotted_key="cloud_run.max_instances") == 1
    with pytest.raises(KeyError):
        read_key(content=content, dotted_key="cloud_run.cpu")


def test_real_environment_files_have_expected_keys() -> None:
    config_dir = Path(__file__).resolve().parents[2] / "portal" / "config"
    for env in ("qa", "prd"):
        content = yaml.safe_load((config_dir / f"env_{env}.yaml").read_text(encoding="utf-8"))
        for key in (
            "ambiente.proyecto",
            "cloud_run.servicio",
            "cloud_run.cuenta_runtime",
            "cloud_run.min_instances",
            "cloud_run.max_instances",
            "imagen.repositorio",
            "bucket.nombre",
            "bucket.prefijo",
        ):
            read_key(content=content, dotted_key=key)


def test_declared_version(tmp_path: Path) -> None:
    (tmp_path / "portal" / "config").mkdir(parents=True)
    (tmp_path / "portal" / "config" / "portal.yaml").write_text(
        'portal:\n  version: "2026-10-01-01"\n', encoding="utf-8"
    )
    app_dir = tmp_path / "apps" / "comercial" / "simulador"
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text('version: "2026-10-05-02"\n', encoding="utf-8")

    assert declared_version(repo_root=tmp_path, unit="portal") == "2026-10-01-01"
    assert declared_version(repo_root=tmp_path, unit="apps/comercial/simulador") == "2026-10-05-02"
    assert verify_version(repo_root=tmp_path, unit="portal", expected="2026-10-01-01") == 0
    assert verify_version(repo_root=tmp_path, unit="portal", expected="2026-10-02-01") == 1


def test_render_mapping_as_gcloud_labels() -> None:
    assert render(value={"domain": "analitica", "ceco": "x"}) == "domain=analitica,ceco=x"
    assert render(value=1) == "1"


def test_deploy_args_follow_environment_config() -> None:
    config = environment_config(env="prd")
    portal = load_yaml(CONFIG_DIR / "portal.yaml")
    labels = service_labels(portal=portal, env_name="prd", version="2026-10-01-01")
    args = deploy_args(
        config=config,
        labels=labels,
        image_ref="repo/portal@sha256:abc",
        identity_api_key="key",
        identity_auth_domain="dominio",
    )
    assert args[2] == config["cloud_run"]["servicio"]
    assert f"--max-instances={config['cloud_run']['max_instances']}" in args
    assert f"--service-account={config['cloud_run']['cuenta_runtime']}" in args
    assert "--allow-unauthenticated" in args
    env_vars = next(a for a in args if a.startswith("--set-env-vars="))
    assert "APP_ENV=prd" in env_vars
    assert f"GCP_PROJECT_ID={config['ambiente']['proyecto']}" in env_vars
    label_arg = next(a for a in args if a.startswith("--labels="))
    assert "env=prd" in label_arg
    assert "version=2026-10-01-01" in label_arg
