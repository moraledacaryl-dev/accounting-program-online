from pathlib import Path


def test_webhook_auth_diagnostic_records_presence_not_values():
    source = (Path(__file__).resolve().parents[1] / "app/api/integrations_beds24.py").read_text()
    start = source.index("event_type='webhook_auth_rejected'")
    end = source.index("raise HTTPException(status_code=400, detail=message)", start)
    diagnostic = source[start:end]
    assert "x_beds24_secret_present" in diagnostic
    assert "x_webhook_secret_present" in diagnostic
    assert "x_api_key_present" in diagnostic
    assert "lower_headers.get('x-beds24-secret')" in diagnostic
    assert "lower_headers.get('x-webhook-secret')" in diagnostic
    assert "lower_headers.get('x-api-key')" in diagnostic
    assert "payload=lower_headers" not in diagnostic
    assert "header values not retained" in diagnostic
