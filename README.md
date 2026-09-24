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
| `--voice` | auto | Voix TTS Gemini (`auto` = rotation par reel, `catalog/voix.json`) |
| `--sans-voix` | — | Sans voix off : texte à l'écran + musique |
| `--angle` | — | Impose un angle marketing (sinon choisi stratégiquement, voir plus bas) |
| `--scenario` | — | Fichier JSON de scénario écrit à la main (voir `scenarios/exemple.json`) |
| `--format` / `--theme` / `--hook` | auto | Impose un élément du catalogue (voir « Ligne éditoriale ») |
| `--no-sfx` | — | Sans effets sonores (musique conservée) — case « sfx » dans le workflow |
| `--no-hook-overlay` | — | N'affiche pas l'accroche en grand au début |
| `--anims` | `none` | Animations HTML/JS intégrées au montage : `overlay`, `scene`, `highlight` (séparées par des virgules), `all` ou `none` — voir ci-dessous |
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

## Animations HTML/JS (`--anims`)

Des gabarits d'animation (`assets/anim/*.html`, GSAP embarqué dans `assets/anim/vendor/`) sont
rendus image par image par Playwright (`scripts/render_js_anim.py`), puis intégrés au montage.
Trois modes, cumulables :

| Mode | Gabarit par défaut | Effet | Capture |
|---|---|---|---|
| `overlay` | `score_ats` | Surimpression (jauge du score ATS qui monte de 42 à 94, coches) sur la scène qui parle d'ATS/optimisation, accélérée si besoin pour tenir dans sa scène | tous modes |
| `scene` | `cta` | La dernière scène devient un plan animé plein cadre (logo, titre, bouton), sur fond de sa capture floutée | `screenshots` |
| `highlight` | `highlight` | Cadre lumineux animé autour de la zone montrée, au début de chaque scène (suit le zoom) | `screenshots` |

```bash
python scripts/run_pipeline.py --n 3 --saas-url https://tonapp.com/demo --capture-mode screenshots --anims all
python scripts/run_pipeline.py ... --anims overlay,highlight
```

Le scénario peut placer lui-même les animations et régler leurs textes et valeurs, via les champs
`overlay` et `anim` d'une scène (`true`, `"gabarit?param=valeur"` ou un objet) :

```json
{"feature": "checklist", "texte": "...", "overlay": {"template": "score_ats", "from": 35, "to": 92}},
{"feature": "apercu_cv", "texte": "...", "anim": {"template": "cta", "title": "Ton CV en 2 minutes", "button": "Essaie OpusCV"}}
```

Paramètres des gabarits : `score_ats` (`from`, `to`, `label`, `lines` séparées par `|`, `cta`),
`cta` (`brand`, `title`, `sub`, `button`, `bg`). Pour prévisualiser un gabarit, ouvre simplement le
fichier `.html` dans un navigateur (lecture en boucle) ; pour le rendre à part :

```bash
python scripts/render_js_anim.py --spec "score_ats?from=35&to=92" --out /tmp/frames   # PNG transparents
python scripts/render_js_anim.py --spec cta --duration 4 --out /tmp/cta.mp4
```

Nouveau gabarit : une page 1080×1920 qui charge `vendor/gsap.min.js` et `common.js`, construit une
timeline GSAP en pause et appelle `expose(tl)` (voir `common.js` pour le contrat).

`highlight` a besoin de la position des cartes, enregistrée dans `captures.json` par les captures
récentes : sur des captures plus anciennes, relance avec `--from-step video`.

## Ligne éditoriale : le catalogue (`catalog/`)

Pour éviter que les reels se ressemblent, chaque vidéo combine 4 choix pris dans des fichiers JSON
éditables (aucun code à toucher pour enrichir) :

| Fichier | Contenu | Exemples |
|---|---|---|
| `catalog/formats.json` | **Structure** de la vidéo, catégorie `conseil` (contenu utile) ou `produit` (démo), usage des cartes texte | liste d'erreurs, idée reçue vs réalité, avant/après, astuce, décryptage d'offre, série « 30 jours », démo |
| `catalog/sujets.json` | **De quoi** parle la vidéo, avec des tags croisés avec les formats | titre du CV, ATS, résultats chiffrés, lettre, entretien, LinkedIn… |
| `catalog/hooks.json` | **Style d'accroche** des 2 premières secondes | question choc, chiffre, erreur, contre-intuitif, POV, stop, verdict, scénario catastrophe… |
| `catalog/themes.json` | **Habillage** : couleurs, polices (`assets/fonts/`), style des sous-titres, accord de la musique | violet nuit, corail, vert, bleu corporate |
| `catalog/config.json` | Mix cible (`conseil` 65 % / `produit` 35 %), fenêtres anti-répétition, seuil de similarité, variantes de CTA (`ctas_*`, `cta_anim`), scène preuve, phrases bannies | |

Sélection automatique (`1_generate_script.py`, via `scripts/catalog.py`) :
- le **format** est pris dans la catégorie la plus en retard sur le mix cible, en évitant les derniers utilisés ;
- le **sujet** est choisi par Gemini parmi ceux compatibles avec le format et non traités récemment ;
- l'**accroche** et le **thème** tournent (tirage pondéré par `poids`, sans les plus récents) ;
- une accroche trop proche d'une accroche déjà publiée est refusée et Gemini recommence ;
- tout est historisé dans `output/content_history.json` (persisté entre les runs CI par le cache).

Chaque scénario contient aussi l'**accroche affichée** en grand dès la première image (pas de fondu
depuis le noir), une **légende** et des **hashtags** (écrits dans `output/final/reel_XX.txt`), une
offre d'emploi fictive et un style de CV pour la démo. Les textes sont en français accentué (vérifié :
un script sans accents est renvoyé à Gemini), car les sous-titres affichent le texte exact.

**Promotion de l'outil (~35 à 40 % du contenu)** : en plus des formats `produit` (démo, avant/après
avec OpusCV, défi chronométré, « le recruteur a 6 secondes »), chaque reel `conseil` contient une
**scène preuve** (`"preuve": true`) où le conseil est appliqué en direct dans OpusCV, avec le curseur
qui clique (`preuve_produit` dans `config.json` pour la désactiver). Le CTA dit et le CTA animé
sont tirés parmi plusieurs variantes.

**Originalité** : formats POV, « ce que le recruteur voit vraiment », tier list, red flag / green flag,
quiz « trouve l'erreur » ; Gemini doit apporter un élément concret par scène (exemple de formulation,
cas précis), les conseils génériques de `phrases_bannies` sont refusés, et la dernière phrase répond
à l'accroche pour que la vidéo boucle naturellement.

Les formats `conseil` utilisent des **cartes texte animées** (`assets/anim/carte.html` : styles
`normal`, `mythe`, `realite`, `avant`, `apres`) à la place des captures, en `--capture-mode screenshots`.

Imposer un élément : `--format liste_erreurs`, `--theme vert_confiance`, `--hook pov` (aussi dans le
workflow). Vérifier le catalogue après modification : `python scripts/catalog.py`.

Ajouter par exemple un format : une entrée dans `formats.json` avec `id`, `nom`, `categorie`,
`poids`, `cartes` (`aucune`/`autorisees`/`majoritaires`), `sujets` (tags) et `structure` (consigne
donnée à Gemini ; `{episode}` est remplacé par le numéro d'épisode si `"serie": true`). Option
`habillage` : surimpression sur tout le reel, ex. `"chrono"` (chronomètre, `habillage_params` :
`label`, `from`, `down`).

## Son et effets (`catalog/audio.json`)

- **Musique** synthétisée (aucun droit à gérer) : 10 ambiances (lo-fi piano, pop énergique,
  corporate, tension tech, minimal pulsé, house douce, piano minimal, synthwave, acoustique, trap
  légère), avec 4 instruments (`nappe`, `piano`, `pluck`, `synth`), basses (`pulse`, `808`, `douce`)
  et batterie (kick, snare, hat, clap, shaker). Chaque thème liste ses ambiances compatibles
  (`"ambiances"`), une est tirée par reel sans reprendre les plus récentes. La musique baisse
  automatiquement quand la voix parle.
- **Mastering** : compression douce, normalisation à **-14 LUFS** (niveau de référence TikTok /
  Reels) et limiteur à -1 dBFS : tous les reels sortent au même volume perçu.
- **Effets accordés à l'ambiance** (`"effets"` de chaque ambiance) : volume, tonalité en demi-tons
  (pop, ding, scintillement) et son de transition propres, plus doux en lo-fi, plus nets en tech.
  Pour utiliser de vrais morceaux libres de droits, dépose-les dans `assets/music/<id_ambiance>/`.
- **Mix sobre par défaut** : voix au débit posé (pauses entre les phrases, `ton` des formats),
  musique basse (volume 0,10, baissée de 70 % sous la voix), effets limités aux moments clés
  (3 max par 10 s ; `whoosh`, `click`, `tick`, `buzz`, `riser` dans `bannis`, aucun son de
  transition). Pour un rendu plus nerveux, retirer des effets de `bannis` dans `audio.json`.
- **Effets sonores** calés sur le montage (`scripts/sound_design.py`) : impact sur l'accroche,
  whoosh aux changements de scène, pop à l'apparition d'une carte, clics de clavier, montée de
  tension + impact pour le suspense, ding (réalité/après), buzz (idée reçue/avant), scintillement
  sur le CTA. Garde-fous dans `audio.json` : volumes par effet, écart minimal, maximum par 10 s,
  liste `bannis` pour désactiver un effet.
- **Effets de carte** (`"effet"`, choisi par Gemini) : `standard`, `frappe` (texte tapé au clavier)
  et `suspense` (titre caché puis révélé, un seul par reel).

Écouter : `python scripts/audio_gen.py --ambiance pop_energie --out /tmp/a.wav` ou `--sfx whoosh`.

## Effets visuels et voix

- **Sous-titres** : 4 styles par thème (`sous_titres.style`) : `karaoke` (mot prononcé coloré et
  agrandi), `encadre` (mot prononcé sur une pastille), `boite` (phrase sur un bandeau), `mot` (un
  seul mot à la fois, en très grand). Les **mots-clés** choisis par Gemini (`mots_cles`) s'affichent
  dans la couleur d'accent du thème (`couleurs.mot_cle`).
- **Captures habillées** (`cadre` dans `themes.json`, `navigateur` par défaut) : la capture est posée
  dans une fenêtre de navigateur, avec ombre et liseré, sur un fond aux couleurs du thème.
- **Accroche « pattern interrupt »** : le texte claque (flash, secousse), le mot fort est souligné ;
  la vidéo s'ouvre sur un zoom arrière rapide, puis de petits coups de zoom rythment chaque mot-clé
  prononcé (`--no-punch` dans `5_assemble.py` pour les retirer).
- **Rythme** : un changement de plan toutes les 2,5 à 5 s environ.
- **13 thèmes**, dont verre givré, éditorial magazine, néon nuit, tableau à la craie et affiche
  impact (polices libres Playfair Display, Space Grotesk, DM Sans, Kalam, Bebas Neue).
- **Barre de progression** fine en haut de l'écran, aux couleurs du thème (`--no-progress-bar` dans
  `5_assemble.py` pour la retirer).
- **Fin en boucle** : les dernières images se fondent dans la première (accroche comprise), la
  vidéo s'enchaîne sans coupure → revisionnages (`--no-loop` pour un fondu au noir).
- **Zoom ciblé** : chaque capture zoome vers son bouton d'action (repéré à la capture, `focus`
  dans `captures.json`) au lieu du centre.
- **Curseur animé** (`--anims cursor`) : une flèche vient cliquer sur ce bouton, avec un son de
  clic de souris. Avec `highlight`, les deux alternent d'une scène à l'autre.
- **Transitions par thème** (`transitions` dans `themes.json`, transitions ffmpeg xfade).
- **Nouvelles cartes** (choisies par Gemini) : `chiffre` (nombre qui compte), `comparaison`
  (avant/après sur le même écran), `liste` (points qui se cochent), en plus des cartes texte.
- **Texture** : grain de film léger et particules lentes sur les cartes et le CTA.
- **Voix en rotation** (`--voice auto`, `catalog/voix.json`) et **ton de lecture par format**
  (`ton` dans `formats.json`).
- **Mode sans voix** (`--sans-voix`, case « sans_voix » du workflow) : texte à l'écran + musique,
  pour le public qui regarde sans le son.

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

## Console web (docs/index.html)

Interface pour lancer le workflow, suivre les runs et regarder/télécharger les
reels avec leur légende. Page statique : activer GitHub Pages (Settings → Pages →
branche `main`, dossier `/docs`, dépôt public ou compte payant) ou ouvrir
`docs/index.html` en local. Le token reste dans le navigateur.

### Créer le token GitHub (fine-grained)

Lien direct (dans un navigateur, l'app mobile GitHub n'a pas ce menu) :
https://github.com/settings/personal-access-tokens/new

Chemin manuel : photo de profil (en haut à droite) → **Settings** → tout en bas
du menu de gauche **Developer settings** → **Personal access tokens** →
**Fine-grained tokens** → **Generate new token**.

1. **Token name** : `console realGen`
2. **Expiration** : 90 jours (par exemple)
3. **Repository access** : *Only select repositories* → **realGen**
4. **Permissions** → **Repository permissions** :
   - **Actions** : *Read and write*
   - **Contents** : *Read-only*
5. **Generate token**, copier le `github_pat_...` (affiché une seule fois) et le
   coller dans la console au premier accès.

À l'expiration : en générer un nouveau de la même façon, puis « Déconnexion »
dans la console et coller le nouveau.
