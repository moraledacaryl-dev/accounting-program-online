import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.deps import _csrf_tokens_match, _enforce_cookie_csrf
from app.core.settings import Settings, looks_like_placeholder_secret
from app.services.auth_service import is_integration_username
from app.services.permission_service import ROLE_PERMISSION_PRESETS


class SecuritySettingsTests(unittest.TestCase):
    def test_placeholder_integration_secrets_are_detected(self):
        placeholders = [
            '',
            'pos-integration-secret',
            'CHANGE_ME_SHARED_SECRET_LATER',
            'CHANGE_ME_SHARED_POS_ACCOUNTING_INTEGRATION_SECRET',
            'replace-with-real-secret',
        ]
        for value in placeholders:
            with self.subTest(value=value):
                self.assertTrue(looks_like_placeholder_secret(value))

    def test_realistic_secret_is_not_flagged(self):
        self.assertFalse(looks_like_placeholder_secret('hidden-oasis-shared-2026-strong-token'))

    def test_auth_cookie_secure_defaults_to_production(self):
        prod_settings = Settings(environment='production', auth_cookie_secure=None)
        dev_settings = Settings(environment='development', auth_cookie_secure=None)

        self.assertTrue(prod_settings.auth_cookie_secure_effective)
        self.assertFalse(dev_settings.auth_cookie_secure_effective)

    def test_invalid_auth_cookie_samesite_falls_back_to_lax(self):
        app_settings = Settings(auth_cookie_samesite='surprise')

        self.assertEqual(app_settings.auth_cookie_samesite_value, 'lax')

    def test_cookie_csrf_enforcement_allows_matching_double_submit_token(self):
        request = SimpleNamespace(
            method='POST',
            cookies={'erp_csrf': 'token'},
            headers={'x-csrf-token': 'token'},
        )

        _enforce_cookie_csrf(request, bearer_token=None, cookie_token='session')

    def test_cookie_csrf_enforcement_blocks_missing_token(self):
        request = SimpleNamespace(method='POST', cookies={}, headers={})

        with self.assertRaises(HTTPException) as caught:
            _enforce_cookie_csrf(request, bearer_token=None, cookie_token='session')
        self.assertEqual(caught.exception.status_code, 403)

    def test_bearer_auth_skips_cookie_csrf_enforcement(self):
        request = SimpleNamespace(method='POST', cookies={}, headers={})

        _enforce_cookie_csrf(request, bearer_token='api-token', cookie_token='session')

    def test_csrf_token_comparison(self):
        self.assertTrue(_csrf_tokens_match('same', 'same'))
        self.assertFalse(_csrf_tokens_match('same', 'different'))
        self.assertFalse(_csrf_tokens_match('', 'same'))

    def test_pos_integration_role_is_limited_but_operational(self):
        permissions = ROLE_PERMISSION_PRESETS['pos_integration']

        self.assertIn('bookings.view', permissions)
        self.assertIn('folios.manage', permissions)
        self.assertIn('cashflow.money_in', permissions)
        self.assertNotIn('users.manage', permissions)
        self.assertNotIn('system_settings.manage', permissions)

    def test_integration_username_matching_is_case_insensitive(self):
        self.assertTrue(is_integration_username('POS_INTEGRATION'))
        self.assertTrue(is_integration_username(' pos_integration '))
        self.assertFalse(is_integration_username('admin'))


if __name__ == '__main__':
    unittest.main()
