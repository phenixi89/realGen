# Reel Pipeline — OpusCV et chaînes faceless

Pipeline automatique de génération de reels TikTok / Instagram / YouTube Shorts, d'abord pour OpusCV (SaaS d'optimisation de CV) :
scénario + choix d'angle (Gemini) → voix off (Gemini TTS) → démo écran (Playwright) → sous-titres (Whisper) → montage final (FFmpeg, musique + CTA mis en avant).
Le même outil fait tourner plusieurs **chaînes** (voir « Chaînes ») : OpusCV (avec captures de l'app) et des chaînes
faceless sans produit — `examen_civique` (révision de l'examen civique) et `psycho` (psychologie du quotidien).

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
| `SAAS_URL` | oui (ou `--saas-url`), sauf `--capture-mode aucune` et chaîne sans produit | URL de démo d'OpusCV |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | selon le parcours | Identifiants du compte de démo (connexion réelle capturée). Un compte Pro évite le filigrane « OPUSCV.TECH » du plan gratuit sur l'aperçu capturé |
| `GEMINI_MODEL` | non | Modèle texte (défaut : `gemini-flash-latest`) |
| `GEMINI_TTS_MODEL` | non | Modèle des voix (défaut : `gemini-3.8-flash-tts`, choisi à l'écoute après le run 58) |
| `GEMINI_TTS_FALLBACK_MODEL` | non | Modèle des voix de secours si le principal reste indisponible (défaut : `gemini-3.1-flash-tts-preview`) |
| `GEMINI_TTS_RPM` | non | Requêtes TTS par minute à ne pas dépasser (défaut : 10, quota du niveau 1) : les appels en rafale sont espacés |
| `ALLOW_AI_QUOTA_FEATURES` | non | `1` pour inclure la simulation d'entretien IA (consomme le quota IA du compte démo) |

## Utilisation

Pipeline complet :

```bash
python scripts/run_pipeline.py --n 3 --saas-url https://tonapp.com/demo --voice Kore --capture-mode screenshots
```

Principales options de `run_pipeline.py` :

| Option | Défaut | Description |
|---|---|---|
| `--chaine` | `opuscv` | Chaîne (`catalog/chaines/<id>/`) : son catalogue, son historique, sa marque — voir « Chaînes ». Une chaîne sans produit impose `--capture-mode aucune` et n'a pas besoin de `--saas-url` |
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
| `--plateformes` | `all` | Déclinaisons produites : `tiktok` (légende `.txt`), `instagram` (légende Instagram + couverture), `carrousel` (carrousel 4:5), `youtube` (titre + description Shorts `.youtube.txt`), séparées par des virgules — voir « Instagram et YouTube » |
| `--no-sfx` | — | Sans effets sonores (musique conservée) — case « sfx » dans le workflow |
| `--no-music` | — | Sans musique de fond (voix et effets conservés) — case « Musique de fond » dans le workflow et la console ; par reel : `"ambiance": "aucune"` dans `--plan` |
| `--no-hook-overlay` | — | N'affiche pas l'accroche en grand au début |
| `--sans-flou` | — | Sans flou de mouvement sur les animations — voir « Cadence et flou de mouvement » ; case « flou » du workflow et de la console (groupe Animations) |
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
  produit sans image du produit ne montrerait rien ; `--format` d'un autre format est refusé. Le format
  **dessin animé** (`dessin_anime`, voir « Dessin animé ») n'existe que dans ce mode : demandé avec
  `--format dessin_anime` ou par un reel de `--plan` (console « Je compose mes reels »), il y bascule tout seul
  pour tout le run (les autres reels du plan sont alors des conseils à cartes) ; il n'est jamais tiré au sort avec captures. Même règle pour le **jeu vidéo** (`jeu_quete`, voir « Format `jeu_quete` »).
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
`dialogue` (`style`, `repliques`, `gauche`, `droite`, `fond`, `surtitre`, `bg` : voir « Gabarit `dialogue` »), `scene` (`scene` :
JSON d'une ou plusieurs scènes, voir « Dessin animé »).
Image fixe (état final du gabarit, taille libre) : `--out fichier.png --size 1080x1350`. Pour prévisualiser un gabarit, ouvre simplement le
fichier `.html` dans un navigateur (lecture en boucle) ; pour le rendre à part :

```bash
python scripts/render_js_anim.py --spec "points_corriger?lines=Profil%20trop%20court|Titre%20vague" --out /tmp/frames   # PNG transparents
python scripts/render_js_anim.py --spec cta --duration 4 --out /tmp/cta.mp4
```

Nouveau gabarit : une page 1080×1920 qui charge `vendor/gsap.min.js` et `common.js`, construit une
timeline GSAP en pause et appelle `expose(tl)` (voir `common.js` pour le contrat).

### Cadence et flou de mouvement

- **30 images/s partout** (`timeline.FPS`, source unique : rendu des gabarits, zoom des captures, enregistrement
  desktop, assemblage final). 25 i/s, la norme de la télévision, saccade légèrement sur un téléphone à 60 Hz. Un gabarit
  qui dépend de la cadence la lit dans l'URL (`?fps=`).
- **Flou de mouvement** (`render_js_anim.py`) : chaque image est la moyenne de trois instants pris à une demi-image
  d'écart (poids 1/4, 1/2, 1/4), comme une caméra dont l'obturateur reste ouvert le temps d'une image. Les éléments fixes
  restent nets, ceux qui bougent vite laissent un léger filé. Les demi-images sont partagées entre images voisines
  (2 prises de vue par image au lieu de 3) et une animation à l'arrêt n'est rendue qu'une fois. Coût mesuré (machine sans GPU, plan de
  1,2 s) : ≈ 2,5 fois le rendu net (1,16 s par image contre 0,46 s), soit environ 40 % de plus par seconde d'animation que l'ancien rendu
  net à 25 i/s grâce à la capture rapide (ci-dessous) ; `--sans-flou` (`run_pipeline.py` ou `render_js_anim.py`, variable `REALGEN_FLOU=0`) le retire.
  Le mélange se fait en alpha pré-multiplié : pas de liseré sombre sur les bords transparents des surimpressions.
  Jamais de flou sur `jeu` (pixel art) ni `scene` (dessin animé, traits qui bouillonnent à la main) : `SANS_FLOU` dans `render_js_anim.py`.
- **Zoom des captures** : courbe en sinus (départ et arrivée ralentis) de 1 à `ZOOM_MAX` (1,12) sur toute la durée du plan,
  plus une ligne droite. Même formule dans ffmpeg (`3b_build_video_from_screenshots.py`) et dans `common.js` (`zoomAt`,
  paramètres d'URL `zoom`, `frames`, `zmax`, `fps`) pour que le souligne, le curseur et l'annotation restent collés à la carte.
  Le zoom suit le bouton visé **en hauteur** mais son décalage latéral est borné (`keep_card_in_view`, marge de 14 px) : la fenêtre
  du navigateur reste entière à l'écran. Au run 89, 4 captures sur 9 perdaient de 40 à 51 px de bord (la fenêtre, presque aussi large que
  l'écran, était poussée hors cadre par la visée sur le bouton) ; pire marge après correction : +13,6 px.
- **Langage de mouvement** (`window.EASE`, `common.js`) : une seule courbe par intention, jamais un réglage propre à un gabarit —
  `entree` (apparition principale, décélérée), `sortie` (plus courte, accélérée), `pop` (petit rebond des moments forts),
  `rebond` (gros rebond joueur : bouton d'appel à l'action, lettres qui tombent) et `doux` (dérive lente du fond). Les valeurs
  viennent du **profil de mouvement de la chaîne** (`catalog/config.json` « mouvements », choisi par `mouvement` dans `chaine.json`,
  transmis aux gabarits en `?ease_entree=…` par `catalog.anim_params`) :

  | Profil | entrée | sortie | pop | rebond | Pour |
  |---|---|---|---|---|---|
  | `dynamique` (défaut) | `power3.out` | `power2.in` | `back.out(1.7)` | `elastic.out(1,.55)` | énergie d'acquisition (OpusCV) |
  | `pose` | `power2.out` | `power1.in` | `back.out(1.1)` | `back.out(1.1)` | sobre, confiance (examen civique) |
  | `fluide` | `expo.out` | `sine.in` | `back.out(1.3)` | `back.out(1.3)` | arrivées longues et soyeuses (psychologie) |

  Un nouveau profil = une entrée dans `config.json`, aucun code (`catalog.py` vérifie les cinq courbes). Les dessins animés
  (`scene.html`, `dessin/*.js`) et le jeu (`jeu.html`) gardent leurs propres courbes. Un nouveau gabarit reprend `EASE`.
- **Capture des images** : par le protocole DevTools avec `optimizeForSpeed` (PNG peu compressé) après un cycle d'affichage, environ
  2 à 4 fois plus rapide que `page.screenshot()` (qui compense largement le coût du flou). Mesuré : aucune image décalée, seuls
  quelques centaines de pixels de bord (texte qui bouge) diffèrent d'un demi-pixel ; repli automatique sur `page.screenshot()`.
- **Contrôle des gabarits** : `python scripts/verif_gabarits.py [gabarit…]` charge chaque gabarit avec chaque profil de mouvement, avance
  l'animation à plusieurs instants et échoue sur toute erreur JavaScript (ce que `py_compile` ne voit pas ; 26 × 3 en ≈ 12 s).
  Un gabarit à planches (`civique`) est chargé une fois par planche (`PLANCHES`, avec des paramètres d'exemple) : une erreur dans
  une planche autre que celle par défaut ne passe plus inaperçue.

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
dans une boîte 100×100 ; JSON strict, validé par `python scripts/catalog.py` et listé à Gemini). Une icône à `"chaines"` est
réservée à ces chaînes (`catalog.icons()` ne la donne qu'à elles, le prompt d'OpusCV reste identique) : les 20 icônes civiques
d'Objectif Civique (drapeau, urne, balance de la justice, mairie, livre ouvert, couronne, plume, mains serrées, école, euro,
croix médicale, bouclier, Hexagone, montagnes, vagues, colombe, alliances, landau, étoiles de l'Europe, bonnet phrygien).

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

### Dessin animé : scènes, fonds et objets (`scene`, `assets/anim/dessin/`)

**Vérification des mouvements (règle permanente)** : toute action d'un personnage est contrôlée, avant publication,
sur une planche d'images successives (pose de départ, anticipation, action, impact, résultat). L'action doit se
comprendre sans le son et paraître humaine : un bras ou une main ne surgit jamais de nulle part, un objet décisif est
assez grand pour se lire (sinon un insert plein écran), le geste découle de l'état psychologique du personnage, et la
tête reste fixe quand il parle sans marcher. Tant qu'un spectateur ne comprendrait pas ce que fait le personnage, on
corrige.

Moteur de dessin animé **pensé par objet, pas par scène** : tout ce qui apparaît est un *objet*
(personnage, animal, objet, élément de décor, fond), et une **scène = un fond + des objets placés + des
actions**. Plusieurs scènes s'enchaînent dans un même rendu (fondu, puis le nouveau décor se dessine,
sans bruit : le feutre qui s'entendait à chaque changement de scène a été retiré).

Style « trait blanc » sur fond noir, dans l'esprit des petites histoires dessinées qui tournent sur TikTok
(sans en reprendre les personnages) : trait principal assuré doublé de fines passes d'esquisse ; cercles qui
ondulent doucement et finissent par un léger dépassement ; deux variantes du dessin alternent environ
6 fois par seconde (traits qui « bouillonnent », **personnages et animaux seulement** : le décor et les objets — tableau,
fenêtre, meubles, plante — ne bougent jamais ; seuls restent animés les effets de lumière et de temps : lampe, vapeur de la
tasse, aiguilles de l'horloge, ville qui défile dans le métro, afficheur d'ascenseur, point d'enregistrement de la visio) ; tout se dessine à l'apparition ; **touches de couleur
légères** (lavis transparent un peu décalé du trait, posé après le dessin, comme une aquarelle). Le décor
de fond est tracé plus fin et plus transparent (profondeur). Bulles **petites et translucides** (fond noir à 58 %, la scène reste visible dessous ; contour irrégulier, queue en deux traits),
sans prénom du personnage, texte et titres manuscrits (Kalam). Déterministe (pseudo-hasard à graine fixe), comme les autres gabarits.

| Fichier | Rôle |
|---|---|
| `dessin/pinceau.js` | trait à main levée, cercles, rectangles, texte manuscrit, lavis de couleur, bouillonnement, apparition ; registre des types (`Dessin.enregistrer`) |
| `dessin/personnages.js` | **Léa** (`lea` : queue de cheval qui se balance avec un chouchou corail, veste cintrée, jupe, cil), **Karim** (`karim` : cheveux courts avec un épi, chemise, cravate bleue, pantalon) et **le recruteur** (`recruteur` : crâne dégarni aux cheveux gris, lunettes rondes, moustache, veste, cravate verte ; voix Charon) |
| `dessin/animaux.js` | `chat` roux (queue qui bouge ; `marcher`/`traverser`, `miauler`, `dormir`) |
| `dessin/objets.js` | `tasse` (orange, qui fume), `telephone` (`vibrer`, `notifier`), `cv` (`corriger`), `ordinateur` (`taper`, `afficher`), `table` (bureau), `table_ronde`, `chaise`, `canape` (deux places), `plante`, `corbeille`, `tampon` (`tamponner`), `horloge`, `cadre` et `calendrier` (`defiler`) (muraux) |
| `dessin/fonds.js` | `vide` (sol, cailloux, herbe, une fleur rose), `bureau` (fenêtre bleutée, livres colorés), `cafe` (suspensions à la lumière chaude, ardoise du menu), `salle_attente` (porte des RH à la plaque orange, affiche « On recrute ! », chaises, horloge qui tourne), `salle_entretien` (fenêtre à stores, tableau blanc, porte-manteau), `salon` (rideaux corail, lampadaire, tableau, tapis), `metro` (la ville défile derrière les vitres, poignées qui se balancent), `visio` (appel vidéo : deux vignettes, point d'enregistrement, boutons), `ascenseur` (portes coulissantes, afficheur d'étage qui monte avec un « ding » à chaque étage, boutons), `open_space` (bureaux et écrans au fond, baie vitrée, suspensions), `bureau_manager` (baie sur la ville au crépuscule, diplômes, bibliothèque, « Direction »), `salon_emploi` (banderole, fanions qui bougent, stands RH / Tech / Vente) ; réservés à Objectif Civique (`"chaines"` dans `dessins.json`) : `mairie` (devise au-dessus du hall, drapeau tricolore, guichet « État civil », panneau d'affichage, plafonnier qui respire), `bureau_vote` (panneau « Bureau de vote », isoloirs à rideau, urne transparente au centre, enveloppes et bulletins), `salle_cours` (tableau vert avec la devise à la craie, affiche de l'Hexagone, rayon de lumière de la fenêtre) |
| `dessin/moteur.js` | assemble les scènes : place les objets, joue les actions, caméra, inserts, bulles, titres, cartons d'ellipse, enchaînement |
| `catalog/dessins.json` | la liste des fonds, objets (ancres, actions), expressions, gestes et actions des personnages |

**Personnages** (de profil, regard retourné par le moteur) : grosse tête ronde, œil blanc plein à pupille
noire et reflet, petit nez, petite bouche qui enchaîne trois ouvertures quand il parle, sourcil seulement
quand l'expression le demande ; bras articulés (épaule, coude) et mains avec doigts, jambes articulées à la
hanche et au genou (marche, position assise). 9 expressions (`neutre`, `content`, `choc`, `doute`,
`triste`, `agace`, `rire`, `soulagement`, `gene`) avec **effets manga** (yeux « ^ » et joues hachurées,
effroi + « ! », goutte de sueur, veine en croix ; rire : grand « D », tête qui sautille et « ha ! » ;
soulagement : yeux mi-clos, petit nuage d'air, épaules qui retombent ; gêne : joue rose, bouche ondulée,
goutte) et des actions : `parler` (bulle), `expression`, `geste`, `marcher` (`vers`), `entrer` /
`sortir` (par la gauche ou la droite), `regarder` (`vers` : côté ou objet), `tenir` (`objet` : le prend
dans la main avant), `poser` (`objet`, `sur`), `boire` (tasse tenue), `telephoner` (téléphone tenu),
`sauter`, `s_asseoir` (`sur` : une chaise ou un canapé ; y marche si besoin et se tourne comme elle ; sur
un canapé, le premier prend la place de gauche, le second celle de droite, tournés l'un vers l'autre),
`se_lever`, `imaginer` (nuage de pensée en haut de l'écran, hors caméra : une icône de
`assets/anim/icones.js` (`image`), une légende de 4 mots au plus (`texte`), une grande croix rouge avec
`"barre": true` ; main au menton pendant), `jeter` (`objet` tenu, `dans` : id d'une corbeille ; boule de
papier en cloche, la corbeille sursaute).
Ancres : `main_avant`, `main_arriere`, `tete`.

**Gestes et postures** (action `geste`, champ `geste` de `parler` — tenu le temps de la réplique — ou
action du même nom avec `duree`, 2,2 s par défaut) : `salut`, `montre`, `hausse`, `explique`,
`bras_croises`, `tete_mains` (désespoir : penché, le visage dans les mains), `idee` (doigt levé, ampoule
jaune qui s'allume au-dessus de la tête), `penser` (main au menton, regard en l'air, petits ronds de
réflexion). **Assis** : un personnage peut commencer assis (`"assis": "id_chaise"` ou un canapé, déclaré
avant lui : il prend sa place et son orientation), avant-bras posés vers l'avant (genoux ou table).

**Caméra** (action sans `qui`) : `{"action": "camera", "cadre": "visage", "sur": "karim"}` ; cadres
`large` (retour au décor entier), `buste` et `visage` (sur un personnage), `objet` (sur un objet, zoom
calculé sur sa taille), `dessous` (contre-plongée : la caméra remonte des pieds au visage, le personnage domine),
`epaule` (par-dessus l'épaule : on regarde `sur`, le personnage `depuis` reste de dos au bord du cadre) ;
`"rapide": true` = coupe sèche avec un petit souffle (`zoom`), `"lent": true` = travelling avant progressif de
3 s (tension qui monte), sinon travelling de 0,55 s. Jouée à l'instant de l'action suivante, sans la retarder ; jamais hors du décor. Les bulles
suivent le cadrage (au-dessus de la tête à l'écran) ; les nuages de pensée, les inserts et les cartons
restent hors caméra.
**Bulles et gros plans** : le contenu d'un insert est descendu sous la zone des bulles (`INSERT_DECALAGE`,
150 px), la réplique dite pendant le gros plan ne le cache plus. Un nuage de pensée se place du côté
que les bulles ouvertes pendant ce temps laissent libre (sinon près de celui qui pense), et ces bulles se
resserrent à 520 px (`BULLE_ETROITE`) pour tenir à côté.

**Split-screen** : l'objet invisible `diptyque` (mural) et son action `comparer` (`titre_gauche` / `texte_gauche` en rouge = ce
qui rate, `titre_droite` / `texte_droite` en vert = ce qui marche, 3 à 12 mots) montrent deux versions d'un même moment
côte à côte (trame « deux lendemains », avant / après).

**Inserts** (gros plan plein écran sur un objet, au-dessus de la scène et sous les bulles, pendant que le
dialogue continue ; bornés à la fin de la scène) : `cv.corriger` (`avant` s'écrit à la main, est barré en
rouge, puis `apres` s'écrit dessous, surligné en vert, avec un « ding »), `tampon.tamponner` (`texte` :
REFUSÉ, ENTRETIEN !… ; `couleur` rouge ou vert ; le tampon s'abat sur un CV), `ordinateur.afficher`
(e-mail : `titre` = objet, `texte`), `telephone.notifier` (écran verrouillé, `heure`, notification :
`titre` = expéditeur, `texte`). Longueurs contrôlées par `catalog.TEXTES_ACTIONS`.

**Ellipse** (champ de scène, à la place de `titre`) : `"ellipse": "Une semaine plus tard…"` (6 mots au
plus) → carton manuscrit en haut pendant ~2,4 s, pages qui s'envolent (son `pages`). Le `calendrier`
mural peut aussi `defiler`.

**Format d'une scène** (JSON ; `{"scenes": [...], "surtitre": "..."}` pour en enchaîner plusieurs) :

```json
{"fond": "cafe", "titre": "Après l'entretien",
 "objets": [{"id": "table", "type": "table_ronde", "x": 540},
            {"id": "tasse", "type": "tasse", "sur": "table.dessus_gauche"},
            {"id": "lea", "type": "lea", "x": 270, "regard": "droite"},
            {"id": "karim", "type": "karim", "x": 810, "regard": "gauche"},
            {"id": "horloge", "type": "horloge", "x": 900, "y": 600}],
 "actions": [{"qui": "karim", "action": "parler", "texte": "Ils m'ont dit : on vous rappelle.", "expr": "triste", "geste": "hausse"},
             {"qui": "lea", "action": "tenir", "objet": "tasse"},
             {"qui": "lea", "action": "boire"},
             {"qui": "karim", "action": "parler", "texte": "Euh… non.", "expr": "choc", "avec": true}]}
```

Objet : `x` (px, 0-1080) au sol, ou `sur` (`id.ancre` : posé sur / tenu par un objet déclaré avant), ou
`y` (px) pour un objet mural ; `regard` (`gauche`/`droite`) ; `echelle` (multiplie celle de la scène,
1,1 par défaut) ; `assis` (personnage : id d'une chaise ou d'un canapé) ; un objet déclaré après un
personnage passe devant lui (le recruteur derrière son bureau). `calendrier` : `jour` (page affichée). Actions jouées dans l'ordre : à la suite de la précédente, en même temps avec
`"avec": true`, ou à `t` secondes du début de la scène ; `{"action": "pause", "duree": 1}` avance le temps.
`expression` peut porter un `geste`, joué en même temps. Scène `"dessine": false` : déjà dessinée à la
1re image (pas de tracé progressif).
Une réplique dure 0,9 s + 0,28 s par mot (entre 1,4 et 4 s) ; la première action démarre après le dessin
du décor (~1,2 s). `catalog.validate_scene_dessin(scene)` vérifie une scène contre `catalog/dessins.json`
(fond, types, ancres, actions, expressions) ; `python scripts/catalog.py` vérifie que le catalogue et le
code correspondent. Ajouter un objet = l'écrire dans `assets/anim/dessin/*.js` (`Dessin.enregistrer`) et le
déclarer dans `catalog/dessins.json`.

```bash
python scripts/render_js_anim.py --spec scene --duration 37 --out /tmp/demo.mp4                    # démo : 3 décors
python scripts/render_js_anim.py --spec scene --scene ma_scene.json --duration 12 --out /tmp/s.mp4  # sa propre scène
```

**Bruitages** : chaque action signale son son à l'instant exact (`Dessin.son(nom, t)`), le moteur les
renvoie (`Scene.monter` → `sons`, publiés dans `window.SONS`) et le montage les mixe (voir « Son et
effets ») : pas à chaque foulée (`marcher`, `entrer`, `sortir`), `saut` puis réception, `chaise`
(s'asseoir, se lever), `pose` (objet posé), `vibreur` (téléphone), `clavier` (ordinateur), `idee`
(ampoule), `miaou` et `ronron` (chat), `froisse` puis `poubelle` (jeter), `tampon`, `notification`
(téléphone, e-mail), `pages` (calendrier, carton d'ellipse), `zoom` (coupe sèche de la caméra), le feutre
de l'écriture dans un insert, un `ding` sur la phrase corrigée et un `buzz` sur la croix d'un nuage de
pensée. Aucun son quand un décor se dessine (changement de scène). En rendu manuel
d'un `.mp4`, la liste est écrite à côté (`.sons.json`).

#### Format `dessin_anime` : le générateur écrit le dessin animé

`--format dessin_anime` (avec `--capture-mode aucune`, imposé automatiquement) : Gemini écrit un mini
dessin animé où **Léa et Karim jouent la situation**. Il reçoit tout le catalogue `dessins.json` (décors,
objets et leurs ancres, actions des personnages et des objets, expressions, gestes, cadres de caméra,
icônes) et des règles de mise en scène (positions au sol, face à face, objets posés ou tenus, personnage
assis) :

- **Série « Karim cherche un job »** (`serie` dans `formats.json` et dans `chaine.json` de la chaîne ; chaque chaîne a
  sa série, ses trames et l'identité de ses personnages) : chaque reel est un
  épisode numéroté (historique de la chaîne, `output/content_history.json` pour OpusCV, gardé d'un run à l'autre par le cache du
  workflow). Gemini rend aussi `resume_episode` (une phrase : ce qui arrive à Karim, où il en est) ; les 5
  derniers résumés sont rappelés à l'épisode suivant (continuité, clins d'œil, pas d'histoire refaite).
  Couverture : surtitre « Karim cherche un job · ép. N » (`serie_titre` du scénario).
- **Un conseil emploi, pas une pub** : le dessin animé donne un vrai conseil de recruteur (négocier,
  démissionner, choisir entre deux offres, premier jour, réseau, entretien, CV…). Sujets du tag `emploi`
  (famille `carriere_emploi`, 14 sujets) en plus des tags CV / candidature / entretien / lettre / LinkedIn.
  Le prompt est celui d'un scénariste + expert marketing (pas d'« informations produit ») : OpusCV n'est cité
  que dans l'appel à l'action final ; un « OpusCV » dans une réplique de l'histoire est refusé par la
  validation (nouvelle tentative).
- **Un problème, une solution, en mots simples** (consigne `DRAMATURGIE` de `1_generate_script.py`) : le reel pose un
  problème précis vécu par le candidat (dans une situation réelle : entretien jeudi, CV sans réponse, offre bizarre), puis UNE
  solution concrète avec la phrase exacte à dire ou écrire entre « guillemets français », puis le résultat montré et une
  chute courte. Langage de tous les jours, réplique de 12 mots au plus, aucun jargon ni « règle du … » inventé ; le
  contexte (qui, quelle situation, quel problème) est donné dans les 2 premières répliques. Karim vit le problème, Léa
  l'aide comme une amie : jamais 3 répliques de suite par le même personnage, « montrer plutôt qu'expliquer ».
- **Accroche = une question** : soit le **titre à l'écran** (`accroche_ecran`, au « tu », 6 mots au plus, ex. « Pourquoi
  personne ne te rappelle ? »), soit la **1re réplique** posée par un personnage dans la situation (« Pourquoi
  personne ne me rappelle ? »). Jamais un slogan ni le titre dit dans une bulle : la bulle est une vraie phrase de la
  scène, qui ne répète pas le titre. Pas de nombre annoncé dans le titre (« 3 conseils », « 2 questions »). Contrôlé par
  `dessin_texte_problems` (nouvelle tentative sinon) ; les accroches `chiffre` et `liste_numerotee` sont exclues du
  dessin animé.
- **Titre seul, une seconde** : le titre n'est plus affiché par-dessus les personnages. Il occupe **tout l'écran seul**
  (fond uni aux couleurs du thème, texte centré très gros, `hook.html` paramètre `plein`, `5_assemble.py --hook-plein`)
  pendant `catalog.TITRE_DESSIN_S` = 1 s, puis la scène de Karim et Léa prend la suite à la coupe. La voix attend : 
  `2_generate_voice.py` ajoute ce silence en tête de l'audio (mesure de vitesse de voix corrigée d'autant), si bien que
  la timeline, les bulles et les bruitages restent calés sur la voix. Une pause de 1,1 s (au lieu de 0,3 s) sépare aussi
  la dernière réplique de l'appel à l'action (`CTA_PAUSE_DESSIN_S`) : la réaction de la chute (gros plan, mains sur la
  tête) reste à l'écran avant que l'écran de fin ne la remplace. 6 mots au plus (`dessin_texte_problems`).
- **Relecture du scénario** : une fois les contrôles de forme passés, un second appel Gemini (`relecture_dessin`) lit le
  titre, les répliques et ce qui est dessiné comme un spectateur qui ne sait rien : il raconte l'histoire en deux phrases
  et signale ce qui ne se comprend pas (rôles flous ou inversés sans explication, réplique qui ne répond pas à la
  précédente, chute à deviner, nombre dit qui ne correspond pas au dessin). Un défaut relance l'écriture (jusqu'à 3
  tentatives, la meilleure est gardée) ; la consigne `DRAMATURGIE` demande la même relecture à l'auteur. Un échec de
  l'appel de relecture n'empêche jamais la génération.
- **Ouverture et solution enseignée** (contrôlés par `dessin_texte_problems`, nouvelle tentative sinon) : la 1re
  réplique fait 8 mots au plus, nomme de qui ou de quoi on parle (pas de « lui », « elle », « ça » sans antécédent) et
  ne partage pas 2 mots clés avec le titre ; aucune réplique ne s'adresse au public (« reste pour… », « abonne-toi »,
  réservés à la dernière scène) ; au moins une phrase exacte entre « guillemets français » est dite, enseignée par le
  personnage qui sait (« Écris plutôt : « … » ») sur un exemple précis et réaliste, puis essayée par l'autre. Pas de
  suspense artificiel : une réplique qui annonce ce qu'elle va dire (« attends la formule exacte », « tu vas voir ») est
  refusée, la phrase est donnée tout de suite ; la chute est une réaction ou un retournement, pas un slogan.
  Les mots sont comptés sans la ponctuation isolée (`nb_mots` : « … ? » ne compte pas pour un mot). Le titre
  à l'écran garde son « ? » collé au dernier mot (espace insécable, `hook.html`).
- **Trame d'histoire** (`trames` du `chaine.json` de la chaîne, une par reel, la moins récemment utilisée ;
  imposable par `--plan` : `"trame"`) : 17 trames : avant / après, ce que pense le recruteur, quiproquo,
  l'erreur en direct, vrai ou faux, le chat juge (running gag), ça aurait pu être pire, la phrase à retenir,
  à la place du recruteur (rôles inversés), dix minutes avant (compte à rebours), deux lendemains, le faux
  conseil, l'enquête, flashback, la répétition générale, le coup de fil surprise (la voix du recruteur au téléphone n'est jamais entendue : seuls Karim et Léa parlent), ce que je ne dis jamais (seuls Karim et le recruteur parlent).
  Ajouter une trame = une entrée `{id, nom, consigne}`, sans code.
- **Chute** obligatoire juste avant le CTA (retournement ou réplique drôle, souvent un gros plan
  `rapide` sur le visage qui réagit).
- **Une scène = un lieu et un moment** : on ne change de scène que si le lieu change ou si des heures
  passent (`ellipse`) ; sinon les plans varient avec la caméra. Deux scènes de suite dans le même décor
  sans ellipse sont fusionnées en une (`fusionner_meme_lieu`, titre de la seconde oublié ; run 61 :
  « Deux minutes après » dans le même salon) : le décor ne se redessine plus pour rien.
- **Répliques dites à voix haute** : pas de « POV » ni de code des réseaux dans une réplique (contrôlé :
  Gemini reformule) ; les accroches `pov` et `personne_moi` (`"dessin": false` dans `hooks.json` : écrites, elles ne se disent pas) n'est jamais tirée pour le
  dessin animé (ni proposée par la console, refusée dans `--plan`). OpusCV n'a que ses fonctions réelles :
  aucun chiffre de performance inventé dans la bouche d'un personnage (« trois variantes en deux clics »).
- **Montrer au lieu de dire** : au moins une mise en scène « cinéma » par reel (`ACTIONS_MISE_EN_SCENE` :
  caméra, `corriger`, `tamponner`, `afficher`, `notifier`, `imaginer`), le CV à l'écran dès que le
  conseil porte sur une formulation ; ni `imaginer` ni `ellipse` en scène 1 (l'accroche occupe le haut).
- **Personnages** : 2 parlent au plus dans tout le reel (Léa et Karim, ou Karim et le recruteur) ; un
  troisième peut être là sans parler. L'appel à l'action est dit par un personnage `principal` (Léa ou
  Karim, `role` dans `dessins.json`), de préférence un qui parle déjà.
- **Scénario** : 1 à ~4 scènes dessinées (`{"fond", "titre" ou "ellipse", "objets", "actions"}`, le même format que
  ci-dessus), puis la scène CTA `{"cta": true, "qui": "lea", "texte": "..."}`. **Tout est dit par les
  personnages** (pas de voix off) : chaque `parler` porte une réplique de 16 mots au plus ; la 1re
  réplique est l'accroche (12 mots max, elle peut être à la 1re personne : « Pourquoi personne ne me
  rappelle ? ») ; `accroche_ecran` reste au « tu ». 2 personnages qui parlent au plus.
- **Contrôle** : chaque scène passe par `catalog.clean_scene_dessin` : objet, ancre, siège, action,
  expression ou geste inconnus sont retirés (le rendu ne casse jamais) et signalés à Gemini, qui corrige
  (3 essais). Corrigé sans le relancer : geste écrit en expression (et l'inverse), action `expr` →
  `expression` ; personnage, animal ou chaise sans `regard` tourné vers le centre ; objet mural sans `y`
  accroché à 700 px ; `boire` / `telephoner` avec un `objet` pas encore en main → `tenir` ajouté avant ;
  objet à main (tasse, ordinateur…) posé par terre → posé sur la table de la scène (sinon retiré),
  et signalé ; support déclaré après ce qu'il porte → objets réordonnés ; geste écrit comme une action
  (`"action": "montre"`) → action `geste` ; action d'objet donnée à un personnage (Léa qui « tape ») →
  rendue à l'objet de la scène qui la sait ; action écrite comme geste (`"geste": "sauter"`) → jouée à
  part, en même temps. Si aucune tentative n'est parfaite, la plus propre (le moins de problèmes) est
  gardée, pas la dernière ; une scène restée sans action visible reçoit alors une posture pour celui qui
  écoute (`penser` après une question, sinon `bras_croises`).
- **Mise en scène exigée** : chaque scène dessinée a au moins une action visible (pas seulement des
  paroles), et le reel au moins 2 actions qui s'entendent (`ACTIONS_BRUITEES` : entrer, marcher,
  s'asseoir, poser, vibrer, taper, miauler, idée…) ; l'accroche parlée n'a ni pourcentage ni statistique ;
  une révélation annoncée doit arriver avant le CTA ; une phrase de CV donnée en exemple ne dicte pas
  de chiffres (« avec TES vrais chiffres »). Un personnage qui joue sans avoir été déclaré dans
  `objets` y est ajouté à la place libre (250, 820 ou 540) au lieu de faire relancer Gemini.
  Le montage repasse chaque scène par ce contrôle (corrections récentes appliquées aux anciens scénarios). Dans `scripts.json`, une scène porte `repliques` (`[{qui, texte}]`), `dessin` (la scène
  jouable) et `texte` (les répliques bout à bout) ; le reel porte `dessin: true` et `voix_personnages`.
- **Voix** : toutes les répliques en **un seul appel** Gemini TTS multi-locuteurs, une voix par
  personnage (`voix` dans `dessins.json` : Léa = Aoede, Karim = Puck). Avec `gemini-3.8-flash-tts`,
  chaque réplique part avec son personnage et son ton (`speech_metadata`) : le ton du reel + celui de
  l'expression du personnage (`voix_expressions` de `dessins.json` : « agacé, un peu sec »,
  « hésitant, perplexe »…). Le modèle de secours (`gemini-3.1-flash-tts-preview`) ne connaît que
  l'ancien format : le dialogue en texte, consigne au format de la doc Gemini (« TTS the following
  conversation… » ; une consigne libre en français a inversé les voix à l'essai). Les répliques sont
  demandées « parlées » (mots de tous les jours, relances, « Attends… », pas de jargon écrit). La
  réplique finale (CTA) vient de l'enregistrement de la voix du personnage qui la dit (voir « CTA
  enregistré »). `audio/reel_XX.voix.json` note le modèle qui a parlé.
- **Contrôle des voix** (`scripts/voix_controle.py`), pour l'ancien format seulement : le modèle y
  devine qui parle et fond parfois tout le dialogue dans une seule voix (run 58 : Karim dit avec la
  voix de Léa). Inutile, et faux, quand chaque réplique porte son personnage : avec un ton par
  réplique, Puck enjoué monte à ~200 Hz, au-dessus d'Aoede au naturel. Après Whisper, chaque réplique doit avoir au
  moins 40 % de ses trames plus proches (en hauteur) de la voix de son personnage que de l'autre ;
  hauteur de référence d'une voix = mesurée sur ses enregistrements de CTA (`assets/voix_cta/`).
  Sinon : nouvelle synthèse du reel (`2_generate_voice.py --index N --force`), puis, si elle échoue
  encore, une synthèse par réplique (`--par-replique`, voix garantie, dialogue un peu moins liant).
  Deux voix de hauteurs trop proches (moins de 25 % d'écart) ne sont pas contrôlées.
- **Caméra au montage** : une action `camera` sans instant prend celui de la réplique qui la suit (un
  gros plan tombe avec la réplique, pas après la précédente).
- **Synchro** : Whisper mesure quand chaque réplique est dite (`repliques` de la timeline,
  `4_generate_subtitles.py`) ; au montage, chaque bulle s'ouvre à cet instant et la bouche bouge le temps
  exact de la réplique (`run_pipeline.dessin_spec`) ; une action qui suit une réplique finissant à
  moins d'1 s de la fin de la scène est jouée pendant la réplique (`"avec": true`), sinon elle ne
  serait jamais vue. Chaque scène devient un plan `scene` de 3b ; la
  dernière est le CTA animé, dit par un personnage.
- **Montage** : pas de sous-titres incrustés (le texte est dans les bulles, `5_assemble.py
  --no-captions`) ; toutes les scènes ont le même cadrage
  (`DESSIN_CADRAGE`, un peu plus petit qu'en rendu libre pour qu'une bulle de 3 lignes reste sous le titre de scène) :
  le titre n'est plus sur la scène, il la précède (voir « Titre seul, une seconde »). Une bulle
  s'efface au plus tard quand la suivante s'ouvre. La 1re scène est complète dès son apparition
  (`"dessine": false`) ; les suivantes se dessinent.
- **Durée** : la vitesse de la voix varie d'un run à l'autre (2,0 mots/s au run 66, 2,8 au run 65 : tout le texte, CTA
  compris). `2_generate_voice.py` mesure donc mots dits / durée de l'audio de chaque dessin animé
  (`output/vitesse_voix.json`, gardé par le cache du workflow) et `1_generate_script.py` cale son budget de mots sur la
  médiane des 6 dernières mesures (bornée à 1,8–2,9 mots/s ; `DIALOGUE_WORDS_PER_SECOND` = 2,3 tant qu'il n'y a pas de
  mesure : 25 s ≈ 58 mots, de 49 à 64), rappelé à Gemini en nombre de répliques de 6 à 8 mots. Le ton de la voix du
  format est vif (répliques enchaînées sans temps mort, une très courte pause avant la chute seulement).
- **Variété** : un **lieu possible** est proposé à chaque épisode (`pick_lieu` : le décor le moins récemment utilisé,
  mémorisé dans `fonds` de l'historique), à n'utiliser que s'il colle à l'histoire ; **au moins un plan original** par
  reel est exigé (cadre `dessous` ou `epaule`, `"lent": true`, ou split-screen `diptyque.comparer`), sinon nouvelle
  tentative.
- **Objet en main** : un personnage qui tient un objet ne fait pas de geste `idee`, `tete_mains` ni `penser` (la main
  monterait devant son visage : téléphone sur l'œil en gros plan) ; le geste est retiré à la validation.
- **Promesse tenue** : ce qu'un personnage annonce (« je te donne la phrase ») est dit mot pour mot plus loin,
  avant la chute.
- **Musique** : le format a ses propres musiques douces (`"ambiances"` dans `formats.json` : jazz de café, bossa,
  ukulélé, boîte à musique, cinéma doux, matinale, acoustique, piano minimal, lo-fi, comique sautillant) : celles du
  thème qui y figurent, sinon celles du format ; jamais de synthwave ni de trap sous un dialogue.

```bash
python scripts/run_pipeline.py --n 1 --format dessin_anime --duration 25
```

### Format `jeu_quete` : un jeu vidéo rétro (`jeu`, `assets/anim/jeu/`)

Une partie de RPG en pixel art qui donne un vrai conseil d'emploi. **Martin** (le héros, voix Fenrir) et **Léa** (sa guide,
voix Aoede) parlent à deux voix comme dans le dessin animé ; le **boss est le système** (le robot qui trie les CV, le
fantôme du ghosting, la paperasse), jamais une personne. Déroulé : titre plein écran 1 s (comme le dessin animé), puis
3 niveaux + l'appel à l'action. (1) le boss apparaît, Martin se trompe et perd un cœur ; (2) Léa lui donne UN réflexe avec
la phrase exacte entre « guillemets » : c'est un **objet obtenu** ; (3) Martin l'utilise, le boss perd de la vie, victoire,
**niveau gagné**, chute-réaction.

- **Rendu** (`assets/anim/jeu.html`) : un écran de 270 × 480 « pixels de jeu » dessiné sur un canvas puis agrandi ×4 sans
  lissage, calculé à partir du temps seul (rendu image par image reproductible). Interface : portrait, cœurs, barre
  d'expérience, bandeau de quête, barre de vie du boss, boîte de dialogue qui s'écrit avec la voix, fenêtres « OBJET OBTENU »,
  « NIVEAU n », « VICTOIRE », secousse d'écran aux coups, lignes de balayage. Police **Press Start 2P** (OFL,
  `assets/fonts/`). Le titre plein écran réduit sa taille pour que le mot le plus long tienne (polices très larges).
- **Catalogue** `catalog/jeu.json` : personnages (`martin`, `lea`), 5 niveaux (`plaine`, `foret`, `donjon`, `ville`, `chateau`),
  3 boss (`robot_trieur`, `fantome`, `paperasse`) et les événements d'une scène ; `catalog.py` vérifie que les ids
  correspondent au code (`niveaux.js`, `persos.js`). Ajouter un niveau ou un boss = un enregistrement dans le code **et** une
  entrée dans `jeu.json`, puis `python scripts/apercus.py` (aperçus `niveaux/` et `boss/`).
- **Scénario** : chaque scène (sauf la dernière, l'appel à l'action) est un niveau `{niveau, boss, quete, repliques,
  evenements}`. Événements : `apparition`, `blessure`, `objet`, `degats`, `xp`, `niveau`, `victoire`, rattachés à une réplique
  (`apres`). `completer_jeu` calcule l'état (cœurs, expérience, niveau, vie du boss) et les valeurs absolues de chaque
  événement ; au montage (`jeu_spec`, `run_pipeline.py`) les répliques sont calées sur la voix et chaque événement tombe juste
  après sa réplique. Les mêmes contrôles que le dessin animé s'appliquent (`dessin_texte_problems` : titre de 6 mots,
  ouverture de 8 mots, phrase exacte, pas de teaser, rien adressé au public) plus ceux du jeu (`jeu_scenes` : un seul boss,
  niveaux différents, enchaînement apparition → blessure → objet → dégâts → victoire → niveau, objet juste après la phrase
  exacte, nom d'objet de 20 caractères au plus, victoire avant les deux dernières répliques du dernier niveau) ; la phrase exacte
  n'invente aucun chiffre précis et la **relecture** du scénario par un second appel (`relecture_dessin`).
- **Son** : bruitages 8 bits synthétisés par `audio_gen.py` (`blip` à chaque réplique, `coup`, `degats`, `blessure`, `objet`,
  `niveau`, `victoire`, `boss`), publiés par la page (`window.SONS`) à l'instant exact ; musiques **chiptune**
  (`chiptune_quete`, `chiptune_boss`, instrument `chip` : ondes carrées étroites). Thèmes `jeu_arcade` et `jeu_donjon`
  (réservés à ce format : `"formats"` dans `themes.json`, `"themes"` dans `formats.json` ; un format qui cite un thème réservé
dans ses `"themes"` y a droit aussi, ex. `question_revision` de la chaîne `examen_civique`), sans sous-titres incrustés (le
  texte est dans la boîte de dialogue).
- Réservé à `--capture-mode aucune` (imposé automatiquement).

```bash
python scripts/run_pipeline.py --n 1 --format jeu_quete --duration 25
```

### Plateau civique (`civique_plateau`, chaîne `examen_civique`)

Un habillage **propre à la chaîne Objectif Civique**, jamais utilisé par OpusCV (thème réservé : `"chaines":
["examen_civique"]` dans `themes.json`, tous les formats de la chaîne n'ont que lui). Gabarit `assets/anim/civique.html`,
dans l'univers du logo « L'Hexagone validé » : plateau de quiz marine, alvéoles d'hexagones qui dérivent, projecteur qui
balaie, bande tricolore en bas, onglet en forme d'hexagone étiré et progression en petits hexagones. Polices Anton
(titres) et Poppins. Planches (`catalog._gabarit_civique`, paramètre `mode`) :

| Carte du scénario | Planche | Ce qu'on voit |
|---|---|---|
| `texte` | `fait` | la phrase mot à mot (mots clés en or, soulignés en tricolore) ; un grand hexagone avec un « ? » si c'est une question, sinon la coche du logo |
| `quiz` | `quiz` | la question, trois réponses en capsules (badges hexagonaux A / B / C), **compte à rebours 3-2-1** dans un hexagone qui se vide, puis la bonne réponse s'allume en vert, les autres s'éteignent |
| `chiffre` | `chiffre` | le nombre dans un hexagone tricolore qui se trace |
| `liste` / `schema` | `liste` / `etapes` | alvéoles qui se cochent / trois étapes numérotées reliées par un trait |
| `comparaison` | `avant_apres` | « IDÉE REÇUE » barrée, puis « EN VRAI » |
| `impact` | `retenir` | « À RETENIR » sur une plaque, tampon hexagone + coche |
| `duel` | `duel` | deux grandes tuiles hexagonales A / B et un « VS » doré, compte à rebours, la bonne tuile passe au vert avec des confettis, l'autre s'efface |
| `intrus` | `intrus` | quatre tuiles ; l'intrus devient rouge et tremble, les trois autres passent au vert (révélation à `DUR - 0,9` s : la voix de la même scène lit les éléments puis pose la question) |
| `relier` | `relier` | deux colonnes de capsules (la droite est décalée), des traits de couleur se tracent un à un pour relier chaque paire |
| `definition` | `definition` | le mot en grand dans un hexagone (les lettres rebondissent une à une ; une expression longue passe sur deux lignes), sa définition sur une plaque « DÉFINITION » |
| `frise` | `frise` | une frise verticale : la ligne se trace, un nœud hexagonal numéroté et une date en grand par jalon |
| `indices` | `indices` | trois indices qui arrivent un à un, un hexagone « ? » qui bat, puis la réponse en plaque avec la coche verte et des confettis |
| `qcm` | `quiz` (4 réponses) | **comme à l'examen** : quatre capsules A / B / C / D plus serrées, compte à rebours, une seule bonne réponse s'allume |
| `citation` | `citation` | une phrase d'un texte officiel **mot pour mot** : plaque crème « MOT POUR MOT », guillemets dorés et grand « en filigrane, lettres à empattement (Playfair Display), la source qui se signe sous un trait tricolore, puis un sceau hexagonal doré tamponné |
| `chapitre` | `chapitre` | un **chapitre de récit** : bandes de cinéma, lumière de projecteur qui vacille, le jour et le mois au-dessus, l'année qui défile comme un compteur puis s'arrête (tic-tac, impact), la phrase mot à mot, l'icône (ou le chiffre romain du chapitre) dessinée dans un hexagone |
| `situation` | `situation` | une **mise en situation** : un viseur de caméra qui se trace avec un point rouge qui clignote, une onde d'alerte rouge qui pulse autour de l'icône, la situation mot à mot sur une plaque, puis « Que fais-tu ? » qui rebondit |
| scène 1 | `accroche` | l'icône dessinée (trait néon) dans l'hexagone, sous l'accroche ; format à `carte_accroche` : la carte de la scène 1 à la place, avec `immediat=1` (pas de fondu d'entrée, la question est là dès la 1re image, les réponses arrivent en moins d'une seconde) |
| dernière scène | `fin` | le logo se trace, « OBJECTIF / CIVIQUE » (dégradé tricolore), titre, sous-titre, bouton « S'ABONNER » |

**Animations communes** : hexagones qui flottent doucement derrière le contenu, **compte à rebours 3-2-1** dans un hexagone
qui se vide (quiz, duel, intrus), **confettis hexagonaux** (tricolores et or) à chaque bonne réponse et sur la définition,
coup de projecteur qui balaie la scène. **Transitions** du thème entre les plans : ouverture en cercle, radial, glissements
doux, pixels, compression (`circleopen`, `radial`, `smoothleft`, `smoothup`, `pixelize`, `squeezeh`).

**Bandeau de série** (`entete`, format à `"entete"`) : une ligne dorée sous l'onglet de chaque carte, précédée d'un trait tricolore
(« EXAMEN CIVIQUE · ENTRAÎNEMENT N°12 ») ; sa taille baisse pour tenir sur une ligne. Le rendez-vous se reconnaît dès la 1re image.

**Mots longs** : les tuiles hexagonales (`quiz`, `duel`, `intrus`) réduisent leur taille de texte jusqu'à ce que leur mot le plus long tienne dans 80 % de leur largeur (`ajusterTuiles`, `civique.html` ; run 90 : « Gouvernement » touchait les deux bords).

**Zone libre** : les sous-titres incrustés occupent le bas de l'écran (à partir de y = 1574 sur 1920) : toutes les planches du plateau gardent leur contenu au-dessus de y ≈ 1500 (note, hexagone, définition, frise, indices, appel à l'action).

**Temps de réflexion** (`pause_reflexion_s` du `config.json` de la chaîne : 2 s pour Objectif Civique depuis la rénovation, 3 s
avant, absent ailleurs) : après une
scène qui pose une question (carte `quiz`, `qcm`, `duel`, `intrus`, `indices`, `relier`, ou scène suivie d'un verdict VRAI / FAUX),
`4_generate_subtitles.py` insère un silence dans la voix (une seule prise TTS, coupée à l'instant le plus calme du blanc entre le
dernier mot de la scène et le suivant, mesuré par fenêtres de 20 ms : jamais dans un mot, `instant_le_plus_calme`) et décale les sous-titres ;
la timeline le note (`reflexion`), `run_pipeline.plan_montage` le passe à la planche, qui y fait son **compte à rebours 3-2-1** et ne
révèle la réponse qu'à la fin de la scène (les traits de `relier` se tracent pendant le silence). Une trace
(`audio/reel_XX.reflexion.json`, datée de l'audio) évite de rallonger deux fois le même audio quand l'étape est refaite. Côté écriture
(`question_problems`, chaîne à temps de réflexion seulement) : la scène d'une carte `quiz`, `qcm` ou `duel` dit la question, **lit
les réponses** et finit par « Réfléchis. » ; un « Réfléchis » dans la scène suivante fait recommencer l'IA. Run 93 : la question
seule, puis « Avril 1792, 1795 ou 1879 ? Réfléchis. » dans la scène d'après, alors que la carte avait déjà allumé 1879 en vert (la
voix n'avait pas encore lu les choix). L'onglet « RÉPONSE » (`suite` d'une `etiquette`) ne suit plus qu'une carte question (il
s'affichait sur le texte qui suivait un chapitre).

**Compter les questions, pas les cartes** (run 96, `serie_flash` : 3 questions, mais « QUESTION 1/5 » et cinq hexagones, parce que les
6 cartes — questions et réponses — étaient comptées, et « QUESTION 2/5 » s'affichait sur la réponse de la question 1). Un format à
`"progression": "questions"` (`serie_flash`, `rappel_revision`) compte seulement les cartes question (`quiz`, `qcm`, `duel`) : le numéro
et les hexagones de progression valent « question k sur K », et la réponse garde la progression de sa question avec l'onglet « RÉPONSE »
(`etiqueter_cartes`, champ `progression` de la carte, lu par `catalog._gabarit_civique`). `question_problems` vérifie aussi que le
nombre annoncé en scène 1 (« 3 questions éclair ») est le nombre de cartes question du reel (réponses purement numériques : dites en
lettres ou en chiffres, pas exigées mot à mot).

**Drapeau `quiz`** : une carte quiz n'est proposée à l'IA que si le format a `"quiz": true`. Run 96 : `serie_flash` demandait des « cartes
quiz » sans ce drapeau, l'IA a écrit des cartes liste (ni A / B / C, ni compte à rebours, ni révélation). Corrigé pour `serie_flash`,
`rappel_revision`, `mot_du_jour`, `frise_dates` et `citation_expliquee` ; `serie_flash` écrit maintenant chaque question en deux scènes
(la carte quiz dont la voix lit les réponses puis « Réfléchis. », puis la réponse), sans relance « enregistre » (`sans_relance`) et dure
40 s au moins (`duree_min`).

Tampon de réponse (`verdict`) : badge hexagonal vert avec coche (VRAI) ou rouge avec croix (FAUX), à 0,45 s. Les sons
(clics des mots, pop, tic-tac du compte à rebours, ding, buzz, coup du tampon) sont **publiés par la page** (`window.SONS`,
lus par `render_js_anim.render_clip`) : rien à recopier dans `sound_design.py`. `run_pipeline.plan_montage` remplace
l'illustration de l'accroche et l'écran d'appel à l'action par les planches `accroche` et `fin` quand le thème du reel a
`"cartes_gabarit": "civique"`. Les dix cartes `duel`, `intrus`, `relier`, `definition`, `frise`, `indices`, `qcm`, `citation`, `chapitre` et `situation` n'existent que pour
les formats à `"cartes_civique": true` (le prompt les décrit alors, `CIVIQUE_CARDS_RULE` ; `catalog.py` impose la chaîne sans
produit et le seul thème `civique_plateau`) ; leurs champs sont nettoyés par `clean_card`, leur texte compte pour le contrôle des
nombres (`faits_problems` : une date de frise absente des faits fait recommencer l'IA) ; la réponse d'une carte `indices` doit être redite dans les scènes suivantes (`civique_problems`, run 84 : réponse « À toi ! », run 85 : « ? » refusé aussi ; run 86 : une carte dont la phrase fait moins de 6 mots, affichée 1 s, fait recommencer l'IA ; run 90 : la scène d'une carte `intrus` doit contenir la question « Lequel est l'intrus ? Réfléchis. », sinon l'IA l'avait dite dans la scène suivante, sur un schéma « Réponse » qui donnait déjà la solution, après la révélation vert/rouge). Un thème imposé (console, `--theme`) incompatible avec les `themes` du format est ignoré avec un avertissement : run 85, `ardoise_indigo` imposé à un format à planches civiques, qui sont alors sorties vides (« Titre de la carte »). `etiquette` d'un format peut être un dictionnaire : un texte par type de carte, `suite` pour la carte qui suit une carte à étiquette propre (« RÉPONSE »), `*` pour les autres (« À RETENIR ») ; `{k}` y est remplacé par le rang de la carte parmi celles de son type (« CHAPITRE {k} » : chapitre 1, 2, 3 ; `etiqueter_cartes`). Carte `citation` : la phrase doit se retrouver telle quelle dans les faits du sujet (`faits_problems`, sinon l'IA recommence) ; carte `qcm` : une mauvaise réponse qui est une date reprend une autre date des faits (le contrôle des nombres s'applique aux quatre réponses). Aperçu de la console : une planche quiz révélée (`apercus.py`).

### Format `cours_eclair` : mini-cours éducatif (thèmes `carnet_cours` et `pop_art`)

Une vidéo éducative de 30 à 35 s, une seule idée : accroche (« 3 choses qui rendent ton CV invisible »), 3
**leçons** d'une phrase de 10 mots au plus (une carte chacune), un **pivot** (pourquoi passer à un outil qui adapte
le CV à chaque offre, sans chiffre inventé sur OpusCV), puis le CTA. Format `cours_eclair` (`formats.json`, drapeau
`quiz: true` = l'IA peut écrire une carte `quiz`), réservé aux deux thèmes ci-dessous (thèmes à `formats` : jamais
tirés ailleurs). Le thème porte `cartes_gabarit` : toutes les cartes du scénario sont dessinées par son gabarit,
avec la **planche** qui correspond à leur type (`catalog.gabarit_carte`) ; `conversation`, `scan` et `meme` gardent
leur gabarit habituel. Texte mot à mot, mots clés entre `*étoiles*` (le mot le plus long de la carte, ou le mot fort
d'une carte `impact`, est mis en valeur automatiquement).

| Type de carte | `carnet_cours` (`lecon.html`, papier à carreaux, surligneur, post-it) | `pop_art` (`pop.html`, comics, rayons, bulles) |
|---|---|---|
| `texte` | `lecon` : phrase écrite, icône, post-it (la phrase de la carte) | `fait` : « FAIT N°n », mots qui claquent, bulle de BD |
| `chiffre` | `chiffre` : gros chiffre entouré au feutre | `choc` : chiffre plein cadre, « BAM ! » |
| `comparaison` | `avant_apres` : l'erreur se barre, la correction arrive | `versus` : deux cases face à face, explosion « VS » |
| `liste` | `liste` : points cochés un à un | `top` : rangs numérotés (3 au plus) |
| `schema` | `etapes` : 3 étapes numérotées reliées | `bande` : 3 cases de BD |
| `quiz` | `quiz` : question, 3 réponses, la bonne passe en vert | `quiz` : grand « ? », 3 réponses, « BRAVO ! » |
| `impact` (pivot) | `lecon` avec l'étiquette « EN RÉSUMÉ » (`resume=1`) | `fait` avec l'étiquette « EN RÉSUMÉ » (`resume=1`) |

- Carte `quiz` : `question` (4 à 9 mots), `reponses` (2 à 3), `bonne` (1..3) ; sans thème éducatif elle devient une
  carte `liste`. Aperçu : `docs/apercus/cartes/quiz.jpg`.
- Format à `"etiquette"` (chaîne `examen_civique`) : l'onglet (carnet) ou le bandeau (comics) affiche ce texte au lieu de
  « LEÇON n/N » (« RÉVISION », « VRAI OU FAUX ? » ; `{n}` et `{total}` remplacés) ; format à `"verdicts"` : une scène dont
  la voix commence par « Vrai » ou « Faux » prend l'étiquette « RÉPONSE » et un **tampon VRAI (vert) / FAUX (rouge)** dès
  0,45 s, avec son coup sonore (`etiqueter_cartes`, paramètres `etiquette` et `verdict` des gabarits, `EDU_VERDICT_AT` de
  `sound_design.py`). Grand chiffre (planches `chiffre` et `choc`) : « 18 ans » garde son espace et la taille baisse pour
  tenir dans la page (run 82 : « 18an » coupé).
- Étiquette « LEÇON n/N » / « FAIT N°n » : les cartes `impact` (pivot) ne comptent pas parmi les leçons, ni, en comics, les
  planches à bandeau propre (`bande` « EN 3 CASES », `versus`, `top`, `quiz`, `choc`) : les numéros se suivent (1, 2, 3)
  (`run_pipeline.carte_numerotee`). La barre de progression est celle du carnet.
- **La voix dit la leçon, la carte en affiche les mots clés** (drapeau `educatif: true` du format, contrôlé par
  `educatif_problems` dans `1_generate_script.py`, qui relance l'IA sinon) : au moins un mot important de la phrase dite
  revient sur la carte. Pas de relance « enregistre » en cours éclair : la scène 2 est déjà la leçon 1 (run 76 : la relance
  l'avait remplacée et les cartes parlaient d'autre chose que la voix). Les teasers restent permis s'ils sont tenus
  (voir « Vérité et cohérence » ci-dessous).
- Sons : `sound_design.educatif_cues` (un clic par mot, pop par point, ding à la bonne réponse, impact sur le chiffre /
  le « VS » / le tampon) ; les instants (`FIRST_AT`, `wordGap`, `gapOf`) sont identiques dans `lecon.html`, `pop.html` et
  `sound_design.py`.
- Palette propre à chaque gabarit ; les couleurs du thème servent aux sous-titres, à la couverture Instagram et au CTA.
- Un gabarit se teste seul : `render_js_anim.py` avec `?mode=quiz&texte=…&points=a|b|c&bonne=2`.
- Lancer : `python scripts/run_pipeline.py --n 1 --format cours_eclair --capture-mode aucune --duration 35`.

### Gabarit `dialogue` : deux personnages qui se parlent

Raccourci pour un dialogue simple : `repliques` = `g:texte {expr,geste}|d:texte|…` (`g` = gauche, `d` =
droite, `{expr,geste}` optionnel, 6 répliques au plus), `gauche` / `droite` (personnage : `femme`/`lea`,
`homme`/`karim`), `surtitre`. Deux styles (`style`) :

- **`trait`** (par défaut) : les répliques deviennent une scène du moteur ci-dessus (fond `fond`, `vide` par
  défaut) ; celui qui écoute revient à une expression neutre.
- **`editorial`** — `assets/anim/perso.js` : deux personnages en **illustration éditoriale** colorée :
  **Léa** (carré brun, veste bleu nuit sur un haut à la couleur d'accent du thème, collier fin) et **Karim**
  (veste camel, chemise claire, cheveux courts châtain foncé avec raie sur le côté, lunettes fines couleur
  écaille). Proportions réalistes, palette sobre, aplats sans contour avec ombres douces, visage fin. Assis
  à mi-corps derrière un bureau d'entretien (feuille de CV et stylo), mêmes expressions et gestes, bras
  articulés au coude ; `bg` + thème. Ajouter un personnage = une entrée de `PERSOS` dans `perso.js`
  (couleurs, coiffure `carre`/`raie`, accessoire `collier`/`lunettes`, `visage` `doux`/`carre`, `cils` ;
  une couleur `var(--c1)` suit le thème).

```bash
python scripts/render_js_anim.py --spec "dialogue?surtitre=En entretien&repliques=g:Tu as postulé à combien d'offres ? {doute}|d:Cinquante. Zéro réponse. {triste,hausse}" --duration 9 --out /tmp/dialogue.mp4
```

## Chaînes (`catalog/chaines/`)

Une **chaîne** = une ligne éditoriale complète : `catalog/chaines/<id>/` contient

| Fichier | Rôle |
|---|---|
| `chaine.json` | Identité : `nom`, `marque` (écran d'appel à l'action, couverture, carrousel), `marque_accent` (lettres finales de la marque en dégradé sur l'écran d'appel à l'action), `watermark` (incrusté en haut à gauche), `pied` (bas des planches pop art), `logo` (icône de la chaîne dans `assets/marques/<chaîne>/` : `logo.svg`, `profil.png` = photo de profil, `logo_nom.png` = icône + nom ; `catalog.py` vérifie qu'il existe), `mouvement` (profil de mouvement des animations : `dynamique` par défaut, `pose`, `fluide` — voir « Cadence et flou de mouvement »), `produit` (`"OpusCV"` ou `null` = faceless), dessin animé : `personnages`, `serie`, `trames` |
| `formats.json`, `sujets.json`, `hooks.json` | Formats, sujets et accroches **de la chaîne** (obligatoires, aucun repli sur une autre chaîne) |
| `config.json` | Fusionné clé par clé par-dessus `catalog/config.json` (réglages communs) : mix, registres, CTA (`ctas_*`, `cta_anim`), phrases bannies, `consigne_humour`, textes Instagram, scène preuve, relance |

Partagés par toutes les chaînes : `themes.json`, `audio.json`, `voix.json`, `dessins.json` (décors, objets, dessins des
personnages), `jeu.json`. La chaîne active est passée à toutes les étapes par la variable d'environnement `CHAINE`
(`run_pipeline.py --chaine`, champ `chaine` du workflow, sélecteur de la console) ; chaque chaîne a son **historique**
anti-répétition (`output/content_history.json` pour OpusCV, `output/content_history_<id>.json` pour les autres) et
sa numérotation d'épisodes. `python scripts/catalog.py` valide toutes les chaînes (`python scripts/catalog.py psycho`
pour une seule) et vérifie que les options `chaine` du workflow suivent les dossiers.

**Chaîne faceless** (`"produit": null`) : aucune capture (capture `aucune` imposée, pas de compte démo ni d'URL),
formats `conseil` à cartes ou dessinés uniquement (pas de jeu vidéo pour l'instant). Le prompt ne dit rien d'OpusCV ni
de l'emploi : il part de `niche`, `public`, `expertise`, `promesse`, `appel_action` et `regles` (règles impératives de la
chaîne) de `chaine.json` (`intro_faceless`, `niche_rule`, `neutraliser` dans `1_generate_script.py`) ; les exemples
écrits pour OpusCV (carte scan, « ligne de CV réécrite », « Pourquoi personne ne me rappelle ? »…) sont remplacés
par leur version générale (`exemple_accroche` / `exemple_replique` de la chaîne pour le dessin animé), la relecture de
cohérence contrôle les règles de la chaîne au lieu du produit. `scripts/verif_prompts.py` échoue si un prompt d'une
chaîne faceless parle encore d'OpusCV. Le dessin animé garde les mêmes dessins (Karim, Léa, le recruteur) mais la
chaîne leur donne un autre nom et un autre rôle (`personnages` : `nom`, `description`, `role`, `voix`), sa série et ses
trames ; `caracteres` donne leur caractère à l'IA (consigne `DRAMATURGIE_NICHE`). Légendes : `mention` de la chaîne
ajoutée à toutes les légendes (TikTok, Instagram, YouTube).

**Chaîne vérifiée** (`"verification": true`) : chaque sujet porte `faits` (phrases recopiées d'une source officielle) et
`source` ; les faits sont la **seule base autorisée** (bloc « FAITS VÉRIFIÉS » du prompt), un nombre supérieur à 10 dit ou
affiché qui n'est pas dans les faits fait recommencer l'IA (`faits_problems`), et la source est ajoutée aux légendes
(« Source : … »). Un ton qui contient « lent » compte 1,9 mot/s (au lieu de 2,6, mesuré au run 83) pour le budget de mots.

| Chaîne | Nom | Formats | Particularités |
|---|---|---|---|
| `opuscv` | OpusCV | les 37 capsules (voir « Ligne éditoriale ») | produit montré, chaîne par défaut, rien ne change pour elle |
| `examen_civique` | Objectif Civique (TikTok `@objectif.civique`, logo « L'Hexagone validé » : `assets/marques/examen_civique/`) | 18 formats, thème propre `civique_plateau` (voir « Plateau civique », « Objectif Civique : la rénovation » et « Objectif Civique : apprendre par les histoires » ci-dessous). **Tirés automatiquement** : `examen_blanc` (format phare « Réussirais-tu l'examen civique ? »), `mise_en_situation`, `vrai_ou_faux`, `dessin_anime` ; **en sommeil** (`"actif": false`, avec `--format` seulement) : `question_revision` (quiz 3 réponses), `vrai_ou_faux`, `cours_eclair`, `duel_ab` (« A ou B ? »), `trouve_intrus`, `relie_paires`, `mot_du_jour` (définition, exemple, quiz), `qui_suis_je` (3 indices), `frise_dates` (sujets à tag `dates` seulement), `serie_flash` (3 questions éclair), `histoire_racontee` (« Il était une fois… », récit en chapitres), `citation_expliquee`, `mise_en_situation` (« Que fais-tu ? », QCM à 4 réponses), `ne_confonds_plus`, `rappel_revision` (« Tu te souviens ? », révision espacée), `examen_mode_emploi`, `dessin_anime` (série « Sami prépare son examen ») | vérifiée : 80 sujets sourcés (Constitution, DDHC, lois sur Légifrance, service-public.fr, et surtout les fiches officielles de la formation civique, `formation-civique.interieur.gouv.fr`, ministère de l'Intérieur) rangés selon les cinq thèmes officiels de l'examen (familles valeurs, institutions, droits, histoire, géographie, culture, vie quotidienne) + le sujet `examen_modalites` (40 questions dont 28 de connaissance et 12 mises en situation, 4 réponses dont une bonne, 45 minutes, 32 bonnes réponses pour réussir, recopiés de la page officielle) ; français simple (A2-B1), débit naturel (lent avant la rénovation), un fait ne se généralise jamais (règle ajoutée après le run 82 : « seuls les Français peuvent voter » oubliait les citoyens européens aux municipales et européennes, désormais dans les faits du sujet `droit_de_vote`), registre sérieux seul, neutre, « chaîne non officielle » dans les légendes et le bas des planches. Les règles de l'examen ne se citent que depuis le sujet `examen_modalites` |
| `psycho` | Dans ta tête (provisoire, `@danstatete`) | `dessin_anime` (série « Dans la tête de Théo », 9 trames), `cours_eclair`, `mythe_realite` | 24 notions reconnues (pensée, habitudes, relations, émotions, travail) ; Karim devient Théo, Léa devient Jade, le recruteur devient « le chef » (mêmes dessins et voix) ; jamais de diagnostic ni d'étude inventée ; 40 % humour |

### Objectif Civique : la rénovation (format phare `examen_blanc`)

Constat de l'utilisateur : vues bloquées très bas. Diagnostic sur le reel du run 98 (`relie_paires`, 33 s) : rien à jouer pendant
les 3 premières secondes (une plume néon et un titre, la question n'arrive qu'à 4,5 s), « en six secondes » sans chrono, 2 paires
seulement et les traits de réponse tracés pendant la consigne, « Enregistre la vidéo » à 4 s, un fait hors sujet puis une phrase
de remplissage, 6 s de fin, voix lente au ton de professeur, sujet loin de ce que le public cherche (« examen civique » absent de
l'écran), et 17 formats : aucun rendez-vous reconnaissable. Ce qui change :

- **Format phare `examen_blanc`** « Réussirais-tu l'examen civique ? » (`"phare": true`, poids 6 : environ 7 reels sur 10) :
  3 questions QCM à 4 réponses comme à l'examen, chacune d'un sujet d'une famille différente (`"melange": 3`), de la plus facile à
  la plus piégeuse (« La plus difficile : »). **Pas de scène d'accroche** (`"carte_accroche": true`) : la 1re image montre déjà le
  bandeau « EXAMEN CIVIQUE · ENTRAÎNEMENT N°X » (`entete`, série numérotée), « QUESTION 1/3 » et la question ; les 4 réponses sont
  là avant 1 s. La voix pose le défi en 4 à 7 mots (accroches réservées `defi_examen`, `sans_faute`, `pret_examen`), lit la
  question et les réponses, « Réfléchis. », 2 s de compte à rebours, la réponse s'allume, puis une phrase des faits. Fin en une
  phrase : « Ton score sur trois ? Écris-le en commentaire, et abonne-toi. » (`ctas` du format). Environ 45 s (`duree_min` 38 :
  le budget de mots, les silences s'y ajoutent). Le titre (couverture, YouTube) et la légende contiennent « examen civique ».
  Pourquoi 3 questions et pas 5 : avec les 4 réponses lues à voix haute, une question coûte environ 13 s (5 questions = plus de
  70 s) ; pour en changer, `melange` et la structure du format.
- **En complément** : `mise_en_situation` et `vrai_ou_faux` (poids 2, la situation ou la 1re affirmation s'affiche aussi dès la
  1re image : `carte_accroche`), `dessin_anime` (poids 2). Les 14 autres formats sont **en sommeil** (`"actif": false`) : rien n'est
  supprimé, `--format` ou la console les lancent toujours.
- **Rythme** : ton « débit naturel et dynamique » (2,6 mots/s au lieu de 1,9), temps de réflexion 2 s au lieu de 3, plus de relance
  « enregistre » (`relance_enregistrer: false`), plus de scène de résumé ni de transition dans le format phare.
- **Règles inchangées** : faits sourcés seulement (contrôle des nombres, citation mot pour mot), jamais « question officielle »,
  aucune promesse de réussite, « chaîne non officielle » dans les légendes.

```bash
python scripts/run_pipeline.py --chaine examen_civique --n 1 --format examen_blanc
```

### Objectif Civique : apprendre par les histoires

La chaîne `examen_civique` apprend comme un bon formateur : le spectateur **cherche avant d'avoir la réponse** (question,
situation ou énigme d'abord), un seul fait par scène, un exemple de la vie en France, la phrase à retenir redite à la fin avec les
mots des faits, et une **astuce pour retenir** permise si elle n'ajoute aucun fait (règles de `chaine.json`). Les sujets suivent les
cinq thèmes officiels de l'examen (fiches de `formation-civique.interieur.gouv.fr`, recopiées, jamais de mémoire ; tags de format :
`recit`, `citation`, `situation`, `confusion`, `memoire`, `examen` — voir le `_doc` de `sujets.json`).

| Format | Durée min. | Ce que voit le spectateur |
|---|---|---|
| `histoire_racontee` « Il était une fois… » | 40 s | « Imagine : … », puis 2 ou 3 **chapitres** (planche `chapitre`, « CHAPITRE 1, 2, 3 »), la voix raconte au présent comme un conteur, chaque chapitre répond à la question laissée par le précédent ; un QCM à 4 réponses sur l'histoire, la réponse, le CTA. Le récit n'ajoute rien aux faits (ni foule, ni météo, ni parole inventée) |
| `citation_expliquee` « Une phrase, une explication » | 35 s | une phrase célèbre (DDHC, Constitution, Charte de l'environnement, Simone de Beauvoir…) en planche `citation`, **mot pour mot** (contrôlé), le mot difficile en définition, ce que ça change au quotidien, un quiz |
| `mise_en_situation` « Que fais-tu ? » | 35 s | une situation au « tu » (planche `situation`, dès la 1re image), un **QCM à 4 réponses comme à l'examen** (qui compte 12 mises en situation sur 40 questions), la bonne réponse et le fait qui la justifie, ce qu'il ne faut pas faire |
| `ne_confonds_plus` « Ne confonds plus ! » | 35 s | deux notions qu'on mélange (police / gendarmerie, contravention / délit / crime, Assemblée / Sénat…) reliées à ce qui les distingue, l'astuce pour ne plus confondre, un duel pour vérifier |
| `rappel_revision` « Tu te souviens ? » | 35 s | **révision espacée** : les faits viennent des 3 derniers sujets publiés par la chaîne (`catalog.sujet_rappel`, format à `"rappel": true` ; sujet ordinaire tant que l'historique n'en a pas 3, ou si ces 3 sujets viennent d'être révisés), une question par sujet, le score en commentaire |
| `examen_mode_emploi` « L'examen en 30 secondes » | — | les chiffres clés de l'examen (cartes chiffre), les cinq thèmes (liste), « autant de fois que nécessaire », la préparation peut être gratuite — tout vient du sujet `examen_modalites` |
| `dessin_anime` « Sami prépare son examen » | — | la série dessinée de la chaîne (voir ci-dessous) |

`duree_min` d'un format (`formats.json`) : une durée demandée plus courte est relevée à ce minimum pour l'écriture (le scénario
garde la durée demandée dans `duree_cible_s`, la reprise du pipeline ne le croit pas périmé). `sans_relance` (récit, citation, mise en situation) : pas de
relance « enregistre » au début de la scène 2, elle casserait l'immersion.

**Série dessinée « Sami prépare son examen »** (`chaine.json` : `personnages`, `caracteres`, `serie`, `trames`, `lieux` ; noms
**provisoires**) : mêmes dessins qu'OpusCV, autre identité — **Sami** (dessin de Karim) prépare son examen civique et découvre la
France, **Claire** (dessin de Léa), sa voisine bénévole dans une association, connaît les faits et les fait chercher, **M. Bernard**
(dessin du recruteur, secondaire), le voisin retraité qui croit tout savoir, lance l'idée reçue que l'épisode corrige. Huit trames :
`situation_vraie`, `faux_conseil` (le voisin qui sait tout), `quiz_du_soir`, `dans_sa_tete`, `le_mot_bizarre`, `la_veille`
(l'astuce pour retenir), `le_prof_c_est_lui` (Sami explique à M. Bernard), `le_chat_juge`. Chaque épisode apprend **un fait des
FAITS VÉRIFIÉS**, dit entre « guillemets » par Claire (contrôle des nombres et relecture comme les autres formats). `lieux` : décors
proposés en priorité (`catalog.pick_lieu`) — les décors civiques `mairie`, `bureau_vote`, `salle_cours`, puis salon, café, salle
d'attente. Sujet de mémoire (Shoah) : ton grave, jamais en vrai ou faux, en dessin animé ni avec une blague (tag `memoire`, formats
`cours_eclair` et `histoire_racontee` seulement).

Accroches ajoutées (`hooks.json`, `tags` = sujets visés) : `imagine` (récit, jamais en dessin animé), `situation_tu`, `on_confond`,
`phrase_celebre`, `idee_recue`, `detail_surprenant`.

```bash
python scripts/run_pipeline.py --chaine examen_civique --n 1 --format histoire_racontee --duration 40
python scripts/run_pipeline.py --chaine examen_civique --n 1 --format mise_en_situation --duration 35
python scripts/run_pipeline.py --chaine examen_civique --n 1 --format dessin_anime --duration 30
```

**Mouvement** : `opuscv` = `dynamique` (rebonds francs, entrées vives), `examen_civique` = `pose` (sobre, rebond à peine marqué : une chaîne qui doit inspirer confiance), `psycho` = `fluide` (arrivées longues et soyeuses). Les profils sont dans `catalog/config.json` (« mouvements »).

Changer un nom (celui de `psycho` est provisoire, comme les prénoms de la série d'Objectif Civique : Sami, Claire, M. Bernard) : `nom`, `marque`, `watermark`, `pied` (et les prénoms dans `personnages`, `caracteres`,
`serie`) dans `chaine.json`, rien d'autre. **Ajouter une chaîne** : copier le dossier d'une chaîne faceless, adapter
`chaine.json`, les formats, sujets, accroches et la config, ajouter son id aux options `chaine` de
`.github/workflows/generate-reels.yml`, puis `python scripts/catalog.py` et `python scripts/verif_prompts.py`. Ses phrases
de CTA sont enregistrées au premier reel qui les tire (ou d'avance : `python scripts/2_generate_voice.py --precompute-cta`).

## Ligne éditoriale : le catalogue (`catalog/`)

Pour éviter que les reels se ressemblent, chaque vidéo combine un **registre** (sérieux ou humour) et
4 choix pris dans des fichiers JSON éditables (aucun code à toucher pour enrichir). Ce qui suit décrit la chaîne
OpusCV ; formats, sujets, accroches et config sont dans `catalog/chaines/opuscv/` (voir « Chaînes ») :

| Fichier | Contenu | Exemples |
|---|---|---|
| `catalog/chaines/opuscv/formats.json` | **Structure** de la vidéo (37 « capsules »), catégorie `conseil` (contenu utile) ou `produit` (démo), registres compatibles (`registres`), usage des cartes animées, ton de lecture (`ton`, `ton_humour`) | voir le tableau ci-dessous |
| `catalog/chaines/opuscv/sujets.json` | **De quoi** parle la vidéo (165 sujets, 14 familles), avec des tags croisés avec les formats et une **famille** (grand thème) qui tourne | ATS, rédaction du CV, forme du CV, parcours, candidature, lettre, entretien, LinkedIn, organisation de la recherche, carrière et emploi (négocier, démissionner, choisir une offre, premier jour…), métiers (CV de commercial, de développeur, de soignant…), familles produit (dont les nouveautés : 6 mises en page, conversion de langue, chiffres sans invention, sections libres, lettre en PDF…) |
| `catalog/chaines/opuscv/hooks.json` | **Style d'accroche** des 2 premières secondes (25), avec leurs `registres` et, pour celles centrées sur le CV (`erreur_visible`, `comparaison_inattendue`), des `tags` : elles ne sont tirées que pour un sujet de ce tag (pas pour « démissionner proprement ») | question choc, chiffre, erreur, contre-intuitif, POV, stop, verdict, scénario catastrophe ; en humour : autodérision, « Personne : … Moi : … », fausse pub, exagération, réplique absurde, plot twist… |
| `catalog/themes.json` | **Habillage** : couleurs, polices (`assets/fonts/`), style des sous-titres, ambiances musicales, support des dessins (`dessin`), `registres` (absent = tous) | violet nuit, corail, vert, bleu corporate, bande dessinée pop, sitcom pastel… |
| `catalog/config.json` | Réglages communs : mix de registres (`registres` : sérieux 70 % / humour 30 %), `ton_humour`, fenêtres anti-répétition, seuil de similarité, CTA enregistré | |
| `catalog/chaines/opuscv/config.json` | Mix cible (`conseil` 65 % / `produit` 35 %), règles d'écriture humoristique (`consigne_humour`), variantes de CTA (`ctas_*`, `cta_anim`), textes Instagram (`instagram`), scène preuve, relance, phrases bannies | |

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
| conseil | Dessin animé : Karim cherche un job (`dessin_anime`) | série en mini dessin animé : Léa, Karim (et le recruteur) jouent une situation d'emploi et en tirent un conseil, chacun avec sa voix, sur une trame tirée en rotation ; le produit n'apparaît que dans le CTA ; capture `aucune` uniquement |
| conseil | Jeu vidéo : la quête de Martin (`jeu_quete`) | partie de RPG en pixel art : Martin (héros) et Léa (guide) affrontent un boss qui est le système de recrutement (robot trieur, fantôme, paperasse), gagnent un objet (la phrase exacte), des points de vie, un niveau ; chacun sa voix, musique chiptune ; le produit n'apparaît que dans le CTA ; capture `aucune` uniquement |
| conseil | Mini-cours éclair (`cours_eclair`) | vidéo éducative : accroche, 3 leçons d'une phrase (cartes carnet de cours ou comics pop-art, quiz possible), pivot vers l'outil, CTA ; thèmes `carnet_cours` et `pop_art` seulement |
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
  en évitant les derniers utilisés ; un format à `"actif": false` est **en sommeil** (jamais tiré, toujours possible avec
  `--format` ou la console) et un format à `"phare": true` n'est jamais écarté parce qu'il vient de passer (son poids en fait le
  rendez-vous de la chaîne : `examen_blanc` d'Objectif Civique) ;
- la **famille** du sujet (`famille` dans `sujets.json`) tourne : la moins récemment traitée passe en
  premier, celles des `historique_familles` (5) derniers reels sont écartées — l'ATS ou le chiffrage des
  résultats ne reviennent donc plus reel après reel ;
- le **sujet** est choisi par Gemini dans cette famille, parmi ceux compatibles avec le format et non traités
  récemment ; hors des familles ATS / rédaction, le prompt lui interdit de dériver vers l'ATS, les mots-clés
  ou le chiffrage des résultats ;
- l'**accroche** et le **thème** tournent (tirage pondéré par `poids`, sans les plus récents) ; les accroches « Pourquoi… ? » sur une douleur vécue (`question_choc`, `pourquoi_douleur`, poids 3) sont favorisées, les listes, chiffres et « secrets » réduits (poids 0,5) car ils ont moins bien performé ;
- les **exemples de phrases** de CV ou de lettre donnés dans un reel n'inventent aucun chiffre précis (« 200 k€ de ventes ») : formule sans chiffre ou « [ton chiffre] » (consigne commune à tous les formats) ;
- une accroche trop proche d'une accroche déjà publiée est refusée et Gemini recommence ;
- tout est historisé dans l'historique de la chaîne (`output/content_history.json` pour OpusCV, `content_history_<id>.json` pour les autres ; persisté entre les runs CI par le cache).

**Prompt du scénario** (`build_prompt`, `scripts/1_generate_script.py`) : Gemini joue un expert du contenu
viral emploi/recrutement (TikTok, Reels, Shorts) avec des règles strictes : accroche (0-3 s) au tutoiement,
émotion forte (peur de l'échec, curiosité, gain de temps, injustice du recrutement) et chiffre précis si
possible ; corps (3-20 s) problème précis puis solution OpusCV montrée à l'écran, phrases courtes ; CTA
« tester gratuitement » (lien en bio). Sujets dédiés : `meme_cv_50_boites`, `adapter_cv_30_secondes`,
`recruteur_6_secondes`. Garde-fous : chiffres uniquement concrets ou vérifiables (jamais de statistique
inventée), public = candidats (jamais « recruteurs » dans le CTA). Format `tier_list` : Rang S = l'erreur la
plus grave, annoncé dès l'accroche ; `temoignage_produit` : tout à la 1re personne jusqu'au CTA.

**Vérité et cohérence** (reels à cartes et à captures ; le dessin animé et le jeu ont leur propre relecture) : un
**teaser** (« reste pour la formule finale », « la dernière est la plus utile ») est permis, il retient le spectateur, mais
il doit être **tenu**. Consigne `COHERENCE_RULE` + deux contrôles qui relancent l'écriture (3 tentatives, la meilleure est
gardée) :
- `promesses_problems` (règles, sans appel IA) : la chose annoncée (« formule », « astuce »…) doit revenir dans une scène
  suivante, voix ou carte (`PROMESSE_RES`) ; un rang annoncé (« la troisième leçon va te surprendre ») doit exister parmi
  les éléments numérotés du reel (étape / leçon / erreur… n°).
- `relecture_coherence` (un second appel Gemini, jamais bloquant, sautée pour une séquence imposée) : un spectateur qui ne
  connaît que le reel vérifie les promesses tenues, que le titre, l'accroche et la légende décrivent bien le contenu, que
  chaque voix colle à son écran (carte = les mots de la voix, capture = la fonctionnalité dite), que ce qui est dit d'OpusCV
  est vrai d'après `PRODUCT_CONTEXT`, et que les chiffres pris en exemple sont présentés comme des exemples.
(Runs 76 et 79 : « la troisième leçon va te surprendre » pour deux leçons, « reste pour la formule finale » sans formule.)

**Relance « enregistre »** (`relance_enregistrer` dans `config.json`, activée par défaut, désactivée pour Objectif Civique depuis
la rénovation : au run 98 elle arrivait à 4 s, avant même le jeu) : sur les reels
`conseil` en registre sérieux (sauf `cours_eclair`, dont la scène 2 est déjà une leçon), la 1re phrase de la scène 2 invite en 5 à 7 mots à enregistrer la vidéo
(« Enregistre-la, tu vas en avoir besoin. »), puis le contenu enchaîne. L'abonnement n'est demandé qu'à
la fin : les CTA `ctas_conseil` associent « abonne-toi » et le test gratuit en bio.

Chaque scénario contient aussi l'**accroche affichée** en grand dès la première image (pas de fondu
depuis le noir ; format à `carte_accroche` : elle ne sert que de titre à la couverture et à YouTube, la carte de la scène 1
occupe l'écran), une **légende** et des **hashtags** (écrits dans `output/final/reel_XX.txt`), leurs
équivalents Instagram et le texte du carrousel (voir « Instagram »), une
offre d'emploi fictive et un style de CV pour la démo. Les textes sont en français accentué (vérifié :
un script sans accents est renvoyé à Gemini), car les sous-titres affichent le texte exact.

**Promotion de l'outil (~35 à 40 % du contenu)** : en plus des formats `produit` (démo, avant/après
avec OpusCV, défi chronométré, « le recruteur a 6 secondes », scanner ATS), chaque reel `conseil`
contient une **scène preuve** (`"preuve": true`) où le conseil est appliqué en direct dans OpusCV,
avec le curseur qui clique puis le bouton entouré au feutre avec un post-it (`preuve_produit` dans
`config.json` pour la désactiver). Le CTA dit et le CTA animé
sont tirés parmi plusieurs variantes.

**CTA enregistré** (`cta_enregistre` dans `config.json`, activé par défaut) : la dernière phrase du reel
est **exactement** une phrase de `ctas_conseil` / `ctas_produit` (Gemini la recopie, `fixer_cta` la
remet telle quelle de toute façon) et sa voix n'est **pas resynthétisée** : `2_generate_voice.py` dit
le reste du texte, puis colle l'enregistrement de cette phrase pour la voix du reel (ou du personnage
qui la dit, en dessin animé) après une pause de 0,3 s, ramené au volume de la voix. Enregistrements :
`assets/voix_cta/<voix>_<empreinte de la phrase>.ogg` (versionnés, une fois par voix et par phrase :
`python scripts/2_generate_voice.py --precompute-cta`, `--force` pour tout réenregistrer après un
changement de modèle TTS — fait pour `gemini-3.8-flash-tts`) ; une phrase ou une voix nouvelle est enregistrée
au premier besoin dans `output/voix_cta/` (gardé par le cache de la CI). L'écho à l'accroche (boucle)
passe alors à l'avant-dernière scène. Scénario écrit à la main (`--scenario`) : son CTA est gardé tel quel.

**Originalité** : formats POV, « ce que le recruteur voit vraiment », tier list, red flag / green flag,
quiz « trouve l'erreur » ; Gemini doit apporter un élément concret par scène (exemple de formulation,
cas précis), les conseils génériques et promesses intenables (« entretien garanti ») de `phrases_bannies`
sont refusés, et la dernière phrase (l'avant-dernière avec le CTA enregistré) répond
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
| `quiz` | `lecon.html` / `pop.html` (`liste.html` sinon) | format `cours_eclair` : une question, 3 réponses, la bonne se révèle (`question`, `reponses`, `bonne`) |

Imposer un élément : `--format liste_erreurs`, `--theme vert_confiance`, `--hook pov`, `--registre humour`
(aussi dans le workflow ; un format imposé sans registre prend un des registres qu'il accepte). Vérifier le catalogue après modification : `python scripts/catalog.py`.

### Combinaison par reel (`--plan`)

`--plan` impose, reel par reel, tout ou partie de la combinaison : une liste JSON d'objets aux clés
`format`, `sujet`, `hook`, `theme`, `voix`, `registre`, `ambiance` (id de `audio.json`, ou `aucune` = sans musique), `trame`
(dessin animé : id de `trames` dans le `chaine.json` de la chaîne, proposé par la console quand le format est un dessin
animé) et `angle` (sujet libre, à la place de `sujet`). Une clé absente ou vide reste automatique (rotation
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
`ton_humour` (ton de lecture quand un format des deux registres est joué en humour). Options d'Objectif Civique (utilisables
par toute chaîne, aucun format d'OpusCV ne les a : ses prompts restent identiques) : `actif` / `phare` (ci-dessus),
`carte_accroche` (la scène 1 a sa carte, affichée dès la première image sans titre par-dessus, `immediat=1` sur la planche),
`melange` (sujet composé de n sujets de familles différentes, `catalog.sujet_melange`), `entete` (bandeau de la série sur chaque
carte, `{episode}`), `serie_titre` (surtitre de la couverture), `ctas` / `cta_anim` (fin propre au format, à la place de ceux du
`config.json` ; `2_generate_voice.py --precompute-cta` les enregistre aussi). Une accroche à `"formats"` (`hooks.json`) est réservée
à ces formats, et un format qui en a de réservées ne prend qu'elles.

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

## Instagram et YouTube (`--plateformes`)

Le même reel vertical 9:16 sert de Reel Instagram ; `scripts/instagram.py` (appelé par
`run_pipeline.py` après l'assemblage) produit en plus, à côté de `output/final/reel_XX.mp4` :

| Plateforme | Fichiers | Contenu |
|---|---|---|
| `tiktok` | `reel_XX.txt` | légende courte + 4 à 6 hashtags |
| `instagram` | `reel_XX.instagram.txt` | légende Instagram (1re ligne accrocheuse visible avant « plus », résumé des conseils, question, invitation à enregistrer) + 5 hashtags au plus (`instagram.hashtags_max`) |
| `tiktok` ou `instagram` | `reel_XX.couverture.jpg` | couverture 1080×1920 : l'accroche en grand sur un fond uni aux couleurs du thème (jamais une capture, illisible une fois réduite dans la grille), texte dans la zone commune aux recadrages de la grille (3:4 et carré) ; surtitre pour une série : « Karim cherche un job · ép. N » (dessin animé), « Jour N/30 » (`serie_30_jours`). À importer comme couverture à la publication (voir ci-dessous) |
| `youtube` | `reel_XX.youtube.txt` | YouTube Shorts : 1re ligne = titre (l'accroche, 100 caractères au plus, « #Shorts » compris), puis la description (légende, hashtags + `#Shorts`) ; écrit par `run_pipeline.py` |
| `carrousel` | `reel_XX_carrousel/01.png…` + `legende.txt` | carrousel 4:5 (1080×1350) : couverture, une idée par diapositive (numéro, barre de progression, « Glisse → »), diapositive finale d'appel à l'action (`instagram.carrousel_fin`) |

Chaîne vérifiée ou à `mention` (voir « Chaînes ») : « Source : … » et la mention de la chaîne (« Chaîne non officielle… »)
sont ajoutées à toutes les légendes. Marque de la couverture et du carrousel : `marque` de la chaîne.

**Publication** : manuelle pour l'instant (vidéo, légende et couverture téléchargées depuis la console).
La publication automatique après validation (Instagram via l'API Instagram Login, brouillon TikTok via
l'API Content Posting) est prévue mais pas encore écrite ; les jetons iront uniquement dans les secrets
GitHub du dépôt.

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

- **Musique** synthétisée (aucun droit à gérer) : 17 ambiances (lo-fi piano, pop énergique,
  corporate, tension tech, minimal pulsé, house douce, piano minimal, synthwave, acoustique, trap
  légère, comique sautillant, et les plus douces : ambiance matinale sans rythme, jazz de café, bossa
  douce, ukulélé bonne humeur, boîte à musique, cinéma doux), avec 4 instruments (`nappe`, `piano`, `pluck`, `synth`), basses (`pulse`, `808`, `douce`)
  et batterie (kick, snare, hat, clap, shaker). Chaque thème liste ses ambiances compatibles
  (`"ambiances"`), une est tirée par reel sans reprendre les plus récentes. La musique baisse
  automatiquement quand la voix parle.
- **Sans musique** : `--no-music` (case « Musique de fond » du workflow `generate-reels.yml` et de la
  console), ou `"ambiance": "aucune"` pour un reel du `--plan` (tuile « Sans musique » de la console) :
  la voix et les effets restent, le mastering à -14 LUFS aussi. Pour changer de musique : choisir une
  ambiance par reel dans la console, ajouter des ambiances à un thème (`"ambiances"` de `themes.json`) ou
  déposer ses propres morceaux libres de droits dans `assets/music/<id_ambiance>/`.
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
- **Bruitages du dessin animé** (`bruitages` dans `audio.json`) : pas, saut, chaise, objet posé,
  vibreur, clavier, ampoule, papier froissé, corbeille, tampon, notification, pages, zoom (synthétisés), miaou et ronron (enregistrements **CC0**, `assets/sfx/`,
  sources dans `assets/sfx/LICENCES.md`). Émis par le moteur de dessin à l'instant de l'action, ils
  échappent à l'écart minimal et au maximum par 10 s (un même bruitage est seulement espacé de
  `bruitage_ecart_min_s`) ; volumes discrets réglables dans `volumes`.
- **Effets de carte** (`"effet"`, choisi par Gemini) : `standard`, `frappe` (texte tapé au clavier)
  et `suspense` (titre caché puis révélé, un seul par reel).

Écouter : `python scripts/audio_gen.py --ambiance pop_energie --out /tmp/a.wav` ou `--sfx whoosh`
(`--sfx pas`, `--sfx miaou`…).

## Effets visuels et voix

- **Sous-titres** : 4 styles par thème (`sous_titres.style`) : `karaoke` (mot prononcé coloré et
  agrandi), `encadre` (mot prononcé sur une pastille), `boite` (phrase sur un bandeau), `mot` (un
  seul mot à la fois, en très grand). Les **mots-clés** choisis par Gemini (`mots_cles`) s'affichent
  dans la couleur d'accent du thème (`couleurs.mot_cle`). La ponctuation isolée par une espace
  (« », :, ?, !) reste collée à son mot : jamais de guillemet seul à l'écran. Police : celle du thème (`police_texte`) ;
  sans thème, repli sur Poppins Bold (`catalog.DEFAULT_FONT`), plus la police système. Les sous-titres commencent à
  y = 1574 sur 1920 : les gabarits gardent leur contenu au-dessus (≈ 1500), ne pas les remonter sans revoir toutes les planches.
  Chaque nouvelle phrase **arrive** : fondu et petite montée (~23 px) en 0,14 s sur son premier mot (`CAPTION_*`, `5_assemble.py`) ;
  les mots suivants gardent la même image. Le filigrane suit la police du thème (repli Poppins Bold).
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
- **19 thèmes**, dont verre givré, éditorial magazine, néon nuit, tableau à la craie, affiche
  impact, bande dessinée pop, sitcom pastel, carnet de cours et comics pop-art (polices libres Playfair Display, Space Grotesk, DM Sans,
  Kalam, Bebas Neue, Bangers).
- **Barre de progression** fine en haut de l'écran, aux couleurs du thème (`--no-progress-bar` dans
  `5_assemble.py` pour la retirer).
- **Fin en boucle** : les dernières images se fondent dans la première (accroche comprise), la
  vidéo s'enchaîne sans coupure → revisionnages (`--no-loop` pour un fondu au noir).
- **Zoom ciblé** : chaque capture zoome vers son bouton d'action (repéré à la capture, `focus`
  dans `captures.json`) au lieu du centre, en courbe douce (voir « Cadence et flou de mouvement »).
- **Curseur animé** (`--anims cursor`) : une flèche vient cliquer sur ce bouton en suivant un arc (x et y arrivent avec
  des courbes différentes), avec un son de clic de souris. Avec `highlight`, les deux alternent d'une scène à l'autre.
- **Transitions** : par thème (`transitions` dans `themes.json`, transitions ffmpeg xfade) ; sans réglage, un fondu
  sur deux et, entre les deux, défilement vers le haut, vers la gauche, zoom puis vers la droite
  (`timeline.XFADE_TRANSITIONS`, 0,35 s, chacune démarre pile au début de la scène suivante).
- **9 types de cartes** (choisis par Gemini, voir le tableau des cartes) : texte, chiffre,
  comparaison, liste, schéma dessiné à la main, conversation, scan ATS, typographie cinétique, mème.
- **Dessin à la main** : cartes schéma et annotations au feutre sur les captures (voir « Dessin à
  la main »), sur papier, tableau à craie ou néon selon le thème.
- **Texture** : grain de film léger et particules lentes sur les cartes et le CTA.
- **Appel à l'action animé** (`cta.html`) : les lettres de la marque tombent une à une, le titre monte mot à mot, un reflet lumineux traverse le bouton, qui entre avec le `rebond` du profil de la chaîne puis « respire » (+3 %) ; la flèche rebondit sous lui.
- **Contraste automatique** : sur les thèmes à couleur principale claire (jaune craie, cyan néon,
  bleu givré, jaune affiche), le texte posé sur cette couleur (pastilles, accroche, bouton du CTA,
  bulles, mot fort) passe en sombre (`--c1fg` calculé dans `assets/anim/common.js`).
- **Voix en rotation** (`--voice auto`, `catalog/voix.json`) et **ton de lecture par format**
  (`ton` dans `formats.json`, `ton_humour` en registre humour). Dessin animé : une voix par personnage
  (`voix` dans `catalog/dessins.json`), en un seul appel multi-locuteurs.
- **Mode sans voix** (`--sans-voix`, case « sans_voix » du workflow) : texte à l'écran + musique,
  pour le public qui regarde sans le son.

## Catalogue des fonctionnalités capturables

```bash
python scripts/features.py
```

Liste les fonctionnalités qu'un scénario peut montrer — c'est ce catalogue que Gemini reçoit pour écrire
le scénario. Il suit l'interface actuelle d'OpusCV (septembre 2026) :

- **Le CV** : `checklist` (points à corriger, sans note ; un point déplié dit pourquoi et comment), `reperes_cv` (les points posés
  sur le CV, dans la marge de l'aperçu, et la carte d'un point), `avant_envoyer` (la fenêtre « Avant d'envoyer » quand un point
  bloque encore le CV), `identite`, `aide_redaction` (conseil de rédaction en bulle près du champ), `ecrire_sur_page` (le champ
  posé directement sur le CV : le nom, puis une phrase tapée dans le profil), `experiences` (tiroir des missions),
  `formation`, `competences`, `langues`.
- **Structure** : `structure` (ordre des blocs, langue et format du CV, pied de page), `sections_perso`
  (section libre : certifications…).
- **IA** : `relecture`, `fonctions_ia` (adapter à une offre), `lettre_motivation`, `entretien`.
- **Diffusion** : `convertir` (variante en anglais, allemand, espagnol ou au format Letter), `partage`.
- **Mise en page** : `apercu_pdf` (l'aperçu et ses trois modes Rapide / Auto / PDF ; en mode PDF, le PDF exact), `design` (41 thèmes en
  pastilles), `mises_en_page` (6 structures, le CV en frise, classique puis minimal),
  `personnalisation` (détails et réglages fins).
- **Affichage** : `mode_sombre`, `apercu_cv`.

Aucune capture ne déclenche d'appel IA, sauf `entretien` (`ALLOW_AI_QUOTA_FEATURES=1`). Les captures qui modifient le CV
(`aide_redaction`, `ecrire_sur_page`) remettent le texte d'origine et enregistrent (rien ne change) ; `avant_envoyer` passe par
« Partager » (sans point bloquant, il ouvre simplement le partage : pas d'export lancé).

**CV de démonstration des captures** (`scripts/demo_compte.py`, `assets/cv_demo.json`) : avant de filmer, `3_record_demo.py`
(modes `screenshots` et `video_desktop`) crée par l'API de l'app un CV neuf « Camille Duval - Conseillère de vente » sur le compte de
démo (`DEMO_EMAIL`, `DEMO_PASSWORD`), le filme (la ligne du tableau de bord est choisie par son titre), puis le supprime ; un reste
d'un run interrompu (même titre) est supprimé avant la création. Le contenu est le profil de démonstration de l'app **sans
téléphone** : l'app signale alors un point bloquant (« téléphone manquant »), d'où les points à corriger, les repères et « Avant
d'envoyer ». Il remplace l'ancien CV du compte (coquilles « Growthds », « Globalds » vues dans le reel du run 79) et contourne le
changement de l'app du 06/10 (plus de profil de démonstration proposé à un compte connecté). Échec de la création (compte au
plafond de 3 CV en plan gratuit, réseau) : alerte, et les captures retombent sur le premier CV du compte. Un compte **Pro** est
préférable (CV illimités, quota IA pour `entretien`). Si le profil de l'app change (`client/src/utils/demoCv.js`), mettre à jour
`assets/cv_demo.json`. Le contexte
produit donné à Gemini (`PRODUCT_CONTEXT` dans `1_generate_script.py`) décrit les mêmes fonctions.
Il dit aussi ce que l'outil ne fait pas : pas de score, jamais de chiffre inventé.

## Automatisation via GitHub Actions

Le workflow `.github/workflows/generate-reels.yml` tourne chaque lundi (et manuellement via
l'onglet Actions, avec les mêmes options que `run_pipeline.py`, dont `chaine`, `registre`, `hook`, `plan` et
`plateformes`). Le lancement du lundi produit la chaîne `opuscv` ; les autres chaînes se lancent à la main (console ou
Actions, champ `chaine`), sans réveil du service de démo ni compte démo. Capture par défaut du workflow (et donc du lancement du lundi) : `screenshots`, le seul
mode avec capture qui affiche les cartes animées (`run_pipeline.py` seul garde `video` par défaut).
Les déclinaisons Instagram sont dans l'artefact `output`, sous `final/`.

Le workflow `.github/workflows/test.yml` (chaque push) vérifie : syntaxe de tous les scripts, catalogue
(`scripts/catalog.py`), **construction du prompt de chaque format** (`scripts/verif_prompts.py`, sans appel IA : un nom de
variable utilisé avant sa définition passe `py_compile` mais plante tous les lancements, run 80), **chargement de chaque gabarit d'animation avec chaque
profil de mouvement** (`scripts/verif_gabarits.py`) et `--help` de chaque étape.

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

- **Surcharge Gemini** (503 « high demand », 429, 500/502/504) : chaque appel (scénario, choix du sujet,
  voix) attend puis réessaie (15, 30, 60 puis 90 s, `scripts/gemini_retry.py`) au lieu de faire échouer
  le run. Pour le scénario, les deux derniers essais passent sur un modèle de repli
  (`GEMINI_FALLBACK_MODEL`, `gemini-2.5-flash` par défaut) ; dès que le repli a répondu, les appels
  suivants du même script partent directement sur lui (le run 58 perdait ~1 min 45 par appel à
  réessayer le modèle principal). Une autre erreur (clé invalide…) arrête tout de suite, comme un
  quota du jour épuisé (429 « per day ») : la voix passe alors directement au modèle de secours, qui
  a son propre quota. Quotas du niveau 1 pour les voix : 10 requêtes/minute et 100/jour par modèle ;
  un reel = 1 appel, mais `--precompute-cta` enregistre chaque phrase de CTA de toutes les chaînes pour chaque voix
  (plus de 100 appels : à lancer un jour sans run, et à relancer le lendemain, les phrases déjà enregistrées sont sautées).
- Voix : `gemini-3.8-flash-tts` (version stable) ; le secours `gemini-3.1-flash-tts-preview` est une préversion (pas de SLA garanti).
- Whisper tourne en CPU (`--model small` par défaut) ; largement suffisant pour des reels de 15-30s.
- Aucun GPU nécessaire pour ce pipeline (pas d'avatar animé, juste du screen-record + montage).
- La musique de fond est synthétisée localement (pas de fichier audio externe) : aucune question de droits.
  Seules exceptions : le miaou et le ronron du dessin animé, enregistrements CC0 (`assets/sfx/LICENCES.md`).

## Console web (docs/index.html)

Interface pour lancer le workflow (dont le registre et les plateformes), composer les
combinaisons, parcourir le catalogue, suivre les runs
(bouton « Logs » : étapes du job avec état et durée, rafraîchies toutes les 15 s ;
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

- **Principe** : un écran minimal par défaut, le détail seulement à la demande ; une seule couleur d'accent, presque pas
  d'emojis, des listes plutôt que des murs de vignettes.
- **Apparence** : bouton en haut à droite de la page, qui fait défiler Auto (suit le mode clair / sombre de l'appareil) → Clair → Sombre ;
  le choix est mémorisé dans le navigateur.
- **Chaîne** : sélecteur en tête de l'onglet Lancer (dossiers de `catalog/chaines/`) ; il recharge formats, sujets,
  accroches, trames et personnages de la chaîne, garde une composition par chaîne et envoie `chaine` au workflow. Une
  chaîne sans produit grise le choix de capture (« Sans capture » imposé). Le titre de la page affiche le nom de la chaîne.
- **Onglet Lancer** : nombre de reels, durée, plateformes, bouton **Lancer** dans une barre fixe en bas de l'écran
  (nombre de reels, durée, combien sont personnalisés). Le générateur varie tout seul format, sujet, style et accroche.
  « Choisir moi-même les reels → » ouvre le **compositeur** : une fiche par reel (une seule ouverte, les autres tiennent sur
  une ligne de résumé), avec **Au hasard / Dupliquer / Retirer**, le **Ton** (Auto / Sérieux / Humour) et une ligne par
  réglage : Format, Sujet, Histoire (dessin animé seulement), Accroche, Thème, Musique et voix. Chaque ligne affiche son
  choix (« Auto » en gris) et ouvre un **sélecteur** (fenêtre, feuille du bas sur téléphone) qui se ferme au choix :
  formats en liste (une phrase de description et l'étiquette Cartes / App / App + cartes / Dessin animé / Jeu vidéo, filtre
  Tous / Conseil / Produit / Dessinés), sujets en liste avec recherche et « Mon propre sujet », thèmes en vignettes,
  accroches avec leur exemple, musiques et voix avec ▶ pour écouter (« Terminé » pour fermer). Choisir le dessin animé
  passe la capture du lot en « Sans capture » (le workflow l'exige) et le signale. Un format à cartes choisi avec une
  capture vidéo (`video`, `video_desktop`) affiche un avertissement. Les **options avancées** (repliées) : contenu imposé
  (mode automatique), image (capture, animations), son, reprise et cache. Envoyé au workflow dans le champ `plan`. La
  composition est mémorisée dans le navigateur.
- **Onglet Résultats** (runs et reels réunis) : les derniers runs (statut, durée, Logs, Reels, GitHub, Annuler ; pastille ●
  sur l'onglet quand un run est en cours), puis les reels du dernier run réussi, qui s'ouvrent tout seuls (bouton Reels
  d'un run pour en voir un autre). Chaque reel : la vidéo, « Copier la légende » et « Vidéo », la légende et les
  déclinaisons Instagram (couverture, carrousel, légende, images) dans des sections repliables.
- **Aperçus** (`docs/apercus/`, produits par `python scripts/apercus.py`) : couverture de chaque thème,
  chaque carte animée (texte d'exemple sans chiffre présenté comme réel), chaque décor et personnage du
  dessin animé, une phrase de chaque voix (enregistrements de CTA) et 8 s de chaque musique, en JPEG et
  MP3 légers (~1,5 Mo en tout). Servis à côté de la page (GitHub Pages), sinon lus par l'API GitHub
  avec le token. À relancer après un ajout au catalogue (thème, décor, personnage, voix, ambiance ;
  `--seulement themes,decors`, `--force` pour tout refaire) : `python scripts/catalog.py` signale les
  aperçus manquants (sans bloquer : la console montre alors une vignette neutre).
- **Catalogue** : fiches par type (formats, sujets, accroches, thèmes, ambiances, voix, trames et décors
  du dessin animé, niveaux et boss du jeu vidéo) avec recherche et filtres catégorie / registre ; formats : structure, visuel, sujets
  compatibles (« Voir ses sujets ») ; thèmes : vignette, nuancier, polices, musiques ; voix et ambiances :
  ▶ pour écouter ; décors : vignette. Fiches compactes (3 lignes de texte ; un clic sur la fiche déplie tout) ; les
  filtres catégorie / registre ne s'affichent que pour les types où ils servent. « Ajouter au lot » ajoute l'élément au compositeur
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
