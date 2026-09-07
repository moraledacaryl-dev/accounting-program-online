"""Store journal amounts with exact decimal precision; reject lossy conversion.

Revision ID: 0009_journal_precision
Revises: 0008_operations_outbox
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_journal_precision'
down_revision = '0008_operations_outbox'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        invalid = bind.execute(sa.text("""
            SELECT count(*) FROM journal_lines
            WHERE debit::text IN ('NaN', 'Infinity', '-Infinity')
               OR credit::text IN ('NaN', 'Infinity', '-Infinity')
               OR abs(debit) >= 1e16 OR abs(credit) >= 1e16
               OR abs(debit::numeric - round(debit::numeric, 4)) > 0.000000001
               OR abs(credit::numeric - round(credit::numeric, 4)) > 0.000000001
        """)).scalar()
        if invalid:
            raise RuntimeError('Journal precision migration stopped: review out-of-range or higher-precision ledger amounts before retrying.')
        for column in ('debit', 'credit'):
            op.alter_column('journal_lines', column, type_=sa.Numeric(20, 4), postgresql_using=f'{column}::numeric(20,4)')
    # SQLite has dynamic storage; model-level Numeric conversion is used in tests.


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        for column in ('debit', 'credit'):
            op.alter_column('journal_lines', column, type_=sa.Float(), postgresql_using=f'{column}::double precision')
