"""Older authorized files remain retrievable behind restricted newer files."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.attachments import list_attachments
from app.db.database import Base
from app.models.entities import Attachment, Booking, PayrollRun, User


def test_global_attachment_pages_skip_restricted_files_and_reach_history():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = User(username='isolated-frontdesk', full_name='Isolated front desk',
                        hashed_password='unused', role='front_desk', is_active=True)
            db.add_all([
                user,
                Booking(id=1, guest_name='Synthetic booking', status='confirmed'),
                PayrollRun(id=1, name='Synthetic payroll'),
            ])
            db.flush()
            db.add(Attachment(
                id=1, entity_type='booking', entity_id=1, file_name='older.pdf',
                stored_name='isolated-older.pdf', file_path='/uploads/isolated-older.pdf',
            ))
            for attachment_id in range(2, 12):
                db.add(Attachment(
                    id=attachment_id, entity_type='payroll_run', entity_id=1,
                    file_name='restricted.pdf', stored_name=f'isolated-{attachment_id}.pdf',
                    file_path=f'/uploads/isolated-{attachment_id}.pdf',
                ))
            db.add(Attachment(
                id=12, entity_type='booking', entity_id=1, file_name='newer.pdf',
                stored_name='isolated-newer.pdf', file_path='/uploads/isolated-newer.pdf',
            ))
            db.commit()

            newest = list_attachments(db=db, user=user, limit=1, before_id=None)
            older = list_attachments(db=db, user=user, limit=1, before_id=newest[-1]['id'])
            assert [(row['id'], row['file_name']) for row in newest] == [(12, 'newer.pdf')]
            assert [(row['id'], row['file_name']) for row in older] == [(1, 'older.pdf')]
            assert list_attachments(db=db, user=user, limit=1, before_id=1) == []
            assert all(row['entity_type'] == 'booking' for row in newest + older)
    finally:
        engine.dispose()
