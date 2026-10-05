from conftest import catalog_entry

from alejandria.authorization import apps_for_email, find_app
from alejandria.catalog import parse_entry

ENTRIES = [
    parse_entry(raw=catalog_entry("stock", "supply", ["ana@alicorp.com.pe"])),
    parse_entry(
        raw=catalog_entry("churn", "clientes", ["ana@alicorp.com.pe", "beto@alicorp.com.pe"])
    ),
]


def test_apps_for_email():
    assert [e.app_id for e in apps_for_email(entries=ENTRIES, email="beto@alicorp.com.pe")] == [
        "churn"
    ]
    assert len(apps_for_email(entries=ENTRIES, email="ana@alicorp.com.pe")) == 2
    assert apps_for_email(entries=ENTRIES, email="nadie@alicorp.com.pe") == []


def test_find_app_authorized_and_denied():
    ok = find_app(entries=ENTRIES, email="ana@alicorp.com.pe", domain="supply", app_id="stock")
    assert ok.authorized and ok.entry is not None
    denied = find_app(entries=ENTRIES, email="beto@alicorp.com.pe", domain="supply", app_id="stock")
    assert denied.entry is not None and not denied.authorized


def test_find_app_requires_matching_domain():
    lookup = find_app(entries=ENTRIES, email="ana@alicorp.com.pe", domain="ventas", app_id="stock")
    assert lookup.entry is None and not lookup.authorized
