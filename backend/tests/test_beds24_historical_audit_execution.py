"""Execution-level regression tests for the read-only historical Beds24 audit."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from app.services.beds24_service import Beds24ApiError
from scripts import audit_beds24_statuses as audit


def _session(bookings):
    db = Mock()
    result = Mock()
    result.mappings.return_value.all.return_value = bookings

    def execute(statement):
        if "SELECT id, external_booking_id" in str(statement):
            return result
        assert "SET TRANSACTION READ ONLY" in str(statement)
        return Mock()

    db.execute.side_effect = execute
    return db


def _rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def _run(db, path, responses, *, max_requests=100, start_after_id=""):
    with (
        patch.object(audit, "SessionLocal", return_value=db),
        patch.object(audit, "load_beds24_settings", return_value={
            "enabled": True,
            "access_token": "unit-test-token",
            "api_base_url": "https://beds24.example/api/v2",
        }),
        patch.object(audit, "_api_get", side_effect=responses) as api,
        patch.object(audit.time, "sleep") as sleep,
    ):
        result = audit.run(path, 0.5, max_requests, start_after_id)
        db.commit.assert_not_called()
        db.close.assert_called()
        return result, api.call_args_list, sleep.call_args_list


def test_read_only_batch_then_automatic_csv_resume():
    bookings = [
        {"id": 1, "external_booking_id": "123", "status": "confirmed"},
        {"id": 2, "external_booking_id": "124", "status": "confirmed"},
    ]
    with TemporaryDirectory() as folder:
        path = Path(folder) / "report.csv"
        db = _session(bookings)
        rc, calls, _ = _run(db, path, [[{"id": "123", "status": "confirmed"}]], max_requests=1)
        assert rc == 0
        assert len(calls) == 1
        assert calls[0].kwargs["params"]["id"] == "123"
        assert calls[0].kwargs["headers"]["token"] == "unit-test-token"
        rc, calls, _ = _run(db, path, [[{"id": "124", "status": "cancelled"}]], max_requests=1)
        assert rc == 0
        assert len(calls) == 1
        assert calls[0].kwargs["params"]["id"] == "124"
        assert [r["classification"] for r in _rows(path)] == ["MATCHED", "CANCELLATION_MISMATCH"]


def test_rate_limit_records_error_and_retries_on_next_run():
    bookings = [{"id": 1, "external_booking_id": "123", "status": "confirmed"}]
    with TemporaryDirectory() as folder:
        path = Path(folder) / "report.csv"
        db = _session(bookings)
        limit = Beds24ApiError("limited", status_code=429, retry_after_seconds=1)
        rc, calls, sleeps = _run(db, path, [limit] * 5)
        assert rc == 2
        assert len(calls) == 5
        assert len(sleeps) == 4
        assert _rows(path)[0]["classification"] == "API_ERROR"
        rc, calls, _ = _run(db, path, [[{"id": "123", "status": "cancelled"}]])
        assert rc == 0
        assert len(calls) == 1
        assert [r["classification"] for r in _rows(path)] == ["API_ERROR", "CANCELLATION_MISMATCH"]


def test_authentication_failure_stops_before_next_booking():
    db = _session([
        {"id": 1, "external_booking_id": "123", "status": "confirmed"},
        {"id": 2, "external_booking_id": "124", "status": "confirmed"},
    ])
    with TemporaryDirectory() as folder:
        path = Path(folder) / "report.csv"
        rc, calls, _ = _run(db, path, [Beds24ApiError("unauthorized", status_code=401)])
        assert rc == 2
        assert len(calls) == 1
        assert _rows(path)[0]["classification"] == "API_ERROR"


def test_invalid_cursor_refuses_to_skip_unknown_booking():
    db = _session([{"id": 1, "external_booking_id": "123", "status": "confirmed"}])
    with TemporaryDirectory() as folder:
        with (
            patch.object(audit, "SessionLocal", return_value=db),
            patch.object(audit, "load_beds24_settings", return_value={
                "enabled": True, "access_token": "unit-test-token"
            }),
            pytest.raises(ValueError, match="not present"),
        ):
            audit.run(Path(folder) / "report.csv", 0.5, 1, "999")
        db.close.assert_called()
        db.commit.assert_not_called()


def test_absent_remote_status_is_api_error_not_cancellation():
    db = _session([{"id": 1, "external_booking_id": "123", "status": "confirmed"}])
    with TemporaryDirectory() as folder:
        path = Path(folder) / "report.csv"
        rc, _, _ = _run(db, path, [[{"id": "123"}]])
        assert rc == 2
        assert _rows(path)[0]["classification"] == "API_ERROR"


def test_duplicate_local_link_does_not_send_api_request():
    db = _session([
        {"id": 1, "external_booking_id": "123", "status": "confirmed"},
        {"id": 2, "external_booking_id": "123", "status": "confirmed"},
    ])
    with TemporaryDirectory() as folder:
        path = Path(folder) / "report.csv"
        rc, calls, _ = _run(db, path, [])
        assert rc == 0
        assert not calls
        assert _rows(path)[0]["classification"] == "DUPLICATE_LINK"
