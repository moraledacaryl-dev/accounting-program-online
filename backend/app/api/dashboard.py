from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permissions
from app.db.database import get_db
from app.models.entities import (
    Booking,
    BookingFolio,
    CashReconciliation,
    Employee,
    Guest,
    InventoryItem,
    JournalEntry,
    MoneyTransaction,
    Payable,
    PayrollPeriod,
    PeriodLock,
    PurchaseOrder,
    PurchaseRequest,
    Receivable,
    Record,
    Room,
    SaleOrder,
    StaffMealLog,
)
from app.services.cashflow_service import cashflow_summary
from app.services.guest_service import folio_balance_summary
from app.services.system_settings_service import (
    dashboard_widget_catalog,
    get_effective_dashboard_widgets,
    load_system_settings,
)

router = APIRouter()


def _to_currency(value) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def _metric_card(key: str, label: str, value, description: str = ''):
    return {
        'key': key,
        'type': 'metric',
        'label': label,
        'description': description,
        'value': value,
    }


def _table_card(key: str, label: str, columns: list[str], rows: list[dict], description: str = ''):
    return {
        'key': key,
        'type': 'table',
        'label': label,
        'description': description,
        'columns': columns,
        'rows': rows,
    }


@router.get('/summary')
def summary(db: Session = Depends(get_db), user=Depends(require_permissions('dashboard.view'))):
    today = datetime.utcnow().strftime('%Y-%m-%d')

    income = db.query(func.coalesce(func.sum(Record.amount), 0)).filter(
        Record.direction == 'income',
        Record.workflow_status == 'approved',
    ).scalar() or 0
    expense = db.query(func.coalesce(func.sum(Record.amount), 0)).filter(
        Record.direction == 'expense',
        Record.workflow_status == 'approved',
    ).scalar() or 0

    inventory_rows = db.query(InventoryItem).all()
    inventory_value = sum((float(i.quantity_on_hand or 0) * float(i.average_cost or 0) for i in inventory_rows))
    low_stock_rows = [
        item for item in inventory_rows
        if float(item.quantity_on_hand or 0) <= float(item.reorder_level or 0)
    ]
    low_stock_count = len(low_stock_rows)

    cashflow = cashflow_summary(db)
    cards = cashflow.get('summary_cards') or {}

    bookings_total = int(db.query(Booking).count() or 0)
    confirmed_bookings = int(db.query(Booking).filter(Booking.status == 'confirmed').count() or 0)
    in_house = int(db.query(Booking).filter(Booking.status == 'checked_in').count() or 0)

    arrivals_today = int(
        db.query(Booking).filter(
            Booking.check_in == today,
            Booking.status.in_(['confirmed', 'checked_in']),
        ).count() or 0
    )
    departures_today = int(
        db.query(Booking).filter(
            Booking.check_out == today,
            Booking.status.in_(['confirmed', 'checked_in']),
        ).count() or 0
    )
    vip_arrivals_today = int(
        db.query(Booking)
        .join(Guest, Booking.guest_id == Guest.id)
        .filter(Booking.check_in == today, Guest.vip_flag == True)
        .count() or 0
    )

    cancelled_bookings = int(db.query(Booking).filter(Booking.status == 'cancelled').count() or 0)
    no_show_bookings = int(db.query(Booking).filter(Booking.status.in_(['no_show', 'noshow'])).count() or 0)

    room_count_total = int(db.query(Room).filter(Room.is_active == True).count() or 0)
    occupancy_rate = round((float(in_house) / float(room_count_total) * 100.0), 2) if room_count_total else 0.0

    room_revenue_today = _to_currency(
        db.query(func.coalesce(func.sum(Booking.gross_amount), 0))
        .filter(Booking.check_in == today, Booking.status.in_(['confirmed', 'checked_in', 'checked_out']))
        .scalar()
    )

    channel_rows = (
        db.query(
            Booking.channel,
            func.count(Booking.id),
            func.coalesce(func.sum(Booking.gross_amount), 0),
        )
        .group_by(Booking.channel)
        .order_by(func.count(Booking.id).desc())
        .limit(8)
        .all()
    )
    top_channels = [
        {
            'channel': row[0] or 'Walk-in',
            'booking_count': int(row[1] or 0),
            'revenue': _to_currency(row[2]),
        }
        for row in channel_rows
    ]

    open_folios = (
        db.query(BookingFolio)
        .options(selectinload(BookingFolio.lines))
        .filter(BookingFolio.status.in_(['open', 'reviewed']))
        .all()
    )
    guest_balance_due = 0.0
    for folio in open_folios:
        guest_balance_due += float(folio_balance_summary(folio).get('balance') or 0)

    pending_records = int(db.query(Record).filter(Record.workflow_status.in_(['draft', 'pending_review'])).count() or 0)
    pending_pr = int(db.query(PurchaseRequest).filter(PurchaseRequest.status == 'submitted').count() or 0)
    pending_po = int(db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(['draft', 'issued'])).count() or 0)
    pending_money = int(db.query(MoneyTransaction).filter(MoneyTransaction.status.in_(['draft', 'pending_approval'])).count() or 0)
    pending_recons = int(db.query(CashReconciliation).filter(CashReconciliation.status.in_(['counted', 'reviewed'])).count() or 0)
    pending_payroll = int(db.query(PayrollPeriod).filter(PayrollPeriod.status.in_(['draft', 'reviewed'])).count() or 0)
    pending_approvals = pending_records + pending_pr + pending_po + pending_money + pending_recons + pending_payroll

    pending_by_workflow = {
        'records': pending_records,
        'purchase_requests': pending_pr,
        'purchase_orders': pending_po,
        'cashflow_transactions': pending_money,
        'cash_reconciliations': pending_recons,
        'payroll_periods': pending_payroll,
    }

    receivables_overdue = int(
        db.query(Receivable).filter(
            Receivable.balance_due > 0,
            Receivable.due_date.isnot(None),
            Receivable.due_date < today,
        ).count() or 0
    )
    payables_overdue = int(
        db.query(Payable).filter(
            Payable.balance_due > 0,
            Payable.due_date.isnot(None),
            Payable.due_date < today,
        ).count() or 0
    )

    sales_today_rows = db.query(SaleOrder).filter(SaleOrder.order_date == today, SaleOrder.status != 'voided').all()
    sales_today_total = sum(float(row.net_amount or 0) for row in sales_today_rows)
    staff_meals_today_rows = db.query(StaffMealLog).filter(StaffMealLog.meal_date == today).all()
    staff_meals_today_cost = sum(float(row.cogs_amount or 0) for row in staff_meals_today_rows)

    cash_in_today = _to_currency(
        db.query(func.coalesce(func.sum(MoneyTransaction.amount), 0)).filter(
            MoneyTransaction.transaction_date == today,
            MoneyTransaction.direction == 'in',
            MoneyTransaction.is_reversed == False,
            MoneyTransaction.status.in_(['approved', 'posted']),
        ).scalar()
    )
    cash_out_today = _to_currency(
        db.query(func.coalesce(func.sum(MoneyTransaction.amount), 0)).filter(
            MoneyTransaction.transaction_date == today,
            MoneyTransaction.direction == 'out',
            MoneyTransaction.is_reversed == False,
            MoneyTransaction.status.in_(['approved', 'posted']),
        ).scalar()
    )

    revenue_today = _to_currency(room_revenue_today + sales_today_total)

    locked_bir_periods = int(
        db.query(PeriodLock)
        .filter(PeriodLock.scope == 'bir', PeriodLock.is_locked == True)
        .count() or 0
    )

    employee_count = int(db.query(Employee).count() or 0)
    labor_summary = {
        'employees': employee_count,
        'payroll_periods_pending': pending_payroll,
    }

    settings = load_system_settings(db)
    dashboard_role, widget_keys = get_effective_dashboard_widgets(db, user, settings=settings)
    widget_catalog = {row['key']: row for row in dashboard_widget_catalog()}

    widget_cards = []
    for key in widget_keys:
        info = widget_catalog.get(key) or {'label': key.replace('_', ' ').title(), 'description': ''}
        if key == 'arrivals_today':
            widget_cards.append(_metric_card(key, info['label'], arrivals_today, info.get('description', '')))
        elif key == 'departures_today':
            widget_cards.append(_metric_card(key, info['label'], departures_today, info.get('description', '')))
        elif key == 'in_house_guests':
            widget_cards.append(_metric_card(key, info['label'], in_house, info.get('description', '')))
        elif key == 'vip_arrivals_today':
            widget_cards.append(_metric_card(key, info['label'], vip_arrivals_today, info.get('description', '')))
        elif key == 'occupancy_rate':
            widget_cards.append(_metric_card(key, info['label'], occupancy_rate, info.get('description', '')))
        elif key == 'revenue_today':
            widget_cards.append(_metric_card(key, info['label'], revenue_today, info.get('description', '')))
        elif key == 'cash_in_today':
            widget_cards.append(_metric_card(key, info['label'], cash_in_today, info.get('description', '')))
        elif key == 'cash_out_today':
            widget_cards.append(_metric_card(key, info['label'], cash_out_today, info.get('description', '')))
        elif key == 'pending_approvals':
            widget_cards.append(_metric_card(key, info['label'], pending_approvals, info.get('description', '')))
        elif key == 'low_stock_count':
            widget_cards.append(_metric_card(key, info['label'], low_stock_count, info.get('description', '')))
        elif key == 'overdue_receivables':
            widget_cards.append(_metric_card(key, info['label'], receivables_overdue, info.get('description', '')))
        elif key == 'overdue_payables':
            widget_cards.append(_metric_card(key, info['label'], payables_overdue, info.get('description', '')))
        elif key == 'fnb_sales_today':
            widget_cards.append(_metric_card(key, info['label'], _to_currency(sales_today_total), info.get('description', '')))
        elif key == 'labor_summary':
            widget_cards.append(_metric_card(key, info['label'], labor_summary, info.get('description', '')))
        elif key == 'bir_status':
            widget_cards.append(_metric_card(key, info['label'], {'locked_periods': locked_bir_periods}, info.get('description', '')))
        elif key == 'top_channels':
            widget_cards.append(_table_card(key, info['label'], ['channel', 'booking_count', 'revenue'], top_channels, info.get('description', '')))
        elif key == 'low_stock_items':
            widget_cards.append(_table_card(key, info['label'], ['name', 'quantity_on_hand', 'reorder_level', 'unit'], [
                {
                    'name': row.name,
                    'quantity_on_hand': float(row.quantity_on_hand or 0),
                    'reorder_level': float(row.reorder_level or 0),
                    'unit': row.unit,
                }
                for row in sorted(low_stock_rows, key=lambda x: float(x.quantity_on_hand or 0))[:12]
            ], info.get('description', '')))
        elif key == 'pending_by_workflow':
            widget_cards.append(_table_card(
                key,
                info['label'],
                ['workflow', 'pending'],
                [{'workflow': workflow, 'pending': count} for workflow, count in pending_by_workflow.items()],
                info.get('description', ''),
            ))

    return {
        'income_total': float(income),
        'expense_total': float(expense),
        'net_income': round(float(income) - float(expense), 2),
        'inventory_value': round(inventory_value, 2),
        'low_stock_count': low_stock_count,
        'employees': employee_count,
        'payroll_periods': int(db.query(PayrollPeriod).count() or 0),
        'journal_entries': int(db.query(JournalEntry).count() or 0),
        'bookings': bookings_total,
        'bookings_confirmed': confirmed_bookings,
        'bookings_checked_in': in_house,
        'arrivals_today': arrivals_today,
        'departures_today': departures_today,
        'vip_arrivals_today': vip_arrivals_today,
        'cancelled_bookings': cancelled_bookings,
        'no_show_bookings': no_show_bookings,
        'open_folios': len(open_folios),
        'guest_balance_due': round(guest_balance_due, 2),
        'pending_approvals': pending_approvals,
        'cash_on_hand': _to_currency(cards.get('total_cash_on_hand')),
        'bank_balance': _to_currency(cards.get('total_bank_balance')),
        'receivables_due': _to_currency(cards.get('receivables_due')),
        'payables_due': _to_currency(cards.get('payables_due')),
        'unreconciled_accounts': int(cards.get('unreconciled_accounts') or 0),
        'variance_alerts': int(cards.get('variance_alerts') or 0),
        'receivables_overdue': receivables_overdue,
        'payables_overdue': payables_overdue,
        'fnb_sales_today': _to_currency(sales_today_total),
        'fnb_orders_today': len(sales_today_rows),
        'staff_meals_today': len(staff_meals_today_rows),
        'staff_meals_today_cost': _to_currency(staff_meals_today_cost),
        'top_channels': top_channels,
        'low_stock_items': [
            {
                'id': row.id,
                'name': row.name,
                'quantity_on_hand': float(row.quantity_on_hand or 0),
                'reorder_level': float(row.reorder_level or 0),
                'unit': row.unit,
            }
            for row in sorted(low_stock_rows, key=lambda x: float(x.quantity_on_hand or 0))[:12]
        ],
        'pending_by_workflow': pending_by_workflow,
        'in_house_guests': in_house,
        'occupancy_rate': occupancy_rate,
        'room_count_total': room_count_total,
        'room_revenue_today': room_revenue_today,
        'revenue_today': revenue_today,
        'cash_in_today': cash_in_today,
        'cash_out_today': cash_out_today,
        'labor_summary': labor_summary,
        'bir_status': {'locked_periods': locked_bir_periods},
        'dashboard_role': dashboard_role,
        'dashboard_widget_keys': widget_keys,
        'dashboard_widget_cards': widget_cards,
        'dashboard_widget_catalog': dashboard_widget_catalog(),
        'dashboard_allow_user_overrides': bool((settings.get('dashboard') or {}).get('allow_user_overrides', False)),
    }
