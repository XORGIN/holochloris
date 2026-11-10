CORRECTIF SERVEUR HOLOCHLORIS — C1/C2 ACTUALISATION

1. Arrêter l'ancien serveur : Ctrl+C dans sa fenêtre PowerShell.
2. Sauvegarder l'ancien server.py et config.json si personnalisés.
3. Copier ces deux fichiers dans C:\holochloris_web_p5.
   NE PAS remplacer sketch.js / style.css / index.html / output.
4. Relancer :
   cd C:\holochloris_web_p5
   py server.py
5. Navigateur : http://127.0.0.1:8765/api/status
   Attendu : c1.ready true et c2.ready true (si sorties existantes).
   Vérifier que c1.version augmente et c2.filename change après générations.
6. Page : http://127.0.0.1:8765 (Ctrl+F5). Appuyer sur I pour diagnostic.

Entrées configurées :
 C1 : C:\holochloris_web_p5\output\c1\c1_sequence.json
 C2 : C:\Users\alize\Documents\ComfyUI\output\holochloris-c2-respiration*.mp4

La page met à jour C1/C2 par sondage toutes les 2 secondes.
Le serveur ne remplace pas les générations ; les scripts MST++ et ComfyUI doivent rester lancés.
