"""Offline behavioral tests of the actual GitHub Actions deployment CI gate.

No GitHub network calls, SSH, production data access, or workflow dispatch.
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
WORKFLOW = ROOT / ".github/workflows/deploy-accounting.yml"
RELEASE_SHA = "a" * 40
MAIN_SHA = "b" * 40


@pytest.fixture
def gate(tmp_path):
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow["jobs"]["certify-release"]["steps"]
    source = next(step["run"] for step in steps if step["name"] == "Require successful CI for exact release SHA")
    gh = tmp_path / "gh"
    gh.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import json
        import os
        import sys

        argv = sys.argv[1:]
        endpoint = next((value for value in argv if value.startswith("repos/")), "")
        release_sha = os.environ["RELEASE_SHA"]
        if endpoint.endswith("/commits/" + release_sha):
            print(release_sha)
        elif endpoint.endswith("/commits/main"):
            print(os.environ["FAKE_MAIN_SHA"])
        elif "/compare/" in endpoint:
            print(os.environ.get("FAKE_COMPARISON", "ahead"))
        elif "/actions/workflows/ci.yml/runs?" in endpoint:
            # A filter that triggered the Inventory false negative must NOT
            # occur in Accounting's release gate either.
            if "head_sha=" in endpoint or "event=" in endpoint:
                sys.exit(49)
            if os.environ.get("FAKE_API_FAILURE") == "1":
                sys.exit(50)
            page = 2 if "page=2" in endpoint else 1
            key = "FAKE_CI_RUNS_PAGE2" if page == 2 else "FAKE_CI_RUNS"
            print(json.dumps({"workflow_runs": json.loads(os.environ.get(key, "[]"))}))
        else:
            sys.exit(51)
    """))
    gh.chmod(0o755)

    def check(rows, *, page2=(), comparison="ahead", failure=False):
        env = {
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
            "GH_REPO": "test/accounting",
            "GH_TOKEN": "offline-test-token",
            "RELEASE_SHA": RELEASE_SHA,
            "FAKE_MAIN_SHA": MAIN_SHA,
            "FAKE_COMPARISON": comparison,
            "FAKE_CI_RUNS": json.dumps(list(rows)),
            "FAKE_CI_RUNS_PAGE2": json.dumps(list(page2)),
            "FAKE_API_FAILURE": "1" if failure else "0",
        }
        return subprocess.run(["bash", "-c", source], env=env, capture_output=True, text=True, timeout=15)
    return check


def run_row(*, sha=RELEASE_SHA, event="push", branch="main", status="completed",
            conclusion="success", run_id=42):
    return dict(id=run_id, head_sha=sha, event=event, head_branch=branch,
                status=status, conclusion=conclusion)


def test_exact_successful_main_push_is_accepted_amid_unrelated_ci_runs(gate):
    result = gate([
        run_row(sha=MAIN_SHA, run_id=21),
        run_row(event="pull_request", run_id=22),
        run_row(status="in_progress", conclusion=None, run_id=23),
        run_row(run_id=99),
    ])
    assert result.returncode == 0, result.stderr
    assert "run 99" in result.stdout
    assert "Certified exact release SHA" in result.stdout


@pytest.mark.parametrize("bad", [
    run_row(sha=MAIN_SHA),
    run_row(event="pull_request"),
    run_row(branch="feature"),
    run_row(status="in_progress", conclusion=None),
    run_row(conclusion="failure"),
])
def test_no_other_commit_or_event_can_satisfy_release_gate(gate, bad):
    result = gate([bad])
    assert result.returncode != 0
    assert "Certified" not in result.stdout


def test_unfiltered_two_page_history_finds_exact_commit_but_not_other(gate):
    first_page = [run_row(sha=MAIN_SHA, run_id=i) for i in range(1, 101)]
    result = gate(first_page, page2=[run_row(run_id=201)])
    assert result.returncode == 0
    assert "run 201" in result.stdout


def test_bad_ancestry_and_api_failure_fail_closed(gate):
    assert gate([run_row()], comparison="diverged").returncode != 0
    assert gate([run_row()], failure=True).returncode != 0


def test_workflow_keeps_immutable_sha_backup_and_deployment_controls():
    source = WORKFLOW.read_text()
    assert "head_sha=$RELEASE_SHA&event=push" not in source
    assert "select(.head_sha == $sha" in source
    assert '.event == "push"' in source
    assert '.head_branch == "main"' in source
    assert '.status == "completed"' in source
    assert '.conclusion == "success"' in source
    assert "for page in 1 2 3 4 5" in source
    assert "needs: certify-release" in source
    assert "activate-release.sh" in source
    assert "4294967296" in source
