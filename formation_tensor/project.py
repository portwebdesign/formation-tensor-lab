"""Verification, isolated reproduction and local execution of the study."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

EXPERIMENTS = {'interactions':'run_interactions.py','bargaining':'run_bargaining.py',
               'parliament':'run_parliament.py','input-correction':'check_minor_vote_correction.py',
               'completion-sensitivity':'run_completion_sensitivity.py'}
MODULES = tuple(EXPERIMENTS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_manifest(root, relative):
    record=json.loads((root/relative).read_text())
    for name, expected in record['files'].items():
        path=(root/name).resolve()
        if root not in path.parents or not path.is_file() or sha(path)!=expected:
            raise ValueError('Inventory mismatch: '+name)
    return record


def verify(root):
    inputs=checked_manifest(root,'data/input-manifest.json')
    results={m:checked_manifest(root,'results/'+m+'/manifest.json') for m in MODULES}
    if (root/'project-manifest.json').exists():
        checked_manifest(root,'project-manifest.json')
    return {'status':'passed','input_files':len(inputs['files']),
            'experiments':list(results),'scope':'Source and numerical-output integrity.'}


def same_value(a,b,path='root'):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return path+': keys differ'
        for key in a:
            mismatch=same_value(a[key],b[key],path+'.'+key)
            if mismatch:return mismatch
        return None
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return path+': lengths differ'
        for i,(x,y) in enumerate(zip(a,b)):
            mismatch=same_value(x,y,path+'['+str(i)+']')
            if mismatch:return mismatch
        return None
    if type(a) is float or type(b) is float:
        if type(a) not in (int,float) or type(b) not in (int,float) or not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10):
            return path+': numerical difference'
        return None
    return None if type(a)==type(b) and a==b else path+': value differs'


def compute(root):
    for module in MODULES:
        command=[sys.executable,'-B','experiments/'+EXPERIMENTS[module]]
        result=subprocess.run(command,cwd=root)
        if result.returncode:return result.returncode
    return 0


def reproduce(root):
    verify(root)
    with tempfile.TemporaryDirectory(prefix='formation-tensor-reproduction-') as folder:
        fresh=Path(folder).resolve()
        for directory in ('formation_tensor','native','data','experiments','tests'):
            shutil.copytree(root/directory,fresh/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(root/'run.py',fresh/'run.py')
        log=fresh/'reproduction.log'
        with log.open('w') as stream:
            result=subprocess.run([sys.executable,'-B','run.py','_compute'],cwd=fresh,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Reproduction failed:\n'+log.read_text())
        compared=[]
        for module in MODULES:
            for original in sorted((root/'results'/module).glob('*.json')):
                if original.name in ('manifest.json','run.json'):continue
                actual=fresh/'results'/module/original.name
                if not actual.is_file():raise ValueError('Missing reproduced output: '+module+'/'+original.name)
                mismatch=same_value(json.loads(original.read_text()),json.loads(actual.read_text()))
                if mismatch:raise ValueError(module+'/'+original.name+': '+mismatch)
                compared.append(module+'/'+original.name)
            for original in sorted((root/'results'/module).glob('*.csv')):
                actual=fresh/'results'/module/original.name
                if original.read_bytes()!=actual.read_bytes():raise ValueError('CSV mismatch: '+module+'/'+original.name)
                compared.append(module+'/'+original.name)
        return {'status':'passed','recomputed_files':compared,'numerical_mismatches':0,
                'integer_comparison':'exact','floating_comparison':'absolute1e-10 or relative1e-12',
                'working_copy_modified':False,'scope':'Fresh directory on this host; no downloads or inherited numerical outputs.'}


def tests(root):
    out=root/'results/verification';out.mkdir(parents=True,exist_ok=True)
    build=root/'build';build.mkdir(exist_ok=True)
    commands=[
        [sys.executable,'-B','-m','unittest','discover','-s','tests','-t','.','-v'],
        [sys.executable,'-B','-m','unittest','discover','-s','data/formation','-p','test_curated_events.py','-v'],
        ['rustc','--edition=2024','--test','native/adapter.rs','-o',str(build/'native-tests')],
        [str(build/'native-tests')],
        ['node','--check','web/app.js'],
    ]
    records=[]
    for i,command in enumerate(commands):
        result=subprocess.run(command,cwd=root,capture_output=True,text=True)
        log=out/('check-'+str(i+1)+'.txt');log.write_text(result.stdout+result.stderr)
        records.append({'command':command,'returncode':result.returncode,
                        'log':str(log.relative_to(root)),'sha256':sha(log)})
        if result.returncode:break
    record={'status':'passed' if len(records)==len(commands) and all(r['returncode']==0 for r in records) else 'failed',
            'created_at_utc':datetime.now(timezone.utc).isoformat(),'checks':records}
    (out/'tests.json').write_text(json.dumps(record,indent=2)+'\n')
    if record['status']!='passed':
        raise RuntimeError('Test failure; see results/verification/')
    return record


def main(root):
    root=Path(root).resolve()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','reproduce','test','serve','figures','paper','_compute'])
    parser.add_argument('--port',type=int,default=7878)
    args=parser.parse_args()
    if args.command=='verify': result=verify(root)
    elif args.command=='reproduce':result=reproduce(root)
    elif args.command=='test':result=tests(root)
    elif args.command=='_compute':return compute(root)
    elif args.command=='serve':
        if not 1<=args.port<=65535:parser.error('Port must be 1..65535.')
        from .server import serve
        serve(root,args.port);return 0
    elif args.command=='figures':
        return subprocess.call([sys.executable,'-B','experiments/build_figures.py'],cwd=root)
    else:
        for name in ('main.tex','supplement.tex'):
            if subprocess.call(['tectonic','--keep-logs',name],cwd=root/'paper'):return 1
        return 0
    print(json.dumps(result,ensure_ascii=False))
    return 0
