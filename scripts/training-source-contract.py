"""Bind reviewed Accounting source to the curriculum; refuse silent source drift."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'docs/training/source-contract.json'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sources():
    files=list((ROOT/'backend/app').rglob('*.py'))+list((ROOT/'shared').glob('*.json'))
    for folder in ('app','components','lib'):
        files.extend(path for path in (ROOT/'frontend'/folder).rglob('*.js')
            if 'training' not in path.as_posix().lower())
    files.extend(ROOT/name for name in ('frontend/package-lock.json','backend/requirements.lock.txt','frontend/next.config.js','backend/training-requirements.txt'))
    return {path.relative_to(ROOT).as_posix():digest(path) for path in sorted(files)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record-reviewed-source',action='store_true');args=parser.parse_args()
    actual=sources()
    if args.record_reviewed_source:
        CONTRACT.parent.mkdir(parents=True,exist_ok=True)
        CONTRACT.write_text(json.dumps({'accounting_baseline':'ad1a350b87cb19f09533043143f44dbb532b9cff','curriculum_version':'2026.11.28.1','reviewed_training_ui_fixes':['cash-count form retains and submits actual entered count','folio route reads Next dynamic parameters through useParams'],'files':actual},indent=2)+'\n')
    else:
        expected=json.loads(CONTRACT.read_text())['files']
        changed=sorted(name for name in set(expected)|set(actual) if expected.get(name)!=actual.get(name))
        if changed:raise SystemExit('Accounting source changed; review lessons and browser evidence before refreshing the contract: '+', '.join(changed))
    print(f'Accounting Training source contract verified: {len(actual)} files')
if __name__=='__main__':main()
