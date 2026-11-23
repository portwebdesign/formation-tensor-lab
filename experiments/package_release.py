"""Create a checksummed research release and portable source archive."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

RELEASE_DATE = '2026-11-23'
PUBLIC_DIRECTORIES = {'formation_tensor', 'native', 'data', 'experiments',
                      'results', 'paper', 'web', 'tests'}
PUBLIC_ROOT_FILES = {'README.md', 'Makefile', 'run.py', 'requirements-figures.txt', '.gitignore'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admitted(path, root):
    relative = path.relative_to(root)
    if relative.parts[0] not in PUBLIC_DIRECTORIES and relative.as_posix() not in PUBLIC_ROOT_FILES:
        return False
    if any(part in {'.git', 'build', '__pycache__', '.venv'} for part in relative.parts):
        return False
    if path.name == '.DS_Store' or path.suffix in {'.pyc', '.aux', '.log', '.out', '.blg', '.bbl', '.toc', '.fls', '.fdb_latexmk'} or path.name.endswith('.synctex.gz'):
        return False
    return True


def main(root):
    root = root.resolve()
    paths = sorted(path for path in root.rglob('*') if path.is_file() and admitted(path, root))
    frozen = [p for p in paths if not p.relative_to(root).as_posix().startswith('results/verification/')]
    inventory = {'schema': 'formation-tensor-lab.project-inventory.v1',
                 'date': RELEASE_DATE,
                 'scope': 'Frozen release files; rerunnable validation logs are excluded.',
                 'files': {p.relative_to(root).as_posix(): digest(p) for p in frozen}}
    (root / 'project-manifest.json').write_text(json.dumps(inventory, indent=2) + '\n')
    documents = ['paper/main.pdf', 'paper/supplement.pdf', 'paper/main.tex', 'paper/supplement.tex']
    release = {'schema': 'formation-tensor-lab.release.v1', 'date': RELEASE_DATE,
               'files': {name: digest(root / name) for name in documents}}
    release_bytes = (json.dumps(release, indent=2) + '\n').encode()
    archive = root / 'formation-tensor-lab.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=7) as target:
        for path in paths + [root / 'project-manifest.json']:
            info = zipfile.ZipInfo('formation-tensor-lab/' + path.relative_to(root).as_posix(),
                                   date_time=(2026, 11, 23, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_STORED if path.suffix in {'.zip', '.gz', '.jpg', '.png'} else zipfile.ZIP_DEFLATED
            target.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo('formation-tensor-lab/release.json', date_time=(2026, 11, 23, 0, 0, 0))
        info.external_attr = 0o644 << 16
        target.writestr(info, release_bytes)
    release['files']['formation-tensor-lab.zip'] = digest(archive)
    (root / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
    print(json.dumps({'archive': archive.name, 'bytes': archive.stat().st_size,
                      'frozen_files': len(frozen), 'archive_sha256': digest(archive)}))


if __name__ == '__main__':
    main(Path(__file__).resolve().parents[1])
