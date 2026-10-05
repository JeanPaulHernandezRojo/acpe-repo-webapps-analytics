import pytest
from conftest import FakeObjectStore, ManualClock, catalog_entry, put_entry

from alejandria.catalog import CatalogStore, parse_entry


def test_parse_entry_resolves_missing_capabilities_as_true():
    raw = catalog_entry("a", "supply", ["x@alicorp.com.pe"], capacidades={"descargas": False})
    entry = parse_entry(raw=raw)
    assert entry.capabilities == {
        "descargas": False,
        "ventanas": True,
        "dialogos": True,
        "formularios": True,
    }
    assert entry.access == frozenset({"x@alicorp.com.pe"})


def test_parse_entry_rejects_unknown_capability():
    raw = catalog_entry("a", "supply", [], capacidades={"mismo_origen": True})
    with pytest.raises(ValueError, match="Capacidades desconocidas"):
        parse_entry(raw=raw)


def test_parse_entry_rejects_invalid_watermark():
    with pytest.raises(ValueError, match="marca_agua"):
        parse_entry(raw=catalog_entry("a", "supply", [], marca_agua="gigante"))


def test_catalog_skips_invalid_entries_and_sorts_by_title():
    store = FakeObjectStore()
    put_entry(store, "qa", catalog_entry("b", "supply", []))
    put_entry(store, "qa", catalog_entry("a", "ventas", []))
    store.put("qa/_catalogo/roto/malo.json", b"{no es json")
    store.put("qa/_catalogo/otro/archivo.txt", b"ignorado")
    catalog = CatalogStore(
        object_store=store, bucket_prefix="qa", ttl_seconds=60, clock=ManualClock()
    )
    assert [entry.app_id for entry in catalog.entries()] == ["a", "b"]


def test_catalog_uses_ttl():
    store = FakeObjectStore()
    clock = ManualClock()
    put_entry(store, "qa", catalog_entry("a", "supply", []))
    catalog = CatalogStore(object_store=store, bucket_prefix="qa", ttl_seconds=60, clock=clock)
    assert len(catalog.entries()) == 1
    put_entry(store, "qa", catalog_entry("b", "supply", []))
    assert len(catalog.entries()) == 1
    clock.now += 61
    assert len(catalog.entries()) == 2


def test_catalog_only_reads_its_environment():
    store = FakeObjectStore()
    put_entry(store, "prd", catalog_entry("a", "supply", []))
    catalog = CatalogStore(
        object_store=store, bucket_prefix="qa", ttl_seconds=0, clock=ManualClock()
    )
    assert catalog.entries() == []
