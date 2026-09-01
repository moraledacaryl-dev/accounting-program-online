from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_combined_pass83_and_runtime_cache_release_contract():
    creation_guard = (
        ROOT / 'backend/app/services/subledger_creation_guard.py'
    ).read_text()
    receivables = (
        ROOT / 'backend/app/api/receivables.py'
    ).read_text()
    payables = (
        ROOT / 'backend/app/api/payables.py'
    ).read_text()
    receivable_page = (
        ROOT / 'frontend/app/cashflow/receivables/page.js'
    ).read_text()
    payable_page = (
        ROOT / 'frontend/app/cashflow/payables/page.js'
    ).read_text()
    prepare_release = (
        ROOT / 'scripts/release/prepare-release.sh'
    ).read_text()
    activate_release = (
        ROOT / 'scripts/release/activate-release.sh'
    ).read_text()

    assert 'ensure_receivable_starts_unsettled' in creation_guard
    assert 'ensure_payable_starts_unsettled' in creation_guard
    assert 'ensure_receivable_starts_unsettled(payload)' in receivables
    assert 'ensure_payable_starts_unsettled(payload)' in payables

    assert 'Already Collected' not in receivable_page
    assert 'Already Paid' not in payable_page
    assert "amount_collected: editingId ? Number(form.amount_collected || 0) : 0" in receivable_page
    assert "amount_paid: editingId ? Number(form.amount_paid || 0) : 0" in payable_page
    assert "setNotice('Balance saved.')" in receivable_page
    assert "setNotice('Bill saved.')" in payable_page

    cache_path = 'frontend/.next/cache/images'
    assert cache_path in prepare_release
    assert 'install -d -o hiddenoasis -g hiddenoasis -m 0750' in prepare_release
    assert cache_path in activate_release
    assert "hiddenoasis:hiddenoasis" in activate_release
    assert 'sudo -u hiddenoasis test -w' in prepare_release
    assert 'sudo -u hiddenoasis test -w' in activate_release
