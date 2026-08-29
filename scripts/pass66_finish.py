from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{path}: expected {count} occurrence(s), found {found}: {old!r}')
    target.write_text(text.replace(old, new, count), encoding='utf-8')


def replace_in_function(path: str, function_name: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    marker = f'def {function_name}('
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f'{path}: function {function_name} not found')
    next_def = text.find('\ndef ', start + len(marker))
    end = len(text) if next_def < 0 else next_def + 1
    block = text[start:end]
    found = block.count(old)
    if found != count:
        raise SystemExit(f'{path}:{function_name}: expected {count} occurrence(s), found {found}: {old!r}')
    block = block.replace(old, new, count)
    target.write_text(text[:start] + block + text[end:], encoding='utf-8')


# Procurement: standalone PO creation can participate in caller-owned transactions.
replace_exact(
    'backend/app/services/procurement_service.py',
    'def create_purchase_order(db: Session, payload: PurchaseOrderCreate, username: str | None = None):',
    'def create_purchase_order(db: Session, payload: PurchaseOrderCreate, username: str | None = None, *, commit: bool = True):',
)

replace_in_function(
    'backend/app/services/procurement_service.py',
    'create_purchase_order',
    "    if payload.purchase_request_id and not db.get(PurchaseRequest, int(payload.purchase_request_id)):\n        raise ValueError('purchase_request_id not found.')\n",
    "    locked_pr = None\n    if payload.purchase_request_id:\n        locked_pr = (\n            db.query(PurchaseRequest)\n            .filter(PurchaseRequest.id == int(payload.purchase_request_id))\n            .populate_existing()\n            .with_for_update()\n            .first()\n        )\n        if not locked_pr:\n            raise ValueError('purchase_request_id not found.')\n        existing_po = (\n            db.query(PurchaseOrder)\n            .filter(PurchaseOrder.purchase_request_id == locked_pr.id)\n            .order_by(PurchaseOrder.id.asc())\n            .first()\n        )\n        if existing_po:\n            raise ValueError('Purchase request has already been converted to a purchase order.')\n",
)

replace_in_function(
    'backend/app/services/procurement_service.py',
    'create_purchase_order',
    "    db.commit()\n    row = (\n",
    "    db.flush()\n    if commit:\n        db.commit()\n    row = (\n",
)

# Serialize receiving state transitions before stock/payable effects.
for function_name in ('update_receiving_record', 'set_receiving_status'):
    replace_in_function(
        'backend/app/services/procurement_service.py',
        function_name,
        "    row = db.get(ReceivingRecord, int(receiving_id))\n",
        "    row = (\n        db.query(ReceivingRecord)\n        .filter(ReceivingRecord.id == int(receiving_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n    )\n",
    )

# Replace the final PR->PO conversion helper with a row-locked/idempotent outer transaction.
procurement_path = ROOT / 'backend/app/services/procurement_service.py'
text = procurement_path.read_text(encoding='utf-8')
marker = 'def create_purchase_order_from_request('
start = text.find(marker)
if start < 0:
    raise SystemExit('create_purchase_order_from_request not found')
new_tail = '''def create_purchase_order_from_request(db: Session, pr_id: int, username: str | None = None):
    pr = (
        db.query(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines))
        .filter(PurchaseRequest.id == int(pr_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not pr:
        raise ValueError('Purchase request not found.')

    if pr.status == 'converted_to_po':
        existing = (
            db.query(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.inventory_item),
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.purchase_request),
            )
            .filter(PurchaseOrder.purchase_request_id == pr.id)
            .order_by(PurchaseOrder.id.asc())
            .first()
        )
        if existing:
            return _serialize_po(existing)
        raise ValueError('Purchase request is marked converted but no purchase order exists.')

    if not (pr.lines or []):
        raise ValueError('Purchase request has no lines.')
    po_payload = PurchaseOrderCreate(
        po_date=pr.request_date,
        supplier_id=pr.supplier_id,
        purchase_request_id=pr.id,
        status='issued',
        payment_terms=pr.supplier.payment_terms if pr.supplier else None,
        expected_delivery_date=pr.needed_by_date,
        notes=f'Auto-created from {pr.request_no}',
        lines=[
            PurchaseOrderLineInput(
                purchase_request_line_id=line.id,
                inventory_item_id=line.inventory_item_id,
                description=line.description,
                quantity_ordered=float(line.quantity or 0),
                unit=line.unit,
                unit_cost=float(line.estimated_unit_cost or 0),
                notes=line.notes,
                sort_order=line.sort_order,
            )
            for line in sorted(pr.lines or [], key=lambda x: (x.sort_order, x.id))
        ],
    )
    po = create_purchase_order(db, po_payload, username=username, commit=False)
    db.commit()
    return po
'''
procurement_path.write_text(text[:start] + new_tail, encoding='utf-8')

# Payroll posting: lock the period before deciding whether a journal already exists.
replace_in_function(
    'backend/app/services/payroll_period_service.py',
    'post_payroll_period',
    "        .options(selectinload(PayrollPeriod.lines))\n        .filter(PayrollPeriod.id == int(period_id))\n        .first()\n",
    "        .options(selectinload(PayrollPeriod.lines))\n        .filter(PayrollPeriod.id == int(period_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n",
)

# Event workflow roots: serialize all state mutations that can touch financial links.
event_path = ROOT / 'backend/app/services/event_service.py'
event_text = event_path.read_text(encoding='utf-8')
helper_anchor = "def _event_query(db: Session):\n    return db.query(EventBooking).options(\n"
if helper_anchor not in event_text:
    raise SystemExit('event _event_query anchor not found')
# Add helper after _event_query block, before _line_total.
line_marker = '\n\ndef _line_total('
idx = event_text.find(line_marker)
if idx < 0:
    raise SystemExit('event _line_total marker not found')
if 'def _lock_event(' not in event_text:
    helper = '''\n\ndef _lock_event(db: Session, event_id: int):
    return (
        db.query(EventBooking)
        .filter(EventBooking.id == int(event_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
'''
    event_text = event_text[:idx] + helper + event_text[idx:]
    event_path.write_text(event_text, encoding='utf-8')

for function_name in ('update_event', 'confirm_event', 'complete_event', 'cancel_event', 'record_event_payment'):
    target = event_path
    text = target.read_text(encoding='utf-8')
    marker = f'def {function_name}('
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f'event function {function_name} not found')
    next_def = text.find('\ndef ', start + len(marker))
    end = len(text) if next_def < 0 else next_def + 1
    block = text[start:end]
    old = "    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()\n"
    if block.count(old) != 1:
        raise SystemExit(f'{function_name}: expected one initial event query, found {block.count(old)}')
    new = "    locked_event = _lock_event(db, event_id)\n    if not locked_event:\n        raise ValueError('Event not found.')\n    event = _event_query(db).filter(EventBooking.id == int(event_id)).first()\n"
    block = block.replace(old, new, 1)
    # Existing not-found check is now redundant but harmless; remove exactly once for clarity.
    redundant = "    if not event:\n        raise ValueError('Event not found.')\n"
    if redundant in block:
        block = block.replace(redundant, '', 1)
    target.write_text(text[:start] + block + text[end:], encoding='utf-8')

# Extend SQLite rollback/source-contract tests.
atomic_path = ROOT / 'backend/tests/test_transaction_atomicity_pass66.py'
atomic = atomic_path.read_text(encoding='utf-8')
atomic = atomic.replace(
    'from app.models.entities import EventPayment, FinancialAccount, JournalEntry, MoneyTransaction, Receivable\n',
    'from app.models.entities import (\n    EventPayment, FinancialAccount, InventoryItem, JournalEntry, MoneyTransaction,\n    Payable, PurchaseOrder, PurchaseRequest, StockMovement, Supplier, Receivable,\n)\n',
    1,
)
atomic = atomic.replace(
    'from app.services import event_service, procurement_service\n',
    'from app.services import event_service, procurement_service\nfrom app.schemas.procurement import (\n    ProcurementStatusAction, PurchaseRequestCreate, PurchaseRequestLineInput,\n    ReceivingCreate, ReceivingLineInput,\n)\n',
    1,
)
if 'def test_receiving_late_failure_rolls_back_stock_effects' not in atomic:
    atomic += '''\n\ndef test_receiving_late_failure_rolls_back_stock_effects(monkeypatch):
    db = make_session()
    item = InventoryItem(
        name='Pass66 rollback item', module_name='Inventory', category_name='Test',
        subcategory_name='Atomicity', unit='pc', quantity_on_hand=10,
        reorder_level=0, average_cost=5,
    )
    db.add(item)
    db.commit()

    receiving = procurement_service.create_receiving_record(
        db,
        ReceivingCreate(
            receiving_no='PASS66-RCV-ROLLBACK',
            receiving_date='2026-08-29',
            status='draft',
            lines=[ReceivingLineInput(
                inventory_item_id=item.id,
                description='rollback line',
                quantity_received=3,
                unit='pc',
                unit_cost=5,
            )],
        ),
        username='pass66',
    )

    def fail_after_stock(*args, **kwargs):
        raise RuntimeError('pass66 receiving late failure')

    monkeypatch.setattr(procurement_service, '_maybe_create_payable_from_receiving', fail_after_stock)
    with pytest.raises(RuntimeError, match='pass66 receiving late failure'):
        procurement_service.set_receiving_status(
            db,
            receiving['id'],
            ProcurementStatusAction(status='posted', auto_create_payable=True),
            username='pass66',
        )

    db.rollback()
    db.expire_all()
    refreshed_item = db.get(InventoryItem, item.id)
    refreshed_receiving = db.get(procurement_service.ReceivingRecord, receiving['id'])
    assert refreshed_receiving.status == 'draft'
    assert float(refreshed_item.quantity_on_hand or 0) == 10
    assert db.query(StockMovement).filter(StockMovement.receiving_record_id == receiving['id']).count() == 0
    assert db.query(Payable).filter(Payable.source_type == 'receiving', Payable.source_id == receiving['id']).count() == 0


def test_purchase_request_conversion_late_failure_rolls_back_po(monkeypatch):
    db = make_session()
    supplier = Supplier(name='Pass66 rollback supplier', code='P66-RB-SUP', is_active=True)
    db.add(supplier)
    db.commit()

    request = procurement_service.create_purchase_request(
        db,
        PurchaseRequestCreate(
            request_no='PASS66-PR-ROLLBACK',
            request_date='2026-08-29',
            supplier_id=supplier.id,
            status='approved',
            lines=[PurchaseRequestLineInput(
                description='rollback purchase', quantity=2, unit='pc', estimated_unit_cost=100,
            )],
        ),
        username='pass66',
    )

    original = procurement_service.create_purchase_order

    def create_then_fail(*args, **kwargs):
        kwargs['commit'] = False
        original(*args, **kwargs)
        raise RuntimeError('pass66 conversion late failure')

    monkeypatch.setattr(procurement_service, 'create_purchase_order', create_then_fail)
    with pytest.raises(RuntimeError, match='pass66 conversion late failure'):
        procurement_service.create_purchase_order_from_request(db, request['id'], username='pass66')

    db.rollback()
    db.expire_all()
    pr = db.get(PurchaseRequest, request['id'])
    assert pr.status == 'approved'
    assert db.query(PurchaseOrder).filter(PurchaseOrder.purchase_request_id == pr.id).count() == 0


def test_workflow_roots_are_locked_and_pr_conversion_is_non_committing():
    procurement_source = inspect.getsource(procurement_service.create_purchase_order_from_request)
    receiving_source = inspect.getsource(procurement_service.set_receiving_status)
    event_source = inspect.getsource(event_service.record_event_payment)

    assert '.with_for_update()' in procurement_source
    assert 'commit=False' in procurement_source
    assert '.with_for_update()' in receiving_source
    assert '_lock_event(' in event_source
'''
atomic_path.write_text(atomic, encoding='utf-8')

# Extend PostgreSQL concurrency coverage for PR conversion and payroll posting.
pg_path = ROOT / 'backend/tests/test_postgresql_transaction_concurrency.py'
pg = pg_path.read_text(encoding='utf-8')
pg = pg.replace(
    'from app.models.entities import FinancialAccount, MoneyTransaction, Receivable\n',
    'from app.models.entities import (\n    FinancialAccount, JournalEntry, MoneyTransaction, PayrollPeriod, PayrollPeriodLine,\n    PurchaseOrder, PurchaseRequest, PurchaseRequestLine, Receivable, Supplier,\n)\n',
    1,
)
pg = pg.replace(
    'from app.services.cashflow_service import (\n',
    'from app.services.cashflow_service import (\n',
    1,
)
if 'from app.services.payroll_period_service import post_payroll_period' not in pg:
    pg = pg.replace(
        ')\n\n\npytestmark',
        ')\nfrom app.services.payroll_period_service import post_payroll_period\nfrom app.services.procurement_service import create_purchase_order_from_request\n\n\npytestmark',
        1,
    )
if 'def test_postgresql_concurrent_pr_conversion_creates_one_po' not in pg:
    pg += '''\n\ndef test_postgresql_concurrent_pr_conversion_creates_one_po():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        supplier = Supplier(name=f'Pass66 supplier {marker}', code=f'P66S-{marker}', is_active=True)
        db.add(supplier)
        db.flush()
        pr = PurchaseRequest(
            request_no=f'P66PR-{marker}', request_date='2026-08-29', supplier_id=supplier.id,
            status='approved', requested_by='pass66-ci', approved_by='pass66-ci',
        )
        db.add(pr)
        db.flush()
        db.add(PurchaseRequestLine(
            purchase_request_id=pr.id, description='Concurrent conversion', quantity=2,
            unit='pc', estimated_unit_cost=100, sort_order=0,
        ))
        db.commit()
        pr_id = pr.id

    def convert():
        with SessionLocal() as db:
            try:
                return create_purchase_order_from_request(db, pr_id, username='pass66-ci')
            except Exception:
                db.rollback()
                raise

    results = _run_concurrently(convert, convert)
    assert [kind for kind, _ in results].count('ok') == 2
    ids = {value['id'] for kind, value in results if kind == 'ok'}
    assert len(ids) == 1

    with SessionLocal() as db:
        pr = db.get(PurchaseRequest, pr_id)
        assert pr.status == 'converted_to_po'
        assert db.query(PurchaseOrder).filter(PurchaseOrder.purchase_request_id == pr_id).count() == 1


def test_postgresql_concurrent_payroll_posting_creates_one_journal():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        period = PayrollPeriod(
            name=f'Pass66 payroll {marker}', period_start='2026-08-01', period_end='2026-08-15',
            release_date='2026-08-16', status='reviewed', source_type='manual',
        )
        db.add(period)
        db.flush()
        db.add(PayrollPeriodLine(
            payroll_period_id=period.id, employee_name='Pass66 Employee', department='Test',
            gross_pay=1000, net_pay=900, deductions=100, employer_contribution=50,
        ))
        db.commit()
        period_id = period.id

    def post():
        with SessionLocal() as db:
            try:
                return post_payroll_period(db, period_id, username='pass66-ci', post_date='2026-08-29')
            except Exception:
                db.rollback()
                raise

    results = _run_concurrently(post, post)
    assert [kind for kind, _ in results].count('ok') == 2
    journal_ids = {value['journal']['id'] for kind, value in results if kind == 'ok'}
    assert len(journal_ids) == 1

    with SessionLocal() as db:
        period = db.get(PayrollPeriod, period_id)
        assert period.status == 'posted'
        assert period.generated_journal_entry_id in journal_ids
        assert db.query(JournalEntry).filter(JournalEntry.reference_no == f'PPR-{period_id}').count() == 1
'''
pg_path.write_text(pg, encoding='utf-8')

# Permanent source guard: composed workflows must not regress to premature commits.
guard_path = ROOT / 'backend/tests/test_transaction_boundaries_pass66.py'
if not guard_path.exists():
    guard_path.write_text('''from __future__ import annotations\n\nimport inspect\n\nfrom app.services import event_service, payroll_period_service, procurement_service\nfrom app.services import cashflow_service\n\n\ndef test_pass66_composite_transaction_contracts():\n    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_money_transaction)\n    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_receivable)\n    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_payable)\n    assert 'commit: bool = True' in inspect.getsource(procurement_service.create_purchase_order)\n    assert 'commit=False' in inspect.getsource(procurement_service.create_purchase_order_from_request)\n    assert '.with_for_update()' in inspect.getsource(procurement_service.create_purchase_order_from_request)\n    assert '.with_for_update()' in inspect.getsource(procurement_service.set_receiving_status)\n    assert '.with_for_update()' in inspect.getsource(payroll_period_service.post_payroll_period)\n    assert '_lock_event(' in inspect.getsource(event_service.record_event_payment)\n    assert 'commit=False' in inspect.getsource(event_service.record_event_payment)\n''', encoding='utf-8')

print('Pass 66 workflow-root atomicity/concurrency closure applied.')
