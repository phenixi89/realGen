# realGen — consignes pour Claude

Pipeline de reels TikTok/Instagram/YouTube Shorts pour OpusCV (acquisition organique) et pour des chaînes
faceless (`catalog/chaines/<id>/` : `opuscv`, `examen_civique`, `psycho`). Documentation utilisateur : `README.md`.

## Règle permanente : documentation à jour

**Chaque modification (code, catalogue `catalog/*.json` et `catalog/chaines/*/`, gabarits `assets/anim/`, workflow,
console `docs/`) met à jour `README.md` dans le même commit** : nouvelle option, nouveau
format/thème/ambiance, changement de comportement ou de valeur par défaut, règle de montage.
Si la modification change une consigne de ce fichier, mettre aussi à jour `CLAUDE.md`.
Avant de commiter, relire les passages du README concernés et retirer ce qui est devenu faux.

## Conventions

- Commits directement sur `main` (autorisé), puis pousser aussi sur la branche de travail de la
  session. Messages de commit en français.
- Échanges avec l'utilisateur en français.
- Textes affichés dans les vidéos (prompts, cartes, sous-titres) en français accentué.
- Vérifications avant commit : `python -m py_compile scripts/*.py`, `python scripts/catalog.py`,
  `python scripts/verif_gabarits.py` (charge chaque gabarit d'animation) et `python scripts/verif_prompts.py` (construit le prompt de chaque format : `py_compile` ne voit pas une variable utilisée avant
  sa définition, run 80) — mêmes contrôles que `.github/workflows/test.yml`.
- Chaînes : formats, sujets, accroches et config d'une chaîne dans `catalog/chaines/<id>/` (aucun repli d'une chaîne sur
  une autre) ; `chaine.json` = identité (nom, marque, watermark, produit ou faceless, niche, public, règles, personnages,
  série, trames). Les noms de la chaîne `psycho` et des personnages sont PROVISOIRES : ne les changer que dans
  `chaine.json`. Toute modification d'un prompt doit laisser **identiques** les prompts d'OpusCV (comparer avant / après)
  et sans trace d'OpusCV ceux des chaînes faceless (`verif_prompts.py`). Une nouvelle chaîne s'ajoute aussi aux options
  `chaine` de `generate-reels.yml` (`catalog.py` vérifie).
- Chaîne vérifiée (`examen_civique`, `"verification": true`) : un sujet = des `faits` recopiés d'une source officielle
  (jamais de mémoire : Légifrance, service-public.fr, fiches de `formation-civique.interieur.gouv.fr`) + `source` ; aucune date
  ni chiffre hors des faits ; une carte `citation` est recopiée mot pour mot d'un fait. Les règles de l'examen ne viennent que du
  sujet `examen_modalites`. Neutre, « non officielle », jamais de promesse de réussite ; sujet `memoire` (Shoah) : ton grave,
  jamais de jeu ni d'humour. Chaîne `psycho` : notions reconnues seulement, jamais de diagnostic ni d'étude inventée.
- Enrichir le catalogue = éditer `catalog/*.json` ou `catalog/chaines/<id>/*.json` (aucun code) ; documenter les champs dans le
  `_doc` du fichier et dans le README. Un nouveau thème, décor, personnage, voix ou ambiance a un aperçu
  dans la console : relancer `python scripts/apercus.py` et committer `docs/apercus/`.
- Cadence et mouvement : 30 i/s, source unique `timeline.FPS` (jamais `25` écrit en dur) ; le flou de mouvement est dans
  `render_js_anim.py` (`--sans-flou`, `REALGEN_FLOU=0`, jamais sur `jeu` ni `scene` : `SANS_FLOU`). Un gabarit à cartes n'a **aucune
  courbe propre** : il prend `window.EASE` (`entree`, `sortie`, `pop`, `rebond`, `doux`, `common.js`), dont les valeurs viennent du
  profil de mouvement de la chaîne (`catalog/config.json` « mouvements », `mouvement` dans `chaine.json` ; OpusCV = `dynamique`,
  ses courbes d'avant). Le zoom des captures a la même formule dans `3b_build_video_from_screenshots.py` et `common.js` (`zoomAt`) ;
  il ne doit jamais rogner la fenêtre de la capture (`keep_card_in_view`).
  Les sous-titres commencent à y = 1574 : le contenu des gabarits reste au-dessus. Après avoir touché un gabarit :
  `python scripts/verif_gabarits.py` (aussi dans `test.yml`).
- Icônes dessinables : `assets/anim/icones.js` (JSON strict après `window.ICONES = `, lu aussi par
  `catalog.py`) ; une icône, un décor ou un objet propre à une chaîne porte `"chaines"` (`icones.js`, `dessins.json`) : les autres
  ne le voient pas, le prompt d'OpusCV reste identique. Nouveau gabarit dessiné : s'appuyer sur `assets/anim/sketch.js`. Tout instant
  d'animation repris par `scripts/sound_design.py` doit rester identique des deux côtés.
- Dessin animé (`assets/anim/scene.html`) : un type (personnage, animal, objet, décor, fond) = un
  `Dessin.enregistrer` dans `assets/anim/dessin/*.js` **et** une entrée dans `catalog/dessins.json` (série, trames et
  identité des personnages : `chaine.json` de chaque chaîne)
  (`catalog.py` vérifie la correspondance). Penser par objet, pas par scène ; touches de couleur légères
  (lavis) plutôt qu'aplats. Une action qui fait du bruit le signale avec `Dessin.son(nom, t)` (nom déclaré dans
  `catalog/audio.json` "bruitages" et produit par `scripts/audio_gen.py`).
- Dessin animé, règles d'écriture et de mise en scène (contrôlées dans `1_generate_script.py`, détail
  dans le README « Format `dessin_anime` » ; elles valent pour toutes les chaînes, les noms ci-dessous sont ceux d'OpusCV) :
  - deux personnages parlent au plus par reel (voix Gemini multi-locuteurs) ; l'appel à l'action est dit
    par un personnage `principal` (Léa ou Karim) ;
  - une scène = un lieu et un moment : même décor sans `ellipse` = même scène (fusionnée) ; les plans
    varient avec la caméra ;
  - les répliques sont dites à voix haute : pas de « POV » ni de code des réseaux ; une accroche qui ne se
    dit pas porte `"dessin": false` dans `hooks.json` ;
  - un problème puis une solution, en mots simples (réplique de 12 mots au plus, pas de jargon ni de « règle du … »
    inventé) ; l'accroche est une question (titre à l'écran ou 1re réplique d'un personnage), jamais le titre dit dans
    une bulle ni un nombre annoncé (`dessin_texte_problems`) ;
  - le titre (6 mots au plus, accrocheur) s'affiche seul plein écran 1 s avant la scène (jamais sur les personnages) ;
    le scénario passe une relecture « spectateur qui ne sait rien » (`relecture_dessin`) : s'il ne se comprend pas
    seul, il est réécrit ;
  - pas de suspense artificiel (« attends la formule exacte ») : la phrase est donnée tout de suite ; la chute est une
    réaction, pas un slogan ;
  - ouverture de 8 mots au plus qui nomme de qui on parle et ne répète pas le titre, solution enseignée avec une phrase
    exacte entre « guillemets », aucune réplique adressée au public (`dessin_texte_problems`) ; budget de mots calé sur
    la vitesse réelle de la voix (`output/vitesse_voix.json`) ;
  - le dessin animé donne un conseil emploi / recrutement (écriture de scénariste, consigne `DRAMATURGIE`) :
    OpusCV n'est cité que dans l'appel à l'action final, jamais dans une réplique de l'histoire ;
  - aucune fonction ni chiffre de performance inventé sur OpusCV dans la bouche d'un personnage ;
  - bulles petites et translucides, sans prénom du personnage (la place est comptée) ;
  - le décor et les objets ne bougent jamais (le « bouillonnement » des traits ne concerne que les personnages et
    les animaux) ; seuls les effets de lumière et de temps (lampe, horloge, ville du métro…) sont animés ;
  - au moins un plan original par reel (caméra `dessous` / `epaule` / `lent`, ou split-screen) ; musiques douces
    seulement (`ambiances` du format dans `formats.json`) ;
  - rien ne cache la scène : les bulles passent au-dessus des têtes, les gros plans (inserts) sous la
    zone des bulles, le nuage de pensée du côté libre ; aucun son au changement de scène.
  - chaque mouvement de personnage doit se comprendre sans le son et paraître humain : avant de publier, le vérifier
    sur une planche d'images successives de l'action (pose de départ → anticipation → action → impact → résultat)
    et corriger tant qu'un spectateur ne comprendrait pas ce que fait le personnage. Jamais de main ou de bras qui
    apparaît d'un coup (il sort de quelque part), un objet important assez grand pour se lire (sinon un insert), le
    geste motivé par l'état psychologique du moment, la tête fixe quand le personnage parle sans marcher.
- Reels à cartes et à captures (hors dessin animé et jeu) : un teaser est permis **s'il est tenu** (ce qui est annoncé est livré plus
  loin, le rang annoncé existe) ; le reel doit être vrai et cohérent avec ce qu'on voit (titre / légende fidèles, voix collée à
  l'écran, rien d'inventé sur OpusCV, chiffres d'exemple signalés) : `promesses_problems` et `relecture_coherence` dans
  `1_generate_script.py`, consigne `COHERENCE_RULE`. Le dessin animé garde sa règle (pas de suspense artificiel).
- Jeu vidéo rétro (`assets/anim/jeu.html`, `assets/anim/jeu/`, `catalog/jeu.json`) : format `jeu_quete`, Martin et Léa
  (héros et guide) contre un boss qui est le SYSTÈME (jamais une personne) ; mêmes règles d'écriture que le dessin animé
  (dialogue à deux voix, titre plein écran 1 s, relecture) plus les événements du jeu (apparition → blessure → objet →
  dégâts → victoire → niveau). Un niveau ou un boss = un enregistrement dans `assets/anim/jeu/` **et** une entrée dans
  `catalog/jeu.json` (`catalog.py` vérifie), puis `python scripts/apercus.py`. Texte du jeu en 8 px (grille de la police
  Press Start 2P), jamais d'autre taille que 8 ou 16.
- Vidéo éducative (`cours_eclair`, thèmes `carnet_cours` et `pop_art`, gabarits `assets/anim/lecon.html` et `pop.html`) : un
  thème à `cartes_gabarit` dessine toutes les cartes avec sa planche (`catalog.gabarit_carte`, paramètre `mode`) ; ajouter une
  planche = le `mode` dans le gabarit **et** son entrée dans `gabarit_carte` **et** ses instants dans `sound_design.educatif_cues`
  (identiques des deux côtés) ; mêmes règles d'écriture que les autres formats à cartes (phrases courtes, pas de suspense, pas de
  chiffre inventé sur OpusCV).
- Captures de l'app (`scripts/features.py`) : une fonctionnalité = une fonction Playwright **et** une `Feature` (description de ce
  qu'on VOIT, vraie d'après l'app) **et** `DEFAULT_FEATURE_ORDER` **et** le contexte produit `PRODUCT_CONTEXT` de
  `1_generate_script.py` si l'app a gagné une fonction. Une capture qui modifie le CV remet l'état d'origine. Le CV filmé est
  celui de `scripts/demo_compte.py` (`assets/cv_demo.json`, créé puis supprimé à chaque run). Tester contre une copie locale de
  l'app (`dev`, SQLite) avant de pousser.
- Sons enregistrés (`assets/sfx/`) : licence CC0 uniquement, source notée dans `assets/sfx/LICENCES.md`.
- Polices : uniquement sous licence libre (OFL), licence copiée dans `assets/fonts/`.
- Après un run du workflow `generate-reels.yml`, l'analyse se fait sur l'artefact `output`
  (images extraites des reels, loudness mesurée avec `ffmpeg -af ebur128`, cible -14 LUFS).

## Points ouverts (décisions utilisateur en attente)

- Nom définitif de la mascotte d'Objectif Civique (« Hexa », provisoire ; `assets/marques/examen_civique/mascotte*.svg`) : sa place dans les reels (intro, écran de fin, personnage du dessin animé) reste à décider.
- Nom définitif de la chaîne `psycho` (`Dans ta tête`, provisoire) et des personnages (Théo, Jade).
- Noms de la série dessinée d'Objectif Civique (« Sami prépare son examen » : Sami, Claire, M. Bernard), provisoires.

- Format `temoignage_produit` : ajouter la mention « histoire illustrative » ou le retirer.
- Publication automatique après validation, reportée par l'utilisateur : workflow « TikTok : autoriser »
  (échange du code OAuth, `TIKTOK_REFRESH_TOKEN` écrit via `SECRETS_PAT`) et workflow « Publier un reel »
  (Instagram API with Instagram Login, brouillon TikTok `video.upload`, mention contenu IA, rafraîchissement
  des jetons, bouton dans la console). Les jetons ne passent jamais par le chat : secrets GitHub seulement.

## Décisions prises

- Domaines : `opuscv.tech` (`PRODUCT_CONTEXT`, bio) et `opuscv.fr` (watermark) sont conservés tous les deux, volontairement.
- Voix : `gemini-3.8-flash-tts` avec un ton par réplique (choisi à l'écoute), secours
  `gemini-3.1-flash-tts-preview` (également apprécié).
- Dessin animé = série « Karim cherche un job » (épisodes numérotés, résumés gardés dans l'historique),
  une trame d'histoire par épisode, chute obligatoire avant l'appel à l'action. Chaîne `psycho` : série « Dans la tête
  de Théo » (mêmes dessins, autres noms).
- Chaînes faceless : une ligne éditoriale = un dossier `catalog/chaines/<id>/` ; d'abord `examen_civique` (révision de
  l'examen civique, vérifiée) et `psycho` (psychologie du quotidien) ; « savais-tu que » et « motivation » viendront
  ensuite. Audience d'abord (monétisation plus tard) : reels courts ; TikTok, Instagram et YouTube Shorts.
- Chaîne `examen_civique` : nom « Objectif Civique », compte TikTok `@objectif.civique` (watermark), logo « L'Hexagone validé »
  (`assets/marques/examen_civique/`, sans Marianne ni bloc-marque de l'État) ; habillage propre, jamais celui d'OpusCV :
  thème `civique_plateau` réservé à la chaîne (`"chaines"`), gabarit `assets/anim/civique.html` (plateau de quiz en hexagones,
  sons publiés par la page dans `window.SONS`). Une nouvelle planche = le `mode` dans `civique.html` **et** sa carte (`clean_card`,
  `catalog._gabarit_civique`, `carte_texte`, `instagram.slide_from_card`, `CIVIQUE_CARDS_RULE`) **et** son exemple dans `PLANCHES`
  (`verif_gabarits.py`) ; les formats qui l'utilisent ont
  `"cartes_civique": true` (jamais un format d'OpusCV : ses prompts doivent rester identiques). Apprendre par les histoires :
  récit en chapitres, citation expliquée, mise en situation (QCM à 4 réponses comme l'examen), « ne confonds plus », révision
  espacée (`"rappel": true`), série dessinée « Sami prépare son examen » (décors civiques `mairie`, `bureau_vote`, `salle_cours`).
  Modalités de l'examen recopiées de la page officielle (sujet `examen_modalites`). Le spectateur a le temps de chercher :
  silence de réflexion après chaque question (`pause_reflexion_s`, inséré par `4_generate_subtitles.py`), la carte révèle la
  réponse à la fin de sa scène, dont la voix dit la question, les réponses et « Réfléchis. » (`question_problems`). Un format dont la
  structure demande une carte quiz a `"quiz": true` ; un format à questions compte les questions, pas les cartes
  (`"progression": "questions"`).
- Objectif Civique, rénovation (vues bloquées très bas) : un format phare `examen_blanc` « Réussirais-tu l'examen civique ? »
  (`"phare": true`, environ 7 reels sur 10) — 3 questions QCM de familles différentes (`"melange"`), la question dès la 1re image
  (`"carte_accroche"`, planche `immediat=1`, aucun titre par-dessus), bandeau de série « EXAMEN CIVIQUE · ENTRAÎNEMENT N°X »
  (`"entete"`), score en commentaire ; en complément `mise_en_situation`, `vrai_ou_faux` (eux aussi `carte_accroche`) et
  `dessin_anime` ; les autres formats sont en sommeil (`"actif": false`, jamais supprimés). Débit naturel (plus de « débit lent »),
  temps de réflexion 2 s, pas de relance « enregistre ». La 1re image d'un reel de la chaîne doit déjà montrer le jeu.
