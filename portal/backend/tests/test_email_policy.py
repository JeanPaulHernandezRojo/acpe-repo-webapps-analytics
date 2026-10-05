import pytest

from alejandria.email_policy import EmailPolicy, evaluate_email, load_email_policy, normalize_email

POLICY = EmailPolicy(
    allowed_domains=("alicorp.com.pe",),
    excluded_prefixes=("ext_",),
    rejection_message="Solo correos corporativos.",
)


def test_normalize_strips_and_lowercases():
    assert normalize_email("  JPerez@Alicorp.COM.pe ") == "jperez@alicorp.com.pe"


@pytest.mark.parametrize(
    ("email", "allowed", "reason"),
    [
        ("jperez@alicorp.com.pe", True, ""),
        ("JPerez@ALICORP.com.pe", True, ""),
        ("jperez@gmail.com", False, "dominio_no_permitido"),
        ("jperez@alicorp.com.pe.evil.com", False, "dominio_no_permitido"),
        ("EXT_jperez@alicorp.com.pe", False, "prefijo_excluido"),
        ("ext_jperez@alicorp.com.pe", False, "prefijo_excluido"),
        ("sin-arroba", False, "formato_invalido"),
        ("@alicorp.com.pe", False, "formato_invalido"),
        ("j perez@alicorp.com.pe", False, "formato_invalido"),
    ],
)
def test_evaluate_email(email, allowed, reason):
    result = evaluate_email(email=email, policy=POLICY)
    assert result.allowed is allowed
    assert result.reason == reason
    assert result.email == normalize_email(email)


def test_load_policy_from_repo_config():
    from conftest import CONFIG_DIR

    policy = load_email_policy(path=CONFIG_DIR / "politica_correos.yaml")
    assert policy.allowed_domains == ("alicorp.com.pe",)
    assert policy.rejection_message


def test_load_policy_requires_domains(tmp_path):
    path = tmp_path / "politica.yaml"
    path.write_text(
        "politica:\n  dominios_permitidos: []\n  mensaje_rechazo: x\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="dominios_permitidos"):
        load_email_policy(path=path)
