from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.services import beds24_service


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


def test_historical_booking_request_fails_fast_with_retry_metadata(monkeypatch):
    calls = {'count': 0}

    def fake_urlopen(_request, timeout):
        assert timeout == 30
        calls['count'] += 1
        raise _rate_limit_error(54)

    monkeypatch.setattr(beds24_service, 'urlopen', fake_urlopen)

    with pytest.raises(beds24_service.Beds24ApiError) as exc_info:
        beds24_service._api_get(
            'https://beds24.com/api/v2',
            '/bookings',
            headers={'token': 'test-token'},
            params={
                'arrivalFrom': '2025-01-01',
                'arrivalTo': '2025-01-31',
                'limit': 99,
            },
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 54
    assert exc_info.value.headers['x-five-min-limit-resets-in'] == '54'
    assert calls['count'] == 1


def test_non_historical_request_fails_fast_on_429(monkeypatch):
    calls = {'count': 0}

    def fake_urlopen(_request, timeout):
        assert timeout == 30
        calls['count'] += 1
        raise _rate_limit_error(54)

    monkeypatch.setattr(beds24_service, 'urlopen', fake_urlopen)

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
