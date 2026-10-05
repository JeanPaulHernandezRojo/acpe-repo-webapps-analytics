import json
from pathlib import Path

import pase_prd
import pytest

ISSUE_BODY = """### Unidad a desplegar

apps/comercial/simulador

### Versión

2026-10-05-01

### Tipo de cambio

Incremental

### Área de negocio impactada

Comercial

### Detalle del cambio

Agrega el escenario de canal moderno.

### Notas

_No response_
"""


def test_parse_issue_form() -> None:
    fields = pase_prd.parsear_formulario(ISSUE_BODY)
    assert fields[pase_prd.CAMPO_RUTA] == "apps/comercial/simulador"
    assert fields[pase_prd.CAMPO_VERSION] == "2026-10-05-01"
    assert fields[pase_prd.CAMPO_TIPO] == "Incremental"
    assert fields[pase_prd.CAMPO_DETALLE] == "Agrega el escenario de canal moderno."
    assert fields["Notas"] == ""


def test_issue_template_labels_match_the_parser() -> None:
    template = Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "pase_prd.yml"
    text = template.read_text(encoding="utf-8")
    for label in (
        pase_prd.CAMPO_RUTA,
        pase_prd.CAMPO_VERSION,
        pase_prd.CAMPO_TIPO,
        pase_prd.CAMPO_AREA,
        pase_prd.CAMPO_DETALLE,
    ):
        assert f"label: {label}" in text
    for change_type in pase_prd.TIPOS_VALIDOS:
        assert f"- {change_type}" in text


@pytest.mark.parametrize(
    ("unit", "valid"),
    [
        ("portal", True),
        ("apps/comercial/simulador", True),
        ("apps/Comercial/simulador", False),
        ("apps/comercial", False),
        ("scripts", False),
    ],
)
def test_unit_pattern(unit: str, valid: bool) -> None:
    assert bool(pase_prd.PATRON_RUTA.match(unit)) is valid


def test_release_branch_and_log_folder() -> None:
    assert pase_prd.rama_release(ruta="portal", version="2026-10-01-01") == (
        "release_portal_2026-10-01-01"
    )
    assert pase_prd.rama_release(ruta="apps/comercial/simulador", version="2026-10-01-01") == (
        "release_comercial_simulador_2026-10-01-01"
    )
    assert pase_prd.carpeta_bitacora(ruta="portal") == "_portal"
    assert pase_prd.carpeta_bitacora(ruta="apps/comercial/simulador") == "comercial/simulador"


@pytest.mark.parametrize(
    ("validation", "qa", "job", "expected"),
    [
        ("success", "success", "success", "exitoso"),
        ("failure", "skipped", "failure", "rechazado"),
        ("success", "failure", "failure", "rechazado"),
        ("success", "success", "failure", "fallido"),
        ("success", "success", "cancelled", "cancelado"),
    ],
)
def test_resolve_state(validation: str, qa: str, job: str, expected: str) -> None:
    result = pase_prd.resolver_estado(
        estado_validacion=validation, estado_qa_control=qa, estado_job=job
    )
    assert result == expected


def test_app_qa_control_accepts_matching_fingerprint(tmp_path: Path, monkeypatch) -> None:
    context = tmp_path / "contexto.json"
    context.write_text(json.dumps({"des_ruta_unidad": "apps/comercial/simulador"}))
    monkeypatch.setattr(
        pase_prd,
        "leer_gcs_json",
        lambda uri: {"huella": "abc", "sha_commit": "123", "publicado_en": "t"},
    )
    code = pase_prd.validar_qa_app(
        huella_release="abc",
        qa_catalogo_uri="gs://b/qa/_catalogo/comercial/simulador.json",
        bucket_uri="gs://b/prd_bitacora",
        contexto_path=str(context),
    )
    assert code == 0
    assert json.loads(context.read_text())["qa"]["des_origen"] == "catalogo_qa"


def test_app_qa_control_rollback_uses_previous_successful_pass(tmp_path: Path, monkeypatch) -> None:
    context = tmp_path / "contexto.json"
    context.write_text(
        json.dumps({"des_ruta_unidad": "apps/comercial/simulador", "tip_cambio": "Rollback"})
    )
    documents = {
        "gs://b/qa/_catalogo/comercial/simulador.json": {"huella": "nueva"},
        "gs://b/prd_bitacora/comercial/simulador/1_exitoso.json": {
            "artefacto": {"cod_huella": "antigua"},
            "qa": {"cod_sha_probado": "999"},
        },
    }
    monkeypatch.setattr(pase_prd, "leer_gcs_json", lambda uri: documents.get(uri))
    monkeypatch.setattr(
        pase_prd,
        "pases_exitosos",
        lambda bucket_uri, carpeta: ["gs://b/prd_bitacora/comercial/simulador/1_exitoso.json"],
    )
    code = pase_prd.validar_qa_app(
        huella_release="antigua",
        qa_catalogo_uri="gs://b/qa/_catalogo/comercial/simulador.json",
        bucket_uri="gs://b/prd_bitacora",
        contexto_path=str(context),
    )
    assert code == 0
    assert json.loads(context.read_text())["qa"]["cod_sha_probado"] == "999"


def test_app_qa_control_rejects_different_fingerprint(tmp_path: Path, monkeypatch) -> None:
    context = tmp_path / "contexto.json"
    context.write_text(
        json.dumps({"des_ruta_unidad": "apps/comercial/simulador", "tip_cambio": "Incremental"})
    )
    monkeypatch.setattr(pase_prd, "leer_gcs_json", lambda uri: {"huella": "otra"})
    code = pase_prd.validar_qa_app(
        huella_release="abc",
        qa_catalogo_uri="gs://b/qa/_catalogo/comercial/simulador.json",
        bucket_uri="gs://b/prd_bitacora",
        contexto_path=str(context),
    )
    assert code == 1
    assert "no coincide" in json.loads(context.read_text())["des_motivo_resultado"]


def test_app_qa_control_rollback_without_log_is_rejected(tmp_path: Path, monkeypatch) -> None:
    context = tmp_path / "contexto.json"
    context.write_text(
        json.dumps({"des_ruta_unidad": "apps/comercial/simulador", "tip_cambio": "Rollback"})
    )
    monkeypatch.setattr(pase_prd, "leer_gcs_json", lambda uri: {"huella": "nueva"})

    def no_debe_listar(bucket_uri: str, carpeta: str) -> list[str]:
        raise AssertionError("sin bitácora no se lista")

    monkeypatch.setattr(pase_prd, "pases_exitosos", no_debe_listar)
    code = pase_prd.validar_qa_app(
        huella_release="antigua",
        qa_catalogo_uri="gs://b/qa/_catalogo/comercial/simulador.json",
        bucket_uri="",
        contexto_path=str(context),
    )
    assert code == 1


def test_root_path_hash_uses_contents_root(monkeypatch) -> None:
    calls: list[str] = []

    def fake_api(token: str, method: str, ruta: str, payload: dict | None) -> tuple[int, list]:
        calls.append(ruta)
        return 200, [{"name": "uv.lock", "sha": "abc"}]

    monkeypatch.setattr(pase_prd, "api", fake_api)
    assert pase_prd.hash_de_ruta(token="t", repo="o/r", sha="s", ruta="uv.lock") == "abc"
    assert calls == ["/repos/o/r/contents?ref=s"]
