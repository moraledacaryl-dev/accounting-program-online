from unittest.mock import MagicMock, patch

from app.services.beds24_sync_service import sync_from_webhook


def test_room_sync_notification_is_acknowledged_without_booking_sync():
    db = MagicMock()
    payload = {"roomId": "123", "propId": "456", "ownerId": "789", "action": "SYNC_ROOM"}
    settings = {"webhook_enabled": True, "manual_sync_only": False, "webhook_require_secret": False}

    with patch("app.services.beds24_sync_service.load_beds24_settings", return_value=settings), \
         patch("app.services.beds24_sync_service._upsert_sync_log", return_value={"id": 42}) as log, \
         patch("app.services.beds24_sync_service.sync_booking_by_id") as sync_booking:
        result = sync_from_webhook(db, payload)

    assert result["ok"] is True
    assert result["ignored"] is True
    assert result["action"] == "SYNC_ROOM"
    assert result["booking_ids"] == []
    assert result["synced"] == 0
    assert result["failed"] == 0
    sync_booking.assert_not_called()
    log.assert_called_once()
    assert log.call_args.kwargs["event_type"] == "webhook_room_sync"
    assert log.call_args.kwargs["status"] == "ignored"


def test_unknown_notification_without_booking_id_still_fails_safe():
    db = MagicMock()
    settings = {"webhook_enabled": True, "manual_sync_only": False, "webhook_require_secret": False}

    with patch("app.services.beds24_sync_service.load_beds24_settings", return_value=settings), \
         patch("app.services.beds24_sync_service._upsert_sync_log", return_value={"id": 43}) as log:
        try:
            sync_from_webhook(db, {"action": "SOMETHING_UNKNOWN"})
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "no booking ID" in str(exc)

    assert log.call_args.kwargs["event_type"] == "webhook_missing_booking_id"
    assert log.call_args.kwargs["status"] == "error"
