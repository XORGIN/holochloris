"""HOLOCHLORIS — serveur de projection locale p5.js, Python standard uniquement.
C1: lit output/c1/c1_sequence.json (publié par holochloris_mst_flux_auto.py)
C2: expose la dernière vidéo holochloris-c2-respiration_*.mp4 depuis ComfyUI.
Lancement: py server.py
"""
import json
import mimetypes
import os
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
C1 = Path(CFG['c1_directory'])
C2 = Path(CFG['c2_directory'])
PREFIX = CFG['c2_prefix']
PORT = int(CFG.get('port', 8765))


def latest_video():
    if not C2.is_dir():
        return None
    videos = []
    for p in C2.glob(PREFIX + '*.mp4'):
        try:
            st = p.stat()
            # avoid serving a file still being encoded by Video Combine
            if st.st_size > 0 and time.time() - st.st_mtime > 2:
                videos.append((st.st_mtime_ns, p))
        except OSError:
            pass
    return max(videos, default=(None, None))[1]


def load_manifest():
    f = C1 / 'c1_sequence.json'
    try:
        v = json.loads(f.read_text(encoding='utf-8'))
        if (isinstance(v, dict) and isinstance(v.get('frames'), list)
                and len(v['frames']) == 3 and v.get('version')):
            return v
    except (ValueError, OSError):
        pass
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):
        if self.path.startswith('/api/') or self.path.startswith('/output/'):
            self.send_header('Cache-Control', 'no-store, max-age=0')
        super().end_headers()

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_video(self, p):
        size = p.stat().st_size
        range_header = self.headers.get('Range')
        first, last = 0, size - 1
        if range_header:
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
            if not m or (not m.group(1) and not m.group(2)):
                self.send_error(416, 'Invalid Range')
                return
            if m.group(1):
                first = int(m.group(1))
                last = min(size - 1, int(m.group(2))) if m.group(2) else size - 1
            else:
                tail = int(m.group(2))
                first = max(0, size - tail)
            if first >= size or first > last:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
        length = last - first + 1
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        if range_header:
            self.send_header('Content-Range', f'bytes {first}-{last}/{size}')
        self.end_headers()
        try:
            with p.open('rb') as f:
                f.seek(first)
                remaining = length
                while remaining > 0:
                    block = f.read(min(256 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/status':
            manifest, video = load_manifest(), latest_video()
            version = None
            if video:
                st = video.stat()
                version = f'{st.st_mtime_ns}-{st.st_size}'
            self.send_json({
                'c1': {'ready': bool(manifest), 'version': manifest.get('version') if manifest else None},
                'c2': {'ready': bool(video), 'version': version, 'filename': video.name if video else None},
                'bioclip': {'ready': False}
            })
            return
        if path == '/api/c1/sequence':
            manifest = load_manifest()
            self.send_json(manifest, 200) if manifest else self.send_json({'error': 'Pas encore de série MST++'}, 404)
            return
        if path == '/api/c2/video':
            p = latest_video()
            self.send_video(p) if p else self.send_error(404, 'Aucune vidéo C2 disponible')
            return
        if path.startswith('/output/c1/sets/'):
            # Only allow files in the configured C1 directory, not arbitrary local files
            rel = path[len('/output/c1/'):]
            requested = (C1 / rel).resolve()
            if not requested.is_relative_to(C1.resolve()) or requested.suffix.lower() != '.png':
                self.send_error(403)
                return
            if not requested.is_file():
                self.send_error(404)
                return
            data = requested.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()


if __name__ == '__main__':
    print('HOLOCHLORIS — PROJECTION', flush=True)
    print(f'Page : http://127.0.0.1:{PORT}', flush=True)
    print('C1 MST++ :', C1, flush=True)
    print('C2 ComfyUI :', C2, flush=True)
    print('Arrêt : Ctrl+C', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
