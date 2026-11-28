"""Private CI answer keys; output is never bundled in the learner web app."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from training.curriculum import LESSONS
from training.scenarios import public_lesson, practical_question
from training.exams import blueprint
from training.paths import PATHS

print(json.dumps({'lessons':[{**public_lesson(row), 'answer':row.answer,
    'observation':practical_question(row,'guided')[1],
    'variants':{mode:{**public_lesson(row,mode),'answer':row.answer,'observation':practical_question(row,mode)[1]} for mode in ('guided','assisted','independent')}} for row in LESSONS],
    'exams':{path.id:{module or 'final':{q.id:q.answer for q in blueprint(path.id,module)['questions']}
        for module in sorted({row.module for row in LESSONS if row.id in path.lessons})+[None]} for path in PATHS}}))
