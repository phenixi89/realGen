# Reel Pipeline — SaaS CV

Pipeline automatique de génération de reels TikTok/Instagram pour un SaaS de CV :
script (Gemini) → voix off (Gemini TTS) → démo écran (Playwright) → sous-titres (Whisper) → montage final (FFmpeg).

## Installation locale

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

# ffmpeg doit être installé sur la machine (brew install ffmpeg / apt install ffmpeg)

cp .env.example .env
# renseigne GEMINI_API_KEY dans .env, puis :
export $(cat .env | xargs)
```

## Étape indispensable avant utilisation

Ouvre `scripts/3_record_demo.py` et remplace les commentaires d'exemple
dans `play_demo_steps()` par les vrais sélecteurs CSS/texte de ton produit
(le champ à remplir, le bouton "Générer mon CV", le sélecteur du résultat, etc.).
Sans ça, la vidéo enregistrée sera un simple scroll de la page.

## Utilisation

Pipeline complet (3 reels d'un coup) :

```bash
python scripts/run_pipeline.py --n 3 --saas-url https://tonapp.com/demo --voice Kore
```

Ou étape par étape :

```bash
python scripts/1_generate_script.py --n 5 --out output/scripts.json
python scripts/2_generate_voice.py --scripts output/scripts.json --voice Kore --out output/audio
python scripts/3_record_demo.py --url https://tonapp.com/demo --out output/video
python scripts/4_generate_subtitles.py --audio output/audio/reel_01.mp3 --out output/subs/reel_01.srt
python scripts/5_assemble.py --video output/video/xxx.webm --audio output/audio/reel_01.mp3 --subs output/subs/reel_01.srt --out output/final/reel_01.mp4
```

Résultat final : `output/final/reel_XX.mp4`, prêt à uploader sur TikTok/Instagram (vertical 9:16, sous-titres brûlés, audio synchronisé).

## Automatisation via GitHub Actions

Le workflow `.github/workflows/generate-reels.yml` tourne chaque lundi
(et manuellement via l'onglet Actions).

À configurer dans le repo GitHub (Settings → Secrets and variables → Actions) :
- **Secret** `GEMINI_API_KEY`
- **Variable** `SAAS_URL` (l'URL de démo de ton SaaS)

Les vidéos générées sont récupérables dans l'onglet Actions → run → Artifacts.

## Notes

- Le modèle TTS Gemini est en statut *preview* côté Google (pas de SLA garanti) — teste régulièrement la qualité de sortie.
- Whisper tourne en CPU ici (`--model base`) ; largement suffisant pour des reels de 15-30s.
- Aucun GPU nécessaire pour ce pipeline (pas d'avatar animé, juste du screen-record + montage).
