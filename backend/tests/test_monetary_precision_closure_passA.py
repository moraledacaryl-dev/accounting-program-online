from decimal import Decimal

from sqlalchemy import Float, Numeric

from app.db.database import Base
from app.db.monetary_precision import MONEY_COLUMNS, MONEY_PRECISION, MONEY_SCALE, centavos
from app.models import entities  # noqa: F401
from app.models import payable_adjustments  # noqa: F401


def test_every_registered_money_column_uses_exact_numeric_type():
    missing = []
    wrong_type = []

    for table_name, column_name in sorted(MONEY_COLUMNS):
        table = Base.metadata.tables.get(table_name)
        if table is None or column_name not in table.c:
            missing.append(f'{table_name}.{column_name}')
            continue

        column_type = table.c[column_name].type
        if not isinstance(column_type, Numeric):
            wrong_type.append(f'{table_name}.{column_name}:{column_type}')
            continue
        assert column_type.precision == MONEY_PRECISION
        assert column_type.scale == MONEY_SCALE
        assert column_type.asdecimal is True

    assert missing == []
    assert wrong_type == []


def test_measurements_and_percentages_remain_non_money_types():
    expected_float_columns = (
        ('inventory_items', 'quantity_on_hand'),
        ('stock_movements', 'quantity'),
        ('attendance_entries', 'overtime_hours'),
        ('payroll_lines', 'hours_worked'),
        ('booking_channels', 'default_commission_rate'),
        ('menu_promotions', 'min_qty'),
    )

    for table_name, column_name in expected_float_columns:
        column_type = Base.metadata.tables[table_name].c[column_name].type
        assert isinstance(column_type, Float), f'{table_name}.{column_name} unexpectedly became money'


def test_centavo_arithmetic_does_not_reintroduce_binary_float_error():
    assert centavos(Decimal('0.1') + Decimal('0.2')) == Decimal('0.30')
    assert centavos('6890.305') == Decimal('6890.31')
