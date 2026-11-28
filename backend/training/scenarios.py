"""Disposable real Accounting schemas and read-only evidence checks.

Only fixture preparation writes initial state. Completion re-reads the same
source models changed by the actual Accounting handlers; clicks never grant a pass.
"""
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.business_clock import business_today
from app.db.database import Base
import app.models
from app.models.entities import (
    AccountTransfer, Asset, AssetDepreciationLog, AssetDisposalLog, AssetMaintenanceLog,
    BIRBookEntry, Booking, BookingFolio, BookingFolioLine, CashReconciliation,
    ChartAccount, FinancialAccount, IntegrationReviewItem, JournalEntry, JournalLine,
    MoneyTransaction, Payable, PeriodLock, Receivable, Record, RecordSettlement, User,
)
from app.schemas.cashflow import AccountTransferCreate, MoneyTransactionCreate
from app.schemas.common import AssetDisposalCreate, JournalEntryCreate
from app.services.cashflow_service import create_money_transaction, create_transfer, ensure_default_financial_accounts
from app.services.permission_service import ensure_permissions_seed
from training.curriculum import VERSION

IDS = dict(actor=1, cash=101, bank=102, tx=201, transfer=201, ar=301, ap=401,
           folio=501, line=601, asset=701, journal=801, review=901)
FIXTURE_ACTOR = SimpleNamespace(username='practice_fixture',role='owner')

def engine_for(path: Path):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink() or path.parent.name != 'accounting-training':
        raise ValueError('Practice must use a file inside its dedicated training directory.')
    if not re.fullmatch(r'attempt-[a-f0-9-]{36}\.sqlite',path.name):
        raise ValueError('Invalid practice file identity.')
    marker=path.parent/'training-only.json'
    if not marker.is_file() or json.loads(marker.read_text()).get('application')!='hidden-oasis-accounting-training':
        raise ValueError('Practice requires a marked Accounting Training directory.')
    return create_engine('sqlite:///'+str(path.resolve()), connect_args={'check_same_thread':False}, future=True)

def values(lesson, mode='guided'):
    amount={'guided':250,'assisted':375,'independent':480}[mode]
    today=business_today()
    return {**IDS, 'amount':amount, 'due':800, 'excess':1200+amount,
        'cash_opening':5000, 'bank_opening':10000, 'excess_cash':7000+amount,
        'counted':5000-{'guided':20,'assisted':35,'independent':50}[mode],
        'counterparty':{'guided':'Practice Acacia Company','assisted':'Practice Narra Group','independent':'Practice Mahogany Events'}[mode],
        'reference':'TRN-'+lesson.id.upper()+'-'+mode.upper(), 'date':today,
        'period':today[:7], 'remaining':10, 'excess_depreciation':30,
        'asset_name':'Practice equipment · '+mode, 'asset_cost':12000+amount, 'salvage':1200,
        'outstanding':800-amount}

def _format(value, data):
    return value.format(**data) if isinstance(value,str) else value

def practical_question(lesson, mode):
    data=values(lesson,mode)
    choices={
        'read-account-position':('How many pesos does Practice Cash hold?',5000),
        'find-before-retry':('What amount is saved on the original practice receipt?',data['amount']),
        'read-close-control':('What actual counted amount is retained in the closed practice reconciliation?',5000),
        'read-settled-folio':('What is the settled practice folio balance?',0),
        'read-trial-balance':('What is the trial balance debit total in this practice?',data['amount']),
        'read-profit':('What is the posted practice revenue total?',data['amount']),
        'read-aging':('What is the outstanding amount on the approved practice credit Record?',data['outstanding']),
        'read-asset-history':('How much depreciation has already been recorded on the practice asset?',80),
        'read-inbox':('Has the practice proposal been accepted? yes or no','no'),
        'read-bir':('How many source Record entries are in the generated practice book?',1),
    }
    prompt,answer=choices.get(lesson.id,('', ''))
    return prompt,str(answer),'Open the actual practice record and read the value; do not infer it from an unrelated balance.'

def inspection_endpoint(lesson, db=None):
    return {
        'read-account-position':'/api/cashflow/summary', 'find-before-retry':'/api/cashflow/ledger',
        'read-close-control':'/api/cashflow/ledger', 'read-settled-folio':'/api/room-folios/501',
        'read-trial-balance':'/api/reports/financial-statements', 'read-profit':'/api/reports/financial-statements',
        'read-aging':'/api/reports/ar-ap-aging', 'read-asset-history':'/api/asset-registry/depreciation-logs',
        'read-inbox':'/api/integration-review/page', 'read-bir':'/api/bir/books',
    }.get(lesson.id)

def public_lesson(lesson, mode='guided'):
    data=values(lesson,mode)
    result=asdict(lesson)
    result.pop('answer',None)
    for key in ('route','situation','concept','example','rule','question','correction'):
        result[key]=_format(result[key],data)
    result['steps']=[{key:_format(value,data) for key,value in asdict(step).items()} for step in lesson.steps]
    result.update(reference=data['reference'], practical_question=practical_question(lesson,mode)[0],
        inspection_route=result['route'], inspection_api_path=inspection_endpoint(lesson),
        curriculum_version=VERSION, practice_file_name=None)
    return result

def _fingerprint(db):
    result={}
    for model in (FinancialAccount, MoneyTransaction, AccountTransfer, Receivable, Payable, Booking,
        BookingFolio, BookingFolioLine, CashReconciliation, Asset, AssetDepreciationLog,
        AssetDisposalLog, AssetMaintenanceLog, Record, RecordSettlement, JournalEntry, JournalLine,
        IntegrationReviewItem, BIRBookEntry, PeriodLock):
        result[model.__tablename__]=[
            {column.name:str(getattr(row,column.name)) for column in model.__table__.columns}
            for row in db.query(model).order_by(model.id).all()]
    return hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()

def _baseline(db):
    return json.loads(db.execute(text('SELECT payload FROM training_baseline')).scalar_one())

def read_only_unchanged(db, actor=None):
    return _fingerprint(db)==_baseline(db)['fingerprint']

def _journal(db, data, *, draft=False):
    row=JournalEntry(id=IDS['journal'],entry_date=data['date'],reference_no=data['reference'],
        description='Fictional approved practice entry',source_module='finance',
        status='draft' if draft else 'posted',posted_by=None if draft else FIXTURE_ACTOR.username)
    db.add(row);db.flush()
    db.add_all([JournalLine(journal_entry_id=row.id,account_code='1000',account_name='Cash on Hand',debit=data['amount'],credit=0),
                JournalLine(journal_entry_id=row.id,account_code='4000',account_name='Practice Revenue',debit=0,credit=data['amount'])])
    db.commit()
    return row


def prepare(path, lesson, role, mode):
    if Path(path).exists():raise ValueError('A fresh practice file is required; existing learner evidence is never overwritten.')
    engine=engine_for(path)
    Base.metadata.create_all(engine)
    data=values(lesson,mode)
    with Session(engine) as db:
        db.add(User(id=IDS['actor'],username='training_actor',full_name='Practice employee',hashed_password='!training-no-password-login',role=role,is_active=True))
        db.add_all([FinancialAccount(id=IDS['cash'],name='Practice Cash',code='TRAIN-CASH',account_type='cash_drawer',
                    opening_balance=5000,current_balance=5000,requires_physical_count=True,requires_daily_reconciliation=True,reconciliation_mode='daily'),
                    FinancialAccount(id=IDS['bank'],name='Practice Bank',code='TRAIN-BANK',account_type='bank',
                    opening_balance=10000,current_balance=10000,requires_physical_count=False,requires_daily_reconciliation=False,reconciliation_mode='manual')])
        for code,name,kind in [('1000','Cash on Hand','asset'),('1020','Bank','asset'),('1100','Accounts Receivable','asset'),
            ('2000','Accounts Payable','liability'),('4000','Practice Revenue','income'),('5000','Operating Expense','expense'),
            ('1500','Property and Equipment','asset'),('1590','Accumulated Depreciation','asset'),('5110','Depreciation Expense','expense')]:
            db.add(ChartAccount(code=code,name=name,account_type=kind,is_active=True))
        db.commit();ensure_default_financial_accounts(db);ensure_permissions_seed(db)
        id=lesson.id
        if id in {'reverse-receipt','find-before-retry'}:
            tx=create_money_transaction(db,MoneyTransactionCreate(direction='in',financial_account_id=IDS['cash'],amount=data['amount'],
                transaction_date=data['date'],reference_no=data['reference'],category='Practice receipt',counterparty_name=data['counterparty']),username=FIXTURE_ACTOR.username)
            # The source assigns the next database ID; all exposed values use the
            # stable seeded identity rather than assuming an autoincrement value.
            row=db.get(MoneyTransaction,tx['id']); row.id=IDS['tx'];db.commit()
        if id=='reverse-transfer':
            result=create_transfer(db,AccountTransferCreate(from_account_id=IDS['cash'],to_account_id=IDS['bank'],amount=data['amount'],reference_no=data['reference']),username=FIXTURE_ACTOR.username)
            row=db.get(AccountTransfer,result['id']);row.id=IDS['transfer'];db.commit()
        if id in {'collect-receivable','refuse-overcollection'}:
            db.add(Receivable(id=IDS['ar'],counterparty_name=data['counterparty'],gross_amount=data['due'],amount_collected=0,
                balance_due=data['due'],status='open',transaction_date=data['date'],due_date=data['date'],receivable_type='guest_balance'))
        if id in {'pay-payable','refuse-overpayment'}:
            db.add(Payable(id=IDS['ap'],supplier_name=data['counterparty'],gross_amount=data['due'],amount_paid=0,
                balance_due=data['due'],status='open',bill_date=data['date'],due_date=data['date'],payable_type='supplier_bill'))
        if id=='read-close-control':
            db.add(CashReconciliation(financial_account_id=IDS['cash'],reconciliation_date=data['date'],shift_name='day',
                opening_balance=5000,expected_closing=5000,actual_counted=5000,variance=0,status='closed',locked_at=data['date'],closed_at=data['date']))
        if lesson.module=='H':
            booking=Booking(guest_name='Practice guest · '+mode,status='confirmed',check_in=data['date'],
                check_out=(date.fromisoformat(data['date'])+timedelta(days=1)).isoformat(),gross_amount=1000,deposit_amount=1000)
            db.add(booking);db.flush()
            folio=BookingFolio(id=IDS['folio'],booking_id=booking.id,folio_no=data['reference'],status='settled' if id=='read-settled-folio' else 'open')
            db.add(folio);db.flush()
            if id!='folio-charge':
                db.add_all([BookingFolioLine(id=IDS['line'],folio_id=folio.id,line_type='room_charge',description='Practice room charge',amount=1000),
                            BookingFolioLine(folio_id=folio.id,line_type='payment',description='Practice payment evidence',amount=1000)])
        if lesson.module=='K' and id!='create-asset':
            db.add(Asset(id=IDS['asset'],name=data['asset_name'],acquisition_cost=100,useful_life_months=3,salvage_value=10))
            db.flush()
            if id in {'depreciation-cap','refuse-excess-depreciation','read-asset-history'}:
                db.add(AssetDepreciationLog(asset_id=IDS['asset'],period_key='2025-01',depreciation_date='2025-01-31',amount=80))
        db.commit()
        if id=='refuse-repeat-disposal':
            from app.api.asset_registry import dispose_asset
            dispose_asset(IDS['asset'],AssetDisposalCreate(disposal_date=data['date'],proceeds_amount=data['amount'],auto_post_accounting=True),db=db,user=FIXTURE_ACTOR)
        if id in {'post-reviewed-journal','reverse-journal','locked-period','read-trial-balance','read-profit'}:
            journal=_journal(db,data,draft=id in {'post-reviewed-journal','locked-period'})
            # JournalLine FKs must retain the real source-generated ID.
            data['journal']=journal.id
        if id=='locked-period':
            db.add(PeriodLock(period_key=data['period'],scope='bir',is_locked=True))
        if id=='read-aging':
            row=Record(module_slug='rooms',module_name='Rooms',category='Training',bucket='Training',item='Practice invoice',
                name=data['reference'],counterparty=data['counterparty'],amount=data['due'],direction='income',payment_method='on_account',
                workflow_status='approved',transaction_date=data['date'],due_date=data['date'])
            db.add(row);db.flush();db.add(RecordSettlement(record_id=row.id,settlement_date=data['date'],amount=data['amount']))
        if id=='read-inbox':
            db.add(IntegrationReviewItem(id=IDS['review'],source_app='pos',source_event_id=data['reference'],source_revision=1,
                source_entity_type='cash_receipt',financial_effect='cash_in',amount=data['amount'],currency='PHP',
                proposed_account_id=IDS['cash'],payload_json=json.dumps({'title':'Practice receipt proposal','reference_no':data['reference']}),
                status='ready_for_review',idempotency_key=data['reference']))
        if id=='read-bir':
            row=Record(module_slug='rooms',module_name='Rooms',category='Training',bucket='Training',item='Practice book record',
                name=data['reference'],document_ref=data['reference'],amount=data['amount'],direction='income',payment_method='cash',
                workflow_status='approved',bir_status='posted_to_bir',transaction_date=data['date'])
            db.add(row);db.commit()
            from app.services.bir_service import generate_books
            generate_books(db,data['period'])
        db.commit()
        engine_payload={**data,'fingerprint':_fingerprint(db)}
        db.execute(text('CREATE TABLE training_baseline (payload TEXT NOT NULL)'))
        db.execute(text('INSERT INTO training_baseline(payload) VALUES (:payload)'),{'payload':json.dumps(engine_payload)})
        db.commit()
    engine.dispose()
    if os.name=='posix':Path(path).chmod(0o600)

def resolve_practice_route(db, lesson, mode):
    return _format(lesson.route,_baseline(db))

def recover_checkpoint(db, lesson, mode, checkpoint, actions):
    # Uncommitted forms reopen from their first action; saved form drafts are
    # restored in the browser. Actual successful source actions skip only their
    # already-saved segment. The database verifier remains authoritative.
    actual=public_lesson(lesson,mode)['steps']
    for index,step in reversed(list(enumerate(actual))):
        if step['outcome'] and any(row['path'].rstrip('/')==('/api'+step['outcome']).rstrip('/')
            and (row['status']==step['outcome_status'] if step['outcome_status'] else 200<=row['status']<300) for row in actions):
            return index+1
    return 0

def verify(db, lesson, mode, actions=()):
    data=_baseline(db)
    id=lesson.id
    def amount(value):return Decimal(str(value or 0)).quantize(Decimal('.0001'))
    def eq(value,expected):return amount(value)==amount(expected)
    cash=db.get(FinancialAccount,IDS['cash']);bank=db.get(FinancialAccount,IDS['bank'])
    result=False
    refusal=next((step for step in lesson.steps if step.outcome_status),None)
    if refusal:
        endpoint='/api'+_format(refusal.outcome,data)
        reasons={
            'refuse-overdraw':'Insufficient account balance',
            'cashier-authority':'cashflow.money_out',
            'refuse-overcollection':'Collection amount cannot exceed receivable balance',
            'refuse-overpayment':'Payment amount cannot exceed payable balance',
            'refuse-excess-depreciation':'exceeds the remaining depreciable value',
            'refuse-repeat-disposal':'Asset has already been disposed',
            'locked-period':'is locked',
        }
        event=any(row['path'].rstrip('/')==endpoint.rstrip('/') and row['method']==(refusal.outcome_method or 'POST')
            and row['status']==refusal.outcome_status and reasons[id] in row.get('detail','') for row in actions)
        result=event and read_only_unchanged(db)
    elif id in {'receipt','receipt-with-journal','payment'}:
        rows=db.query(MoneyTransaction).filter_by(reference_no=data['reference']).all()
        direction='out' if id=='payment' else 'in'
        expected=5000+(-1 if direction=='out' else 1)*data['amount']
        result=len(rows)==1 and eq(rows[0].amount,data['amount']) and rows[0].direction==direction and rows[0].financial_account_id==IDS['cash'] and rows[0].created_by=='training_actor' and rows[0].status=='posted' and eq(cash.current_balance,expected)
        if id=='receipt-with-journal' and result:
            journal=db.get(JournalEntry,rows[0].journal_entry_id) if rows[0].journal_entry_id else None
            result=bool(journal and journal.status=='posted' and len(journal.lines)>=2 and eq(sum(line.debit for line in journal.lines),data['amount']) and eq(sum(line.credit for line in journal.lines),data['amount']))
    elif id=='reverse-receipt':
        original=db.get(MoneyTransaction,IDS['tx'])
        reversals=db.query(MoneyTransaction).filter_by(reversed_from_id=IDS['tx']).all()
        result=original.is_reversed and len(reversals)==1 and eq(cash.current_balance,5000) and eq(reversals[0].amount,data['amount'])
    elif id=='transfer':
        rows=db.query(AccountTransfer).filter_by(reference_no=data['reference']).all()
        result=len(rows)==1 and rows[0].from_account_id==IDS['cash'] and rows[0].to_account_id==IDS['bank'] and eq(rows[0].amount,data['amount']) and eq(cash.current_balance,5000-data['amount']) and eq(bank.current_balance,10000+data['amount'])
    elif id=='reverse-transfer':
        original=db.get(AccountTransfer,IDS['transfer'])
        result=original.is_reversed and eq(cash.current_balance,5000) and eq(bank.current_balance,10000)
    elif id=='create-receivable':
        rows=db.query(Receivable).filter_by(counterparty_name=data['counterparty']).all()
        result=len(rows)==1 and eq(rows[0].gross_amount,data['due']) and eq(rows[0].balance_due,data['due']) and eq(rows[0].amount_collected,0) and eq(cash.current_balance,5000)
    elif id=='collect-receivable':
        row=db.get(Receivable,IDS['ar'])
        payments=db.query(MoneyTransaction).filter_by(receivable_id=row.id,reference_no=data['reference']).all()
        result=len(payments)==1 and eq(row.amount_collected,data['amount']) and eq(row.balance_due,data['outstanding']) and eq(cash.current_balance,5000+data['amount'])
    elif id=='create-payable':
        rows=db.query(Payable).filter_by(supplier_name=data['counterparty']).all()
        result=len(rows)==1 and eq(rows[0].gross_amount,data['due']) and eq(rows[0].balance_due,data['due']) and eq(rows[0].amount_paid,0) and eq(cash.current_balance,5000)
    elif id=='pay-payable':
        row=db.get(Payable,IDS['ap'])
        payments=db.query(MoneyTransaction).filter_by(payable_id=row.id,reference_no=data['reference']).all()
        result=len(payments)==1 and eq(row.amount_paid,data['amount']) and eq(row.balance_due,data['outstanding']) and eq(cash.current_balance,5000-data['amount'])
    elif id=='count-cash':
        rows=db.query(CashReconciliation).filter_by(financial_account_id=IDS['cash'],reconciliation_date=data['date']).all()
        result=len(rows)==1 and eq(rows[0].actual_counted,data['counted']) and eq(rows[0].expected_closing,5000) and eq(rows[0].variance,data['counted']-5000) and rows[0].notes=='Practice recount shows a documented shortage.' and eq(cash.current_balance,5000)
    elif id=='folio-charge':
        rows=db.query(BookingFolioLine).filter_by(folio_id=IDS['folio'],reference_no=data['reference']).all()
        result=len(rows)==1 and rows[0].line_type=='minibar' and eq(rows[0].amount,data['amount']) and rows[0].created_by=='training_actor' and eq(cash.current_balance,5000)
    elif id=='settle-folio':
        from app.services.guest_service import folio_balance_summary
        folio=db.get(BookingFolio,IDS['folio'])
        result=folio.status=='settled' and eq(folio_balance_summary(folio)['balance'],0) and db.query(BookingFolioLine).count()==2
    elif id=='post-reviewed-journal':
        row=db.get(JournalEntry,data['journal']);result=row.status=='posted' and row.posted_by=='training_actor' and db.query(JournalEntry).count()==1
    elif id=='reverse-journal':
        row=db.get(JournalEntry,data['journal']);reversals=db.query(JournalEntry).filter_by(reversed_from_id=row.id).all()
        result=row.is_reversed and len(reversals)==1 and reversals[0].status=='posted' and reversals[0].posted_by=='training_actor'
    elif id=='create-asset':
        rows=db.query(Asset).filter_by(name=data['asset_name']).all()
        result=len(rows)==1 and eq(rows[0].acquisition_cost,data['asset_cost']) and eq(rows[0].salvage_value,data['salvage']) and rows[0].useful_life_months==12 and db.query(JournalEntry).count()==0
    elif id=='depreciation-cap':
        rows=db.query(AssetDepreciationLog).filter_by(asset_id=IDS['asset'],period_key=data['period']).all()
        total=sum(amount(row.amount) for row in db.query(AssetDepreciationLog).filter_by(asset_id=IDS['asset']))
        result=len(rows)==1 and eq(rows[0].amount,10) and rows[0].record_id is not None and eq(total,90) and db.query(JournalEntry).count()==1
    elif id=='dispose-asset':
        rows=db.query(AssetDisposalLog).filter_by(asset_id=IDS['asset']).all()
        result=len(rows)==1 and eq(rows[0].proceeds_amount,data['amount']) and rows[0].income_record_id is not None and db.get(Asset,IDS['asset']).operational_status=='Disposed' and db.query(JournalEntry).count()==1
    evidence={'source_verified':bool(result),'reference':data['reference'],'curriculum_version':VERSION,
              'critical_pass':bool(result),'practical_score':100 if result else 0}
    if not result:evidence['correction']='The saved source evidence does not yet match the practice document. Check the account, amount, reference and status. Use Reset this practice if an incorrect posting was saved; your earlier attempt stays in history.'
    return bool(result),evidence

def practice_csv(*args):return None
