from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import reports
from app.db.database import Base
from app.services import (
    cashflow_service,
    event_service,
    guest_service,
    hospitality_service,
    procurement_service,
    room_setup_service,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_remaining_service_today_helpers_delegate_to_business_clock(monkeypatch):
    modules = [
        cashflow_service,
        event_service,
        guest_service,
        hospitality_service,
        procurement_service,
        room_setup_service,
    ]

    for module in modules:
        monkeypatch.setattr(module, 'business_today', lambda: '2026-08-28')
        assert module._today() == '2026-08-28'


def test_reports_default_aging_date_uses_business_clock(monkeypatch):
    monkeypatch.setattr(reports, 'business_today', lambda: '2026-08-28')
    db = make_session()

    assert reports._today() == '2026-08-28'
    result = reports._build_aging_report(db)
    assert result['as_of_date'] == '2026-08-28'


def test_backend_has_no_date_only_utc_business_fallbacks():
    forbidden = "datetime.utcnow().strftime('%Y-%m-%d')"
    offenders = []

    for path in (REPOSITORY_ROOT / 'backend' / 'app').rglob('*.py'):
        if forbidden in path.read_text(encoding='utf-8'):
            offenders.append(str(path.relative_to(REPOSITORY_ROOT)))

    assert offenders == []


def test_restaurant_and_asset_business_defaults_use_shared_clock():
    targets = [
        REPOSITORY_ROOT / 'backend' / 'app' / 'services' / 'restaurant_service.py',
        REPOSITORY_ROOT / 'backend' / 'app' / 'api' / 'asset_registry.py',
    ]

    for path in targets:
        text = path.read_text(encoding='utf-8')
        assert 'from app.core.business_clock import business_today' in text
        assert 'business_today()' in text


def test_frontend_business_date_pages_do_not_use_date_only_utc_conversion():
    paths = [
        'frontend/app/staff-meals/page.js',
        'frontend/app/bookings/page.js',
        'frontend/app/bookings/calendar/page.js',
        'frontend/app/integrations/beds24/page.js',
        'frontend/app/reports/page.js',
        'frontend/app/assets/page.js',
        'frontend/app/room-folios/[id]/page.js',
        'frontend/app/channel-payouts/page.js',
        'frontend/app/restaurant-ops/page.js',
    ]

    offenders = []
    for relative in paths:
        text = (REPOSITORY_ROOT / relative).read_text(encoding='utf-8')
        if 'toISOString().slice(0, 10)' in text:
            offenders.append(relative)
        assert 'businessDateISO' in text

    assert offenders == []
