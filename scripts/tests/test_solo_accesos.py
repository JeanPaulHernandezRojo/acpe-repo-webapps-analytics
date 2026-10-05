import subprocess
from pathlib import Path

import pytest
import yaml
from app_factory import base_app, write_app
from huella import fingerprint_for
from solo_accesos import fingerprint_at, is_access_only

HTML = b"<html><body>v1</body></html>"
APP_PATH = "apps/comercial/simulador"


def git(repo: Path, args: list[str]) -> str:
    """Ejecuta git en el repo de prueba.

    Args:
        repo: Carpeta del repo.
        args: Argumentos de git.

    Returns:
        La salida estándar.
    """
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    """Hace commit de todo y devuelve el SHA.

    Args:
        repo: Carpeta del repo.
        message: Mensaje del commit.

    Returns:
        SHA del commit.
    """
    git(repo, ["add", "-A"])
    git(repo, ["commit", "-q", "-m", message])
    return git(repo, ["rev-parse", "HEAD"])


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repo git vacío como directorio de trabajo."""
    git(tmp_path, ["init", "-q"])
    git(tmp_path, ["config", "user.email", "ci@example.com"])
    git(tmp_path, ["config", "user.name", "ci"])
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_access_change_is_access_only(repo: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    write_app(repo, app, HTML)
    base = commit_all(repo, "inicial")
    app["acceso"]["prd"].append("rosa@alicorp.com.pe")
    app["version"] = "2026-10-02-01"
    write_app(repo, app, HTML)
    head = commit_all(repo, "accesos")

    assert is_access_only(base_ref=base, head_ref=head, app_path=APP_PATH)
    assert fingerprint_at(ref=head, app_path=APP_PATH) == fingerprint_for(app_dir=repo / APP_PATH)


def test_html_change_is_not_access_only(repo: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    write_app(repo, app, HTML)
    base = commit_all(repo, "inicial")
    write_app(repo, app, b"<html><body>v2</body></html>")
    head = commit_all(repo, "html")

    assert not is_access_only(base_ref=base, head_ref=head, app_path=APP_PATH)


def test_new_app_is_not_access_only(repo: Path) -> None:
    (repo / "README.md").write_text("repo", encoding="utf-8")
    base = commit_all(repo, "inicial")
    write_app(repo, base_app("comercial", "simulador", "herramienta"), HTML)
    head = commit_all(repo, "nueva app")

    assert not is_access_only(base_ref=base, head_ref=head, app_path=APP_PATH)


def test_yaml_formatting_does_not_change_fingerprint(repo: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    write_app(repo, app, HTML)
    base = commit_all(repo, "inicial")
    text = yaml.safe_dump(app, allow_unicode=True, sort_keys=False)
    (repo / APP_PATH / "app.yaml").write_text("# comentario\n" + text, encoding="utf-8")
    head = commit_all(repo, "formato")

    assert is_access_only(base_ref=base, head_ref=head, app_path=APP_PATH)
