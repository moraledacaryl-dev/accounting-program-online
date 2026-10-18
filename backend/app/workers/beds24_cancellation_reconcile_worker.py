"""One-shot Beds24 cancellation recovery; invoked by the systemd timer."""
from __future__ import annotations

import logging
import sys

from app.db.database import SessionLocal
from app.services.beds24_cancellation_reconcile_service import reconcile_beds24_cancellations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    db = SessionLocal()
    try:
        result = reconcile_beds24_cancellations(db)
        logger.info('Beds24 cancellation reconciliation: %s', result)
        return 0
    except Exception:
        logger.exception('Beds24 cancellation reconciliation failed; next timer run will retry')
        return 1
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
