from pathlib import Path

from app_factory import ICONS, base_app, make_policy, write_app
from app_schema import (
    access_diff,
    app_dirs,
    build_catalog_entry,
    catalog_object_name,
    compute_fingerprint,
    html_object_name,
    resolve_capabilities,
    validate_app,
)

POLICY = make_policy()
HTML = b"<!doctype html><html><body>Actualizado al 01/10/2026</body></html>"


def test_valid_tool(tmp_path: Path) -> None:
    folder = write_app(tmp_path, base_app("comercial", "simulador", "herramienta"), HTML)
    assert validate_app(app_dir=folder, policy=POLICY, icons=ICONS) == []


def test_valid_pipeline_without_html(tmp_path: Path) -> None:
    folder = write_app(tmp_path, base_app("supply", "pronostico", "pipeline"), None)
    assert validate_app(app_dir=folder, policy=POLICY, icons=ICONS) == []


def test_tool_requires_html_and_pipeline_rejects_it(tmp_path: Path) -> None:
    tool = write_app(tmp_path, base_app("comercial", "simulador", "herramienta"), None)
    pipeline = write_app(tmp_path, base_app("supply", "pronostico", "pipeline"), HTML)
    assert any("index.html" in e for e in validate_app(app_dir=tool, policy=POLICY, icons=ICONS))
    assert any("pipeline" in e for e in validate_app(app_dir=pipeline, policy=POLICY, icons=ICONS))


def test_id_and_domain_must_match_folders(tmp_path: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    folder = write_app(tmp_path, app, HTML)
    app["id"] = "otro"
    app["dominio"] = "otro"
    (folder / "app.yaml").write_text(
        (folder / "app.yaml").read_text().replace("id: simulador", "id: otro"), encoding="utf-8"
    )
    errors = validate_app(app_dir=folder, policy=POLICY, icons=ICONS)
    assert any("id debe ser igual" in e for e in errors)


def test_reserved_domain(tmp_path: Path) -> None:
    folder = write_app(tmp_path, base_app("portal", "simulador", "herramienta"), HTML)
    assert any("reservado" in e for e in validate_app(app_dir=folder, policy=POLICY, icons=ICONS))


def test_email_rules(tmp_path: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    app["acceso"]["qa"] = [
        "Ana.Perez@alicorp.com.pe",
        "juan@gmail.com",
        "ext_luis@alicorp.com.pe",
        "rosa@alicorp.com.pe",
        "rosa@alicorp.com.pe",
    ]
    folder = write_app(tmp_path, app, HTML)
    errors = " | ".join(validate_app(app_dir=folder, policy=POLICY, icons=ICONS))
    assert "minúsculas" in errors
    assert "dominio_no_permitido" in errors
    assert "prefijo_excluido" in errors
    assert "repetido" in errors


def test_access_must_declare_both_environments(tmp_path: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    app["acceso"] = {"prd": []}
    folder = write_app(tmp_path, app, HTML)
    assert any(
        "'qa' y 'prd'" in e for e in validate_app(app_dir=folder, policy=POLICY, icons=ICONS)
    )


def test_card_capabilities_watermark_labels_and_unknown_keys(tmp_path: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    app["tarjeta"]["icono"] = "rocket"
    app["capacidades"] = {"descargas": "si", "camara": True}
    app["marca_agua"] = "gigante"
    app["labels"] = {"ceco": "Data Analytics"}
    app["frescura"] = "diaria"
    folder = write_app(tmp_path, app, HTML)
    errors = " | ".join(validate_app(app_dir=folder, policy=POLICY, icons=ICONS))
    assert "iconos_permitidos" in errors
    assert "capacidades desconocidas" in errors
    assert "true o false" in errors
    assert "marca_agua" in errors
    assert "managed_by" in errors
    assert "label inválido" in errors
    assert "claves desconocidas" in errors


def test_invalid_version(tmp_path: Path) -> None:
    app = base_app("comercial", "simulador", "herramienta")
    app["version"] = "v1"
    folder = write_app(tmp_path, app, HTML)
    assert any(
        "AAAA-MM-DD-NN" in e for e in validate_app(app_dir=folder, policy=POLICY, icons=ICONS)
    )


def test_fingerprint_ignores_access_and_version() -> None:
    app = base_app("comercial", "simulador", "herramienta")
    original = compute_fingerprint(app=app, html=HTML)
    changed = {**app, "version": "2026-12-01-01", "acceso": {"qa": [], "prd": []}}
    assert compute_fingerprint(app=changed, html=HTML) == original


def test_fingerprint_changes_with_content() -> None:
    app = base_app("comercial", "simulador", "herramienta")
    original = compute_fingerprint(app=app, html=HTML)
    assert compute_fingerprint(app=app, html=HTML + b" ") != original
    assert compute_fingerprint(app={**app, "marca_agua": "franja"}, html=HTML) != original
    assert compute_fingerprint(app=app, html=None) != original


def test_catalog_entry_uses_environment_access_and_defaults() -> None:
    app = base_app("comercial", "simulador", "herramienta")
    app["acceso"]["prd"] = ["zoe@alicorp.com.pe", "ana.perez@alicorp.com.pe"]
    app["capacidades"] = {"descargas": False}
    entry = build_catalog_entry(
        app=app, env="prd", fingerprint="abc", sha="123", actor="jperez", published_at="t"
    )
    assert entry["acceso"] == ["ana.perez@alicorp.com.pe", "zoe@alicorp.com.pe"]
    assert entry["capacidades"] == {
        "descargas": False,
        "ventanas": True,
        "dialogos": True,
        "formularios": True,
    }
    assert entry["marca_agua"] == "patron_suave"
    assert entry["huella"] == "abc"


def test_object_names_and_helpers(tmp_path: Path) -> None:
    write_app(tmp_path, base_app("comercial", "b_app", "herramienta"), HTML)
    write_app(tmp_path, base_app("comercial", "a_app", "herramienta"), HTML)
    assert [p.name for p in app_dirs(repo_root=tmp_path)] == ["a_app", "b_app"]
    assert catalog_object_name(prefix="qa", domain="d", app_id="a") == "qa/_catalogo/d/a.json"
    assert html_object_name(prefix="prd", domain="d", app_id="a") == "prd/d/a/index.html"
    assert resolve_capabilities(raw=None) == dict.fromkeys(
        ("descargas", "ventanas", "dialogos", "formularios"), True
    )
    assert access_diff(previous=["a", "b"], current=["b", "c"]) == {
        "agregados": ["c"],
        "quitados": ["a"],
    }
