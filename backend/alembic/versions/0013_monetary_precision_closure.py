"""Convert persisted monetary fields to exact decimal precision.

Revision ID: 0013_money_precision
Revises: 0012_supplier_credit_reversals
"""
from alembic import op
import sqlalchemy as sa

from app.db.monetary_precision import MONEY_COLUMNS, MONEY_PRECISION, MONEY_SCALE

revision = '0013_money_precision'
down_revision = '0012_supplier_credit_reversals'
branch_labels = None
depends_on = None


def _existing_columns(bind) -> dict[str, set[str]]:
    inspector = sa.inspect(bind)
    return {
        table: {column['name'] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # SQLite uses dynamic storage; the runtime model registry applies Numeric
        # semantics so test/dev behavior still exercises Decimal values.
        return

    existing = _existing_columns(bind)
    target_type = sa.Numeric(MONEY_PRECISION, MONEY_SCALE)

    for table, column in sorted(MONEY_COLUMNS):
        if table not in existing or column not in existing[table]:
            continue

        invalid = bind.execute(sa.text(
            f'SELECT count(*) FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL AND ('
            f'"{column}"::text IN (\'NaN\', \'Infinity\', \'-Infinity\') '
            f'OR abs("{column}") >= 1e16)'
        )).scalar()
        if invalid:
            raise RuntimeError(
                f'Monetary precision migration stopped: {table}.{column} contains '
                'non-finite or out-of-range values.'
            )

        op.alter_column(
            table,
            column,
            type_=target_type,
            postgresql_using=f'round("{column}"::numeric, {MONEY_SCALE})',
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    existing = _existing_columns(bind)
    for table, column in sorted(MONEY_COLUMNS):
        if table not in existing or column not in existing[table]:
            continue
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            postgresql_using=f'"{column}"::double precision',
        )
