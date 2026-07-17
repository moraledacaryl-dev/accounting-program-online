from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.taxonomy import router as taxonomy_router
from app.api.records import router as records_router
from app.api.dashboard import router as dashboard_router
from app.api.seed import router as seed_router
from app.api.people import router as people_router
from app.api.stock import router as stock_router
from app.api.asset_registry import router as asset_router
from app.api.master import router as master_router
from app.api.reservations import router as reservations_router
from app.api.channel import router as channel_router
from app.api.payroll import router as payroll_router
from app.api.journals import router as journals_router
from app.api.menu import router as menu_router
from app.api.bir import router as bir_router
from app.api.approvals import router as approvals_router
from app.api.reports import router as reports_router
from app.api.attachments import router as attachments_router
from app.api.cashflow import router as cashflow_router
from app.api.financial_accounts import router as financial_accounts_router
from app.api.transfers import router as transfers_router
from app.api.reconciliations import router as reconciliations_router
from app.api.receivables import router as receivables_router
from app.api.payables import router as payables_router
from app.api.cashflow_templates import router as cashflow_templates_router
from app.api.room_types import router as room_types_router
from app.api.rooms import router as rooms_router
from app.api.rate_plans import router as rate_plans_router
from app.api.booking_channels import router as booking_channels_router
from app.api.room_package_rules import router as room_package_rules_router
from app.api.suppliers import router as suppliers_router
from app.api.purchase_requests import router as purchase_requests_router
from app.api.purchase_orders import router as purchase_orders_router
from app.api.receiving import router as receiving_router
from app.api.payroll_periods import router as payroll_periods_router
from app.api.chart_of_accounts import router as chart_of_accounts_router
from app.api.account_mappings import router as account_mappings_router
from app.api.guests import router as guests_router
from app.api.room_folios import router as room_folios_router
from app.api.roles_permissions import router as roles_permissions_router
from app.api.system_settings import router as system_settings_router
from app.api.integration import router as integration_router
from app.api.integrations_beds24 import router as integrations_beds24_router
from app.api.integrations_payroll import router as integrations_payroll_router
from app.api.integrations_pos_review import router as integrations_pos_review_router
from app.api.setup_imports import router as setup_imports_router
from app.api.search import router as search_router
from app.api.events import router as events_router
from app.api.integration_review import router as integration_review_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix='/auth', tags=['auth'])
api_router.include_router(taxonomy_router, prefix='/taxonomy', tags=['taxonomy'])
api_router.include_router(records_router, prefix='/records', tags=['records'])
api_router.include_router(dashboard_router, prefix='/dashboard', tags=['dashboard'])
api_router.include_router(seed_router, prefix='/seed', tags=['seed'])
api_router.include_router(people_router, prefix='/people', tags=['people'])
api_router.include_router(stock_router, prefix='/stock', tags=['stock'])
api_router.include_router(asset_router, prefix='/asset-registry', tags=['asset-registry'])
api_router.include_router(master_router, prefix='/master', tags=['master'])
api_router.include_router(reservations_router, prefix='/reservations', tags=['reservations'])
api_router.include_router(channel_router, prefix='/channel', tags=['channel'])
api_router.include_router(payroll_router, prefix='/payroll', tags=['payroll'])
api_router.include_router(journals_router, prefix='/journals', tags=['journals'])
api_router.include_router(menu_router, prefix='/menu', tags=['menu'])
api_router.include_router(bir_router, prefix='/bir', tags=['bir'])
api_router.include_router(approvals_router, prefix='/approvals', tags=['approvals'])
api_router.include_router(reports_router, prefix='/reports', tags=['reports'])
api_router.include_router(attachments_router, prefix='/attachments', tags=['attachments'])
api_router.include_router(cashflow_router, prefix='/cashflow', tags=['cashflow'])
api_router.include_router(financial_accounts_router, prefix='/financial-accounts', tags=['financial-accounts'])
api_router.include_router(transfers_router, prefix='/transfers', tags=['transfers'])
api_router.include_router(reconciliations_router, prefix='/reconciliations', tags=['reconciliations'])
api_router.include_router(receivables_router, prefix='/receivables', tags=['receivables'])
api_router.include_router(payables_router, prefix='/payables', tags=['payables'])
api_router.include_router(cashflow_templates_router, prefix='/cashflow-templates', tags=['cashflow-templates'])
api_router.include_router(room_types_router, prefix='/room-types', tags=['room-types'])
api_router.include_router(rooms_router, prefix='/rooms', tags=['rooms'])
api_router.include_router(rate_plans_router, prefix='/rate-plans', tags=['rate-plans'])
api_router.include_router(booking_channels_router, prefix='/booking-channels', tags=['booking-channels'])
api_router.include_router(room_package_rules_router, prefix='/room-package-rules', tags=['room-package-rules'])
api_router.include_router(suppliers_router, prefix='/suppliers', tags=['suppliers'])
api_router.include_router(purchase_requests_router, prefix='/purchase-requests', tags=['purchase-requests'])
api_router.include_router(purchase_orders_router, prefix='/purchase-orders', tags=['purchase-orders'])
api_router.include_router(receiving_router, prefix='/receiving', tags=['receiving'])
api_router.include_router(payroll_periods_router, prefix='/payroll-periods', tags=['payroll-periods'])
api_router.include_router(chart_of_accounts_router, prefix='/chart-of-accounts', tags=['chart-of-accounts'])
api_router.include_router(account_mappings_router, prefix='/account-mappings', tags=['account-mappings'])
api_router.include_router(guests_router, prefix='/guests', tags=['guests'])
api_router.include_router(room_folios_router, prefix='/room-folios', tags=['room-folios'])
api_router.include_router(roles_permissions_router, prefix='/roles-permissions', tags=['roles-permissions'])
api_router.include_router(system_settings_router, prefix='/system-settings', tags=['system-settings'])
api_router.include_router(integration_router, prefix='/integration', tags=['integration'])
api_router.include_router(integration_review_router, prefix='/integration-review', tags=['integration-review'])
api_router.include_router(integrations_beds24_router, prefix='/integrations/beds24', tags=['integrations-beds24'])
api_router.include_router(integrations_payroll_router, prefix='/integrations/payroll', tags=['integrations-payroll'])
api_router.include_router(integrations_pos_review_router, prefix='/integrations/pos-review', tags=['integrations-pos-review'])
api_router.include_router(setup_imports_router, prefix='/setup-imports', tags=['setup-imports'])
api_router.include_router(search_router, prefix='/search', tags=['search'])
api_router.include_router(events_router, prefix='/events', tags=['events'])
