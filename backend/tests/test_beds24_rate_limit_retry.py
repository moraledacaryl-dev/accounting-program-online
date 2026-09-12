from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.services import beds24_service


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


def _rate_limit_error(reset_seconds: int = 54) -> HTTPError:
    return HTTPError(
        url='https://beds24.com/api/v2/bookings',
        code=429,
        msg='Too Many Requests',
        hdrs={
            'x-five-min-limit-remaining': '0',
            'x-five-min-limit-resets-in': str(reset_seconds),
            'x-request-cost': '25',
        },
        fp=BytesIO(b'{"message":"rate limited"}'),
    )


def test_historical_booking_request_waits_and_retries_after_429(monkeypatch):
    calls = {'count': 0}
    sleeps = []

    def fake_urlopen(_request, timeout):
        assert timeout == 30
        calls['count'] += 1
        if calls['count'] == 1:
            raise _rate_limit_error(54)
        return _FakeResponse(b'{"bookings":[]}')

    monkeypatch.setattr(beds24_service, 'urlopen', fake_urlopen)
    monkeypatch.setattr(beds24_service.time, 'sleep', lambda seconds: sleeps.append(seconds))

    payload = beds24_service._api_get(
        'https://beds24.com/api/v2',
        '/bookings',
        headers={'token': 'test-token'},
        params={
            'arrivalFrom': '2025-01-01',
            'arrivalTo': '2025-01-31',
            'limit': 99,
        },
    )

    assert payload == {'bookings': []}
    assert calls['count'] == 2
    assert sleeps == [56]


def test_non_historical_request_still_fails_fast_on_429(monkeypatch):
    calls = {'count': 0}
    sleeps = []

    def fake_urlopen(_request, timeout):
        assert timeout == 30
        calls['count'] += 1
        raise _rate_limit_error(54)

    monkeypatch.setattr(beds24_service, 'urlopen', fake_urlopen)
    monkeypatch.setattr(beds24_service.time, 'sleep', lambda seconds: sleeps.append(seconds))

    with pytest.raises(beds24_service.Beds24ApiError) as exc_info:
        beds24_service._api_get(
            'https://beds24.com/api/v2',
            '/bookings',
            headers={'token': 'test-token'},
            params={'limit': 1},
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 54
    assert calls['count'] == 1
    assert sleeps == []


def test_historical_booking_request_stops_after_bounded_retry_budget(monkeypatch):
    calls = {'count': 0}
    sleeps = []

    def fake_urlopen(_request, timeout):
        assert timeout == 30
        calls['count'] += 1
        raise _rate_limit_error(1)

    monkeypatch.setattr(beds24_service, 'urlopen', fake_urlopen)
    monkeypatch.setattr(beds24_service.time, 'sleep', lambda seconds: sleeps.append(seconds))

    with pytest.raises(beds24_service.Beds24ApiError) as exc_info:
        beds24_service._api_get(
            'https://beds24.com/api/v2',
            '/bookings',
            headers={'token': 'test-token'},
            params={
                'arrivalFrom': '2025-01-01',
                'arrivalTo': '2025-01-31',
            },
        )

    assert exc_info.value.status_code == 429
    assert calls['count'] == 4
    assert sleeps == [3, 3, 3]
