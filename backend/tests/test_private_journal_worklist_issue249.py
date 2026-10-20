"""Private transaction-level worklists must not reach public GitHub logs."""
import csv
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os

from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dr/private-journal-exception-worklist.py"
spec = spec_from_file_location("private_journal_worklist", SCRIPT)
worklist = module_from_spec(spec)
spec.loader.exec_module(worklist)


def test_export_private_file_permissions_and_formula_injection(tmp_path):
    rows = [
        {"id": 1001, "amount": Decimal("-2.5000"), "reference_no": "=IMPORTXML(A1)",
         "category": "@SUM(1)", "external_source": "legacy", "external_id": "+LINK",
         "transaction_date": "2025-01-01"},
        {"id": 1002, "amount": Decimal("25.2000"), "reference_no": "SAFE-123",
         "module": "import", "external_id": "remote-987"},
    ]
    outfile = worklist.write_worklist(rows, tmp_path / "private", timestamp="20261020T164100Z")
    assert outfile.exists()
    assert (outfile.parent.stat().st_mode & 0o777) == 0o700
    assert (outfile.stat().st_mode & 0o777) == 0o600
    with outfile.open(newline="", encoding="utf-8") as handle:
        data = list(csv.DictReader(handle))
    assert len(data) == 2
    assert data[0]["id"] == "1001"
    assert data[0]["amount"] == "-2.5000"
    assert data[0]["reference_no"] == "'=IMPORTXML(A1)"
    assert data[0]["category"] == "'@SUM(1)"
    assert data[0]["external_id"] == "'+LINK"
    assert data[1]["external_id"] == "remote-987"
    assert len(data[1]) == len(worklist.FIELDS)


def test_rejects_symlinked_worklist_directory(tmp_path):
    target = tmp_path / "actual"
    target.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(target, target_is_directory=True)
    try:
        worklist.write_worklist([], link)
        assert False, "Must not follow symlinked private directory"
    except ValueError as exc:
        assert "symlink" in str(exc)
    assert not list(target.iterdir())


def test_private_worklist_uses_read_only_sql_and_manual_opt_in_workflow():
    sql = worklist.WORKLIST_QUERY.strip().upper()
    assert sql.startswith("SELECT ")
    assert "T.STATUS = 'POSTED' AND T.JOURNAL_ENTRY_ID IS NULL" in sql
    for word in ("DELETE ", "UPDATE ", "INSERT ", "DROP ", "ALTER "):
        assert word not in sql
    script = SCRIPT.read_text()
    assert "SET TRANSACTION READ ONLY" in script
    assert "db.rollback()" in script
    assert "db.commit()" not in script
    assert "root_only_permissions=0700_directory_0600_file" in script

    flow = (ROOT / ".github/workflows/accounting-private-journal-exception-worklist.yml").read_text()
    assert "workflow_dispatch:" in flow
    assert "push:" not in flow
    assert "EXPORT-PRIVATE" in flow
    assert "git -C \"$SOURCE\" show \"$AUDIT_SHA:scripts/dr/private-journal-exception-worklist.py\"" in flow
    assert "actions/upload-artifact" not in flow
