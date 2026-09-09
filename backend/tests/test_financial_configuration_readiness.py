from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import AccountMappingRule, ChartAccount
from app.services.financial_configuration_service import financial_configuration_status


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def add_accounts(db):
    db.add_all([
        ChartAccount(code='INV', name='Inventory', account_type='asset', is_active=True),
        ChartAccount(code='COGS', name='Cost of Goods Sold', account_type='expense', is_active=True),
        ChartAccount(code='MEALS', name='Staff Meals Expense', account_type='expense', is_active=True),
    ])
    db.commit()


def add_rule(db, *, category, debit, credit, bucket=None):
    db.add(AccountMappingRule(
        module_slug='inventory',
        category=category,
        bucket=bucket,
        direction='out',
        debit_account_code=debit,
        credit_account_code=credit,
        priority=10,
        is_active=True,
    ))
    db.commit()


def test_empty_chart_is_not_financially_ready():
    db = make_session()
    status = financial_configuration_status(db)

    assert status['ready'] is False
    assert status['active_chart_account_count'] == 0
    assert status['missing_required_rules'] == ['staff_meals', 'pos_cogs']


def test_required_inventory_rules_with_active_accounts_are_ready():
    db = make_session()
    add_accounts(db)
    add_rule(db, category='Staff Meals', debit='MEALS', credit='INV')
    add_rule(db, category='Cost of Goods Sold', debit='COGS', credit='INV')

    status = financial_configuration_status(db)

    assert status['ready'] is True
    assert status['active_chart_account_count'] == 3
    assert status['missing_required_rules'] == []
    assert all(row['configured'] for row in status['required_inventory_posting_rules'])


def test_rule_referencing_inactive_account_is_not_ready():
    db = make_session()
    add_accounts(db)
    inventory = db.query(ChartAccount).filter(ChartAccount.code == 'INV').one()
    inventory.is_active = False
    db.commit()
    add_rule(db, category='Staff Meals', debit='MEALS', credit='INV')
    add_rule(db, category='Cost of Goods Sold', debit='COGS', credit='INV')

    status = financial_configuration_status(db)

    assert status['ready'] is False
    assert status['missing_required_rules'] == ['staff_meals', 'pos_cogs']
    assert all(row['credit_account_active'] is False for row in status['required_inventory_posting_rules'])


def test_more_specific_rule_does_not_mask_missing_integration_rule():
    db = make_session()
    add_accounts(db)
    add_rule(db, category='Staff Meals', debit='MEALS', credit='INV', bucket='Kitchen')
    add_rule(db, category='Cost of Goods Sold', debit='COGS', credit='INV')

    status = financial_configuration_status(db)

    assert status['ready'] is False
    assert status['missing_required_rules'] == ['staff_meals']
    meals = next(row for row in status['required_inventory_posting_rules'] if row['key'] == 'staff_meals')
    assert meals['mapping_id'] is None
