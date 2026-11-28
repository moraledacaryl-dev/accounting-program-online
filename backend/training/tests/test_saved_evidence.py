import pytest
from training.curriculum import LESSONS, BY_ID
from training.scenarios import values,practical_question,inspection_endpoint
from conftest import start

def perform(client,lesson,mode='guided',wrong=False):
    v=values(lesson,mode);id=lesson.id
    client.headers['idempotency-key']=v['reference']
    paid=v['amount']+1 if wrong else v['amount']
    if id in {'receipt','receipt-with-journal','payment','refuse-overdraw','cashier-authority'}:
        return client.post('/api/cashflow/transactions',json={'direction':'out' if id in {'payment','refuse-overdraw','cashier-authority'} else 'in',
            'financial_account_id':v['cash'],'amount':v['excess_cash'] if id=='refuse-overdraw' else paid,
            'transaction_date':v['date'],'reference_no':v['reference'],'counterparty_name':v['counterparty'],
            'payment_method':'cash','auto_post_accounting':id=='receipt-with-journal','status':'posted'})
    if id=='reverse-receipt':return client.post(f"/api/cashflow/transactions/{v['tx']}/reverse",json={'reason':'Fictional correction','action_date':v['date']})
    if id=='transfer':return client.post('/api/transfers/',json={'from_account_id':v['cash'],'to_account_id':v['bank'],'amount':paid,'reference_no':v['reference'],'transfer_date':v['date']})
    if id=='reverse-transfer':return client.post(f"/api/transfers/{v['transfer']}/reverse",json={'reason':'Fictional correction','action_date':v['date']})
    if id=='create-receivable':return client.post('/api/receivables/',json={'counterparty_name':v['counterparty'],'gross_amount':v['due'],'transaction_date':v['date']})
    if id in {'collect-receivable','refuse-overcollection'}:return client.post(f"/api/receivables/{v['ar']}/collect",json={'amount':v['excess'] if id.startswith('refuse') else paid,'financial_account_id':v['cash'],'reference_no':v['reference'],'collection_date':v['date']})
    if id=='create-payable':return client.post('/api/payables/',json={'supplier_name':v['counterparty'],'gross_amount':v['due'],'bill_date':v['date']})
    if id in {'pay-payable','refuse-overpayment'}:return client.post(f"/api/payables/{v['ap']}/pay",json={'amount':v['excess'] if id.startswith('refuse') else paid,'financial_account_id':v['cash'],'reference_no':v['reference'],'payment_date':v['date']})
    if id=='count-cash':return client.post('/api/reconciliations/',json={'financial_account_id':v['cash'],'reconciliation_date':v['date'],'actual_counted':v['counted'],'status':'counted','notes':'Practice recount shows a documented shortage.'})
    if id=='folio-charge':return client.post(f"/api/room-folios/{v['folio']}/lines",json={'line_type':'minibar','description':'Practice minibar charge','amount':paid,'reference_no':v['reference'],'transaction_date':v['date']})
    if id=='settle-folio':return client.post(f"/api/room-folios/{v['folio']}/settle",json={'tolerance':.01})
    if id in {'post-reviewed-journal','locked-period'}:return client.post(f"/api/journals/entries/{v['journal']}/post")
    if id=='reverse-journal':return client.post(f"/api/journals/entries/{v['journal']}/reverse")
    if id=='create-asset':return client.post('/api/asset-registry/assets',json={'name':v['asset_name'],'acquisition_cost':v['asset_cost'],'salvage_value':v['salvage'],'useful_life_months':12})
    if id in {'depreciation-cap','refuse-excess-depreciation'}:return client.post(f"/api/asset-registry/assets/{v['asset']}/depreciate",json={'period_key':v['period'],'amount':v['excess_depreciation'] if id.startswith('refuse') else None,'auto_post_accounting':True})
    if id in {'dispose-asset','refuse-repeat-disposal'}:return client.post(f"/api/asset-registry/assets/{v['asset']}/dispose",json={'proceeds_amount':paid,'auto_post_accounting':True,'disposal_date':v['date']})
    raise AssertionError('Missing real workflow execution for '+id)

@pytest.mark.parametrize('mode',['guided','assisted','independent'])
@pytest.mark.parametrize('lesson',LESSONS,ids=lambda row:row.id)
def test_every_lesson_needs_actual_source_evidence(learner,lesson,mode):
    start(learner,lesson,mode=mode)
    answer={'answer':lesson.answer,'observation':practical_question(lesson,mode)[1]}
    empty=learner.post('/api/training/check',json=answer)
    assert empty.status_code==200,empty.text
    assert not empty.json()['passed'],'A knowledge answer alone must not pass a practical lesson'
    if lesson.workflow.startswith('read_'):
        response=learner.get(inspection_endpoint(lesson))
    else:
        response=perform(learner,lesson,mode)
    refusal=next((step for step in lesson.steps if step.outcome_status),None)
    assert response.status_code==(refusal.outcome_status if refusal else 200),response.text
    checked=learner.post('/api/training/check',json=answer)
    assert checked.status_code==200,checked.text
    assert checked.json()['passed'],checked.json()

@pytest.mark.parametrize('id',['receipt','receipt-with-journal','payment','transfer','collect-receivable','pay-payable','folio-charge','dispose-asset'])
def test_matching_clicks_with_wrong_saved_amount_do_not_pass(learner,id):
    lesson=BY_ID[id];start(learner,lesson)
    response=perform(learner,lesson,wrong=True)
    assert response.status_code==200,response.text
    result=learner.post('/api/training/check',json={'answer':lesson.answer})
    assert not result.json()['passed']

def test_a_passed_attempt_is_preserved_against_further_business_edits(learner):
    lesson=BY_ID['receipt'];start(learner,lesson)
    assert perform(learner,lesson).status_code==200
    assert learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']
    assert perform(learner,lesson).status_code==409

def test_old_attempt_header_cannot_write_to_new_practice(learner):
    lesson=BY_ID['receipt'];first=start(learner,lesson)
    current=learner.post('/api/training/start',json={'lesson_id':lesson.id}).json()
    assert first['attempt_id']!=current['attempt_id']
    assert perform(learner,lesson).status_code==409

def test_trainer_roster_requires_private_key_even_for_owner_practice(learner):
    start(learner,BY_ID['receipt'],role='owner')
    assert learner.get('/api/training/management').status_code==403

def test_wrong_origin_cannot_save_training_work(learner):
    start(learner,BY_ID['receipt'])
    learner.headers['origin']='https://accounting.hiddenoasis.app'
    assert perform(learner,BY_ID['receipt']).status_code==403

def test_live_connections_and_integration_intake_have_no_training_transport(learner):
    start(learner,BY_ID['receipt'])
    assert learner.post('/api/integrations/beds24/sync/recent',json={}).status_code==403
    assert learner.post('/api/integration/transactions',json={}).status_code==403

def test_independent_guidance_prevents_an_independent_pass(learner):
    lesson=BY_ID['receipt'];start(learner,lesson,mode='independent')
    assert learner.post('/api/training/hint').status_code==200
    assert perform(learner,lesson).status_code==200
    assert not learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']

def test_guided_then_assisted_prerequisites_cannot_be_skipped(learner):
    learner.post('/api/training/enrol',json={'name':'New employee','role':'cashier'})
    assert learner.post('/api/training/start',json={'lesson_id':'receipt','mode':'independent'}).status_code==409
    assert learner.post('/api/training/start',json={'lesson_id':'receipt','mode':'assisted'}).status_code==409

def test_learner_report_excludes_private_runtime_keys(learner):
    start(learner,BY_ID['receipt'])
    response=learner.get('/api/training/report')
    assert response.status_code==200
    assert 'session-key' not in response.text and 'manager-key' not in response.text

def test_a_security_error_is_not_mistaken_for_a_business_refusal(learner):
    lesson=BY_ID['cashier-authority'];start(learner,lesson)
    learner.headers['x-csrf-token']='wrong'
    assert perform(learner,lesson).status_code==403
    result=learner.post('/api/training/check',json={'answer':lesson.answer})
    assert not result.json()['passed']
