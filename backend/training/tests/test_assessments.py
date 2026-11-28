"""Fresh practical exams, critical thresholds, ownership and retained history."""
import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from training.curriculum import BY_ID, VERSION
from training.paths import PATHS, BY_PATH, DutyPath
from training.exams import blueprint, public_blueprint, grade_knowledge, prerequisites, ASSESSMENT_VERSION


BLUEPRINTS=[(path.id,module) for path in PATHS for module in [None]+sorted({BY_ID[id].module for id in path.lessons})]


@pytest.mark.parametrize('path_id,module',BLUEPRINTS)
def test_every_duty_final_respects_permissions_and_explicit_scoring(path_id,module):
    row=blueprint(path_id,module);path=BY_PATH[path_id]
    assert set(row['practical_lessons'])<=set(row['lessons'])<=set(path.lessons)
    assert all(path.role in BY_ID[id].roles for id in row['lessons'])
    assert all('answer' not in question and 'correction' not in question for question in public_blueprint(row)['questions'])
    answers={question.id:question.answer for question in row['questions']}
    assert grade_knowledge(row,answers)['score']==100
    ordinary=next(question for question in row['questions'] if not question.critical)
    result=grade_knowledge(row,{**answers,ordinary.id:'incorrect'})
    assert result['score']>=85 and result['critical_pass']
    critical=next(question for question in row['questions'] if question.critical)
    result=grade_knowledge(row,{**answers,critical.id:'incorrect'})
    assert result['score']>=85 and not result['critical_pass']
    assert not prerequisites(row,[])['ready']
    if module is None:assert all(question.id.split('-')[1] in {BY_ID[id].module for id in path.lessons} for question in row['questions'] if question.id.startswith('final-'))


@pytest.fixture
def small_course(monkeypatch):
    path=DutyPath('test-account-review','Test account review','auditor','A bounded real Accounting review.',('read-account-position',),('read-account-position',))
    monkeypatch.setitem(BY_PATH,path.id,path)
    return path


def enrol(client,path):
    response=client.post('/api/training/enrol',json={'name':'Fictional final learner','role':path.role,'path_id':path.id})
    assert response.status_code==200,response.text
    return response.json()


def task(client,lesson_id,mode='guided',exam_id=None,perform=True):
    response=client.post('/api/training/start',json={'lesson_id':lesson_id,'mode':mode,'exam_id':exam_id})
    assert response.status_code==200,response.text
    prepared=response.json();client.headers['X-Training-Attempt']=prepared['attempt_id']
    if perform:
        from training.scenarios import practical_question
        lesson=BY_ID[lesson_id]
        current=client.get("/api/training/me").json()["lesson"]
        assert client.get(current["inspection_api_path"],params=current.get("inspection_query") or {}).status_code==200
        _,answer,_=practical_question(lesson,mode)
        result=client.post('/api/training/check',json={'answer':lesson.answer,'observation':answer})
        assert result.status_code==200,result.text
        assert result.json()['passed'],result.json()
    return prepared


def study(client,path,modes=('guided','assisted','independent')):
    for id in path.lessons:
        for mode in modes:task(client,id,mode)


def start_exam(client,module='A',restart=False):
    response=client.post('/api/training/exams/start',json={'module':module,'restart':restart})
    assert response.status_code==200,response.text
    return response.json()


def answers(exam):
    return {question.id:question.answer for question in blueprint(exam['path_id'],exam['module'])['questions']}


def submit(client,exam,answer=None):
    response=client.post(f"/api/training/exams/{exam['id']}/submit",json={'answers':answers(exam) if answer is None else answer})
    assert response.status_code==200,response.text
    return response.json()


def test_learning_prerequisites_and_historical_passes_cannot_replace_fresh_exam_work(learner,small_course):
    enrol(learner,small_course)
    assert learner.post('/api/training/exams/start',json={'module':'A'}).status_code==409
    study(learner,small_course)
    exam=start_exam(learner)
    assert start_exam(learner)['id']==exam['id']
    # The previously passed independent task does not belong to this exam.
    result=submit(learner,exam)
    assert result['status']=='failed'
    assert result['result']['knowledge']['score']==100
    assert result['result']['practical_score']==0
    assert result['result']['critical_score']==0
    fresh=start_exam(learner)
    assert fresh['id']!=exam['id']
    practice=task(learner,'read-account-position','independent',fresh['id'])
    assert practice['attempt_id'] not in [row.get('attempt_id') for row in result['result']['practical']]
    result=submit(learner,fresh)
    assert result['status']=='passed'
    assert not result['result']['certificate'] # module pass, not role certification
    assert len(learner.get('/api/training/exams').json()['history'])==2


def test_hint_requires_a_fresh_independent_task_inside_the_same_exam(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    task(learner,'read-account-position','independent',exam['id'],perform=False)
    assert learner.post('/api/training/hint').status_code==200
    result=submit(learner,exam)
    assert result['status']=='failed'
    assert result['result']['practical_score']==0
    assert 'hint' in result['result']['practical'][0]['correction']


def test_module_and_role_finals_retain_frozen_results_and_real_fresh_evidence(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    assert learner.post('/api/training/exams/start',json={}).status_code==409
    module=start_exam(learner);task(learner,'read-account-position','independent',module['id']);assert submit(learner,module)['status']=='passed'
    exam=start_exam(learner,None);fresh=task(learner,'read-account-position','independent',exam['id'])
    result=submit(learner,exam)
    assert result['status']=='passed' and result['result']['certificate']==f"TRAINING-{exam['id']}"
    assert result['result']['practical'][0]['attempt_id']==fresh['attempt_id']
    assert result['result']['meaning'].startswith('This certifies local training performance only')
    assert submit(learner,exam,{} )==result
    assert learner.post(f"/api/training/exams/{exam['id']}/draft",json={'answers':{}}).status_code==409
    assert learner.post('/api/training/start',json={'lesson_id':'read-account-position','mode':'independent','exam_id':exam['id']}).status_code==409


def test_exam_ownership_attempt_scope_and_answer_draft_recovery(learner,application,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    saved={'authority':'no','difference':'-20'}
    assert learner.post(f"/api/training/exams/{exam['id']}/draft",json={'answers':saved}).status_code==200
    assert learner.get(f"/api/training/exams/{exam['id']}").json()['answers_draft']==saved
    assert learner.post(f"/api/training/exams/{exam['id']}/draft",json={'answers':{'unrelated-secret':'x'}}).status_code==422
    other=TestClient(application);other.headers['X-Requested-With']='HiddenOasisAccountingTraining';enrol(other,small_course)
    assert other.get(f"/api/training/exams/{exam['id']}").status_code==404
    assert other.post(f"/api/training/exams/{exam['id']}/submit",json={'answers':{}}).status_code==404
    assert learner.post('/api/training/start',json={'lesson_id':'read-account-position','mode':'guided','exam_id':exam['id']}).status_code==403
    assert learner.post('/api/training/exams/start',json={'module':'V'}).status_code==403
