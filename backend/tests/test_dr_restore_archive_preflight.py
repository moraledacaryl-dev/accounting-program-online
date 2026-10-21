"""Safety regression for the offline evidence archive restore preflight.

Uses disposable tar fixtures; never touches a production database or backup.
"""
from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = ROOT / "scripts" / "dr" / "verify-restore-archive.py"
RESTORE_SCRIPT = ROOT / "scripts" / "dr" / "restore-rehearsal.sh"

spec = importlib.util.spec_from_file_location("dr_restore_archive_preflight", HELPER_PATH)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def archive_with(tmp_path, members):
    target = tmp_path / "evidence.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        for name, kind, contents in members:
            info = tarfile.TarInfo(name)
            if kind == "directory":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            elif kind == "regular":
                info.size = len(contents)
                archive.addfile(info, BytesIO(contents))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "outside"
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = "../outside"
                archive.addfile(info)
            elif kind == "device":
                info.type = tarfile.CHRTYPE
                archive.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
            else:
                raise AssertionError(f"Invalid test member kind: {kind}")
    return target


def test_valid_evidence_restores_without_exposing_private_filenames(tmp_path, capsys):
    archive = archive_with(tmp_path, [
        ("./", "directory", b""),
        ("./docs/", "directory", b""),
        ("./docs/receipt.pdf", "regular", b"%PDF-fake-private-test"),
    ])
    destination = tmp_path / "unpacked"
    destination.mkdir()
    assert guard.inspect_archive(archive) == (1, len(b"%PDF-fake-private-test"))
    assert guard.extract_verified(archive, destination) == (
        1, len(b"%PDF-fake-private-test")
    )
    assert (destination / "docs" / "receipt.pdf").read_bytes() == b"%PDF-fake-private-test"
    assert "receipt.pdf" not in capsys.readouterr().out


@pytest.mark.parametrize("name,kind", [
    ("../escaped.txt", "regular"),
    ("./docs/../../escaped.txt", "regular"),
    ("/tmp/absolute.txt", "regular"),
    ("docs\\unexpected.txt", "regular"),
    ("./docs/link", "symlink"),
    ("./docs/hardlink", "hardlink"),
    ("./docs/char-device", "device"),
    ("./docs/pipe", "fifo"),
])
def test_rejects_unsafe_entries_before_extracting(tmp_path, name, kind):
    archive = archive_with(tmp_path, [(name, kind, b"x")])
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ValueError, match="unsafe"):
        guard.extract_verified(archive, destination)
    assert not list(destination.iterdir())


def test_rejects_repeated_destinations_and_member_bombs(tmp_path, monkeypatch):
    archive = archive_with(tmp_path, [
        ("./docs/item", "regular", b"a"),
        ("docs/item", "regular", b"b"),
    ])
    with pytest.raises(ValueError, match="repeated"):
        guard.inspect_archive(archive)

    archive = archive_with(tmp_path, [
        ("./docs/a", "regular", b"a"),
        ("./docs/b", "regular", b"b"),
        ("./docs/c", "regular", b"c"),
    ])
    monkeypatch.setattr(guard, "MAX_ARCHIVE_MEMBERS", 2)
    with pytest.raises(ValueError, match="member limit"):
        guard.inspect_archive(archive)


def test_insufficient_disk_fails_closed_without_extracting(tmp_path, monkeypatch):
    archive = archive_with(tmp_path, [("./private.dat", "regular", b"12345")])
    destination = tmp_path / "out"
    destination.mkdir()
    monkeypatch.setattr(
        guard.shutil, "disk_usage",
        lambda _: SimpleNamespace(free=guard.FREE_SPACE_RESERVE_BYTES + 4),
    )
    with pytest.raises(ValueError, match="Insufficient free space"):
        guard.extract_verified(archive, destination)
    assert not list(destination.iterdir())


def test_invalid_destination_refused(tmp_path):
    archive = archive_with(tmp_path, [("ok.txt", "regular", b"ok")])
    with pytest.raises(ValueError, match="real directory"):
        guard.extract_verified(archive, tmp_path / "missing")
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="real directory"):
        guard.extract_verified(archive, link)


def test_restore_script_validates_archive_before_createdb_and_preserves_cleanup():
    shell = RESTORE_SCRIPT.read_text()
    assert shell.index('verify-restore-archive.py') < shell.index('sudo -u postgres createdb')
    assert 'trap cleanup EXIT' in shell
    assert 'pg_restore --exit-on-error --no-owner --no-privileges' in shell
    assert 'test "$ACTUAL_SHA" = "$EXPECTED_SHA"' in shell
    assert 'test "$RESTORED_ALEMBIC" = "$EXPECTED_ALEMBIC"' in shell
    assert 'verify-evidence.py' in shell
    assert 'DISASTER RECOVERY RESTORE REHEARSAL: PASS' in shell
