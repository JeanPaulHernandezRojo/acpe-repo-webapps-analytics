import pytest
from conftest import CONFIG_DIR

from alejandria.settings import load_csp_allowlist, load_environment, load_settings


def test_load_settings_qa(settings):
    assert settings.environment.name == "qa"
    assert settings.environment.bucket == "us-qa-stg-ml-webapps"
    assert settings.environment.bucket_prefix == "qa"
    assert settings.environment.session_hours == 12
    assert settings.portal.name == "ALEJANDRÍA"
    assert settings.identity.api_key == "clave-publica"


@pytest.mark.parametrize("env", ["qa", "prd"])
def test_both_environments_load(env):
    environment = load_environment(config_dir=CONFIG_DIR, app_env=env)
    assert environment.name == env
    assert environment.bucket_prefix == env


def test_invalid_environment():
    with pytest.raises(ValueError, match="APP_ENV"):
        load_environment(config_dir=CONFIG_DIR, app_env="dev")


def test_missing_env_vars():
    with pytest.raises(ValueError, match="Variables de entorno faltantes"):
        load_settings(environ={"APP_ENV": "qa"})


def test_csp_allowlist_requires_https(tmp_path):
    (tmp_path / "csp_allowlist.yaml").write_text(
        "csp:\n  mapas: ['http://tiles.inseguro.com']\n  cdn: []\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="https"):
        load_csp_allowlist(config_dir=tmp_path)
