from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import AccountMappingRule, ChartAccount


REQUIRED_INVENTORY_POSTING_RULES = (
    {
        'key': 'staff_meals',
        'module_slug': 'inventory',
        'category': 'Staff Meals',
        'direction': 'out',
    },
    {
        'key': 'pos_cogs',
        'module_slug': 'inventory',
        'category': 'Cost of Goods Sold',
        'direction': 'out',
    },
)


def _normalized(value: str | None) -> str:
    return str(value or '').strip().casefold()


def _matching_rule(db: Session, requirement: dict) -> AccountMappingRule | None:
    candidates = db.query(AccountMappingRule).filter(
        AccountMappingRule.module_slug == requirement['module_slug'],
        AccountMappingRule.is_active == True,
    ).order_by(AccountMappingRule.priority.asc(), AccountMappingRule.id.asc()).all()

    expected_category = _normalized(requirement['category'])
    expected_direction = _normalized(requirement['direction'])
    for rule in candidates:
        if _normalized(rule.category) != expected_category:
            continue
        if _normalized(rule.direction) != expected_direction:
            continue
        # These integration adapters resolve a category/direction record with no
        # bucket/item/payment method. A more-specific rule would not match it.
        if rule.bucket or rule.item or rule.payment_method:
            continue
        return rule
    return None


def financial_configuration_status(db: Session) -> dict:
    active_accounts = db.query(ChartAccount).filter(ChartAccount.is_active == True).all()
    accounts_by_code = {str(row.code or '').strip().upper(): row for row in active_accounts if row.code}

    rules: list[dict] = []
    for requirement in REQUIRED_INVENTORY_POSTING_RULES:
        rule = _matching_rule(db, requirement)
        debit_code = str(rule.debit_account_code or '').strip().upper() if rule else ''
        credit_code = str(rule.credit_account_code or '').strip().upper() if rule else ''
        debit_ok = bool(debit_code and debit_code in accounts_by_code)
        credit_ok = bool(credit_code and credit_code in accounts_by_code)
        configured = bool(rule and debit_ok and credit_ok)
        rules.append({
            **requirement,
            'configured': configured,
            'mapping_id': rule.id if rule else None,
            'debit_account_code': debit_code or None,
            'credit_account_code': credit_code or None,
            'debit_account_active': debit_ok,
            'credit_account_active': credit_ok,
        })

    missing = [row['key'] for row in rules if not row['configured']]
    return {
        'ready': bool(active_accounts) and not missing,
        'active_chart_account_count': len(active_accounts),
        'required_inventory_posting_rules': rules,
        'missing_required_rules': missing,
    }
