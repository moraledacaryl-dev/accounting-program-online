import pytest

from app.core.settings import Settings


def production_settings(**overrides):
    values = {
        'environment': 'production',
        'secret_key': 'a' * 64,
        'integration_enabled': True,
        'integration_secret': 'b' * 64,
        'integration_password': 'c' * 64,
        'allow_default_admin_bootstrap': False,
        'cors_origins': 'https://accounting.hiddenoasis.app',
        'auth_cookie_secure': True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_secure_production_configuration_passes():
    production_settings().validate_production_security()


@pytest.mark.parametrize(
    ('overrides', 'message'),
    [
        ({'secret_key': 'change-me-super-secret'}, 'SECRET_KEY'),
        ({'secret_key': 'too-short'}, 'at least 32'),
        ({'integration_secret': 'pos-integration-secret'}, 'INTEGRATION_SECRET'),
        ({'integration_password': 'pos1234'}, 'INTEGRATION_PASSWORD'),
        ({'allow_default_admin_bootstrap': True}, 'ALLOW_DEFAULT_ADMIN_BOOTSTRAP'),
        ({'cors_origins': '*'}, 'Wildcard CORS'),
        ({'auth_cookie_secure': False}, 'AUTH_COOKIE_SECURE'),
    ],
)
def test_unsafe_production_configuration_fails(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        production_settings(**overrides).validate_production_security()


def test_development_keeps_local_defaults_available():
    Settings(_env_file=None, environment='development').validate_production_security()
