import gzip

from conftest import FakeObjectStore

from alejandria.content import ContentStore


def test_missing_html_returns_none():
    store = ContentStore(object_store=FakeObjectStore(), bucket_prefix="qa")
    assert store.get(domain="supply", app_id="stock") is None


def test_content_is_cached_by_generation():
    objects = FakeObjectStore()
    objects.put("qa/supply/stock/index.html", b"<html>v1</html>")
    store = ContentStore(object_store=objects, bucket_prefix="qa")

    first = store.get(domain="supply", app_id="stock")
    assert gzip.decompress(first.gzipped) == b"<html>v1</html>"
    store.get(domain="supply", app_id="stock")
    assert objects.reads == 1

    objects.put("qa/supply/stock/index.html", b"<html>v2</html>")
    second = store.get(domain="supply", app_id="stock")
    assert gzip.decompress(second.gzipped) == b"<html>v2</html>"
    assert second.generation == first.generation + 1
    assert objects.reads == 2


def test_html_is_delivered_byte_for_byte():
    original = '<html><script>const d = {"a": "ñ</b>"};</script></html>'.encode()
    objects = FakeObjectStore()
    objects.put("qa/supply/stock/index.html", original)
    content = ContentStore(object_store=objects, bucket_prefix="qa").get(
        domain="supply", app_id="stock"
    )
    assert gzip.decompress(content.gzipped) == original
