from __future__ import annotations

import logging
import time

from app.db.database import SessionLocal
from app.services.operations_outbox_service import (
    OperationsDeliveryError,
    claim_next_operations_event,
    deliver_operations_envelope,
    mark_operations_event_delivered,
    mark_operations_event_failed,
)

logger = logging.getLogger(__name__)
POLL_SECONDS = 5


def run_once() -> bool:
    with SessionLocal() as db:
        row = claim_next_operations_event(db)
        if not row:
            return False
        row_id = int(row.id)
        event_id = row.event_id
        envelope_json = row.envelope_json

    try:
        http_status = deliver_operations_envelope(envelope_json)
    except OperationsDeliveryError as exc:
        with SessionLocal() as db:
            failed = mark_operations_event_failed(
                db,
                row_id,
                error_message=str(exc),
                http_status=exc.http_status,
            )
            logger.warning(
                'Operations outbox delivery failed event_id=%s attempt=%s status=%s',
                event_id,
                failed.attempt_count,
                failed.status,
            )
        return True
    except Exception as exc:
        with SessionLocal() as db:
            failed = mark_operations_event_failed(
                db,
                row_id,
                error_message=f'Unexpected delivery error: {exc}',
            )
            logger.exception(
                'Unexpected Operations outbox delivery error event_id=%s attempt=%s status=%s',
                event_id,
                failed.attempt_count,
                failed.status,
            )
        return True

    with SessionLocal() as db:
        mark_operations_event_delivered(db, row_id, http_status=http_status)
    logger.info('Operations outbox delivered event_id=%s http_status=%s', event_id, http_status)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info('Operations outbox worker started')
    while True:
        worked = run_once()
        if not worked:
            time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
