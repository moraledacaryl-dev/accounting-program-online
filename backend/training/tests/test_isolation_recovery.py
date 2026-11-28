import json
import socket
import subprocess
import sys
import zipfile
from pathlib import Path
import pytest
from conftest import start
from training.curriculum import BY_ID,LESSONS
from training.recovery import backup,restore
from test_saved_evidence import perform

def test_recovery_preserves_actual_saved_work_and_session(tmp_path):
    from training.main import create_training_app
    from fastapi.testclient import TestClient
    application=create_training_app(tmp_path/'original'/'accounting-training',guard_network=False)
    learner=TestClient(application)
    learner.headers['x-requested-with']='HiddenOasisAccountingTraining'
    lesson=BY_ID['receipt'];attempt=start(learner,lesson)
    assert perform(learner,lesson).status_code==200
    assert learner.post('/api/training/check',json={'answer':lesson.answer}).json()['passed']
    root=application.state.training_store.root
    archive=tmp_path/'private-recovery.zip'
    result=backup(root,archive,stopped=True)
    target=tmp_path/'restored'/'accounting-training'
    assert restore(archive,target,stopped=True)==result
    for name in ('session-key','manager-key','progress.sqlite','attempt-'+attempt['attempt_id']+'.sqlite'):
        assert (root/name).read_bytes()==(target/name).read_bytes()
    with pytest.raises(ValueError):restore(archive,target,stopped=True)
    bad=tmp_path/'tampered.zip'
    with zipfile.ZipFile(archive) as original,zipfile.ZipFile(bad,'w') as out:
        for name in original.namelist():out.writestr(name,b'changed' if name=='session-key' else original.read(name))
    with pytest.raises(ValueError,match='checksum'):restore(bad,tmp_path/'bad'/'accounting-training',stopped=True)

def test_network_guard_denies_outgoing_connection_in_separate_process():
    code="from training.safety import install_network_guard; import socket; install_network_guard(); socket.create_connection(('127.0.0.1',9))"
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode!=0 and 'Accounting Training cannot initiate network' in result.stderr

def test_config_refuses_inherited_production_database(tmp_path):
    import os
    code="from training.safety import configure; from pathlib import Path; import sys; configure(Path(sys.argv[1]))"
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path/'accounting-training')],env={**os.environ,'DATABASE_URL':'postgresql://example.invalid/live'},capture_output=True,text=True)
    assert result.returncode!=0 and 'refuses inherited' in result.stderr
    assert not (tmp_path/'accounting-training').exists()

def test_collection_paths_do_not_redirect_to_backend_origin(learner):
    start(learner,BY_ID['receipt'])
    response=learner.get('/api/financial-accounts',follow_redirects=False)
    assert response.status_code==200

@pytest.mark.parametrize('lesson,role',[(lesson,role) for lesson in LESSONS for role in lesson.roles],ids=lambda row:getattr(row,'id',row))
def test_assigned_roles_can_complete_their_real_work(learner,lesson,role):
    from training.scenarios import practical_question,inspection_endpoint
    start(learner,lesson,role=role)
    result=learner.get(inspection_endpoint(lesson)) if lesson.workflow.startswith('read_') else perform(learner,lesson)
    expected=next((step.outcome_status for step in lesson.steps if step.outcome_status),200)
    assert result.status_code==expected,result.text
    assert learner.post('/api/training/check',json={'answer':lesson.answer,'observation':practical_question(lesson,'guided')[1]}).json()['passed']
