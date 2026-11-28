"""Incorrect counterparties and unrecorded guidance must never earn a pass."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from conftest import start
from training.curriculum import BY_ID
from training.scenarios import values
from test_saved_evidence import perform

@pytest.mark.parametrize('mode',['guided','assisted','independent'])
@pytest.mark.parametrize('lesson_id',['receipt','receipt-with-journal','payment'])
def test_wrong_counterparty_cannot_pass(learner,lesson_id,mode):
    lesson=BY_ID[lesson_id];start(learner,lesson,mode=mode);v=values(lesson,mode)
    saved=learner.post('/api/cashflow/transactions',json={
        'direction':'out' if lesson_id=='payment' else 'in','financial_account_id':v['cash'],
        'amount':v['amount'],'transaction_date':v['date'],'reference_no':v['reference'],
        'counterparty_name':'Wrong fictional counterparty','status':'posted',
        'auto_post_accounting':lesson_id=='receipt-with-journal'})
    assert saved.status_code==200,saved.text
    checked=learner.post('/api/training/check',json={'answer':lesson.answer})
    assert not checked.json()['passed'],checked.json()

@pytest.mark.parametrize('mode',['assisted','independent'])
def test_guidance_is_only_returned_after_recorded_hint(learner,mode):
    prepared=start(learner,BY_ID['receipt'],mode=mode)
    assert prepared['lesson']['steps']==[]
    before=learner.get('/api/training/me').json()
    assert before['lesson']['steps']==[] and before['attempt']['hints']==0
    catalogue=learner.get('/api/training/catalogue').json()
    assert all(row['steps']==[] for row in catalogue['lessons'])
    assert learner.post('/api/training/checkpoint',json={'step':1}).status_code==403
    hint=learner.post('/api/training/hint')
    assert hint.status_code==200 and hint.json()['lesson']['steps']
    after=learner.get('/api/training/me').json()
    assert after['attempt']['hints']==1 and after['lesson']['steps']
    assert learner.post('/api/training/checkpoint',json={'step':1}).status_code==200

def test_guided_practice_keeps_its_walkthrough(learner):
    result=start(learner,BY_ID['receipt'])
    assert result['lesson']['steps'] and learner.get('/api/training/me').json()['lesson']['steps']

def test_name_matching_accepts_case_and_spacing_but_rejects_blank(learner):
    lesson=BY_ID['receipt']
    for name,expected in [('  PRACTICE   ACACIA COMPANY  ',True),('',False)]:
        start(learner,lesson);v=values(lesson,'guided')
        saved=learner.post('/api/cashflow/transactions',json={
            'direction':'in','financial_account_id':v['cash'],'amount':v['amount'],
            'transaction_date':v['date'],'reference_no':v['reference'],
            'counterparty_name':name,'status':'posted'})
        assert saved.status_code==200,saved.text
        assert learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']==expected

def test_passed_attempt_cannot_release_an_unrecorded_hint(learner):
    lesson=BY_ID['receipt'];start(learner,lesson,mode='independent')
    assert perform(learner,lesson,'independent').status_code==200
    assert learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']
    hint=learner.post('/api/training/hint')
    assert hint.status_code==409 and 'lesson' not in hint.json()

def test_hint_during_verification_prevents_independent_pass(learner,monkeypatch):
    import training.scenarios as scenarios
    lesson=BY_ID['receipt'];start(learner,lesson,mode='independent')
    assert perform(learner,lesson,'independent').status_code==200
    entered=Event();resume=Event();original=scenarios._baseline
    def paused(db):
        entered.set()
        assert resume.wait(10),'The test must release the source verifier'
        return original(db)
    monkeypatch.setattr(scenarios,'_baseline',paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        checking=pool.submit(learner.post,'/api/training/check',json={'answer':lesson.answer})
        try:
            assert entered.wait(5)
            hint=learner.post('/api/training/hint')
            assert hint.status_code==200
        finally:resume.set()
        result=checking.result(timeout=10)
    assert not result.json()['passed'],result.json()

def test_prior_version_passes_stay_historical(learner,application):
    prepared=start(learner,BY_ID['receipt'])
    store=application.state.training_store
    with store.connect() as db:
        db.execute("UPDATE attempts SET status='passed',curriculum_version='2026.11.28.1' WHERE id=?",(prepared['attempt_id'],))
    result=learner.post('/api/training/start',json={'lesson_id':'receipt','mode':'assisted'})
    assert result.status_code==409
    assert any(row['id']==prepared['attempt_id'] and row['status']=='passed' for row in learner.get('/api/training/report').json()['history'])

def test_final_requires_a_checked_pass_for_fresh_saved_work(learner,monkeypatch):
    from training.paths import BY_PATH,DutyPath
    from training.exams import blueprint
    path=DutyPath('test-receipt-review','Receipt review','cashier','A real receipt task.',('receipt',),('receipt',))
    monkeypatch.setitem(BY_PATH,path.id,path)
    assert learner.post('/api/training/enrol',json={'name':'Fictional final learner','role':path.role,'path_id':path.id}).status_code==200
    lesson=BY_ID['receipt']
    for mode in ('guided','assisted','independent'):
        prepared=learner.post('/api/training/start',json={'lesson_id':lesson.id,'mode':mode}).json()
        learner.headers['x-training-attempt']=prepared['attempt_id']
        learner.headers['x-csrf-token']=learner.cookies.get('accounting_training_csrf')
        assert perform(learner,lesson,mode).status_code==200
        assert learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']
    exam=learner.post('/api/training/exams/start',json={'module':'B'}).json()
    prepared=learner.post('/api/training/start',json={'lesson_id':lesson.id,'mode':'independent','exam_id':exam['id']}).json()
    learner.headers['x-training-attempt']=prepared['attempt_id']
    learner.headers['x-csrf-token']=learner.cookies.get('accounting_training_csrf')
    assert perform(learner,lesson,'independent').status_code==200
    answers={q.id:q.answer for q in blueprint(path.id,'B')['questions']}
    result=learner.post('/api/training/exams/'+exam['id']+'/submit',json={'answers':answers})
    assert result.status_code==200,result.text
    assert result.json()['status']=='failed' and result.json()['result']['practical_score']==0
