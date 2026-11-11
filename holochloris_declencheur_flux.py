"""HOLOCHLORIS C2 : capture MJPEG -> workflow API ComfyUI -> MP4.
Lit le biome sélectionné par la page p5.js avant chaque génération.
Prérequis : ComfyUI lancé, fichier holochloris_stream_api.json dans le même dossier.
"""
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

COMFY_URL = 'http://127.0.0.1:8188'
STREAM_URL = 'http://192.168.8.143:8080/stream.mjpg'
WORKFLOW_FILE = Path(__file__).with_name('holochloris_stream_api.json')
BIOME_FILE = Path(r'C:\holochloris_web_p5\output\state\biome_state.json')
CHECK_INTERVAL = 3.0
# Hypothèses artistiques situées — non des descriptions de la vision authentique des espèces.
BIOME_PROMPTS = {
    'tropical': 'tropical ecological hypothesis, layered microhabitats, diffuse humidity, complex organic interfaces, subtle iridescent pigments',
    'desert': 'arid ecological hypothesis, sparse fine networks, dry porous microtextures, high local contrast, restrained amber and mineral pigments',
    'boreal': 'boreal forest ecological hypothesis, damp fine moss interfaces, diffuse understory lighting, subtle emerald and cyan microtextures',
    'taiga': 'open taiga ecological hypothesis, seasonal light contrast, sparse resilient networks, dark resinous and silver microtextures',
    'tundra': 'tundra ecological hypothesis, low vegetation textures, delicate sparse filaments, cool pale mineral tones, subtle motion',
}
BREATHING = {
    'tropical': (0.018, 0.018, 0.045),
    'desert': (0.008, 0.009, 0.025),
    'boreal': (0.012, 0.018, 0.035),
    'taiga': (0.011, 0.014, 0.030),
    'tundra': (0.006, 0.008, 0.020),
}
# Seed stable pour réduire les différences arbitraires entre nouvelles captures.
SEED = 835284289259173


def biome_actif():
    try:
        state = json.loads(BIOME_FILE.read_text(encoding='utf-8'))
        name = state.get('biome', 'boreal')
        return name if name in BIOME_PROMPTS else 'boreal'
    except (OSError, ValueError, TypeError, AttributeError):
        return 'boreal'


def flux_disponible():
    req = urllib.request.Request(STREAM_URL, headers={'User-Agent': 'HOLOCHLORIS/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            ct = response.headers.get('Content-Type', '').lower()
            return response.status == 200 and 'multipart/x-mixed-replace' in ct and bool(response.read(128))
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def requete_json(path, payload=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(COMFY_URL + path, data=data,
        headers={'Content-Type': 'application/json'} if data else {},
        method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Erreur API ComfyUI {exc.code}: {detail}') from exc


def workflow_pret():
    with WORKFLOW_FILE.open('r', encoding='utf-8') as f:
        workflow = json.load(f)
    if not isinstance(workflow, dict) or not workflow:
        raise ValueError('Le workflow API est vide ou invalide')
    if not any(('stream' in n.get('class_type', '').lower() or 'mjpeg' in n.get('class_type', '').lower())
        for n in workflow.values() if isinstance(n, dict)):
        raise ValueError('Noeud MJPEG absent du workflow API')
    if not any(n.get('class_type') == 'VHS_VideoCombine' for n in workflow.values() if isinstance(n, dict)):
        raise ValueError('Le workflow API ne contient pas Video Combine — exporter C2 Respiration au format API')

    biome = biome_actif()
    # C2: modifier le prompt positif SEULEMENT (id 12 dans ton workflow)
    positive = workflow.get('12')
    if positive and positive.get('class_type') == 'CLIPTextEncode':
        text = positive.get('inputs', {}).get('text', '')
        positive['inputs']['text'] = text + ', ' + BIOME_PROMPTS[biome]
    else:
        print('[C2] Avertissement : prompt positif #12 non trouvé, biome non appliqué au prompt.')

    breathing = workflow.get('28')
    if breathing and breathing.get('class_type') == 'HolochlorisBreathingFrames':
        amplitude, wave, pulse = BREATHING[biome]
        breathing['inputs'].update(breathing_amplitude=amplitude, filament_wave=wave, color_pulse=pulse)
    else:
        print('[C2] Avertissement : respiration #28 non trouvée.')

    for node in workflow.values():
        if isinstance(node, dict) and node.get('class_type') == 'KSampler':
            node.setdefault('inputs', {})['seed'] = SEED
    return workflow, biome


def attendre_fin(prompt_id):
    key = urllib.parse.quote(prompt_id, safe='')
    while True:
        result = requete_json(f'/history/{key}')
        if prompt_id in result:
            record = result[prompt_id]
            status = record.get('status', {})
            if status.get('status_str') == 'error':
                raise RuntimeError(f"Workflow en erreur : {status.get('messages', [])}")
            if status.get('status_str') != 'success':
                raise RuntimeError(f"Exécution non confirmée : {status}")
            return
        time.sleep(1.5)


def main():
    print('HOLOCHLORIS — C2 respiration / biome', flush=True)
    print('Workflow API :', WORKFLOW_FILE, flush=True)
    print('État territorial :', BIOME_FILE, flush=True)
    print('Arrêt : Ctrl+C\n', flush=True)
    if not WORKFLOW_FILE.is_file():
        raise FileNotFoundError(f'Workflow API absent : {WORKFLOW_FILE}')
    iteration = 0
    while True:
        if not flux_disponible():
            print('Flux microscope indisponible : génération en pause.')
            time.sleep(CHECK_INTERVAL)
            continue
        try:
            workflow, biome = workflow_pret()
            result = requete_json('/prompt', {'prompt': workflow})
            prompt_id = result.get('prompt_id')
            if not prompt_id:
                raise RuntimeError(f'Prompt refusé : {result}')
            iteration += 1
            print(f'[{iteration}] C2 respiration, territoire {biome} : {prompt_id}', flush=True)
            attendre_fin(prompt_id)
            print(f'[{iteration}] MP4 / génération terminée.', flush=True)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print('ComfyUI inaccessible :', exc)
            time.sleep(CHECK_INTERVAL)
        except (RuntimeError, ValueError) as exc:
            print(exc)
            print('Arrêt : vérifie le workflow API avant de relancer.')
            break


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nAutomatisation arrêtée.')
