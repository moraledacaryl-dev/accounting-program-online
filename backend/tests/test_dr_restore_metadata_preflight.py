"""Offline restore-sidecar validation: no production database or real backup accessed."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/dr/verify-restore-metadata.py"
RESTORE = ROOT / "scripts/dr/restore-rehearsal.sh"
spec = spec_from_file_location("restore_metadata_preflight", SOURCE)
helper = module_from_spec(spec)
spec.loader.exec_module(helper)


def fixture_backup(tmp_path):
    stamp = "20261022T120000Z"
    dump = tmp_path / f"accounting-{stamp}.dump"
    dump.write_bytes(b"synthetic-dump")
    meta = tmp_path / f"accounting-{stamp}.meta"
    body = {
        "format": "postgresql-custom", "created_utc": stamp,
        "database": "synthetic", "sha256": "a" * 64,
        "size_bytes": str(dump.stat().st_size), "release_sha": "b" * 40,
        "alembic_revision": "0017_journal_linkage_review",
        "uploads_archive": f"accounting-{stamp}.uploads.tar.gz",
        "uploads_sha256": "c" * 64,
    }
    meta.write_text("".join(f"{k}={v}\n" for k, v in body.items()))
    return dump, meta, body


def test_valid_manifest_preflight_is_read_only(tmp_path, capsys, monkeypatch):
    dump, meta, _ = fixture_backup(tmp_path)
    before = (dump.read_bytes(), meta.read_bytes())
    assert helper.validate_metadata(dump, meta)["database"] == "synthetic"
    monkeypatch.setattr(helper.sys, "argv", ["validate", str(dump), str(meta)])
    assert helper.main() == 0
    assert (dump.read_bytes(), meta.read_bytes()) == before
    assert "synthetic" not in capsys.readouterr().out


@pytest.mark.parametrize("change", [
    ("size_bytes", "5000"), ("format", "tar"), ("uploads_archive", "../outside"),
    ("uploads_archive", "other.tar.gz"), ("sha256", "invalid"),
    ("alembic_revision", "bad migration"), ("created_utc", "20260101T000000Z"),
])
def test_bad_metadata_rejected(tmp_path, change):
    dump, meta, fields = fixture_backup(tmp_path)
    fields[change[0]] = change[1]
    meta.write_text("".join(f"{k}={v}\n" for k, v in fields.items()))
    with pytest.raises(ValueError):
        helper.validate_metadata(dump, meta)


def test_duplicate_field_and_symlink_sidecar_rejected(tmp_path):
    dump, meta, _ = fixture_backup(tmp_path)
    meta.write_text(meta.read_text() + "sha256=" + "e" * 64 + "\n")
    with pytest.raises(ValueError):
        helper.validate_metadata(dump, meta)
    meta.unlink()
    actual = tmp_path / "real.meta"
    actual.write_text("invalid")
    meta.symlink_to(actual)
    with pytest.raises(ValueError):
        helper.validate_metadata(dump, meta)


def test_restore_invokes_strict_preflight_before_pg_restore_and_createdb():
    shell = RESTORE.read_text()
    check = shell.index('verify-restore-metadata.py')
    assert check < shell.index('pg_restore --list')
    assert check < shell.index('createdb "$REHEARSAL_DB"')
    assert "RESTORE" in shell
