from app.services.beds24_sync_service import _sanitize_webhook_diagnostic


def test_sanitize_webhook_diagnostic_redacts_sensitive_values_and_keeps_shape():
    payload = {
        "event": "booking.modified",
        "bookingRef": "12345",
        "guestName": "Private Guest",
        "email": "private@example.com",
        "token": "secret-token",
        "nested": {"status": "confirmed", "phone": "123"},
    }

    diagnostic = _sanitize_webhook_diagnostic(payload)

    assert diagnostic["event"] == "booking.modified"
    assert diagnostic["bookingRef"] == "<str>"
    assert diagnostic["guestName"] == "<redacted>"
    assert diagnostic["email"] == "<redacted>"
    assert diagnostic["token"] == "<redacted>"
    assert diagnostic["nested"]["status"] == "confirmed"
    assert diagnostic["nested"]["phone"] == "<redacted>"


def test_sanitize_webhook_diagnostic_keeps_booking_identifier_values():
    diagnostic = _sanitize_webhook_diagnostic({"data": {"bookingId": "98765"}})
    assert diagnostic == {"data": {"bookingId": "98765"}}
