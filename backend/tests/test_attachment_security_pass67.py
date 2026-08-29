from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.db.database import Base
from app.models.entities import User
from app.services.attachment_security_service import (
    authorize_attachment_entity,
    can_access_attachment_entity,
    inspect_attachment_content,
    scan_quarantined_file,
)


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return Session()


def add_user(db, username: str, role: str):
    row = User(username=username, full_name=username, hashed_password='x', role=role, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_ooxml(prefix: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr(f'{prefix}/document.xml' if prefix == 'word' else f'{prefix}/workbook.xml', '<x/>')
    return buffer.getvalue()


def test_file_inspection_accepts_known_safe_types_and_server_detects_mime():
    assert inspect_attachment_content('receipt.pdf', b'%PDF-1.7\n%%EOF', 'application/pdf').content_type == 'application/pdf'
    assert inspect_attachment_content('photo.jpg', b'\xff\xd8\xff\xe0data', 'image/jpeg').content_type == 'image/jpeg'
    assert inspect_attachment_content('image.png', b'\x89PNG\r\n\x1a\nrest', 'image/png').content_type == 'image/png'
    assert inspect_attachment_content('rows.csv', b'a,b\n1,2\n', 'text/csv').content_type == 'text/csv'
    assert inspect_attachment_content('book.xlsx', make_ooxml('xl'), None).extension == '.xlsx'
    assert inspect_attachment_content('letter.docx', make_ooxml('word'), None).extension == '.docx'


def test_file_inspection_rejects_extension_content_mismatch_and_executable_payloads():
    with pytest.raises(ValueError, match='Unsupported or mismatched'):
        inspect_attachment_content('fake.pdf', b'MZ executable payload', 'application/pdf')
    with pytest.raises(ValueError, match='Declared MIME type'):
        inspect_attachment_content('real.pdf', b'%PDF-1.7\n%%EOF', 'text/html')
    with pytest.raises(ValueError, match='Unsupported or mismatched'):
        inspect_attachment_content('payload.svg', b'<svg><script>alert(1)</script></svg>', 'image/svg+xml')
    with pytest.raises(ValueError, match='Unsupported or mismatched'):
        inspect_attachment_content('archive.zip', make_ooxml('xl'), 'application/zip')


def test_file_inspection_rejects_unsafe_ooxml_archive_path():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('../evil', 'bad')
        archive.writestr('xl/workbook.xml', '<x/>')
    with pytest.raises(ValueError, match='unsafe archive path'):
        inspect_attachment_content('book.xlsx', buffer.getvalue(), None)


def test_front_desk_can_read_and_write_booking_attachments_but_not_payroll():
    db = make_session()
    user = add_user(db, 'frontdesk-pass67', 'front_desk')
    placeholder = object()
    assert can_access_attachment_entity(db, user, 'booking', placeholder, write=False)
    assert can_access_attachment_entity(db, user, 'booking', placeholder, write=True)
    assert not can_access_attachment_entity(db, user, 'payroll_run', placeholder, write=False)
    with pytest.raises(HTTPException) as exc:
        authorize_attachment_entity(db, user, 'payroll_run', placeholder, write=False)
    assert exc.value.status_code == 403


def test_accounting_admin_cannot_mutate_external_owned_sale_order_attachment():
    db = make_session()
    user = add_user(db, 'accounting-pass67', 'accounting_admin')
    with pytest.raises(HTTPException) as exc:
        authorize_attachment_entity(db, user, 'sale_order', object(), write=True)
    assert exc.value.status_code == 409


def test_production_uploads_fail_closed_when_malware_scanner_is_missing(tmp_path: Path, monkeypatch):
    sample = tmp_path / 'sample.pdf'
    sample.write_bytes(b'%PDF-1.7\n%%EOF')
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr('app.services.attachment_security_service.shutil.which', lambda _name: None)
    with pytest.raises(HTTPException) as exc:
        scan_quarantined_file(sample)
    assert exc.value.status_code == 503
    assert 'scanner is unavailable' in exc.value.detail


def test_nonproduction_allows_static_validation_without_os_scanner(tmp_path: Path, monkeypatch):
    sample = tmp_path / 'sample.pdf'
    sample.write_bytes(b'%PDF-1.7\n%%EOF')
    monkeypatch.setattr(settings, 'environment', 'test')
    monkeypatch.setattr('app.services.attachment_security_service.shutil.which', lambda _name: None)
    scan_quarantined_file(sample)


def test_attachment_api_does_not_expose_storage_metadata():
    source = Path(__file__).resolve().parents[1] / 'app/api/attachments.py'
    text = source.read_text(encoding='utf-8')
    serializer = text.split('def _serialize_attachment', 1)[1].split('def _validate_entity', 1)[0]
    assert "'file_path':" not in serializer
    assert "'stored_name':" not in serializer
    assert 'authorize_attachment_entity' in text
    assert "'X-Content-Type-Options': 'nosniff'" in text
    assert "'Cache-Control': 'private, no-store'" in text
