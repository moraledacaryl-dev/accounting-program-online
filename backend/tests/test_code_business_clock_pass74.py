from datetime import datetime, timezone

from app.services.code_service import _build_stem


RULE = {
    'prefix': 'DOC',
    'separator': '-',
    'include_year': True,
    'include_month': True,
}


def test_code_stem_uses_manila_month_at_utc_month_boundary():
    # 2026-08-31 16:30 UTC is already 2026-09-01 00:30 in Manila.
    stem, separator = _build_stem(
        RULE,
        now=datetime(2026, 8, 31, 16, 30, tzinfo=timezone.utc),
    )

    assert separator == '-'
    assert stem == 'DOC-2026-09'


def test_code_stem_uses_manila_year_at_utc_year_boundary():
    # 2026-12-31 16:30 UTC is already 2027-01-01 00:30 in Manila.
    stem, _ = _build_stem(
        RULE,
        now=datetime(2026, 12, 31, 16, 30, tzinfo=timezone.utc),
    )

    assert stem == 'DOC-2027-01'


def test_naive_injected_code_clock_is_interpreted_as_utc_then_converted_to_manila():
    stem, _ = _build_stem(
        RULE,
        now=datetime(2026, 8, 31, 16, 30),
    )

    assert stem == 'DOC-2026-09'
