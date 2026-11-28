"""Versioned exam blueprints and explicit scoring, separate from HTTP/storage.

A final combines a knowledge check with new source-backed independent attempts.
Public blueprints deliberately omit answer keys; completed grading retains the
specific questions/objectives to revisit rather than a generic failure label.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from training.curriculum import BY_ID, VERSION
from training.paths import BY_PATH
from training.employee_copy import employee_text

ASSESSMENT_VERSION="2026.11.28.1"


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    answer: str
    correction: str
    critical: bool = False


def q(id,prompt,answer,correction,critical=False):return Question(id,employee_text(prompt),str(answer),employee_text(correction),critical)


from training.exam_content import FOUNDATION_DATA, TOPICS
FOUNDATION=tuple(q(*row) for row in FOUNDATION_DATA)

def questions(module,path_id):
    if module is None:
        path=BY_PATH[path_id]
        modules=list(dict.fromkeys([BY_ID[id].module for id in path.final_tasks]+[BY_ID[id].module for id in path.lessons]))
        # Sample the assigned course, beginning with its practical final's
        # responsibilities. A read-only auditor is assessed only on assigned work.
        contextual=[]
        for index in range(3):
            for letter in modules:
                row=TOPICS[letter][index]
                contextual.append(q("final-"+letter+"-"+row[0],*row[1:],critical=True))
                if len(contextual)==5:return FOUNDATION+tuple(contextual)
        return FOUNDATION+tuple(contextual)
    return FOUNDATION+tuple(q(module+"-"+row[0],*row[1:],critical=row[0] in {"truth","approval","independent","limit","raw","refund","laundry","accepted","scope","rejection","reservation"}) for row in TOPICS[module])


def blueprint(path_id,module=None):
    path=BY_PATH[path_id]
    if module is not None and module not in {BY_ID[id].module for id in path.lessons}:raise ValueError("This module is outside the chosen course")
    applicable=tuple(id for id in path.lessons if module is None or BY_ID[id].module==module)
    if module is None:practical=path.final_tasks
    else:
        # The linked exercise covers the module's complete chain where one is
        # available; otherwise sample an actual action and a distinct control.
        caps=[id for id in applicable if BY_ID[id].workflow.startswith("capstone_")]
        actions=[id for id in applicable if not BY_ID[id].workflow.startswith("read_")]
        refusals=[id for id in actions if any(step.outcome_status for step in BY_ID[id].steps)]
        chosen=(caps[:1] or actions[:1] or list(applicable[:1]))+refusals[:1]
        evidence={"B":"receipt-with-journal","G":"count-cash","I":"read-trial-balance","J":"read-profit","K":"depreciation-cap","L":"read-inbox"}.get(module)
        if evidence in applicable:chosen.append(evidence)
        safety={"C":"refuse-overdraw","E":"refuse-overcollection","F":"refuse-overpayment","M":"locked-period","K":"refuse-repeat-disposal"}.get(module)
        if safety in applicable:chosen.append(safety)
        practical=tuple(dict.fromkeys(chosen))
    return {"path_id":path_id,"path_title":path.title,"module":module,"title":(f"Module {module} final" if module else path.title+" final"),"version":VERSION,"assessment_version":ASSESSMENT_VERSION,"lessons":applicable,"practical_lessons":practical,"questions":questions(module,path_id),"thresholds":{"knowledge":85,"practical":90,"critical":100}}


def public_blueprint(row):
    return {**row,"questions":[{key:value for key,value in asdict(question).items() if key not in {"answer","correction"}} for question in row["questions"]]}


def normalize(value):
    clean=" ".join(str(value).lower().strip().replace(",","").split())
    try:
        number=Decimal(clean)
        if number.is_finite():return str(number.normalize())
    except InvalidOperation:pass
    return clean


def grade_knowledge(row,answers):
    checked=[{"id":question.id,"prompt":question.prompt,"passed":normalize(answers.get(question.id,""))==normalize(question.answer),"critical":question.critical,"correction":question.correction} for question in row["questions"]]
    return {"score":round(100*sum(question["passed"] for question in checked)/len(checked),2),"critical_pass":all(question["passed"] for question in checked if question["critical"]),"questions":checked}


def prerequisites(row,history,module_results=()):
    def passed(id,modes):
        actual={attempt["mode"] for attempt in history if attempt["lesson_id"]==id and attempt["role"]==BY_PATH[row["path_id"]].role and attempt["curriculum_version"]==VERSION and attempt["status"]=="passed"}
        return modes<=actual
    modes={"guided","assisted"} if row["module"] else {"guided","assisted","independent"}
    missing=[id for id in row["lessons"] if not passed(id,modes)]
    missing_modules=[]
    if row["module"] is None:
        required={BY_ID[id].module for id in row["lessons"]}
        completed={exam["module"] for exam in module_results if exam["path_id"]==row["path_id"] and exam["curriculum_version"]==VERSION and exam["assessment_version"]==ASSESSMENT_VERSION and exam["status"]=="passed"}
        missing_modules=sorted(required-completed)
    return {"ready":not missing and not missing_modules,"missing_lessons":missing,"missing_module_finals":missing_modules}


def grade_practical(tasks):
    if not tasks:return {"score":0,"critical_pass":False,"passed":False}
    score=round(sum(task["score"] for task in tasks)/len(tasks),2)
    critical=all(task["critical_pass"] for task in tasks)
    return {"score":score,"critical_pass":critical,"passed":score>=90 and critical}
