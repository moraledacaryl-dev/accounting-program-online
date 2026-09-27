from pathlib import Path


def test_invalid_webhook_diagnostic_never_persists_body_or_guest_pii():
    source = Path("app/api/integrations_beds24.py").read_text()
    assert "event_type='webhook_invalid_payload'" in source
    assert "'content_type': content_type or '<missing>'" in source
    assert "'content_length': len(raw_body)" in source
    assert "'first_byte': first_byte or '<empty>'" in source
    diagnostic = source[source.index("event_type='webhook_invalid_payload'"):source.index("raise HTTPException(status_code=400, detail='Invalid Beds24 webhook payload.')", source.index("event_type='webhook_invalid_payload'"))]
    assert "raw_body.decode" not in diagnostic
    assert "guest" not in diagnostic.lower()
    assert "email" not in diagnostic.lower()
    assert "phone" not in diagnostic.lower()
