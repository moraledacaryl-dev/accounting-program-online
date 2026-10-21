"""Production review smoke never discloses transactions or writes financial data."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "scripts/dr/journal-review-production-smoke.py"
spec = spec_from_file_location("journal_review_production_smoke", PATH)
smoke = module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_schema_and_review_history_certification_is_distinct_from_financial_resolution():
    result = {
        "schema_version": "0017_journal_linkage_review",
        "missing_journal_links": 166,
        "reviewed_transaction_count": 2,
        "reviewed_unlinked_transaction_count": 1,
        "review_history_events": 4,
        "orphan_review_references": 0,
        "recorded_review_journal_links": 0,
    }
    assert smoke.check_snapshot(result) is True
    # A successful review does NOT reduce the missing-journal population.
    assert result["missing_journal_links"] == 166
    assert result["reviewed_unlinked_transaction_count"] == 1


@pytest.mark.parametrize("override", [
    {"schema_version": "0016_money_movement_timestamps"},
    {"orphan_review_references": 1},
    {"reviewed_transaction_count": 4, "review_history_events": 3},
    {"reviewed_unlinked_transaction_count": 167},
    {"reviewed_unlinked_transaction_count": 1, "reviewed_transaction_count": 0},
])
def test_integrity_smoke_rejects_unexpected_schema_or_history(override):
    baseline = {
        "schema_version": "0017_journal_linkage_review",
        "missing_journal_links": 166,
        "reviewed_transaction_count": 0,
        "reviewed_unlinked_transaction_count": 0,
        "review_history_events": 0,
        "orphan_review_references": 0,
        "recorded_review_journal_links": 0,
    }
    baseline.update(override)
    with pytest.raises(RuntimeError):
        smoke.check_snapshot(baseline)


def test_production_smoke_is_read_only_and_does_not_leak_money_or_references():
    source = PATH.read_text()
    for sql in smoke.QUERIES.values():
        assert sql.strip().upper().startswith("SELECT")
        for command in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
            assert command not in sql.upper()
    assert "SET TRANSACTION READ ONLY" in source
    assert "db.rollback()" in source
    assert "db.commit()" not in source
    assert "status not in (401, 403)" not in source
    assert "if status not in (401, 403)" in source
    assert "journal-linkage-review/export.csv?queue=unreviewed" in source
    assert "reviewed_unlinked_transaction_count" in source
    assert "reviewed_unlinked_transaction_count" in smoke.QUERIES
    workflow = (ROOT / ".github/workflows/accounting-journal-review-production-smoke.yml").read_text()
    assert "branches: [main]" in workflow
    assert "workflow_dispatch" in workflow
    assert 'git -C "$SOURCE" show "$AUDIT_SHA:scripts/dr/journal-review-production-smoke.py"' in workflow
    assert "upload-artifact" not in workflow


def test_unauthenticated_production_routes_are_checked_without_fetching_response_bodies(monkeypatch):
    from urllib.error import HTTPError
    from urllib.request import Request

    seen = []
    def deny(req, timeout):
        assert isinstance(req, Request)
        seen.append(req.full_url)
        raise HTTPError(req.full_url, 401, 'unauthorized', {}, None)

    monkeypatch.setattr(smoke, "urlopen", deny)
    assert smoke.unauthenticated_route_status(
        "http://127.0.0.1:8000/api/reports/journal-linkage-review/export.csv?queue=unreviewed"
    ) == 401
    assert len(seen) == 1

