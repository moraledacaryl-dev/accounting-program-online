from __future__ import annotations

import io
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.entities import Attachment, Record, User
from app.services.auth_service import is_integration_username
from app.services.permission_service import get_user_permission_keys

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
MAX_UPLOADS_PER_USER_24H = 100
MAX_UPLOAD_BYTES_PER_USER_24H = 250 * 1024 * 1024
MAX_OOXML_MEMBERS = 2000
MAX_OOXML_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
GENERIC_DECLARED_MIME_TYPES = {'', 'application/octet-stream', 'binary/octet-stream'}


@dataclass(frozen=True)
class FileInspection:
    extension: str
    content_type: str


ENTITY_ACCESS = {
    'booking': ({'bookings.view'}, {'bookings.edit'}),
    'asset': ({'assets.view'}, {'assets.manage'}),
    'payroll_run': ({'payroll_periods.view'}, {'payroll_periods.manage'}),
    'channel_payout': ({'cashflow.view'}, {'cashflow.money_in'}),
    'money_transaction': ({'cashflow.view'}, {'cashflow.money_in', 'cashflow.money_out'}),
    'account_transfer': ({'cashflow.view'}, {'cashflow.transfers'}),
    'cash_reconciliation': ({'cashflow.view', 'cash_treasury.view'}, {'cashflow.reconcile'}),
    'receivable': ({'cashflow.view'}, {'cashflow.money_in'}),
    'payable': ({'cashflow.view'}, {'cashflow.money_out'}),
    'stock_movement': ({'inventory.view', 'receiving.view'}, {'stock_movements.create', 'receiving.post'}),
    'sale_order': ({'restaurant.view'}, set()),
}
EXTERNAL_OWNED_ATTACHMENT_ENTITIES = {
    'stock_movement': 'Inventory & Procurement',
    'sale_order': 'POS Cloud',
}


def _record_permissions(record: Record) -> tuple[set[str], set[str]]:
    module = (record.module_slug or '').strip().lower()
    if module in {'inventory', 'procurement'}:
        return {'inventory.view'}, set()
    if module == 'restaurant':
        return {'restaurant.view'}, set()
    return (
        {'cashflow.view', 'journals.view', 'reports.view', 'bir.view'},
        {'cashflow.money_in', 'cashflow.money_out', 'journals.post', 'bir.manage'},
    )


def can_access_attachment_entity(
    db: Session,
    user: User,
    entity_type: str,
    entity_obj,
    *,
    write: bool = False,
) -> bool:
    if getattr(user, 'role', None) in {'owner', 'admin'}:
        if write and entity_type in EXTERNAL_OWNED_ATTACHMENT_ENTITIES:
            return is_integration_username(getattr(user, 'username', None))
        return True

    permissions = get_user_permission_keys(db, user)
    if entity_type == 'record':
        read_permissions, write_permissions = _record_permissions(entity_obj)
        module = (getattr(entity_obj, 'module_slug', None) or '').strip().lower()
        if write and module in {'inventory', 'procurement', 'restaurant'}:
            return is_integration_username(getattr(user, 'username', None)) and bool(
                permissions.intersection(read_permissions)
            )
    else:
        pair = ENTITY_ACCESS.get(entity_type)
        if not pair:
            return False
        read_permissions, write_permissions = pair
        if write and entity_type in EXTERNAL_OWNED_ATTACHMENT_ENTITIES:
            return is_integration_username(getattr(user, 'username', None)) and bool(
                permissions.intersection(read_permissions)
            )

    required = write_permissions if write else read_permissions
    return bool(required and permissions.intersection(required))


def authorize_attachment_entity(
    db: Session,
    user: User,
    entity_type: str,
    entity_obj,
    *,
    write: bool = False,
) -> None:
    if can_access_attachment_entity(db, user, entity_type, entity_obj, write=write):
        return
    if write and entity_type in EXTERNAL_OWNED_ATTACHMENT_ENTITIES:
        owner = EXTERNAL_OWNED_ATTACHMENT_ENTITIES[entity_type]
        raise HTTPException(
            status_code=409,
            detail=f'{owner} owns this operational workflow. Accounting is read-only for attachment mutation.',
        )
    raise HTTPException(status_code=403, detail='Not authorized for attachments on this resource.')


def _inspect_ooxml(data: bytes, extension: str) -> FileInspection:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_OOXML_MEMBERS:
                raise ValueError('Office document contains too many archive members.')
            total = 0
            names: set[str] = set()
            for info in infos:
                name = info.filename.replace('\\', '/')
                path = PurePosixPath(name)
                if info.flag_bits & 0x1:
                    raise ValueError('Encrypted Office documents are not accepted.')
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Office document contains an unsafe archive path.')
                total += int(info.file_size or 0)
                if total > MAX_OOXML_UNCOMPRESSED_BYTES:
                    raise ValueError('Office document expands beyond the safe processing limit.')
                names.add(name)
            if '[Content_Types].xml' not in names:
                raise ValueError('Office document structure is invalid.')
            if extension == '.xlsx':
                if not any(name.startswith('xl/') for name in names):
                    raise ValueError('File extension is .xlsx but workbook structure is missing.')
                return FileInspection('.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            if extension == '.docx':
                if not any(name.startswith('word/') for name in names):
                    raise ValueError('File extension is .docx but document structure is missing.')
                return FileInspection('.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except zipfile.BadZipFile as exc:
        raise ValueError('Office document archive is invalid.') from exc
    raise ValueError('Unsupported Office document type.')


def inspect_attachment_content(file_name: str, data: bytes, declared_content_type: str | None = None) -> FileInspection:
    extension = Path(file_name).suffix.lower()
    if extension == '.pdf' and data.startswith(b'%PDF-'):
        inspection = FileInspection('.pdf', 'application/pdf')
    elif extension in {'.jpg', '.jpeg'} and data.startswith(b'\xff\xd8\xff'):
        inspection = FileInspection('.jpg' if extension == '.jpg' else '.jpeg', 'image/jpeg')
    elif extension == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n'):
        inspection = FileInspection('.png', 'image/png')
    elif extension in {'.xlsx', '.docx'} and data.startswith(b'PK'):
        inspection = _inspect_ooxml(data, extension)
    elif extension == '.csv':
        if b'\x00' in data:
            raise ValueError('CSV files may not contain NUL bytes.')
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('CSV files must be valid UTF-8 text.') from exc
        inspection = FileInspection('.csv', 'text/csv')
    else:
        raise ValueError('Unsupported or mismatched file type. Allowed: PDF, JPEG, PNG, CSV, XLSX, DOCX.')

    declared = (declared_content_type or '').split(';', 1)[0].strip().lower()
    if declared not in GENERIC_DECLARED_MIME_TYPES:
        compatible = {inspection.content_type}
        if inspection.content_type == 'image/jpeg':
            compatible.update({'image/jpg', 'image/pjpeg'})
        if inspection.content_type == 'text/csv':
            compatible.update({'text/plain', 'application/csv', 'application/vnd.ms-excel'})
        if declared not in compatible:
            raise ValueError('Declared MIME type does not match the uploaded file content.')
    return inspection


def enforce_upload_quota(db: Session, username: str | None, incoming_size: int) -> None:
    username = (username or '').strip()
    if not username:
        raise HTTPException(status_code=403, detail='Authenticated username is required for uploads.')
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    count, total = (
        db.query(func.count(Attachment.id), func.coalesce(func.sum(Attachment.size_bytes), 0))
        .filter(Attachment.uploaded_by == username, Attachment.created_at >= cutoff)
        .one()
    )
    if int(count or 0) >= MAX_UPLOADS_PER_USER_24H:
        raise HTTPException(status_code=429, detail='Attachment upload limit reached for the last 24 hours.')
    if int(total or 0) + int(incoming_size) > MAX_UPLOAD_BYTES_PER_USER_24H:
        raise HTTPException(status_code=429, detail='Attachment byte quota reached for the last 24 hours.')


def quarantine_path(upload_root: Path, stored_name: str) -> Path:
    root = upload_root / '.quarantine'
    root.mkdir(parents=True, exist_ok=True)
    return root / Path(stored_name).name


def write_quarantine_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def scan_quarantined_file(path: Path) -> None:
    scanner = shutil.which('clamscan')
    if not scanner:
        if settings.is_production:
            raise HTTPException(status_code=503, detail='Attachment malware scanner is unavailable.')
        return
    try:
        result = subprocess.run(
            [scanner, '--no-summary', '--infected', str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=503, detail='Attachment malware scan timed out.') from exc
    if result.returncode == 1:
        raise HTTPException(status_code=400, detail='Attachment was rejected by malware scanning.')
    if result.returncode != 0:
        raise HTTPException(status_code=503, detail='Attachment malware scanner failed.')


def promote_quarantined_file(quarantine: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(quarantine, final_path)
    os.chmod(final_path, 0o600)
