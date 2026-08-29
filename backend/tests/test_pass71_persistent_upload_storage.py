from pathlib import Path

from app.core.settings import DEFAULT_UPLOADS_PATH, PRODUCTION_UPLOADS_PATH, Settings


def test_production_default_uploads_live_outside_release_tree(monkeypatch):
    monkeypatch.delenv('UPLOADS_DIR', raising=False)
    settings = Settings(environment='production', uploads_dir=str(DEFAULT_UPLOADS_PATH))
    assert settings.uploads_path == PRODUCTION_UPLOADS_PATH


def test_development_keeps_local_uploads_default(monkeypatch):
    monkeypatch.delenv('UPLOADS_DIR', raising=False)
    settings = Settings(environment='development', uploads_dir=str(DEFAULT_UPLOADS_PATH))
    assert settings.uploads_path == DEFAULT_UPLOADS_PATH.resolve()


def test_explicit_uploads_dir_is_respected_in_production(tmp_path):
    explicit = tmp_path / 'uploads'
    settings = Settings(environment='production', uploads_dir=str(explicit))
    assert settings.uploads_path == explicit.resolve()
    assert settings.uploads_path != Path('/var/lib/hiddenoasis/accounting/uploads')
