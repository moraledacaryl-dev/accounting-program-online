"""The offsite diagnostic must report only fixed stages, including on failure."""

import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dr" / "accounting_offsite_preflight.py"
spec = importlib.util.spec_from_file_location("accounting_offsite_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def fake_offsite(*, failed_stage=None):
    def maybe_fail(stage):
        if stage == failed_stage:
            raise RuntimeError("private /path and token must stay hidden")

    class Restic:
        def __init__(self, *_args):
            maybe_fail("repository")
            self.binary = Path("/usr/local/bin/restic")
            self.environment = {"PATH": "/usr/bin"}

    def read_config(_path):
        maybe_fail("config")
        return {"enabled": True, "keys": {"private": "never print"}}

    def verified_source(_backups, _current):
        maybe_fail("source")
        return ((), "synthetic", "a" * 40, 100)

    def verify_key_scope(_keys):
        maybe_fail("key")

    return SimpleNamespace(
        read_config=read_config, verified_source=verified_source,
        verify_key_scope=verify_key_scope, Restic=Restic,
        REPOSITORY_BUDGET_BYTES=1000,
    )


class OffsitePreflightTests(unittest.TestCase):
    def test_native_probe_requests_only_scoped_prefix_and_one_object(self):
        authorization = {
            "authorizationToken": "private-token",
            "apiInfo": {"storageApi": {
                "apiUrl": "https://api004.backblazeb2.com",
                "bucketId": "a" * 24,
            }},
        }
        with patch.object(preflight, "urlopen", side_effect=[
            io.BytesIO(json.dumps(authorization).encode()),
            io.BytesIO(b'{"files":[{"fileName":"accounting/private-object"}]}'),
        ]) as opened:
            self.assertTrue(preflight.native_repository_has_objects({
                "access_key_id": "test-id", "secret_access_key": "private-secret",
            }))
        self.assertIn("prefix=accounting%2F", opened.call_args_list[1].args[0].full_url)
        self.assertIn("maxFileCount=1", opened.call_args_list[1].args[0].full_url)

    def test_success_and_capacity_guard(self):
        offsite = fake_offsite()
        offsite.REPOSITORY_BUDGET_BYTES = 100 * 1024**2
        with patch.object(preflight, "native_repository_has_objects", return_value=True), patch.object(preflight.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, b"[]", b""),
            subprocess.CompletedProcess([], 0, b'{"total_size":100}', b""),
        ]):
            self.assertEqual(preflight.diagnose(offsite), "preflight_pass")
        with patch.object(preflight, "native_repository_has_objects", return_value=True), patch.object(preflight.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, b"[]", b""),
            subprocess.CompletedProcess([], 0, b'{"total_size":100}', b""),
        ]):
            self.assertEqual(preflight.diagnose(fake_offsite()), "repository_capacity_guard")

    def test_private_exception_text_is_replaced_with_stage(self):
        for stage, expected in (
            ("config", "config_unverified"),
            ("source", "source_unverified"),
            ("key", "key_scope_unverified"),
            ("repository", "repository_client_unverified"),
        ):
            with self.subTest(stage=stage):
                with patch.object(preflight, "native_repository_has_objects", return_value=True):
                    result = preflight.diagnose(fake_offsite(failed_stage=stage))
                self.assertEqual(result, expected)
                self.assertNotIn("private", result)

    def test_native_listing_must_find_repository_objects(self):
        with patch.object(preflight, "native_repository_has_objects", return_value=False):
            self.assertEqual(preflight.diagnose(fake_offsite()), "native_repository_empty")
        with patch.object(preflight, "native_repository_has_objects", side_effect=RuntimeError("private token")):
            self.assertEqual(preflight.diagnose(fake_offsite()), "native_repository_list_unverified")

    def test_restic_errors_are_classified_without_echoing_private_stderr(self):
        for stderr, expected in (
            (b"repository is already locked by /private/path", "repository_lock"),
            (b"wrong password for repository", "repository_password"),
            (b"Access Denied: credential SECRET 403", "repository_access"),
            (b"ListObjectsV2: 403 Forbidden", "repository_access_object_list"),
            (b"ListBuckets: 403 Forbidden", "repository_access_bucket_list"),
            (b"connection timeout to private host", "repository_network"),
            (b"unknown error token=PRIVATE", "repository_command_failed"),
        ):
            with self.subTest(expected=expected):
                result = preflight.classify_restic_failure(stderr)
                self.assertEqual(result, expected)
                self.assertNotIn("PRIVATE", result)


if __name__ == "__main__":
    unittest.main()
