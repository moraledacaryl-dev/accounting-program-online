"""Training responsibilities retain the actual source role and its permissions."""
from dataclasses import asdict, dataclass
from training.curriculum import LESSONS, BY_ID, ROLES, ROLE_NAMES

@dataclass(frozen=True)
class DutyPath:
    id: str
    title: str
    role: str
    description: str
    lessons: tuple[str, ...]
    final_tasks: tuple[str, ...]

FINALS = {
    'cashier': ('receipt','collect-receivable','cashier-authority'),
    'front_desk': ('receipt','collect-receivable','folio-charge','settle-folio'),
    'accounting_admin': ('receipt-with-journal','transfer','pay-payable','depreciation-cap','locked-period'),
    'manager': ('pay-payable','count-cash','post-reviewed-journal','refuse-repeat-disposal'),
    'auditor': ('find-before-retry','read-trial-balance','read-profit','read-inbox'),
    'owner': ('receipt-with-journal','post-reviewed-journal','depreciation-cap','refuse-repeat-disposal'),
}
PATHS = [DutyPath('role-'+role, ROLE_NAMES[role], role,
    'Practise the work assigned to '+ROLE_NAMES[role]+'. Your production permissions remain separate.',
    tuple(row.id for row in LESSONS if role in row.roles), FINALS[role]) for role in ROLES]
BY_PATH = {row.id:row for row in PATHS}
for row in PATHS:
    assert set(row.final_tasks) <= set(row.lessons)

def default_path(role): return 'role-'+role
def public_paths(): return [asdict(row) for row in PATHS]
