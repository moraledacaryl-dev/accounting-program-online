from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.settings import settings
from app.db.database import get_db
from app.models.entities import MenuItem, MenuSKU, User
from app.services.cashflow_service import list_financial_accounts

router = APIRouter()

@router.get('/status')
def integration_status(db: Session = Depends(get_db)):
    menu_item_count = db.query(MenuItem).count()
    sku_count = db.query(MenuSKU).count()
    default_admin_exists = db.query(User).filter(User.username == 'admin').count() > 0
    integration_user_exists = db.query(User).filter(User.username == settings.integration_username).count() > 0
    financial_accounts = list_financial_accounts(db)
    security_warnings = settings.security_warnings

    return {
        'ok': True,
        'app_name': settings.app_name,
        'environment': settings.environment,
        'api_prefix': settings.api_prefix,
        'database_url': settings.database_url if settings.database_url.startswith('sqlite') else 'configured',
        'bootstrap_enabled': settings.bootstrap_enabled,
        'integration_enabled': settings.integration_enabled,
        'security': {
            'production_ready': not security_warnings,
            'warning_count': len(security_warnings),
            'warnings': [] if settings.is_production else security_warnings,
        },
        'default_admin_exists': default_admin_exists,
        'integration_user_exists': integration_user_exists,
        'menu_item_count': menu_item_count,
        'sku_count': sku_count,
        'financial_account_count': len(financial_accounts),
        'available_routes': [
            '/api/auth/bootstrap',
            '/api/auth/login',
            '/api/auth/me',
            '/api/auth/integration/token',
            '/api/menu/items',
            '/api/menu/skus',
            '/api/menu/sales',
            '/api/financial-accounts',
            '/api/cashflow/transactions',
            '/api/reconciliations',
            '/api/receivables',
            '/api/transfers',
        ],
    }
