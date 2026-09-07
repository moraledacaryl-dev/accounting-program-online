import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('evidence_verifier', Path(__file__).resolve().parents[2] / 'scripts/dr/verify-evidence.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_recovery_checks_every_attachment_and_size(tmp_path):
    (tmp_path / 'receipt.pdf').write_bytes(b'receipt')
    rows = [dict(id=1, stored_name='receipt.pdf', size_bytes=7)]
    assert verifier.verify(tmp_path, rows) == 1
    (tmp_path / 'receipt.pdf').write_bytes(b'truncated')
    with pytest.raises(ValueError, match='size mismatch'):
        verifier.verify(tmp_path, rows)
    (tmp_path / 'receipt.pdf').unlink()
    with pytest.raises(ValueError, match='missing'):
        verifier.verify(tmp_path, rows)


def test_recovery_rejects_paths_outside_evidence_directory(tmp_path):
    with pytest.raises(ValueError, match='unsafe'):
        verifier.verify(tmp_path, [dict(id=1, stored_name='../secret', size_bytes=1)])
