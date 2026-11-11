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
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BIOME_IDS = {"tropical", "desert", "boreal", "taiga", "tundra"}
STATE_LOCK = threading.Lock()
DEFAULT_STATE = {"biome": "boreal", "x": 0.32, "y": 0.60, "version": 0}

def biome_state():
    try:
        obj = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if obj.get("biome") in BIOME_IDS:
            return obj
    except (OSError, ValueError, AttributeError):
        pass
    return dict(DEFAULT_STATE)

def write_biome_state(obj):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, STATE_FILE)


ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "output" / "state" / "biome_state.json"
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



# Afficher uniquement la carte BioCLIP sans modifier le projet BioCLIP lui-même.
# L'iframe utilise /bioclip/ sur le même port que Holochloris. Ce proxy
# s'adresse exclusivement au serveur de confiance sur 127.0.0.1:8766.
BIOCLIP_ORIGIN = "http://127.0.0.1:8766"
BIOCLIP_MAP_STYLE = r"""
<style id="holochloris-map-only">
:root {color-scheme: dark; --bg:#000; --panel:#000; --ink:#c8d3d3; --line:#101717;}
html,body {background:#000!important;margin:0!important;overflow:hidden!important;}
header, .intro, #tab-map > .intro, #tab-map .row, #tab-map .legend,
#tab-map #gapInfo, #tab-map #mapInfo {display:none!important;}
main {width:100%!important;max-width:none!important;padding:0!important;margin:0!important;}
section.tab {display:none!important;}
#tab-map {display:block!important;height:100vh!important;margin:0!important;padding:0!important;}
#tab-map > .panel {height:100vh!important;margin:0!important;padding:0!important;border:0!important;border-radius:0!important;background:#000!important;}
#map, #map.map-wrap {height:100%!important;margin:0!important;padding:0!important;}
#map svg {height:100%!important;width:100%!important;background:#000!important;border:0!important;border-radius:0!important;}
#tip {background:#161c1c!important;color:#e5eceb!important;}
</style>
"""
BIOCLIP_EARLY_SCRIPT = r"""
<script>
// À l'intérieur du proxy BioCLIP uniquement : redirige les API vers le proxy.
(function(){
 const oldFetch=window.fetch.bind(window);
 window.fetch=function(resource, options){
   if(typeof resource==='string' && (resource.startsWith('/api/') || resource.startsWith('/thumb/'))){
     resource='/bioclip'+resource;
   }
   return oldFetch(resource,options);
 };
})();
</script>
"""
BIOCLIP_MAP_SCRIPT = r"""
<script>
(function(){
  const start=()=>{
    const st=document.getElementById('showText');
    const jt=document.getElementById('joint');
    if(st) st.checked=true;
    if(jt) jt.checked=true;
    if(typeof showTab==='function') showTab('map');
    // Garder le panneau sur la carte au clic des points, tout en conservant le survol.
    const map=document.getElementById('map');
    if(map) map.addEventListener('click', function(e){
      if(e.target.closest && e.target.closest('circle[data-i]')){
        e.preventDefault();e.stopImmediatePropagation();
      }
    },true);
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
</script>
"""

def bioclip_html_map_only(html):
    """Transforme uniquement la copie HTTP de la page, jamais les fichiers BioCLIP."""
    # L'application BioCLIP utilise les URL absolues /thumb/ pour ses images.
    html = html.replace('return "/thumb/"', 'return "/bioclip/thumb/"')
    html = html.replace('</head>', BIOCLIP_MAP_STYLE + BIOCLIP_EARLY_SCRIPT + '\n</head>', 1)
    html = html.replace('</body>', BIOCLIP_MAP_SCRIPT + '\n</body>', 1)
    return html

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


    def proxy_bioclip(self, method='GET'):
        path=urlparse(self.path).path
        if not (path == '/bioclip' or path.startswith('/bioclip/')):
            self.send_error(404)
            return
        upstream_path = path[len('/bioclip'):] or '/'
        query = urlparse(self.path).query
        url = BIOCLIP_ORIGIN + upstream_path + ('?' + query if query else '')
        try:
            data = None
            if method == 'POST':
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 12 * 1024 * 1024:
                    self.send_error(413, 'Requête BioCLIP trop grande ou vide')
                    return
                data = self.rfile.read(length)
            headers = {}
            if data is not None:
                headers['Content-Type'] = self.headers.get('Content-Type','application/json')
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                response = urllib.request.urlopen(request, timeout=45)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read()
                code = response.status
                ct = response.headers.get('Content-Type', 'application/octet-stream')
                if method == 'GET' and upstream_path == '/' and code == 200:
                    html = body.decode('utf-8')
                    body = bioclip_html_map_only(html).encode('utf-8')
                    ct = 'text/html; charset=utf-8'
                self.send_response(code)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                self.wfile.write(body)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            self.send_json({'error':f'BioCLIP : serveur 8766 indisponible ({error})'}, 502)
        except (ValueError, UnicodeDecodeError) as error:
            self.send_json({'error':f'BioCLIP : réponse invalide ({error})'}, 502)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/bioclip' or path.startswith('/bioclip/'):
            return self.proxy_bioclip('POST')
        if path != '/api/biome':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 4096:
                self.send_json({'error': 'Corps trop grand ou absent'}, 400)
                return
            raw = json.loads(self.rfile.read(length))
            biome = raw.get('biome')
            if biome not in BIOME_IDS:
                self.send_json({'error': 'Biome inconnu'}, 400)
                return
            x = float(raw.get('x', 0.5))
            y = float(raw.get('y', 0.5))
            if not (0 <= x <= 1 and 0 <= y <= 1):
                self.send_json({'error': 'Coordonnées hors de [0,1]'}, 400)
                return
            with STATE_LOCK:
                previous = biome_state()
                # Une action ne relance C2 que si le biome sélectionné a changé.
                obj = {'biome': biome, 'x': x, 'y': y,
                       'version': int(time.time_ns()) if previous['biome'] != biome else previous['version']}
                write_biome_state(obj)
            self.send_json(obj)
        except (ValueError, TypeError, KeyError):
            self.send_json({'error': 'État invalide'}, 400)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/bioclip' or path.startswith('/bioclip/'):
            return self.proxy_bioclip('GET')
        if path == '/api/status':
            manifest, video = load_manifest(), latest_video()
            version = None
            if video:
                st = video.stat()
                version = f'{st.st_mtime_ns}-{st.st_size}'
            self.send_json({
                'c1': {'ready': bool(manifest), 'version': manifest.get('version') if manifest else None},
                'c2': {'ready': bool(video), 'version': version, 'filename': video.name if video else None},
                'bioclip': {'ready': False},
                'biome': biome_state()
            })
            return
        if path == '/api/biome':
            self.send_json(biome_state())
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
