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
| `SAAS_URL` | oui (ou `--saas-url`), sauf `--capture-mode aucune` | URL de démo d'OpusCV |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | selon le parcours | Identifiants du compte de démo (connexion réelle capturée). Un compte Pro évite le filigrane « OPUSCV.TECH » du plan gratuit sur l'aperçu capturé |
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
| `--duration` | 25 | Durée cible de chaque reel, en secondes |
| `--capture-mode` | `video` | `screenshots` (captures nettes composées, recommandé — voir ci-dessous), `video` (enregistrement mobile continu), `video_desktop` (enregistrement desktop recadré par fonctionnalité), `aucune` (sans capture de l'app — voir « Mode sans captures ») |
| `--voice` | auto | Voix TTS Gemini (`auto` = rotation par reel, `catalog/voix.json`) |
| `--sans-voix` | — | Sans voix off : texte à l'écran + musique |
| `--angle` | — | Impose un angle marketing (sinon choisi stratégiquement, voir plus bas) |
| `--scenario` | — | Fichier JSON de scénario écrit à la main (voir `scenarios/exemple.json`) |
| `--format` / `--theme` / `--hook` | auto | Impose un élément du catalogue (voir « Ligne éditoriale ») |
| `--registre` | auto | `serieux` ou `humour` (sinon mix de `config.json` `registres`, 70 / 30) — voir « Registre humour » |
| `--plan` | — | Combinaison imposée reel par reel (JSON, remplace `--n`) — voir « Combinaison par reel » |
| `--plateformes` | `all` | Déclinaisons produites : `tiktok` (légende `.txt`), `instagram` (légende Instagram + couverture), `carrousel` (carrousel 4:5), séparées par des virgules — voir « Instagram » |
| `--no-sfx` | — | Sans effets sonores (musique conservée) — case « sfx » dans le workflow |
| `--no-hook-overlay` | — | N'affiche pas l'accroche en grand au début |
| `--anims` | `none` | Animations HTML/JS intégrées au montage : `overlay`, `scene`, `highlight` (séparées par des virgules), `all` ou `none` — voir ci-dessous |
| `--from-step` | — | Reprend à partir d'une étape (`script`/`voice`/`video`/`subs`/`assemble`) sans tout regénérer |
| `--force` | — | Régénère tout depuis zéro |

**`--capture-mode screenshots` est recommandé** : chaque fonctionnalité (formulaire, modale, panneau)
est capturée individuellement puis composée proprement (carte nette + fond flouté, zoom Ken Burns,
transitions), au lieu d'un enregistrement continu qui peut laisser de grandes zones vides quand
l'app garde une mise en page étroite même en résolution desktop.

Les enregistrements vidéo (`video`, `video_desktop`) se font à la taille CSS de la fenêtre : Playwright
n'agrandit pas l'image (une taille supérieure la laissait dans le coin haut gauche d'un cadre gris).
La vidéo mobile (405×720) est ensuite agrandie en 1080×1920 par ffmpeg, donc moins nette que les
captures du mode `screenshots`.

### Mode sans captures (`--capture-mode aucune`)

Aucune connexion à l'app ni compte de démo : le reel est fait uniquement de plans animés.

- **Formats** : seulement les formats conseil qui ont des cartes (`catalog.sans_captures_ok`), une démo
  produit sans image du produit ne montrerait rien ; `--format` d'un autre format est refusé.
- **Scénario** : Gemini écrit une carte animée pour chaque scène sauf la 1re et la dernière. Il n'y a pas de
  champ `feature`. La 1re scène porte `"illustration": "<id d'icône>"` : une icône dessinée à la main
  (`assets/anim/illustration.html`) sous l'accroche. La dernière scène est le CTA animé.
- **Secours** : une scène restée sans carte reçoit une carte texte (sa 1re phrase), sinon au montage
  un plan illustré titré.
- **Scénario écrit à la main** (`--scenario`) : la même forme, sans `feature` ; format par défaut
  `liste_erreurs`.
- **Reprise** : changer de mode (avec ou sans captures) régénère les scénarios (champ `sans_captures`
  de `scripts.json`).

```bash
python scripts/run_pipeline.py --n 3 --capture-mode aucune
```

Ou étape par étape :

```bash
python scripts/1_generate_script.py --n 3 --out output/scripts.json
python scripts/2_generate_voice.py --scripts output/scripts.json --voice Kore --out output/audio
python scripts/3_record_demo.py --url https://tonapp.com/demo --out output/video/reel_01 --mode screenshots
python scripts/4_generate_subtitles.py --audio output/audio/reel_01.mp3 --scripts output/scripts.json --index 1 --out output/subs/reel_01.json
python scripts/5_assemble.py --video output/video/reel_01/zoom.mp4 --audio output/audio/reel_01.mp3 --subs output/subs/reel_01.json --out output/final/reel_01.mp4
```

Résultat final : `output/final/reel_XX.mp4`, prêt à uploader sur TikTok et en Reel Instagram (vertical 9:16,
sous-titres karaoké brûlés, musique de fond, CTA final mis en avant, audio synchronisé)., avec à côté ses déclinaisons (voir « Instagram ») :
`reel_XX.txt` (légende TikTok), `reel_XX.instagram.txt`, `reel_XX.couverture.jpg` et le dossier
`reel_XX_carrousel/`.

Entre deux exécutions, `run_pipeline.py` nettoie automatiquement ce qui ne correspond plus à la
demande courante : reels excédentaires d'un run précédent avec un `--n` plus grand, fichiers d'un
`--capture-mode` différent, audio/sous-titres périmés si le texte a changé.

## Animations HTML/JS (`--anims`)

Des gabarits d'animation (`assets/anim/*.html`, GSAP embarqué dans `assets/anim/vendor/`) sont
rendus image par image par Playwright (`scripts/render_js_anim.py`), puis intégrés au montage.
Trois modes, cumulables :

| Mode | Gabarit par défaut | Effet | Capture |
|---|---|---|---|
| `overlay` | `points_corriger` | Surimpression « N points à corriger » : chaque point se coche et le compteur descend jusqu'à « Prêt à envoyer », sur la scène checklist/optimisation, accélérée si besoin pour tenir dans sa scène. Comme dans le produit, **pas de note globale** : l'ancien `score_ats` (jauge sur 100) reste disponible en gabarit explicite, mais ne décrit plus OpusCV | tous modes sauf `aucune` |
| `scene` | `cta` | La dernière scène devient un plan animé plein cadre (logo, titre, bouton), sur fond de sa capture floutée | `screenshots` |
| `highlight` | `highlight` | Cadre lumineux animé autour de la zone montrée, au début de chaque scène (suit le zoom) | `screenshots` |

```bash
python scripts/run_pipeline.py --n 3 --saas-url https://tonapp.com/demo --capture-mode screenshots --anims all
python scripts/run_pipeline.py ... --anims overlay,highlight
```

Le scénario peut placer lui-même les animations et régler leurs textes et valeurs, via les champs
`overlay` et `anim` d'une scène (`true`, `"gabarit?param=valeur"` ou un objet) :

```json
{"feature": "checklist", "texte": "...", "overlay": {"template": "points_corriger", "lines": "Profil trop court|Mission sans résultat"}},
{"feature": "apercu_cv", "texte": "...", "anim": {"template": "cta", "title": "Ton CV en 2 minutes", "button": "Essaie OpusCV"}}
```

Paramètres des gabarits : `points_corriger` (`lines` séparées par `|`, 5 au plus, `from` = compteur de départ,
`label`, `fin`, `cta`), `score_ats` (`from`, `to`, `label`, `lines` séparées par `|`, `cta`),
`illustration` (`icone`, `titre` optionnel),
`cta` (`brand`, `title`, `sub`, `button`, `bg`), `meme` (`haut`, `bas`, `icone`), `carrousel` (`kind` =
`couverture`/`point`/`fin`, `n`, `total`, `titre`, `texte`, `bouton`), `couverture` (`titre`, `surtitre`, `bg`),
`dialogue` (`repliques`, `gauche`, `droite`, `surtitre`, `bg` : voir « Personnages »).
Image fixe (état final du gabarit, taille libre) : `--out fichier.png --size 1080x1350`. Pour prévisualiser un gabarit, ouvre simplement le
fichier `.html` dans un navigateur (lecture en boucle) ; pour le rendre à part :

```bash
python scripts/render_js_anim.py --spec "points_corriger?lines=Profil%20trop%20court|Titre%20vague" --out /tmp/frames   # PNG transparents
python scripts/render_js_anim.py --spec cta --duration 4 --out /tmp/cta.mp4
```

Nouveau gabarit : une page 1080×1920 qui charge `vendor/gsap.min.js` et `common.js`, construit une
timeline GSAP en pause et appelle `expose(tl)` (voir `common.js` pour le contrat).

### Dessin à la main (`sketch.js`)

Les cartes `schema` et `meme`, le plan `illustration` (mode sans captures) et les annotations sont
**dessinés à la main** : chaque trait se trace
(`stroke-dashoffset`), un feutre (ou une craie) suit la pointe du trait, le texte s'écrit à la plume
(police manuscrite libre Kalam). Le support dépend du thème (`dessin` dans `themes.json`) :

| `dessin` | Rendu | Thèmes |
|---|---|---|
| `papier` | feutre sombre sur une feuille lignée scotchée, traits légèrement tremblés | par défaut |
| `craie` | craie blanche granuleuse sur un tableau vert encadré | `craie_tableau` |
| `neon` | traits lumineux aux couleurs du thème | `neon_nuit`, `verre_givre` |

Le dessin est accéléré (effet « timelapse ») pour être fini à 80 % de la scène, et reste
déterministe (bruit SVG à graine fixe) : deux rendus donnent les mêmes images. Les 33 icônes
dessinables (CV, robot ATS, poubelle, loupe, cible, horloge, ampoule, recruteur, entonnoir,
trophée, fantôme, tasse de café, lune, visage qui rit…) sont dans `assets/anim/icones.js` : ajouter une icône = ajouter une entrée (traits SVG
dans une boîte 100×100 ; JSON strict, validé par `python scripts/catalog.py` et listé à Gemini).

**Annotations au feutre sur les captures** (`assets/anim/annotation.html`, `--annotate` de 3b) :
sur la scène preuve, et sur une autre scène au plus quand le scénario le demande
(`"annotation": "2 à 5 mots"`, écrit par Gemini ou dans un scénario `--scenario`), le bouton montré (`focus`) est entouré au feutre rouge, puis une
flèche dessinée le relie à un post-it manuscrit. L'annotation se pose sur la dernière capture de la
scène (l'écran de résultat), donc après le clic du curseur de la scène preuve. Mode `screenshots`
uniquement.

```bash
python scripts/render_js_anim.py --spec "schema?titre=Le tri ATS&etapes=cv:Ton CV|robot:Le filtre|poubelle:Rejeté&marque=barre&dur=5&dessin=craie" --duration 5 --out /tmp/schema.mp4
```

`highlight` a besoin de la position des cartes, enregistrée dans `captures.json` par les captures
récentes : sur des captures plus anciennes, relance avec `--from-step video`.

### Personnages (`perso.js`, gabarit `dialogue`) — prototype

Deux personnages colorés, dessinés en SVG et animés par GSAP (`assets/anim/perso.js`) : **Léa**
(`femme`, haut rose, cheveux longs, boucles d'oreilles) et **Karim** (`homme`, haut turquoise, lunettes
orange). Style plat avec ombres douces et contours teintés, cadrés en plan taille (buste, bras, tête).
Chacun a 6 expressions (`neutre`, `content`, `choc`, `doute`, `triste`, `agace` : sourcils, yeux et
bouche), 3 gestes (`salut`, `montre` vers l'autre personnage, `hausse` des épaules), bouge la bouche
pendant sa réplique, respire, cligne des yeux et regarde celui qui parle. Tout passe par la timeline :
le rendu est déterministe, comme les autres gabarits.

Le gabarit `dialogue` les fait se parler, une bulle par réplique au-dessus de celui qui parle :
`repliques` = `g:texte {expr,geste}|d:texte|…` (`g` = gauche, `d` = droite, `{expr,geste}` optionnel,
6 répliques au plus), `gauche` / `droite` (id du personnage, `femme` et `homme` par défaut), `surtitre`,
`bg` + thème. Chaque réplique dure 0,9 s + 0,28 s par mot (entre 1,4 et 4 s).

```bash
python scripts/render_js_anim.py --spec "dialogue?surtitre=En entretien&repliques=g:Tu as postulé à combien d'offres ? {doute}|d:Cinquante. Zéro réponse. {triste,hausse}" --duration 7 --out /tmp/dialogue.mp4
```

Pas encore branché au générateur de scénarios (ni bouche synchronisée sur la voix off, ni effets
sonores) : à utiliser en rendu manuel pour tester le rendu. Ajouter un personnage = ajouter une entrée
à `PERSOS` dans `perso.js` (couleurs, coiffure `longs`/`courts`, accessoire `boucles`/`lunettes`).

## Ligne éditoriale : le catalogue (`catalog/`)

Pour éviter que les reels se ressemblent, chaque vidéo combine un **registre** (sérieux ou humour) et
4 choix pris dans des fichiers JSON éditables (aucun code à toucher pour enrichir) :

| Fichier | Contenu | Exemples |
|---|---|---|
| `catalog/formats.json` | **Structure** de la vidéo (34 « capsules »), catégorie `conseil` (contenu utile) ou `produit` (démo), registres compatibles (`registres`), usage des cartes animées, ton de lecture (`ton`, `ton_humour`) | voir le tableau ci-dessous |
| `catalog/sujets.json` | **De quoi** parle la vidéo (151 sujets, 13 familles), avec des tags croisés avec les formats et une **famille** (grand thème) qui tourne | ATS, rédaction du CV, forme du CV, parcours, candidature, lettre, entretien, LinkedIn, organisation de la recherche, métiers (CV de commercial, de développeur, de soignant…), familles produit (dont les nouveautés : 6 mises en page, conversion de langue, chiffres sans invention, sections libres, lettre en PDF…) |
| `catalog/hooks.json` | **Style d'accroche** des 2 premières secondes (25), avec leurs `registres` | question choc, chiffre, erreur, contre-intuitif, POV, stop, verdict, scénario catastrophe ; en humour : autodérision, « Personne : … Moi : … », fausse pub, exagération, réplique absurde, plot twist… |
| `catalog/themes.json` | **Habillage** : couleurs, polices (`assets/fonts/`), style des sous-titres, ambiances musicales, support des dessins (`dessin`), `registres` (absent = tous) | violet nuit, corail, vert, bleu corporate, bande dessinée pop, sitcom pastel… |
| `catalog/config.json` | Mix cible (`conseil` 65 % / `produit` 35 %), mix de registres (`registres` : sérieux 70 % / humour 30 %), règles d'écriture humoristique (`consigne_humour`, `ton_humour`), fenêtres anti-répétition, seuil de similarité, variantes de CTA (`ctas_*`, `cta_anim`), textes Instagram (`instagram`), scène preuve, phrases bannies | |

### Les capsules (`formats.json`)

| Famille | Capsule (`id`) | Principe |
|---|---|---|
| conseil | Liste d'erreurs (`liste_erreurs`) | « 3 erreurs qui te font recaler », une carte par erreur |
| conseil | Idée reçue vs réalité (`mythe_realite`) | idée reçue barrée, puis la réalité |
| conseil | Avant / Après (`avant_apres`) | formulation faible puis réécrite |
| conseil | Astuce express (`astuce_express`) | une astuce actionnable |
| conseil | Décryptage d'offre (`decryptage_offre`) | ce que cache une offre d'emploi |
| conseil | Série 30 jours (`serie_30_jours`) | épisodes numérotés automatiquement |
| conseil | Question de recruteur (`question_recruteur`) | ce que le recruteur veut entendre |
| conseil | Checklist express (`checklist_express`) | points numérotés, liste qui se coche |
| conseil | Top / Flop (`top_bottom`) | ce qui marche / ne marche pas |
| conseil | Cas pratique (`cas_pratique`) | une situation réelle racontée |
| conseil | POV (`pov_situation`) | « POV : tu envoies ta 50e candidature… » |
| conseil | Vu par le recruteur (`vu_par_recruteur`) | ce que tu crois montrer vs ce qu'il comprend |
| conseil | Tier list (`tier_list`) | erreurs classées du rang C au rang S |
| conseil | Red flag / Green flag (`red_green_flag`) | verdicts alternés |
| conseil | Quiz trouve l'erreur (`trouve_erreur`) | ligne piégée puis révélation |
| conseil | Je t'explique au tableau (`tableau_blanc`) | le mécanisme dessiné à la main (cartes schéma), puis la phrase à retenir (carte impact) |
| conseil | Le message du recruteur (`dm_recruteur`) | un échange de messages fictif (carte conversation), puis le décryptage |
| produit | Démo produit (`demo_produit`) | une fonctionnalité réelle par scène |
| produit | Témoignage (`temoignage_produit`) | récit fictif à la 1re personne |
| produit | Avant / Après avec OpusCV (`split_avant_apres`) | comparaison puis le chemin dans l'outil |
| produit | Défi chrono (`defi_chrono`) | chronomètre, CV corrigé en direct |
| produit | Le recruteur a 6 s (`reaction_recruteur`) | décompte, erreur repérée puis corrigée |
| produit | Ton CV au scanner ATS (`scanner_ats`) | scan des mots-clés de l'offre (carte scan), puis l'ajout des manquants dans OpusCV |
| conseil | Débutant, confirmé, expert (`trois_niveaux`) | la même ligne écrite à trois niveaux, jusqu'à la version experte |
| conseil | Vrai ou faux ? (`vrai_ou_faux`) | quiz en 3 affirmations, réponse révélée après une seconde |
| conseil | La question que tout le monde se pose (`question_de_tous`) | réponse tranchée d'abord, puis les nuances concrètes |
| conseil · humour | Le traducteur du jargon (`traducteur_rh`) | « ce qui est écrit » puis « la traduction », pour les offres ou les CV |
| conseil · humour | Sketch : le candidat et le recruteur (`sketch_duo`) | mini-sketch poussé jusqu'à l'absurde, puis « blague à part », le vrai conseil |
| conseil · humour | Attentes vs réalité (`attentes_realite`) | ce que le candidat imagine / ce qui se passe vraiment |
| conseil · humour | Starter pack du CV raté (`starter_pack`) | les éléments typiques, exagérés, puis quoi mettre à la place |
| conseil · humour | Si ton CV pouvait parler (`si_mon_cv_parlait`) | le CV se plaint à la 1re personne de ce qu'on lui fait subir |
| conseil · humour | Format mème « Quand… » (`meme_quand`) | 2 ou 3 cartes mème, chacune suivie du vrai réflexe |
| produit · humour | Moi sous Word vs moi avec OpusCV (`sketch_word_vs_opuscv`) | la galère exagérée, puis la même chose simplement dans OpusCV |
| produit · humour | Commenté comme un match (`commentateur_sportif`) | l'optimisation du CV commentée en direct façon match |

Registres (`registres` du format) : les capsules marquées « humour » ne sortent qu'en registre humour ;
`traducteur_rh`, `trois_niveaux`, `vrai_ou_faux`, `question_de_tous` et plusieurs capsules historiques
(liste d'erreurs, idée reçue, à faire / à ne jamais faire, POV, vu par le recruteur, tier list,
red flag, trouve l'erreur, message du recruteur, le recruteur a 6 s) existent dans les deux registres.

Tester une capsule précise : `--format tier_list` (champ `format` du workflow).

Sélection automatique (`1_generate_script.py`, via `scripts/catalog.py`) :
- le **registre** (sérieux / humour) est le plus en retard sur `config.json` `registres` (mesuré sur les
  10 derniers reels) ; il filtre ensuite formats, accroches et thèmes ;
- le **format** est pris dans la catégorie la plus en retard sur le mix cible (mesuré au sein du registre),
  en évitant les derniers utilisés ;
- la **famille** du sujet (`famille` dans `sujets.json`) tourne : la moins récemment traitée passe en
  premier, celles des `historique_familles` (5) derniers reels sont écartées — l'ATS ou le chiffrage des
  résultats ne reviennent donc plus reel après reel ;
- le **sujet** est choisi par Gemini dans cette famille, parmi ceux compatibles avec le format et non traités
  récemment ; hors des familles ATS / rédaction, le prompt lui interdit de dériver vers l'ATS, les mots-clés
  ou le chiffrage des résultats ;
- l'**accroche** et le **thème** tournent (tirage pondéré par `poids`, sans les plus récents) ; les accroches « Pourquoi… ? » sur une douleur vécue (`question_choc`, `pourquoi_douleur`, poids 3) sont favorisées, les listes, chiffres et « secrets » réduits (poids 0,5) car ils ont moins bien performé ;
- une accroche trop proche d'une accroche déjà publiée est refusée et Gemini recommence ;
- tout est historisé dans `output/content_history.json` (persisté entre les runs CI par le cache).

**Prompt du scénario** (`build_prompt`, `scripts/1_generate_script.py`) : Gemini joue un expert du contenu
viral emploi/recrutement (TikTok, Reels, Shorts) avec des règles strictes : accroche (0-3 s) au tutoiement,
émotion forte (peur de l'échec, curiosité, gain de temps, injustice du recrutement) et chiffre précis si
possible ; corps (3-20 s) problème précis puis solution OpusCV montrée à l'écran, phrases courtes ; CTA
« tester gratuitement » (lien en bio). Sujets dédiés : `meme_cv_50_boites`, `adapter_cv_30_secondes`,
`recruteur_6_secondes`. Garde-fous : chiffres uniquement concrets ou vérifiables (jamais de statistique
inventée), public = candidats (jamais « recruteurs » dans le CTA). Format `tier_list` : Rang S = l'erreur la
plus grave, annoncé dès l'accroche ; `temoignage_produit` : tout à la 1re personne jusqu'au CTA.

**Relance « enregistre »** (`relance_enregistrer` dans `config.json`, activée par défaut) : sur les reels
`conseil` en registre sérieux, la 1re phrase de la scène 2 invite en 5 à 7 mots à enregistrer la vidéo
(« Enregistre-la, tu vas en avoir besoin. »), puis le contenu enchaîne. L'abonnement n'est demandé qu'à
la fin : les CTA `ctas_conseil` associent « abonne-toi » et le test gratuit en bio.

Chaque scénario contient aussi l'**accroche affichée** en grand dès la première image (pas de fondu
depuis le noir), une **légende** et des **hashtags** (écrits dans `output/final/reel_XX.txt`), leurs
équivalents Instagram et le texte du carrousel (voir « Instagram »), une
offre d'emploi fictive et un style de CV pour la démo. Les textes sont en français accentué (vérifié :
un script sans accents est renvoyé à Gemini), car les sous-titres affichent le texte exact.

**Promotion de l'outil (~35 à 40 % du contenu)** : en plus des formats `produit` (démo, avant/après
avec OpusCV, défi chronométré, « le recruteur a 6 secondes », scanner ATS), chaque reel `conseil`
contient une **scène preuve** (`"preuve": true`) où le conseil est appliqué en direct dans OpusCV,
avec le curseur qui clique puis le bouton entouré au feutre avec un post-it (`preuve_produit` dans
`config.json` pour la désactiver). Le CTA dit et le CTA animé
sont tirés parmi plusieurs variantes.

**Originalité** : formats POV, « ce que le recruteur voit vraiment », tier list, red flag / green flag,
quiz « trouve l'erreur » ; Gemini doit apporter un élément concret par scène (exemple de formulation,
cas précis), les conseils génériques de `phrases_bannies` sont refusés, et la dernière phrase répond
à l'accroche pour que la vidéo boucle naturellement ; dès la scène 2, une **boucle ouverte** (révélation promise, tenue vers la fin) retient le spectateur au-delà des 3 premières secondes.

Les formats à cartes affichent des **cartes animées** à la place des captures (en
`--capture-mode screenshots` ou `aucune`), dont Gemini choisit le type selon le contenu :

| Type (`carte.type`) | Gabarit | Effet |
|---|---|---|
| `texte` | `carte.html` | surtitre, titre, texte ; styles `normal`, `mythe`, `realite`, `avant`, `apres` ; effets `standard`, `frappe`, `suspense` |
| `chiffre` | `chiffre.html` | un grand nombre qui compte jusqu'à sa valeur |
| `comparaison` | `comparaison.html` | avant/après sur le même écran, rideau qui révèle l'après |
| `liste` | `liste.html` | 2 à 5 points qui se cochent un par un |
| `schema` | `schema.html` | explication **dessinée à la main** : 1 à 3 icônes reliées par des flèches, légendes manuscrites, marque finale (`barre`, `coche`, `entoure`) |
| `conversation` | `conversation.html` | échange de messages fictif sur un téléphone : « écrit… », bulles qui poussent les précédentes |
| `scan` | `scan.html` | CV passé sous un rayon laser : mots-clés de l'offre trouvés (vert) / manquants (rouge), score final |
| `impact` | `impact.html` | typographie cinétique : la phrase-clé claque mot par mot en très grand, mot fort surligné (une par reel) |
| `meme` | `meme.html` | format mème (registre humour) : la situation en haut, une icône dessinée à la main, la chute qui claque en bas (`haut`, `icone`, `bas`) |

Imposer un élément : `--format liste_erreurs`, `--theme vert_confiance`, `--hook pov`, `--registre humour`
(aussi dans le workflow ; un format imposé sans registre prend un des registres qu'il accepte). Vérifier le catalogue après modification : `python scripts/catalog.py`.

### Combinaison par reel (`--plan`)

`--plan` impose, reel par reel, tout ou partie de la combinaison : une liste JSON d'objets aux clés
`format`, `sujet`, `hook`, `theme`, `voix`, `registre`, `ambiance` (id de `audio.json`) et `angle`
(sujet libre, à la place de `sujet`). Une clé absente ou vide reste automatique (rotation
anti-répétition habituelle) ; une clé renseignée l'emporte sur l'option globale correspondante. Le
nombre de reels est la longueur de la liste. Sujet imposé sans format : le format est tiré parmi ceux
qui acceptent ce sujet. Les ids sont vérifiés avant tout appel IA (`catalog.validate_plan`).

```bash
python scripts/run_pipeline.py --plan '[{"format": "mythe_realite", "hook": "question_choc"},
  {"sujet": "retour_pause", "theme": "editorial", "voix": "Aoede"}, {"registre": "humour"}]'
```

Dans le workflow : champ `plan` (même JSON). La console le construit avec le compositeur (voir
« Console web »).

Ajouter par exemple un format : une entrée dans `formats.json` avec `id`, `nom`, `categorie`,
`poids`, `cartes` (`aucune`/`autorisees`/`majoritaires`), `sujets` (tags) et `structure` (consigne
donnée à Gemini ; `{episode}` est remplacé par le numéro d'épisode si `"serie": true`). Option
`habillage` : surimpression sur tout le reel, ex. `"chrono"` (chronomètre, `habillage_params` :
`label`, `from`, `down`). Options `registres` (`["serieux"]` par défaut, `["humour"]` ou les deux) et
`ton_humour` (ton de lecture quand un format des deux registres est joué en humour).

### Registre humour

Environ 30 % des reels sont écrits sur un ton humoristique (`config.json` `registres`, ou
`--registre humour` pour l'imposer). En registre humour :
- seuls les formats, accroches et thèmes compatibles sont tirés (`registres`), les capsules purement
  humoristiques avec un poids doublé face à celles des deux registres — dont les capsules
  sketch, attentes vs réalité, starter pack, mème, traducteur du jargon, « si ton CV pouvait parler »,
  Word vs OpusCV et le match commenté ;
- Gemini reçoit `consigne_humour` : chaque blague porte un vrai conseil, au moins deux chutes,
  humour bienveillant (on rit des situations, jamais des personnes ; aucun stéréotype, rien de vulgaire) ;
  la scène preuve et le CTA restent ;
- la carte **mème** lui est proposée (situation / icône dessinée / chute) ;
- la voix lit avec le `ton` du format humoristique, ou `ton_humour` (format ou `config.json`) pour un
  format des deux registres ;
- thèmes dédiés : **bande dessinée pop** (`bd_pop`, police Bangers, sous-titres mot à mot) et **sitcom
  pastel** (`sitcom_pastel`, aussi en sérieux), sur l'ambiance **comique sautillante**.

## Instagram (`--plateformes`)

Le même reel vertical 9:16 sert de Reel Instagram ; `scripts/instagram.py` (appelé par
`run_pipeline.py` après l'assemblage) produit en plus, à côté de `output/final/reel_XX.mp4` :

| Plateforme | Fichiers | Contenu |
|---|---|---|
| `tiktok` | `reel_XX.txt` | légende courte + 4 à 6 hashtags |
| `instagram` | `reel_XX.instagram.txt` | légende Instagram (1re ligne accrocheuse visible avant « plus », résumé des conseils, question, invitation à enregistrer) + 5 hashtags au plus (`instagram.hashtags_max`) |
| `tiktok` ou `instagram` | `reel_XX.couverture.jpg` | couverture 1080×1920 : l'accroche en grand sur un fond uni aux couleurs du thème (jamais une capture, illisible une fois réduite dans la grille), texte dans la zone commune aux recadrages de la grille (3:4 et carré). À importer comme couverture à la publication (voir ci-dessous) |
| `carrousel` | `reel_XX_carrousel/01.png…` + `legende.txt` | carrousel 4:5 (1080×1350) : couverture, une idée par diapositive (numéro, barre de progression, « Glisse → »), diapositive finale d'appel à l'action (`instagram.carrousel_fin`) |

**Couverture TikTok** : à la publication, TikTok propose « Modifier la couverture » : choisir une image de la
vidéo ou en importer une depuis la galerie du téléphone (`reel_XX.couverture.jpg`). Sans cela, la grille du
profil affiche une image de la vidéo au hasard, sous-titres compris.

Les textes Instagram et les 4 à 8 diapositives du carrousel sont écrits par Gemini avec le scénario
(`legende_instagram`, `hashtags_instagram`, `carrousel`) ; à défaut (ancien scénario, scénario manuel
sans ces champs), ils sont dérivés de la légende TikTok et des cartes du reel. Les couleurs et polices
sont celles du thème du reel. Refaire seulement les déclinaisons d'un reel :

```bash
python scripts/instagram.py --scripts output/scripts.json --index 1 --final output/final/reel_01.mp4
```

## Son et effets (`catalog/audio.json`)

- **Musique** synthétisée (aucun droit à gérer) : 11 ambiances (lo-fi piano, pop énergique,
  corporate, tension tech, minimal pulsé, house douce, piano minimal, synthwave, acoustique, trap
  légère, comique sautillant), avec 4 instruments (`nappe`, `piano`, `pluck`, `synth`), basses (`pulse`, `808`, `douce`)
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
- **Effets sonores** calés sur le montage (`scripts/sound_design.py`) : impact sur l'accroche et
  la révélation du suspense et la chute d'un mème, pop à l'apparition d'une carte et de chaque message d'une conversation,
  ding (réalité/après, bon score au scan), scintillement sur le CTA, clic de souris du curseur,
  frottement de feutre pendant les dessins et les annotations (`feutre`). Disponibles mais bannis par défaut : whoosh/tick aux
  changements de scène, clics de clavier, buzz, montée de tension. Garde-fous dans `audio.json` : volumes par effet, écart minimal, maximum par 10 s,
  liste `bannis` pour désactiver un effet.
- **Effets de carte** (`"effet"`, choisi par Gemini) : `standard`, `frappe` (texte tapé au clavier)
  et `suspense` (titre caché puis révélé, un seul par reel).

Écouter : `python scripts/audio_gen.py --ambiance pop_energie --out /tmp/a.wav` ou `--sfx whoosh`.

## Effets visuels et voix

- **Sous-titres** : 4 styles par thème (`sous_titres.style`) : `karaoke` (mot prononcé coloré et
  agrandi), `encadre` (mot prononcé sur une pastille), `boite` (phrase sur un bandeau), `mot` (un
  seul mot à la fois, en très grand). Les **mots-clés** choisis par Gemini (`mots_cles`) s'affichent
  dans la couleur d'accent du thème (`couleurs.mot_cle`). La ponctuation isolée par une espace
  (« », :, ?, !) reste collée à son mot : jamais de guillemet seul à l'écran.
- **Captures habillées** (`cadre` dans `themes.json`, `navigateur` par défaut) : la capture est posée
  dans une fenêtre de navigateur, avec ombre et liseré, sur un fond aux couleurs du thème.
- **Accroche « pattern interrupt »** : le texte claque (flash, secousse), le mot fort est souligné ;
  la vidéo s'ouvre sur un zoom arrière rapide, puis de petits coups de zoom rythment chaque mot-clé
  prononcé (`--no-punch` dans `5_assemble.py` pour les retirer).
- **Rythme** : un changement de plan toutes les 2,5 à 5 s environ. Voix au débit posé (≈ 2,6 mots/s,
  budget de mots calculé dessus ; un ton contenant « rapide » compte ≈ 3,4 mots/s).
- **Durée** (25 s par défaut, console et workflow) : 25 s ≈ 65 mots ; 30 s ≈ 78 mots et 6 à 12 scènes ; 45 s ≈ 117 mots et 9 à 18 scènes. Changer la durée
  régénère tout (scénarios, voix, captures), même en reprise.
- **Surimpression points à corriger** (`--anims overlay`) : jamais sur l'accroche, une carte, le CTA, la scène
  preuve, ni dans un reel à habillage (chrono), pour ne rien masquer.
- **15 thèmes**, dont verre givré, éditorial magazine, néon nuit, tableau à la craie, affiche
  impact, bande dessinée pop et sitcom pastel (polices libres Playfair Display, Space Grotesk, DM Sans,
  Kalam, Bebas Neue, Bangers).
- **Barre de progression** fine en haut de l'écran, aux couleurs du thème (`--no-progress-bar` dans
  `5_assemble.py` pour la retirer).
- **Fin en boucle** : les dernières images se fondent dans la première (accroche comprise), la
  vidéo s'enchaîne sans coupure → revisionnages (`--no-loop` pour un fondu au noir).
- **Zoom ciblé** : chaque capture zoome vers son bouton d'action (repéré à la capture, `focus`
  dans `captures.json`) au lieu du centre.
- **Curseur animé** (`--anims cursor`) : une flèche vient cliquer sur ce bouton, avec un son de
  clic de souris. Avec `highlight`, les deux alternent d'une scène à l'autre.
- **Transitions par thème** (`transitions` dans `themes.json`, transitions ffmpeg xfade).
- **9 types de cartes** (choisis par Gemini, voir le tableau des cartes) : texte, chiffre,
  comparaison, liste, schéma dessiné à la main, conversation, scan ATS, typographie cinétique, mème.
- **Dessin à la main** : cartes schéma et annotations au feutre sur les captures (voir « Dessin à
  la main »), sur papier, tableau à craie ou néon selon le thème.
- **Texture** : grain de film léger et particules lentes sur les cartes et le CTA.
- **Contraste automatique** : sur les thèmes à couleur principale claire (jaune craie, cyan néon,
  bleu givré, jaune affiche), le texte posé sur cette couleur (pastilles, accroche, bouton du CTA,
  bulles, mot fort) passe en sombre (`--c1fg` calculé dans `assets/anim/common.js`).
- **Voix en rotation** (`--voice auto`, `catalog/voix.json`) et **ton de lecture par format**
  (`ton` dans `formats.json`, `ton_humour` en registre humour).
- **Mode sans voix** (`--sans-voix`, case « sans_voix » du workflow) : texte à l'écran + musique,
  pour le public qui regarde sans le son.

## Catalogue des fonctionnalités capturables

```bash
python scripts/features.py
```

Liste les fonctionnalités qu'un scénario peut montrer — c'est ce catalogue que Gemini reçoit pour écrire
le scénario. Il suit l'interface actuelle d'OpusCV (septembre 2026) :

- **Le CV** : `checklist` (points à corriger, sans note), `identite`, `experiences` (tiroir des missions),
  `formation`, `competences`, `langues`.
- **Structure** : `structure` (ordre des blocs, langue et format du CV, pied de page), `sections_perso`
  (section libre : certifications…).
- **IA** : `relecture`, `fonctions_ia` (adapter à une offre), `lettre_motivation`, `entretien`.
- **Diffusion** : `convertir` (variante en anglais, allemand, espagnol ou au format Letter), `partage`.
- **Mise en page** : `apercu_pdf` (l'aperçu de l'éditeur est le PDF exact), `design` (41 thèmes en
  pastilles), `mises_en_page` (6 structures, le CV en frise, classique puis minimal),
  `personnalisation` (détails et réglages fins).
- **Affichage** : `mode_sombre`, `apercu_cv`.

Aucune capture ne déclenche d'appel IA, sauf `entretien` (`ALLOW_AI_QUOTA_FEATURES=1`). Le contexte
produit donné à Gemini (`PRODUCT_CONTEXT` dans `1_generate_script.py`) décrit les mêmes fonctions.
Il dit aussi ce que l'outil ne fait pas : pas de score, jamais de chiffre inventé.

## Automatisation via GitHub Actions

Le workflow `.github/workflows/generate-reels.yml` tourne chaque lundi (et manuellement via
l'onglet Actions, avec les mêmes options que `run_pipeline.py`, dont `registre`, `hook`, `plan` et
`plateformes`). Capture par défaut du workflow (et donc du lancement du lundi) : `screenshots`, le seul
mode avec capture qui affiche les cartes animées (`run_pipeline.py` seul garde `video` par défaut).
Les déclinaisons Instagram sont dans l'artefact `output`, sous `final/`.

À configurer dans le repo GitHub (Settings → Secrets and variables → Actions) :
- **Secrets** : `GEMINI_API_KEY`, `DEMO_EMAIL`, `DEMO_PASSWORD` (ces deux derniers inutiles en `capture_mode` `aucune`)
- **Variable** : `SAAS_URL` (l'URL de démo)

Les vidéos générées sont récupérables dans l'onglet Actions → run → Artifacts. Le service de démo
(Render, cold-start possible) est réveillé en arrière-plan avant la capture, avec retry automatique
si le premier chargement dépasse le délai habituel.

## Notes

- La capture ouvre OpusCV **en français** quelle que soit la langue du navigateur (`locale` fr-FR,
  `Accept-Language` et préférence `locale` posée dans le stockage de l'app, `3_record_demo.py`) :
  l'app est traduite et Chromium headless annonce l'anglais, ce qui cassait le parcours (libellés
  français attendus) et aurait filmé une interface anglaise.

- Le modèle TTS Gemini est en statut *preview* côté Google (pas de SLA garanti) — teste régulièrement la qualité de sortie.
- Whisper tourne en CPU (`--model small` par défaut) ; largement suffisant pour des reels de 15-30s.
- Aucun GPU nécessaire pour ce pipeline (pas d'avatar animé, juste du screen-record + montage).
- La musique de fond est synthétisée localement (pas de fichier audio externe) : aucune question de droits.

## Console web (docs/index.html)

Interface pour lancer le workflow (dont le registre et les plateformes), composer les
combinaisons, parcourir le catalogue, suivre les runs
(bouton « 📋 Étapes / logs » : étapes du job avec état et durée, rafraîchies toutes les 15 s ;
log du job une fois celui-ci terminé, limité aux 200 dernières lignes pour un échec, erreurs
en rouge — l'API GitHub ne donne pas le log en direct, pour cela le bouton « GitHub ↗ ») et
regarder/télécharger les reels avec leur légende, et pour chacun ses déclinaisons Instagram
(couverture, carrousel à faire défiler, légende Instagram à copier, images à télécharger). Page statique : activer GitHub Pages (Settings → Pages →
branche `main`, dossier `/docs`, dépôt public ou compte payant) ou ouvrir
`docs/index.html` en local dans un navigateur. Le token reste dans le navigateur. L'aperçu de
fichiers de l'app Claude (ou d'un téléphone) bloque les appels réseau (« Failed to fetch ») :
ouvrir la page dans Chrome, Firefox ou Edge. Si l'onglet Catalogue (et les listes Format,
Thème, Voix) reste vide, la console affiche l'erreur : le plus souvent, le token n'a pas la
permission *Contents : Read-only*. Une erreur inattendue de la page s'affiche en bas de l'écran.

- **Onglet 🚀 Lancer**, en trois zones : 1. l'essentiel (nombre de reels, **accroche** imposée à tous les reels,
  plateformes) ; 2. la composition reel par reel (facultative, ci-dessous) ; 3. les options avancées, repliées
  par défaut (durée, format, thème, registre, voix, capture, animations, reprise, angle, scénario manuel, cases).
  Le bouton « Lancer le workflow » est en bas.
- **Compositeur** (onglet 🚀 Lancer, case « Composer chaque reel moi-même ») : un bloc par reel
  (jusqu'à 10) avec registre, format, sujet (groupés par famille, ou sujet libre), accroche, thème,
  musique et voix. « Auto » laisse le générateur choisir. Les listes ne proposent que les choix
  compatibles (sujet ↔ format, registre ↔ format/accroche/thème, musiques du thème, formats jouables
  en capture `aucune`). Aperçu sous chaque bloc (structure du format, texte du sujet, exemple
  d'accroche, couleurs du thème). 🎲 tire une combinaison compatible, ⧉ duplique. Envoyé au workflow
  dans le champ `plan` ; les champs globaux Nombre, Accroche, Format, Thème, Registre, Voix et Angle sont alors
  masqués. Capture par défaut : « Captures desktop + zoom » (`screenshots`). Un format à cartes
  choisi avec une capture vidéo (`video`, `video_desktop`) affiche un avertissement : ses cartes y
  seraient remplacées par des captures. La composition est mémorisée dans le navigateur.
- **Catalogue** : fiches par type (formats, sujets, accroches, thèmes, ambiances, voix) avec recherche
  et filtres catégorie / registre ; formats : structure, visuel, sujets compatibles (« Voir ses
  sujets ») ; thèmes : nuancier, polices, musiques. « ➕ Composer » ajoute l'élément au compositeur
  (dernier reel si ce champ y est libre, sinon nouveau reel).

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
