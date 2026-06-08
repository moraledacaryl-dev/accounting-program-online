# Test Results

Date: 2026-06-08

## Commands Run

- Accounting: `pytest backend/tests/test_payroll_integration_receiver.py`
  - Result: not run; `pytest` is not installed in the shell.
- Accounting syntax: `python3 -B -c "... ast.parse ..."`
  - Result: passed for `backend/app/api/integrations_payroll.py`, `backend/app/models/entities.py`, and `backend/tests/test_payroll_integration_receiver.py`.
- POS: `pytest backend/tests/test_daily_ops_context.py backend/tests/test_phase7_contracts.py`
  - Result: not run; `pytest` is not installed in the shell.
- POS syntax: `python3 -B -c "... ast.parse ..."`
  - Result: passed for `backend/app/api/reports.py` and `backend/tests/test_daily_ops_context.py`.
- Operations: `pytest backend/tests/test_cross_app_integrations.py`
  - Result: not run; `pytest` is not installed in the shell.
- Operations syntax: `python3 -B -c "... ast.parse ..."`
  - Result: passed for `backend/app/models.py`, `backend/app/routers/api.py`, and `backend/tests/test_cross_app_integrations.py`.
- Staff/Payroll: `.venv/bin/python -m pytest tests/test_payroll_core.py`
  - Result: not run; `pytest` is not installed in the Staff/Payroll virtualenv.
- Staff/Payroll: `.venv/bin/python -m unittest tests.test_payroll_core`
  - Result: passed, 8 tests.
- Frontend package inspection with `node`
  - Result: not run; `node` is not installed in the shell.
- Backend import smoke checks for Accounting/POS/Operations helpers
  - Result: not run; `fastapi` is not installed in the shell.

## Environment Notes

Python bytecode compile checks initially failed because the sandbox blocked writes to `/Users/caryl/Library/Caches/com.apple.python`. Syntax checks were rerun with bytecode disabled.
