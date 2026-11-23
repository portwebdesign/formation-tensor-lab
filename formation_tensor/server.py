"""Read-only research dashboard with checked data and fixed downloads."""
import hashlib
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit


class ResearchData:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, relative):
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError('A repository-relative path is required.')
        path = (self.root / relative).resolve()
        if self.root not in path.parents:
            raise ValueError('The requested path leaves the repository.')
        return path

    def manifest(self, relative):
        path = self.path(relative)
        record = json.loads(path.read_text())
        files = record.get('files')
        if not isinstance(files, dict) or not files:
            raise ValueError('The data inventory has no checked files.')
        for name, expected in files.items():
            member = self.path(name)
            if not member.is_file() or hashlib.sha256(member.read_bytes()).hexdigest() != expected:
                raise ValueError('A checked research file is unavailable or changed: ' + name)
        return record, hashlib.sha256(path.read_bytes()).hexdigest()

    def document(self, relative, inventory):
        if relative not in inventory['files']:
            raise ValueError('The requested data are outside the checked inventory.')
        return json.loads(self.path(relative).read_text())

    def snapshot(self):
        inputs, input_hash = self.manifest('data/input-manifest.json')
        result = {
            'schema': 'formation-tensor-lab.dashboard.v1', 'integrity': 'passed',
            'manifest_sha256': {'inputs': input_hash},
            'events': self.document('data/formation/events2026.json', inputs),
            'sources': self.document('data/formation/source-ledger.json', inputs),
        }
        names = {'interactions': ('summary.json', 'tensor.json'),
                 'bargaining': ('summary.json', 'dashboard.json'), 'parliament': ('summary.json',)}
        for module, members in names.items():
            record, digest = self.manifest('results/' + module + '/manifest.json')
            result['manifest_sha256'][module] = digest
            documents = {name.removesuffix('.json'): self.document('results/' + module + '/' + name, record)
                         for name in members}
            result[module] = documents
        return result

    def download(self, filename):
        allowed = {
            'paper.pdf': 'paper/main.pdf', 'supplement.pdf': 'paper/supplement.pdf',
            'paper.tex': 'paper/main.tex', 'project.zip': 'formation-tensor-lab.zip',
            'interactions.csv': 'results/interactions/cells.csv',
            'chronology.csv': 'data/formation/chronology.csv',
        }
        if filename not in allowed:
            raise ValueError('Unknown research download.')
        relative = allowed[filename]
        if filename == 'interactions.csv':
            record, _ = self.manifest('results/interactions/manifest.json')
        elif filename == 'chronology.csv':
            record, _ = self.manifest('data/input-manifest.json')
        else:
            record = json.loads(self.path('release.json').read_text())
            if not isinstance(record.get('files'), dict):
                raise ValueError('The release inventory has no checked files.')
        if relative not in record['files']:
            raise ValueError('This release artifact is not available.')
        member = self.path(relative)
        if not member.is_file() or hashlib.sha256(member.read_bytes()).hexdigest() != record['files'][relative]:
            raise ValueError('A checked release artifact is unavailable or changed: ' + relative)
        return member


def handler_for(data):
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status, body, kind, encoding=None):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            if encoding:
                self.send_header('Content-Encoding', encoding)
                self.send_header('Vary', 'Accept-Encoding')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if path in ('/', '/project', '/project/'):
                    return self.send_body(200, data.path('web/index.html').read_bytes(), 'text/html; charset=utf-8')
                static = {'/assets/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
                          '/assets/styles.css': ('web/styles.css', 'text/css; charset=utf-8')}
                if path in static:
                    relative, kind = static[path]
                    return self.send_body(200, data.path(relative).read_bytes(), kind)
                if path == '/api/research':
                    body = json.dumps(data.snapshot(), ensure_ascii=False, separators=(',', ':')).encode()
                    if 'gzip' in self.headers.get('Accept-Encoding', ''):
                        return self.send_body(200, gzip.compress(body, compresslevel=5), 'application/json; charset=utf-8', 'gzip')
                    return self.send_body(200, body, 'application/json; charset=utf-8')
                if path.startswith('/download/'):
                    filename = path.removeprefix('/download/')
                    file = data.download(filename)
                    kind = {'pdf': 'application/pdf', 'tex': 'text/plain; charset=utf-8',
                            'zip': 'application/zip', 'csv': 'text/csv; charset=utf-8'}[filename.rsplit('.', 1)[1]]
                    return self.send_body(200, file.read_bytes(), kind)
                return self.send_body(404, b'Not found', 'text/plain; charset=utf-8')
            except (ValueError, OSError, KeyError) as error:
                return self.send_body(409, json.dumps({'status': 'research_unavailable', 'message': str(error)}).encode(), 'application/json; charset=utf-8')

        def log_message(self, format, *args):
            super().log_message(format, *args)

    return Handler


def serve(root, port=7878):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Use a valid localhost port.')
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(ResearchData(root)))
    print('Formation Tensor Lab: http://127.0.0.1:%d/project' % port, flush=True)
    server.serve_forever()
