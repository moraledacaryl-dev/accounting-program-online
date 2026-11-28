from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope='session')
def application(tmp_path_factory):
    from training.main import create_training_app
    root=tmp_path_factory.mktemp('accounting-course')/'accounting-training'
    return create_training_app(root,guard_network=False)

@pytest.fixture
def learner(application):
    with TestClient(application) as client:
        client.headers['x-requested-with']='HiddenOasisAccountingTraining'
        yield client

def start(client,lesson,role=None,mode='guided'):
    response=client.post('/api/training/enrol',json={'name':'Fictional employee','role':role or lesson.roles[0]})
    assert response.status_code==200,response.text
    # Unit scenarios exercise all three fixture variants without forging passes;
    # the actual prerequisites are separately tested through the HTTP contract.
    if mode!='guided':
        store=client.app.state.training_store
        with store.connect() as db:
            learner_id=client.get('/api/training/me').json()['learner']['id']
            for previous in ['guided','assisted'][:1 if mode=='assisted' else 2]:
                import uuid
                id=str(uuid.uuid4())
                from training.curriculum import VERSION
                db.execute("INSERT INTO attempts(id,learner_id,lesson_id,mode,role,status,curriculum_version,path_id) VALUES (?,?,?,?,?,'passed',?,?)",(id,learner_id,lesson.id,previous,role or lesson.roles[0],VERSION,'role-'+(role or lesson.roles[0])))
    response=client.post('/api/training/start',json={'lesson_id':lesson.id,'mode':mode})
    assert response.status_code==200,response.text
    client.headers['x-training-attempt']=response.json()['attempt_id']
    client.headers['x-csrf-token']=client.cookies.get('accounting_training_csrf')
    return response.json()
