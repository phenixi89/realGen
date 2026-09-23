# Reel Pipeline — OpusCV

Pipeline automatique de génération de reels TikTok/Instagram pour OpusCV (SaaS d'optimisation de CV) :
scénario + choix d'angle (Gemini) → voix off (Gemini TTS) → démo écran (Playwright) → sous-titres (Whisper) → montage final (FFmpeg, musique + CTA mis en avant).

## Installation locale

Rapide, via le script d'installation :

```bash
./setup.sh
# renseigne .env (créé depuis .env.example au premier lancement), puis relance ./setup.sh
```

`setup.sh` crée le venv, installe les dépendances Python + Chromium (Playwright), vérifie ffmpeg
et affiche la commande de lancement. Ou manuellement :

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

# ffmpeg doit être installé sur la machine (brew install ffmpeg / apt install ffmpeg)

cp .env.example .env
# renseigne les variables ci-dessous dans .env, puis :
export $(cat .env | xargs)
```

### Variables d'environnement (`.env`)

| Variable | Obligatoire | Description |
|---|---|---|
| `GEMINI_API_KEY` | oui | Clé API Gemini — [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `SAAS_URL` | oui (ou `--saas-url`) | URL de démo d'OpusCV |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | selon le parcours | Identifiants du compte de démo (connexion réelle capturée) |
| `GEMINI_MODEL` | non | Modèle texte (défaut : `gemini-flash-latest`) |
| `GEMINI_TTS_MODEL` | non | Modèle voix off (défaut : `gemini-2.5-flash-preview-tts`) |
| `ALLOW_AI_QUOTA_FEATURES` | non | `1` pour inclure la simulation d'entretien IA (consomme le quota IA du compte démo) |

## Utilisation

Pipeline complet :

```bash
python scripts/run_pipeline.py --n 3 --saas-url https://tonapp.com/demo --voice Kore --capture-mode screenshots
```

Principales options de `run_pipeline.py` :

| Option | Défaut | Description |
|---|---|---|
| `--n` | 3 | Nombre de reels à générer (ignoré avec `--scenario`) |
| `--duration` | 30 | Durée cible de chaque reel, en secondes |
| `--capture-mode` | `video` | `screenshots` (captures nettes composées, recommandé — voir ci-dessous), `video` (enregistrement mobile continu), `video_desktop` (enregistrement desktop recadré par fonctionnalité) |
| `--voice` | Kore | Voix TTS Gemini |
| `--angle` | — | Impose un angle marketing (sinon choisi stratégiquement, voir plus bas) |
| `--scenario` | — | Fichier JSON de scénario écrit à la main (voir `scenarios/exemple.json`) |
| `--from-step` | — | Reprend à partir d'une étape (`script`/`voice`/`video`/`subs`/`assemble`) sans tout regénérer |
| `--force` | — | Régénère tout depuis zéro |

**`--capture-mode screenshots` est recommandé** : chaque fonctionnalité (formulaire, modale, panneau)
est capturée individuellement puis composée proprement (carte nette + fond flouté, zoom Ken Burns,
transitions), au lieu d'un enregistrement continu qui peut laisser de grandes zones vides quand
l'app garde une mise en page étroite même en résolution desktop.

Ou étape par étape :

```bash
python scripts/1_generate_script.py --n 3 --out output/scripts.json
python scripts/2_generate_voice.py --scripts output/scripts.json --voice Kore --out output/audio
python scripts/3_record_demo.py --url https://tonapp.com/demo --out output/video/reel_01 --mode screenshots
python scripts/4_generate_subtitles.py --audio output/audio/reel_01.mp3 --scripts output/scripts.json --index 1 --out output/subs/reel_01.json
python scripts/5_assemble.py --video output/video/reel_01/zoom.mp4 --audio output/audio/reel_01.mp3 --subs output/subs/reel_01.json --out output/final/reel_01.mp4
```

Résultat final : `output/final/reel_XX.mp4`, prêt à uploader sur TikTok/Instagram (vertical 9:16,
sous-titres karaoké brûlés, musique de fond, CTA final mis en avant, audio synchronisé).

Entre deux exécutions, `run_pipeline.py` nettoie automatiquement ce qui ne correspond plus à la
demande courante : reels excédentaires d'un run précédent avec un `--n` plus grand, fichiers d'un
`--capture-mode` différent, audio/sous-titres périmés si le texte a changé.

## Ce que génère l'IA (Gemini)

Un seul appel `1_generate_script.py` produit, par reel :

- **Le choix de l'angle marketing** — un appel stratégique dédié sélectionne les angles les plus
  prometteurs parmi le catalogue (`ANGLES` dans le script), en évitant ceux récemment utilisés
  (historique persisté dans `output/angle_history.json`). Le catalogue inclut des angles "tour
  d'horizon" et des angles **killer feature** ciblant une seule fonctionnalité forte (lettre de
  motivation IA, simulation d'entretien, partage par lien, etc.).
- **Le scénario scène par scène** — texte + fonctionnalité montrée à chaque instant, calé ensuite
  sur le timing réel de la voix off (Whisper mesure, jamais le texte affiché).
- **Une offre d'emploi fictive** cohérente avec l'angle, utilisée dans les démos "Adapter à une
  offre" / "Lettre de motivation" (remplace un exemple statique).
- **Un style visuel** (ex. "sobre et corporate") utilisé pour choisir, parmi les thèmes réellement
  affichés par l'app, ceux qui correspondent le mieux au persona du reel.

## Catalogue des fonctionnalités capturables

```bash
python scripts/features.py
```

Liste les fonctionnalités qu'un scénario peut montrer (`checklist`, `fonctions_ia`, `design`,
`entretien`, `partage`, etc.) — c'est ce catalogue que Gemini reçoit pour écrire le scénario.

## Automatisation via GitHub Actions

Le workflow `.github/workflows/generate-reels.yml` tourne chaque lundi (et manuellement via
l'onglet Actions, avec les mêmes options que `run_pipeline.py`).

À configurer dans le repo GitHub (Settings → Secrets and variables → Actions) :
- **Secrets** : `GEMINI_API_KEY`, `DEMO_EMAIL`, `DEMO_PASSWORD`
- **Variable** : `SAAS_URL` (l'URL de démo)

Les vidéos générées sont récupérables dans l'onglet Actions → run → Artifacts. Le service de démo
(Render, cold-start possible) est réveillé en arrière-plan avant la capture, avec retry automatique
si le premier chargement dépasse le délai habituel.

## Notes

- Le modèle TTS Gemini est en statut *preview* côté Google (pas de SLA garanti) — teste régulièrement la qualité de sortie.
- Whisper tourne en CPU (`--model small` par défaut) ; largement suffisant pour des reels de 15-30s.
- Aucun GPU nécessaire pour ce pipeline (pas d'avatar animé, juste du screen-record + montage).
- La musique de fond est synthétisée localement (pas de fichier audio externe) : aucune question de droits.
