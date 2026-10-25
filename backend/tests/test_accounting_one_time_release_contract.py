"""Offline contract checks for one-time Accounting production release wiring.

No live GitHub access, SSH access, or production mutations.
"""
from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ONCE_PATH = ROOT / ".github/workflows/accounting-certified-one-time-release.yml"
DEPLOY_PATH = ROOT / ".github/workflows/deploy-accounting.yml"
SHA = "a" * 40


def test_one_time_main_only_trigger_and_protected_deployment_reuse():
    once = ONCE_PATH.read_text()
    deploy = DEPLOY_PATH.read_text()
    assert "on:\n  push:\n    branches:\n      - main\n    paths:\n      - .github/workflows/accounting-certified-one-time-release.yml" in once
    assert "uses: ./.github/workflows/deploy-accounting.yml" in once
    assert "secrets: inherit" in once
    assert "needs: await-ci" in once
    assert "release_sha: ${{ needs.await-ci.outputs.release_sha }}" in once
    assert "workflow_call:" in deploy
    assert "workflow_dispatch:" in deploy
    assert "activate-release.sh" in deploy
    assert "4294967296" in deploy
    assert "needs: certify-release" in deploy
    assert "head_sha=$RELEASE_SHA&event=push" not in deploy


@pytest.fixture
def check(tmp_path):
    workflow = yaml.safe_load(ONCE_PATH.read_text())
    source = workflow["jobs"]["await-ci"]["steps"][1]["run"]
    gh = tmp_path / "gh"
    gh.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import json
        import os
        import sys

        endpoint = next((value for value in sys.argv[1:] if value.startswith("repos/")), "")
        if endpoint.endswith("/commits/main"):
            print(os.environ["FAKE_MAIN_SHA"])
        elif endpoint.endswith("/actions/workflows/ci.yml/runs?per_page=100"):
            print(json.dumps({"workflow_runs": json.loads(os.environ["FAKE_RUNS"])}))
        else:
            sys.exit(44)
    """))
    gh.chmod(0o755)

    def run(rows, main_sha=SHA):
        env = {
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
            "GH_REPO": "test/accounting",
            "GH_TOKEN": "offline-test-token",
            "RELEASE_SHA": SHA,
            "FAKE_MAIN_SHA": main_sha,
            "FAKE_RUNS": json.dumps(rows),
        }
        return subprocess.run(
            ["bash", "-c", source],
            env=env, capture_output=True, text=True, timeout=10,
        )

    return run


def _row(sha=SHA, event="push", branch="main",
         status="completed", conclusion="success", run_id=10):
    return {
        "id": run_id, "head_sha": sha, "event": event,
        "head_branch": branch, "status": status, "conclusion": conclusion,
    }


def test_exact_sha_main_push_completed_success_allows_reusable_deploy(check):
    result = check([
        _row(sha="b" * 40, run_id=1),
        _row(event="pull_request", run_id=2),
        _row(branch="other", run_id=3),
        _row(status="completed", conclusion="failure", run_id=4),
        _row(run_id=5),
    ])
    assert result.returncode == 0, result.stderr
    assert "Exact-main CI verified" in result.stdout


def test_failed_exact_main_ci_blocks_production_release(check):
    result = check([_row(conclusion="failure")])
    assert result.returncode != 0
    assert "CI failed" in result.stderr


def test_new_main_commit_blocks_stale_release_even_if_ci_passed(check):
    result = check([_row()], main_sha="b" * 40)
    assert result.returncode != 0
    assert "Main advanced" in result.stderr


def test_only_exact_main_sha_event_and_branch_count_as_ci_proof():
    source = yaml.safe_load(ONCE_PATH.read_text())["jobs"]["await-ci"]["steps"][1]["run"]
    for condition in [
        '.head_sha == $sha', '.head_branch == "main"', '.event == "push"',
        '.status == "completed"', '.conclusion == "success"',
        "repos/$GH_REPO/actions/workflows/ci.yml/runs?per_page=100",
    ]:
        assert condition in source
    assert "head_sha=$RELEASE_SHA" not in source
