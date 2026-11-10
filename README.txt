HOLOCHLORIS — INTERFACE P5.JS + CARTE LOCALE 8766
=================================================

Fichiers complets : index.html, sketch.js, style.css, server.py, config.json.

INSTALLATION :
1. Faire une copie de sauvegarde de C:\holochloris_web_p5\index.html, sketch.js, style.css, server.py, config.json.
2. Décompresser puis copier les cinq fichiers dans C:\holochloris_web_p5\.
3. NE PAS remplacer/supprimer le dossier C:\holochloris_web_p5\output\.
4. Démarrer l'application locale de carte sur http://127.0.0.1:8766 dans sa propre fenêtre terminal.
5. Démarrer la projection : cd C:\holochloris_web_p5 ; py server.py
6. Ouvrir http://127.0.0.1:8765 et actualiser avec Ctrl+F5.

C1 : les trois bandes 450/550/680 nm du manifeste output/c1/c1_sequence.json, cycle 1,2 s.
C2 : dernier MP4 ComfyUI du dossier Documents/ComfyUI/output, lecture en boucle.
Bas : iframe intégrant l'application HTTP 8766.
L'iframe nécessite que 8766 autorise son intégration (pas de X-Frame-Options DENY / CSP frame-ancestors bloquant).
Le pont postMessage reçoit les messages HOLOCHLORIS_BIOME de 8766,
mais NE reparamètre PAS ENCORE MST++ ni ComfyUI.
Pour envoyer une sélection depuis le code de 8766 :
window.parent.postMessage({type:'HOLOCHLORIS_BIOME',biome:'tundra',x:0.5,y:0.25}, 'http://127.0.0.1:8765');

ATTENTION : la règle de 5 mm est nominale et nécessite une calibration réelle de la caméra/microscope.
La règle de C2 ne représente pas une mesure de la morphologie spéculative.
Le navigateur doit avoir accès au CDN p5.js.
