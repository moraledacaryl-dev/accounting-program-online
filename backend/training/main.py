"""Run with python -m training.launch, never with the production service."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import re
from pathlib import Path
import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import jwt
from jwt import PyJWTError as JWTError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from training.safety import configure, install_network_guard
from training.employee_copy import employee_feedback


def create_training_app(root: Path, *, guard_network: bool = True):
    root = configure(root)
    from app.core.settings import settings
    from fastapi import FastAPI
    from app.api import api_router
    from app.db.database import get_db
    from app.services.auth_service import create_access_token
    from app.api.auth import _set_csrf_cookie
    app = FastAPI(title="Accounting Training", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(api_router, prefix="/api")
    SESSION_COOKIE_NAME = settings.auth_cookie_name
    from training.store import Store
    from training.curriculum import BY_ID, LESSONS, VERSION, ROLES, ROLE_NAMES, CAPSTONES, MODULES
    from training.scenarios import IDS, engine_for, prepare, public_lesson, practical_question, inspection_endpoint, read_only_unchanged, recover_checkpoint, resolve_practice_route, verify, values
    from training.paths import BY_PATH, default_path, public_paths

    store = Store(root)
    app.title = "Hidden Oasis Accounting Training — isolated practice"
    cookie_name = "accounting_training_participant"
    manager_file = root / "manager-key"
    if manager_file.is_symlink():
        raise RuntimeError("Manager key cannot be a symlink")
    if not manager_file.exists():
        fd = os.open(manager_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(32))
    manager_key = manager_file.read_text().strip()

    def identity(request):
        try:
            payload = jwt.decode(request.cookies.get(cookie_name, ""), settings.secret_key, algorithms=["HS256"], audience="accounting-training")
            learner = store.learner(payload["sub"])
            if learner:
                return learner
        except (JWTError, KeyError, TypeError):
            pass
        raise HTTPException(401, "Choose your training role to start, or return to the browser where you began.")

    def cookies(response, learner_id, role):
        token = jwt.encode({"sub": learner_id, "aud": "accounting-training", "exp": datetime.now(timezone.utc) + timedelta(days=180)}, settings.secret_key, algorithm="HS256")
        secure=bool(os.environ.get("ACCOUNTING_TRAINING_ORIGIN"))
        response.set_cookie(cookie_name, token, httponly=True, secure=secure, samesite="strict", max_age=180 * 86400)
        response.set_cookie(SESSION_COOKIE_NAME, create_access_token("training_actor"), httponly=True, secure=secure, samesite="strict", max_age=180 * 86400)
        _set_csrf_cookie(response)

    def sandbox_db(request: Request):
        learner = identity(request)
        attempt = getattr(request.state, "training_attempt", None) or store.attempt(learner["id"])
        if not attempt:
            raise HTTPException(409, "Start a lesson before opening practice.")
        path = root / f"attempt-{attempt['id']}.sqlite"
        if not path.exists():
            raise HTTPException(409, "Your practice file is unavailable. Return to Training and reset this lesson.")
        engine = engine_for(path)
        try:
            with Session(engine) as db:
                yield db
        finally:
            engine.dispose()

    app.dependency_overrides[get_db] = sandbox_db

    from training.boundary import install_boundary
    install_boundary(app, store, root, identity)

    router = APIRouter(prefix="/api/training", tags=["isolated-training"])

    class Enrolment(BaseModel):
        name: str = Field(min_length=1, max_length=80)
        role: str
        path_id: str | None = None

    class Start(BaseModel):
        lesson_id: str
        mode: str = "guided"
        exam_id: str | None = None

    class Check(BaseModel):
        answer: str = Field(max_length=200)
        observation: str = Field(default="", max_length=200)

    class Checkpoint(BaseModel):
        step: int = Field(ge=0, le=100)
        revisit: bool = False

    def current_attempt(request):
        learner = identity(request)
        attempt = store.attempt(learner["id"])
        if not attempt:
            raise HTTPException(409, "Start a lesson first.")
        if attempt["curriculum_version"] != VERSION:
            raise HTTPException(409, "Training has been updated. Start a new attempt from your course.")
        if request.headers.get("x-training-attempt") != attempt["id"]:
            raise HTTPException(409, "This practice changed in another tab. Return to Training to continue the current task.")
        if attempt["lesson_id"] not in BY_ID:
            raise HTTPException(409, "The course has changed. Return to Training to choose an updated lesson.")
        return learner, attempt

    @router.get("/practice-file")
    def practice_file(request: Request):
        _,attempt=current_attempt(request)
        from training.scenarios import practice_csv
        fixture=practice_csv(attempt["lesson_id"],values(BY_ID[attempt["lesson_id"]],attempt["mode"]))
        if fixture is None:raise HTTPException(404,"This practice has no CSV input.")
        return JSONResponse(content={"filename":fixture["filename"],"content":fixture["content"]},headers={"Cache-Control":"no-store"})

    @router.get("/catalogue")
    def catalogue():
        return {"version": VERSION, "roles": ROLE_NAMES, "paths":public_paths(),
            "lessons": [public_lesson(lesson) for lesson in LESSONS], "capstones": CAPSTONES,
            "environment": "isolated-training", "modules": MODULES}

    @router.post("/enrol")
    def enrol(payload: Enrolment, request: Request, response: Response):
        if payload.role not in ROLES or not payload.name.strip():
            raise HTTPException(422, "Choose a supported training role and enter your name.")
        path_id=payload.path_id or default_path(payload.role)
        path=BY_PATH.get(path_id)
        if not path or path.role!=payload.role:raise HTTPException(422,"Choose a duty course that matches these training responsibilities.")
        try:
            existing = identity(request)
        except HTTPException:
            existing = None
        learner_id = existing["id"] if existing else str(uuid.uuid4())
        with store.connect() as db:
            if existing:
                db.execute("UPDATE attempts SET status='reset' WHERE learner_id=? AND status='active'", (learner_id,))
                db.execute("UPDATE learners SET role=?,name=?,path_id=?,current_attempt=NULL WHERE id=?", (payload.role, payload.name.strip(), path_id, learner_id))
            else:
                db.execute("INSERT INTO learners(id,name,role,path_id) VALUES (?,?,?,?)", (learner_id, payload.name.strip(), payload.role,path_id))
            db.execute("INSERT OR IGNORE INTO path_assignments(learner_id,path_id) VALUES (?,?)",(learner_id,path_id))
        cookies(response, learner_id, payload.role)
        return {"id": learner_id, "name": payload.name.strip(), "role": payload.role, "path_id":path_id}

    @router.get("/me")
    def me(request: Request, response: Response):
        learner = identity(request)
        cookies(response, learner["id"], learner["role"])
        attempt = store.attempt(learner["id"])
        if attempt and attempt["curriculum_version"] != VERSION:
            attempt = None
        lesson_payload=public_lesson(BY_ID[attempt["lesson_id"]],attempt["mode"]) if attempt and attempt["lesson_id"] in BY_ID else None
        inspected = False
        if attempt and attempt["lesson_id"] in BY_ID:
            path=root / f"attempt-{attempt['id']}.sqlite"
            if path.exists():
                engine=engine_for(path)
                try:
                    with Session(engine) as business:
                        recovered=recover_checkpoint(business,BY_ID[attempt["lesson_id"]],attempt["mode"],attempt["checkpoint"],store.business_actions(attempt["id"]))
                        lesson_payload["route"]=resolve_practice_route(business,BY_ID[attempt["lesson_id"]],attempt["mode"])
                        lesson_payload["inspection_api_path"]=inspection_endpoint(BY_ID[attempt["lesson_id"]],business)
                    if recovered != attempt["checkpoint"]:
                        attempt["checkpoint"]=recovered
                        with store.connect() as db:
                            db.execute("UPDATE attempts SET checkpoint=? WHERE id=?", (recovered,attempt["id"]))
                finally:
                    engine.dispose()
            with store.connect() as db:
                inspected = bool(db.execute("SELECT 1 FROM events WHERE attempt_id=? AND kind='record_read' AND json_extract(detail,'$.path')=? LIMIT 1", (attempt["id"], lesson_payload["inspection_api_path"])).fetchone())
        return {"learner": learner, "attempt": attempt,
            "lesson": lesson_payload,
            "history": store.history(learner["id"]), "assignments":store.assignments(learner["id"]), "version": VERSION, "record_inspected": inspected}

    @router.post("/start")
    def start(payload: Start, request: Request, response: Response):
        learner = identity(request)
        lesson = BY_ID.get(payload.lesson_id)
        if not lesson or learner["role"] not in lesson.roles or lesson.id not in BY_PATH[learner["path_id"]].lessons:
            raise HTTPException(403, "This lesson is outside your selected training responsibilities.")
        if payload.mode not in {"guided", "assisted", "independent"}:
            raise HTTPException(422, "Choose guided, assisted or independent practice.")
        previous = {row["mode"] for row in store.history(learner["id"]) if row["lesson_id"] == lesson.id and row["role"] == learner["role"] and row["status"] == "passed" and row["curriculum_version"] == VERSION}
        if payload.mode == "assisted" and "guided" not in previous or payload.mode == "independent" and not {"guided", "assisted"}.issubset(previous):
            raise HTTPException(409, "Complete guided practice, then assisted practice, before the independent assessment.")
        if payload.exam_id:
            from training.assessment_routes import validate_exam_attempt
            validate_exam_attempt(store,learner,payload.exam_id,lesson.id,payload.mode)
        attempt_id = str(uuid.uuid4())
        path = root / f"attempt-{attempt_id}.sqlite"
        try:
            prepare(path, lesson, learner["role"], payload.mode)
        except Exception as exc:
            logging.getLogger(__name__).exception("Training preparation failed: attempt=%s lesson=%s", attempt_id, lesson.id)
            # Never destroy a previous valid checkpoint on failed preparation.
            raise HTTPException(503, "Practice could not be prepared. Your previous work is safe. Try preparing this lesson again.") from exc
        with store.connect() as db:
            db.execute("UPDATE attempts SET status='reset' WHERE learner_id=? AND status='active'", (learner["id"],))
            db.execute("INSERT INTO attempts(id,learner_id,lesson_id,mode,role,curriculum_version,path_id,exam_id) VALUES (?,?,?,?,?,?,?,?)", (attempt_id, learner["id"], lesson.id, payload.mode, learner["role"], VERSION,learner["path_id"],payload.exam_id))
            db.execute("UPDATE learners SET current_attempt=? WHERE id=?", (attempt_id, learner["id"]))
        cookies(response, learner["id"], learner["role"])
        return {"attempt_id": attempt_id, "lesson": public_lesson(lesson, payload.mode)}

    @router.post("/checkpoint")
    def checkpoint(payload: Checkpoint, request: Request):
        _, attempt = current_attempt(request)
        lesson = BY_ID[attempt["lesson_id"]]
        if payload.step > len(public_lesson(lesson, attempt["mode"])["steps"]):
            raise HTTPException(422, "Invalid lesson checkpoint")
        with store.connect() as db:
            expression="?" if payload.revisit else "MAX(checkpoint,?)"
            db.execute(f"UPDATE attempts SET checkpoint={expression} WHERE id=? AND status='active'", (payload.step, attempt["id"]))
        return {"saved": True}

    @router.post("/hint")
    def hint(request: Request):
        _, attempt = current_attempt(request)
        with store.connect() as db:
            db.execute("UPDATE attempts SET hints=hints+1 WHERE id=? AND status='active'", (attempt["id"],))
        store.event(attempt["id"], "hint", {})
        return {"lesson": public_lesson(BY_ID[attempt["lesson_id"]], attempt["mode"])}

    @router.post("/check")
    def check(payload: Check, request: Request):
        _, attempt = current_attempt(request)
        lesson = BY_ID[attempt["lesson_id"]]
        if attempt["status"] == "passed":
            return {"passed": True, "message": "This attempt has already passed.", "evidence": json.loads(attempt["evidence"])}
        def normalize(value):
            from decimal import Decimal, InvalidOperation
            clean = " ".join(value.lower().strip().replace(",", "").replace("_", " ").split())
            try:
                number=Decimal(clean)
                if number.is_finite(): return str(number.normalize())
            except InvalidOperation:
                pass
            return clean
        knowledge = normalize(payload.answer) == normalize(lesson.answer)
        path = root / f"attempt-{attempt['id']}.sqlite"
        if not path.exists():
            raise HTTPException(409, "Practice is unavailable. Reset this lesson from Training.")
        engine = engine_for(path)
        try:
            with Session(engine) as db:
                if lesson.workflow.startswith("read_"):
                    _, answer, _ = practical_question(lesson, attempt["mode"])
                    with store.connect() as registry:
                        read = registry.execute("SELECT 1 FROM events WHERE attempt_id=? AND kind='record_read' AND json_extract(detail,'$.path')=? LIMIT 1", (attempt["id"], inspection_endpoint(lesson,db))).fetchone()
                    practical = bool(read) and normalize(payload.observation) == normalize(answer)
                    untouched=read_only_unchanged(db,IDS["actor"])
                    practical=practical and untouched
                    evidence = {"record_inspection": practical, "observation": payload.observation,"record_unchanged":bool(untouched)}
                    if not untouched:evidence["correction"]="This is an inspection task. Keep its business records unchanged while reading the actual result. Start a fresh practice if a change was posted."
                else:
                    practical, evidence = verify(db, lesson, attempt["mode"],store.business_actions(attempt["id"]))
        finally:
            engine.dispose()
        passed = knowledge and practical
        if attempt["mode"] == "independent" and attempt["hints"] > 0:
            passed = False
            message = "You used guidance in this independent attempt. Practise with the hint, then start a fresh independent assessment."
        elif not knowledge:
            message = lesson.correction
        elif not practical:
            message = evidence.get("correction") or "Check the account, amount, reference, and saved record. Correct unposted entries, or reset this practice if an incorrect transaction was posted."
        else:
            message = "Correct. The action was refused." if lesson.steps and lesson.steps[-1].outcome_status else "Task complete."
        message = employee_feedback(message, lesson, values(lesson,attempt["mode"]))
        evidence.update(knowledge=knowledge, practical=practical, curriculum_version=VERSION)
        with store.connect() as db:
            if passed:
                db.execute("UPDATE attempts SET status='passed',completed_at=CURRENT_TIMESTAMP,evidence=? WHERE id=? AND status='active'", (json.dumps(evidence), attempt["id"]))
            else:
                db.execute("UPDATE attempts SET mistakes=mistakes+1 WHERE id=? AND status='active'", (attempt["id"],))
        store.event(attempt["id"], "assessment", {"passed": passed, "knowledge": knowledge, "practical": practical})
        return {"passed": passed, "message": message, "evidence": evidence}

    @router.get('/report')
    def report(request: Request):
        learner = identity(request)
        from training.assessment_routes import public_exam
        return {'learner':learner, 'history':store.history(learner['id']),
                'exams':[public_exam(row) for row in store.exams(learner['id'])],
                'curriculum_version':VERSION, 'meaning':'Local training evidence only; not production authorization.'}

    @router.post('/sign-out')
    def sign_out(response: Response):
        response.delete_cookie(cookie_name)
        response.delete_cookie(settings.auth_cookie_name)
        response.delete_cookie(settings.csrf_cookie_name)
        return {'signed_out':True}

    def require_manager(request):
        supplied = request.headers.get("x-training-manager-key", "")
        if not supplied or not secrets.compare_digest(supplied, manager_key):
            raise HTTPException(403, "Trainer access is required to view other employees' progress.")

    @router.get("/management")
    def management(request: Request):
        require_manager(request)
        with store.connect() as db:
            learners = [dict(row) for row in db.execute("SELECT id,name,role,path_id,created_at FROM learners ORDER BY created_at DESC")]
        for learner in learners:
            learner["attempts"] = store.history(learner["id"])
            learner["assignments"] = store.assignments(learner["id"])
            from training.assessment_routes import public_exam
            learner["exams"] = [public_exam(row) for row in store.exams(learner["id"])]
        from training.exams import ASSESSMENT_VERSION
        return {"learners": learners, "version": VERSION, "assessment_version":ASSESSMENT_VERSION}

    class Assignment(BaseModel):
        learner_id: str
        role: str | None = None
        path_id: str | None = None

    @router.post("/assign")
    def assign(payload: Assignment, request: Request):
        require_manager(request)
        path_id=payload.path_id or default_path(payload.role or "")
        path=BY_PATH.get(path_id)
        if not path or payload.role and path.role!=payload.role or not store.learner(payload.learner_id):
            raise HTTPException(422, "Choose a known employee and training path.")
        with store.connect() as db:
            db.execute("UPDATE attempts SET status='reset' WHERE learner_id=? AND status='active'", (payload.learner_id,))
            db.execute("UPDATE learners SET role=?,path_id=?,current_attempt=NULL WHERE id=?", (path.role,path_id,payload.learner_id))
            db.execute("INSERT OR IGNORE INTO path_assignments(learner_id,path_id) VALUES (?,?)",(payload.learner_id,path_id))
        return {"assigned": True}

    from training.assessment_routes import register_assessments
    register_assessments(router,store,root,identity)
    app.include_router(router)
    app.state.training_store = store
    if guard_network:
        install_network_guard()
    return app
