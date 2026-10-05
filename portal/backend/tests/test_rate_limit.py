from conftest import ManualClock

from alejandria.rate_limit import RateLimiter, client_ip


def test_limit_within_window_and_recovery():
    clock = ManualClock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
    assert limiter.allow(key="a")
    assert limiter.allow(key="a")
    assert not limiter.allow(key="a")
    assert limiter.allow(key="b")
    clock.now += 60
    assert limiter.allow(key="a")


def test_client_ip_takes_position_from_end():
    headers = {"x-forwarded-for": "1.1.1.1, 2.2.2.2, 3.3.3.3"}
    assert client_ip(headers=headers, index_from_end=1, fallback="0.0.0.0") == "3.3.3.3"
    assert client_ip(headers=headers, index_from_end=2, fallback="0.0.0.0") == "2.2.2.2"


def test_client_ip_fallback():
    assert client_ip(headers={}, index_from_end=1, fallback="9.9.9.9") == "9.9.9.9"
    headers = {"x-forwarded-for": "1.1.1.1"}
    assert client_ip(headers=headers, index_from_end=3, fallback="9.9.9.9") == "9.9.9.9"
