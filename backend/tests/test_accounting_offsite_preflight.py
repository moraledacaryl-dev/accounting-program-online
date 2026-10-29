"""The offsite diagnostic must report only fixed stages, including on failure."""

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dr" / "accounting_offsite_preflight.py"
spec = importlib.util.spec_from_file_location("accounting_offsite_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def fake_offsite(*, failed_stage=None, used=100):
    def maybe_fail(stage):
        if stage == failed_stage:
            raise RuntimeError("private /path and token must stay hidden")

    class Restic:
        def __init__(self, *_args):
            maybe_fail("repository")

        def run(self, *_args):
            return json.dumps({"total_size": used})

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
    def test_success_and_capacity_guard(self):
        self.assertEqual(preflight.diagnose(fake_offsite()), "repository_capacity_guard")
        self.assertEqual(preflight.diagnose(fake_offsite(used=0)), "repository_capacity_guard")
        large_budget = fake_offsite()
        large_budget.REPOSITORY_BUDGET_BYTES = 100 * 1024**2
        self.assertEqual(preflight.diagnose(large_budget), "preflight_pass")

    def test_private_exception_text_is_replaced_with_stage(self):
        for stage, expected in (
            ("config", "config_unverified"),
            ("source", "source_unverified"),
            ("key", "key_scope_unverified"),
            ("repository", "repository_read_unverified"),
        ):
            with self.subTest(stage=stage):
                result = preflight.diagnose(fake_offsite(failed_stage=stage))
                self.assertEqual(result, expected)
                self.assertNotIn("private", result)


if __name__ == "__main__":
    unittest.main()
